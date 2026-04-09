"""Week 1 통합 e2e 테스트.

플로우
-----
1. POST /auth/register      → 학생 토큰 발급 (개발 환경 → 즉시 ACTIVE)
2. POST /auth/login         → 토큰 재발급 검증
3. GET  /users/me           → 본인 정보 확인
4. POST /diagnostic/start   → 30문항 출제
5. POST /diagnostic/{id}/submit → 채점 + AI 프로파일 자동 생성
6. GET  /diagnostic/me/profile → AIProfile 확인
7. POST /history/answer     → 문제 풀이 (정답)
8. POST /history/answer     → 같은 문제 다른 시점 풀이 (오답, 짧은 시간)
9. GET  /history/wrong-answers → 오답노트 검증
10. GET /history/stats      → 통계 검증
11. GET /ai/info            → Mock provider 활성 확인
12. POST /ai/qa             → 자유 질의응답 (Mock)
13. POST /ai/explain        → 문제 해설 (Mock)
14. GET  /ai/me/logs        → AI 호출 로그 확인
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def _register_student(client) -> tuple[str, dict]:
    """랜덤 이메일/학번으로 학생을 등록하고 (access_token, user) 반환."""
    import secrets
    from datetime import datetime

    nonce = secrets.token_hex(3)
    yy = (datetime.now().year - 1) % 100
    payload = {
        "email": f"e2e_{nonce}@kbu.ac.kr",
        "password": "Test1234",
        "name": f"E2E학생{nonce}",
        "department": "NURSING",
        "role": "STUDENT",
        "student_no": f"{yy:02d}00{nonce[:4]}",
    }
    res = await client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201, res.text
    data = res.json()
    return data["access_token"], data["user"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_week1_full_flow(client) -> None:
    # === 1. 회원가입 ===
    token, user = await _register_student(client)
    assert user["department"] == "NURSING"
    assert user["status"] == "ACTIVE"  # development env
    user_id = user["id"]

    # === 2. 로그인 (별도 토큰 발급) ===
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": user["email"], "password": "Test1234"},
    )
    assert res.status_code == 200, res.text
    login_token = res.json()["access_token"]
    assert login_token

    # === 3. /users/me ===
    res = await client.get("/api/v1/users/me", headers=_auth(token))
    assert res.status_code == 200
    assert res.json()["id"] == user_id

    # === 4. 진단 시작 ===
    res = await client.post("/api/v1/diagnostic/start", headers=_auth(token))
    assert res.status_code == 201, res.text
    start_data = res.json()
    test_id = start_data["test_id"]
    questions = start_data["questions"]
    assert len(questions) > 0
    assert len(questions) <= 30

    # === 5. 진단 제출 (절반 정답으로 응답) ===
    answers = []
    for i, q in enumerate(questions):
        # 절반은 0번, 절반은 1번 — Mock 데이터에 대해 일관된 응답
        answers.append(
            {
                "question_id": q["id"],
                "selected_choice": 0 if i % 2 == 0 else 1,
                "time_spent_sec": 30,
            }
        )
    res = await client.post(
        f"/api/v1/diagnostic/{test_id}/submit",
        headers=_auth(token),
        json={"answers": answers},
    )
    assert res.status_code == 200, res.text
    result = res.json()
    assert result["completed_at"] is not None
    assert result["total_score"] is not None
    assert 0.0 <= result["total_score"] <= 1.0
    assert result["level"] in ("BEGINNER", "INTERMEDIATE", "ADVANCED")

    # === 6. AI 프로파일 자동 생성 확인 ===
    res = await client.get(
        "/api/v1/diagnostic/me/profile", headers=_auth(token)
    )
    assert res.status_code == 200, res.text
    profile = res.json()
    assert profile["user_id"] == user_id
    assert profile["level"] == result["level"]
    assert isinstance(profile["learning_path"], list)
    assert len(profile["learning_path"]) >= 1

    # === 7. 진단 1회 제한 검증 ===
    res = await client.post("/api/v1/diagnostic/start", headers=_auth(token))
    assert res.status_code == 409  # AlreadyTaken

    # === 8. 문제 풀이 — 정답 ===
    target_q = questions[0]
    target_q_id = target_q["id"]
    # 한 번 더 정답 선택지를 직접 알아내야 하므로,
    # /questions/{id} 로 정답을 받아옴 (학생 권한이 아닌 PROFESSOR/ADMIN)
    # → 학생은 /play 만 호출 가능. 정답 모르므로 random submit 후 결과로 검증
    # Quick path: history/answer를 호출하고 응답에서 correct_answer 받기
    res = await client.post(
        "/api/v1/history/answer",
        headers=_auth(token),
        json={
            "question_id": target_q_id,
            "selected_choice": 0,
            "solving_time_sec": 25,
        },
    )
    assert res.status_code == 201, res.text
    first_answer = res.json()
    assert "is_correct" in first_answer
    assert first_answer["attempt_no"] == 1
    correct_idx = first_answer["correct_answer"]

    # === 9. 같은 문제 — 짧은 시간 + 일부러 오답 ===
    wrong_choice = (correct_idx + 1) % len(target_q["choices"])
    res = await client.post(
        "/api/v1/history/answer",
        headers=_auth(token),
        json={
            "question_id": target_q_id,
            "selected_choice": wrong_choice,
            "solving_time_sec": 5,  # < 10 → CARELESS
        },
    )
    assert res.status_code == 201
    second = res.json()
    assert second["is_correct"] is False
    assert second["error_type"] == "CARELESS"
    assert second["attempt_no"] == 2

    # === 10. 오답노트 ===
    res = await client.get(
        "/api/v1/history/wrong-answers", headers=_auth(token)
    )
    assert res.status_code == 200
    wrong = res.json()
    assert wrong["total"] >= 1
    # 우리가 방금 만든 오답이 포함되어야 함
    matched = [
        item for item in wrong["items"] if item["question_id"] == target_q_id
    ]
    assert matched, "방금 등록한 오답이 오답노트에 없음"
    assert matched[0]["wrong_count"] >= 1

    # === 11. 학습 통계 ===
    res = await client.get(
        "/api/v1/history/stats?period=daily", headers=_auth(token)
    )
    assert res.status_code == 200
    stats = res.json()
    assert stats["total_attempts"] >= 2
    assert "CARELESS" in stats["error_type_distribution"]

    # === 12. AI 정보 ===
    res = await client.get("/api/v1/ai/info", headers=_auth(token))
    assert res.status_code == 200
    info = res.json()
    assert info["provider"] == "MOCK"

    # === 13. AI QA ===
    res = await client.post(
        "/api/v1/ai/qa",
        headers=_auth(token),
        json={"question": "심방세동의 정의를 한 줄로 설명해주세요."},
    )
    assert res.status_code == 200, res.text
    qa = res.json()
    assert qa["request_type"] == "QA"
    assert "MOCK" in qa["output_text"] or len(qa["output_text"]) > 0
    assert qa["metadata"]["provider"] == "MOCK"

    # === 14. AI 문제 해설 ===
    res = await client.post(
        "/api/v1/ai/explain",
        headers=_auth(token),
        json={
            "question_id": target_q_id,
            "history_id": first_answer["history_id"],
        },
    )
    assert res.status_code == 200, res.text
    explain = res.json()
    assert explain["request_type"] == "EXPLAIN"
    assert explain["metadata"]["latency_ms"] >= 0

    # === 15. AI 호출 로그 ===
    res = await client.get("/api/v1/ai/me/logs", headers=_auth(token))
    assert res.status_code == 200
    logs = res.json()
    assert logs["total"] >= 2  # qa + explain
    assert all(item["success"] for item in logs["items"])
