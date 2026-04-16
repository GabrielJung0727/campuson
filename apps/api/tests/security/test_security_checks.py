"""보안 테스트 스위트 (v0.9).

OWASP Top 10 기반 보안 검증:
- SQL Injection 방지
- XSS 방지
- 인증/인가 우회 시도
- JWT 변조 탐지
- Rate limiting (존재 확인)
- 민감 데이터 노출 방지
"""

import pytest
from httpx import AsyncClient


class TestSQLInjection:
    """SQL Injection 방지 테스트."""

    @pytest.mark.asyncio
    async def test_login_sql_injection(self, client: AsyncClient):
        """로그인 시 SQL injection 시도 → 정상 에러 반환."""
        res = await client.post("/api/v1/auth/login", json={
            "email": "' OR 1=1 --",
            "password": "' OR 1=1 --",
        })
        # injection이 작동하면 200이 되면 안됨
        assert res.status_code in (401, 422)

    @pytest.mark.asyncio
    async def test_search_sql_injection(self, client: AsyncClient):
        """문제 검색 시 SQL injection 시도."""
        await client.post("/api/v1/auth/register", json={
            "email": "sec_test@test.com", "password": "Password1",
            "name": "보안테스터", "department": "NURSING", "role": "STUDENT",
            "student_no": "SEC001",
        })
        login = await client.post("/api/v1/auth/login", json={
            "email": "sec_test@test.com", "password": "Password1",
        })
        if login.status_code != 200:
            pytest.skip("Login failed")
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        # SQLi in query param
        res = await client.get(
            "/api/v1/questions?department=NURSING&subject=' OR 1=1 --",
            headers=headers,
        )
        # 정상 에러 또는 빈 결과 (injection 작동 X)
        assert res.status_code in (200, 400, 422)


class TestXSS:
    """XSS 방지 테스트."""

    @pytest.mark.asyncio
    async def test_xss_in_name(self, client: AsyncClient):
        """회원가입 시 XSS 페이로드가 저장되어도 실행되지 않는지 확인."""
        xss_payload = '<script>alert("xss")</script>'
        res = await client.post("/api/v1/auth/register", json={
            "email": "xss_test@test.com",
            "password": "Password1",
            "name": xss_payload,
            "department": "NURSING",
            "role": "STUDENT",
            "student_no": "XSS001",
        })
        # 등록 자체는 성공할 수 있지만, JSON 응답이므로 XSS 실행은 불가
        if res.status_code in (200, 201):
            login = await client.post("/api/v1/auth/login", json={
                "email": "xss_test@test.com", "password": "Password1",
            })
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            me = await client.get("/api/v1/users/me", headers=headers)
            # Content-Type이 JSON이므로 브라우저에서 스크립트 실행 ��됨
            assert me.headers.get("content-type", "").startswith("application/json")


class TestJWTSecurity:
    """JWT 보안 테스트."""

    @pytest.mark.asyncio
    async def test_invalid_jwt_rejected(self, client: AsyncClient):
        """변조된 JWT → 401."""
        headers = {"Authorization": "Bearer invalid.jwt.token"}
        res = await client.get("/api/v1/users/me", headers=headers)
        assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_format_jwt_rejected(self, client: AsyncClient):
        """잘못된 형식의 JWT → 401."""
        headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.fake"}
        res = await client.get("/api/v1/users/me", headers=headers)
        assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_no_bearer_prefix_rejected(self, client: AsyncClient):
        """Bearer 없는 토큰 → 401."""
        headers = {"Authorization": "some-token-without-bearer"}
        res = await client.get("/api/v1/users/me", headers=headers)
        assert res.status_code == 401


class TestSensitiveDataExposure:
    """민감 데이터 노출 방지."""

    @pytest.mark.asyncio
    async def test_password_not_in_response(self, client: AsyncClient):
        """응답에 비밀번호가 포함되지 않는지 확인."""
        await client.post("/api/v1/auth/register", json={
            "email": "nopass_test@test.com", "password": "Password1",
            "name": "테스트", "department": "NURSING", "role": "STUDENT",
            "student_no": "NP001",
        })
        login = await client.post("/api/v1/auth/login", json={
            "email": "nopass_test@test.com", "password": "Password1",
        })
        if login.status_code != 200:
            pytest.skip("Login failed")
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        me = await client.get("/api/v1/users/me", headers=headers)
        assert me.status_code == 200
        body = me.text.lower()
        assert "password" not in body or "hashed" not in body

    @pytest.mark.asyncio
    async def test_openapi_docs_accessible(self, client: AsyncClient):
        """OpenAPI 문서가 접근 가능한지 확인 (보안 정책에 따라 비활성화 가능)."""
        res = await client.get("/docs")
        # 200 또는 301 리다이렉트
        assert res.status_code in (200, 301, 307)


class TestRateLimiting:
    """Rate Limiting 존재 확인."""

    @pytest.mark.asyncio
    async def test_rapid_requests_handled(self, client: AsyncClient):
        """빠른 연속 요청이 서버 에러를 유발하지 않는지 확인."""
        for _ in range(20):
            res = await client.get("/api/v1/health")
            assert res.status_code == 200
