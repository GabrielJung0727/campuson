"""부하 테스트 + 성능 프로파일링 스크립트.

Day 14 — 동시 접속 시뮬레이션 + 응답 시간 측정.

사용법
------
```bash
cd apps/api

# 기본 (10 concurrent, 50 requests)
python -m scripts.load_test

# 커스텀
python -m scripts.load_test --concurrent 50 --total 200 --base-url http://localhost:8000/api/v1
```

사전 조건
--------
- 서버 실행 중 (uvicorn app.main:app)
- 최소 1명의 STUDENT 계정이 등록되어 있어야 함

측정 항목
--------
1. /health — 기본 응답 시간
2. /auth/login — 인증 성능
3. /questions — 검색 성능
4. /ai/qa — LLM (Mock) 성능
5. /history/stats — 통계 집계 성능
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time

import httpx


async def measure(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    json: dict | None = None,
) -> tuple[int, float]:
    """단일 요청의 (status, latency_ms)."""
    start = time.monotonic()
    try:
        if method == "GET":
            res = await client.get(url, headers=headers)
        else:
            res = await client.post(url, headers=headers, json=json)
        latency = (time.monotonic() - start) * 1000
        return res.status_code, latency
    except Exception:
        return 0, (time.monotonic() - start) * 1000


async def run_scenario(
    client: httpx.AsyncClient,
    name: str,
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    json: dict | None = None,
    concurrent: int,
    total: int,
) -> dict:
    """시나리오 1개 실행."""
    results: list[tuple[int, float]] = []
    semaphore = asyncio.Semaphore(concurrent)

    async def _task():
        async with semaphore:
            return await measure(client, method, url, headers=headers, json=json)

    tasks = [_task() for _ in range(total)]
    results = await asyncio.gather(*tasks)

    latencies = [r[1] for r in results]
    statuses = [r[0] for r in results]
    ok_count = sum(1 for s in statuses if 200 <= s < 400)

    return {
        "name": name,
        "total": total,
        "concurrent": concurrent,
        "ok": ok_count,
        "errors": total - ok_count,
        "p50": round(statistics.median(latencies), 1),
        "p95": round(sorted(latencies)[int(len(latencies) * 0.95)], 1),
        "p99": round(sorted(latencies)[int(len(latencies) * 0.99)], 1),
        "mean": round(statistics.mean(latencies), 1),
        "max": round(max(latencies), 1),
    }


async def main_async(args: argparse.Namespace) -> int:
    base = args.base_url.rstrip("/")
    concurrent = args.concurrent
    total = args.total

    print(f"\n{'='*60}")
    print(f"CampusON Load Test — {concurrent} concurrent, {total} requests/scenario")
    print(f"Base URL: {base}")
    print(f"{'='*60}\n")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 0) 로그인해서 토큰 받기
        print("[0] Registering test user...")
        import secrets
        from datetime import datetime

        nonce = secrets.token_hex(4)
        yy = (datetime.now().year - 1) % 100
        reg_res = await client.post(
            f"{base}/auth/register",
            json={
                "email": f"loadtest_{nonce}@kbu.ac.kr",
                "password": "Test1234",
                "name": f"LoadTest{nonce}",
                "department": "NURSING",
                "role": "STUDENT",
                "student_no": f"{yy:02d}00{nonce[:4]}",
            },
        )
        if reg_res.status_code != 201:
            # 이미 있을 수 있음, 로그인 시도
            login_res = await client.post(
                f"{base}/auth/login",
                json={"email": f"loadtest_{nonce}@kbu.ac.kr", "password": "Test1234"},
            )
            if login_res.status_code != 200:
                print(f"Registration/Login failed: {reg_res.status_code}")
                return 1
            token = login_res.json()["access_token"]
        else:
            token = reg_res.json()["access_token"]

        auth_headers = {"Authorization": f"Bearer {token}"}
        print(f"  Token acquired.\n")

        scenarios = [
            ("Health Check", "GET", f"{base}/health", None, None),
            ("Auth Login", "POST", f"{base}/auth/login", None, {
                "email": f"loadtest_{nonce}@kbu.ac.kr",
                "password": "Test1234",
            }),
            ("Questions Search", "GET", f"{base}/questions?department=NURSING&page_size=10", auth_headers, None),
            ("My Stats", "GET", f"{base}/history/stats?period=daily", auth_headers, None),
            ("AI QA (Mock)", "POST", f"{base}/ai/qa", auth_headers, {
                "question": "심방세동의 간호 중재를 설명해주세요."
            }),
        ]

        all_results = []
        for name, method, url, headers, json_body in scenarios:
            print(f"[*] {name}...")
            result = await run_scenario(
                client,
                name,
                method,
                url,
                headers=headers,
                json=json_body,
                concurrent=concurrent,
                total=total,
            )
            all_results.append(result)
            print(
                f"    OK={result['ok']}/{result['total']} "
                f"p50={result['p50']}ms p95={result['p95']}ms "
                f"p99={result['p99']}ms max={result['max']}ms"
            )

    # Summary
    print(f"\n{'='*60}")
    print(f"{'Scenario':<25} {'OK':>5} {'p50':>8} {'p95':>8} {'p99':>8} {'Max':>8}")
    print(f"{'-'*60}")
    for r in all_results:
        print(
            f"{r['name']:<25} {r['ok']:>5} {r['p50']:>7.1f} {r['p95']:>7.1f} "
            f"{r['p99']:>7.1f} {r['max']:>7.1f}"
        )
    print(f"{'='*60}")

    # Pass/Fail 기준
    failed = [r for r in all_results if r["p95"] > 5000 or r["errors"] > total * 0.1]
    if failed:
        print(f"\n!! {len(failed)} scenario(s) exceeded thresholds (p95>5s or >10% errors)")
        return 1
    print("\nAll scenarios within acceptable limits.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="CampusON Load Test")
    parser.add_argument("--base-url", default="http://localhost:8000/api/v1")
    parser.add_argument("--concurrent", type=int, default=10)
    parser.add_argument("--total", type=int, default=50)
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
