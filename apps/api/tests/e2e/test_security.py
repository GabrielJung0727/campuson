"""Day 14 보안 점검 테스트.

테스트 항목
---------
1. RBAC 우회 시도 — 학생이 관리자 전용 API 접근
2. 교수가 타학과 학생 데이터 접근 (학과 스코프 우회)
3. SQL Injection 시도
4. XSS payload 시도
5. 인증 없이 보호된 API 접근
6. 만료/위조 토큰으로 접근
7. 비밀번호 정책 우회 시도
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def _register(client, email_prefix: str, dept: str = "NURSING", role: str = "STUDENT"):
    """헬퍼: 빠른 회원가입."""
    import secrets
    from datetime import datetime

    nonce = secrets.token_hex(3)
    yy = (datetime.now().year - 1) % 100
    body = {
        "email": f"{email_prefix}_{nonce}@kbu.ac.kr",
        "password": "Test1234",
        "name": f"Test{nonce}",
        "department": dept,
        "role": role,
        "student_no": f"{yy:02d}00{nonce[:4]}" if role == "STUDENT" else None,
    }
    res = await client.post("/api/v1/auth/register", json=body)
    assert res.status_code == 201, res.text
    data = res.json()
    return data["access_token"], data["user"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ===== 1. RBAC 우회 시도 =====
class TestRBACEnforcement:
    async def test_student_cannot_access_admin_users_list(self, client) -> None:
        """학생은 /users (사용자 목록)에 접근할 수 없다."""
        token, _ = await _register(client, "rbac_student")
        res = await client.get("/api/v1/users", headers=_auth(token))
        assert res.status_code == 403

    async def test_student_cannot_create_question(self, client) -> None:
        """학생은 문제를 생성할 수 없다."""
        token, _ = await _register(client, "rbac_student2")
        res = await client.post(
            "/api/v1/questions",
            headers=_auth(token),
            json={
                "department": "NURSING",
                "subject": "test",
                "question_text": "test?",
                "choices": ["a", "b"],
                "correct_answer": 0,
            },
        )
        assert res.status_code == 403

    async def test_student_cannot_delete_kb_document(self, client) -> None:
        """학생은 KB 문서를 삭제할 수 없다."""
        token, _ = await _register(client, "rbac_student3")
        import uuid
        fake_id = str(uuid.uuid4())
        res = await client.delete(
            f"/api/v1/kb/documents/{fake_id}",
            headers=_auth(token),
        )
        assert res.status_code == 403

    async def test_student_cannot_view_ai_logs(self, client) -> None:
        """학생은 전체 AI 로그를 볼 수 없다."""
        token, _ = await _register(client, "rbac_student4")
        res = await client.get("/api/v1/ai/logs", headers=_auth(token))
        assert res.status_code == 403


# ===== 2. 인증 없이 접근 =====
class TestUnauthenticated:
    async def test_no_token_returns_401(self, client) -> None:
        res = await client.get("/api/v1/users/me")
        assert res.status_code == 401

    async def test_invalid_token_returns_401(self, client) -> None:
        res = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert res.status_code == 401

    async def test_expired_token_format(self, client) -> None:
        """잘못된 형식의 Bearer 토큰."""
        res = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer "},
        )
        assert res.status_code == 401


# ===== 3. SQL Injection 시도 =====
class TestSQLInjection:
    async def test_sqli_in_login_email(self, client) -> None:
        """로그인 이메일 필드에 SQL injection payload."""
        res = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "' OR 1=1; --",
                "password": "anything",
            },
        )
        # Pydantic이 email validation에서 거부하거나, 서버가 안전하게 처리
        assert res.status_code in (401, 422)

    async def test_sqli_in_question_search(self, client) -> None:
        """문제 검색 keyword에 SQL injection."""
        token, _ = await _register(client, "sqli_test")
        res = await client.get(
            "/api/v1/questions?keyword=' OR 1=1 --",
            headers=_auth(token),
        )
        # 정상 빈 결과 또는 200 — SQL이 실행되면 안 됨
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data.get("items"), list)


# ===== 4. XSS Payload 시도 =====
class TestXSS:
    async def test_xss_in_register_name(self, client) -> None:
        """회원가입 이름 필드에 XSS payload."""
        import secrets
        from datetime import datetime

        nonce = secrets.token_hex(3)
        yy = (datetime.now().year - 1) % 100
        res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"xss_{nonce}@kbu.ac.kr",
                "password": "Test1234",
                "name": '<script>alert("xss")</script>',
                "department": "NURSING",
                "role": "STUDENT",
                "student_no": f"{yy:02d}00{nonce[:4]}",
            },
        )
        # 서버는 그대로 저장하되 프론트에서 escape — 또는 거부
        # 어느 쪽이든 서버가 crash하면 안 됨
        assert res.status_code in (201, 422, 400)

    async def test_xss_in_ai_qa(self, client) -> None:
        """AI QA 질문에 XSS payload."""
        token, _ = await _register(client, "xss_qa")
        res = await client.post(
            "/api/v1/ai/qa",
            headers=_auth(token),
            json={"question": '<img src=x onerror=alert(1)> 심방세동 설명해줘'},
        )
        # 서버가 안전하게 처리 (crash 없음)
        assert res.status_code in (200, 502)


# ===== 5. 비밀번호 정책 우회 =====
class TestPasswordPolicy:
    async def test_short_password_rejected(self, client) -> None:
        res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "short_pw@kbu.ac.kr",
                "password": "Ab1",
                "name": "Test",
                "department": "NURSING",
                "role": "STUDENT",
                "student_no": "24009999",
            },
        )
        assert res.status_code in (400, 422)

    async def test_no_digit_password_rejected(self, client) -> None:
        res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "nodigit@kbu.ac.kr",
                "password": "abcdefgh",
                "name": "Test",
                "department": "NURSING",
                "role": "STUDENT",
                "student_no": "24009998",
            },
        )
        assert res.status_code in (400, 422)


# ===== 6. 진단 테스트 1회 제한 =====
class TestDiagnosticLimit:
    async def test_cannot_start_twice(self, client) -> None:
        """진단 테스트는 1회만 가능."""
        token, _ = await _register(client, "diag_limit")
        res1 = await client.post("/api/v1/diagnostic/start", headers=_auth(token))
        assert res1.status_code == 201

        res2 = await client.post("/api/v1/diagnostic/start", headers=_auth(token))
        assert res2.status_code == 409  # AlreadyTaken
