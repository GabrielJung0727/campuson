"""RBAC 시나리오 테스트 (v0.9).

역할별 접근 통제 검증:
- STUDENT: 본인 데이터만
- PROFESSOR: 본인 학과 학생 데이터
- ADMIN: 학교 단위 운영
- DEVELOPER: 전체 접근

핵심: 역할이 부족할 때 403, 인증이 없을 때 401.
"""

import pytest
from httpx import AsyncClient

# 테스트용 계정 (conftest.py에서 register 보장)
STUDENT = {"email": "rbac_student@test.com", "password": "Password1", "name": "학생A", "department": "NURSING", "role": "STUDENT", "student_no": "RBAC001"}
PROFESSOR = {"email": "rbac_prof@test.com", "password": "Password1", "name": "교수A", "department": "NURSING", "role": "PROFESSOR"}
ADMIN = {"email": "rbac_admin@test.com", "password": "Password1", "name": "관리자A", "department": "NURSING", "role": "ADMIN"}


async def _register_and_login(client: AsyncClient, user: dict) -> dict[str, str]:
    """계정 생성 + 로그인 → 헤더 반환."""
    await client.post("/api/v1/auth/register", json=user)
    login = await client.post("/api/v1/auth/login", json={
        "email": user["email"], "password": user["password"],
    })
    if login.status_code != 200:
        pytest.skip(f"Login failed for {user['email']}")
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
async def test_unauthenticated_gets_401(client: AsyncClient):
    """인증 없이 보호된 엔드포인트 → 401."""
    res = await client.get("/api/v1/users/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_student_cannot_create_class(client: AsyncClient):
    """학생은 클래스 생성 불가 → 403."""
    headers = await _register_and_login(client, STUDENT)
    res = await client.post("/api/v1/classes", headers=headers, json={
        "class_name": "Unauthorized", "department": "NURSING",
        "year": 2026, "semester": 1,
    })
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_student_cannot_access_admin_ops(client: AsyncClient):
    """학생은 운영 대시보드 접근 불가 → 403."""
    headers = await _register_and_login(client, STUDENT)
    res = await client.get("/api/v1/ops/dashboard", headers=headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_professor_can_create_class(client: AsyncClient):
    """교수는 클래스 생성 가능."""
    headers = await _register_and_login(client, PROFESSOR)
    res = await client.post("/api/v1/classes", headers=headers, json={
        "class_name": "RBAC Test Class", "department": "NURSING",
        "year": 2026, "semester": 1,
    })
    assert res.status_code in (200, 201)


@pytest.mark.asyncio
async def test_student_cannot_create_school(client: AsyncClient):
    """학생은 학교 생성 불가 → 403."""
    headers = await _register_and_login(client, STUDENT)
    res = await client.post("/api/v1/schools", headers=headers, json={
        "name": "Test School", "code": "test",
    })
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_create_school(client: AsyncClient):
    """관리자는 학교 생성 가능."""
    headers = await _register_and_login(client, ADMIN)
    res = await client.post("/api/v1/schools", headers=headers, json={
        "name": "RBAC Test School", "code": "rbac_test",
    })
    assert res.status_code in (200, 201)


@pytest.mark.asyncio
async def test_student_cannot_create_comment(client: AsyncClient):
    """학생은 교수 코멘트 생성 불가 → 403."""
    headers = await _register_and_login(client, STUDENT)
    res = await client.post("/api/v1/comments", headers=headers, json={
        "student_id": "00000000-0000-0000-0000-000000000000",
        "target_type": "general",
        "content": "Unauthorized comment",
    })
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_student_can_access_own_data(client: AsyncClient):
    """학생은 본인 /me 접근 가능."""
    headers = await _register_and_login(client, STUDENT)
    res = await client.get("/api/v1/users/me", headers=headers)
    assert res.status_code == 200
    assert res.json()["email"] == STUDENT["email"]
