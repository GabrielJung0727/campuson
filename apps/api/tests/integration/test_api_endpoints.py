"""API 통합 테스트 — 주요 엔드포인트 요청/응답 검증 (v0.9).

httpx AsyncClient로 실제 FastAPI 앱에 요청.
DB fixture는 conftest.py에서 제공.
"""

import pytest
from httpx import AsyncClient


# === Health ===


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    res = await client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    res = await client.get("/")
    assert res.status_code == 200
    assert "CampusON" in res.json()["service"]


# === Auth Flow ===


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient):
    """회원가입 → 로그인 → /me 조회 플로우."""
    # Register
    reg_res = await client.post("/api/v1/auth/register", json={
        "email": "inttest@example.com",
        "password": "Password1",
        "name": "통합테스트",
        "department": "NURSING",
        "role": "STUDENT",
        "student_no": "INT001",
    })
    assert reg_res.status_code in (200, 201, 409)  # 409 = already exists

    # Login
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "inttest@example.com",
        "password": "Password1",
    })
    assert login_res.status_code == 200
    tokens = login_res.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    # /me
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    me_res = await client.get("/api/v1/users/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "inttest@example.com"


# === Error Format ===


@pytest.mark.asyncio
async def test_unified_error_format_401(client: AsyncClient):
    """인증 없이 보호된 엔드포인트 호출 시 통합 에러 포맷 확인."""
    res = await client.get("/api/v1/users/me")
    assert res.status_code == 401
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] == "UNAUTHORIZED"
    assert "request_id" in data["error"]


@pytest.mark.asyncio
async def test_unified_error_format_422(client: AsyncClient):
    """잘못된 요청 바디 시 validation 에러 포맷 확인."""
    res = await client.post("/api/v1/auth/register", json={
        "email": "not-an-email",  # invalid
        "password": "x",  # too short
    })
    assert res.status_code == 422
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert data["error"]["details"] is not None
    assert len(data["error"]["details"]) > 0


@pytest.mark.asyncio
async def test_unified_error_format_404(client: AsyncClient):
    """존재하지 않는 리소스 404."""
    # 유효한 토큰 필요
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "inttest@example.com",
        "password": "Password1",
    })
    if login_res.status_code != 200:
        pytest.skip("Login failed — register first")
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    res = await client.get(
        "/api/v1/questions/00000000-0000-0000-0000-000000000000/play",
        headers=headers,
    )
    assert res.status_code == 404


# === Questions ===


@pytest.mark.asyncio
async def test_questions_list(client: AsyncClient):
    """문제 목록 조회 (시드 데이터 확인)."""
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "inttest@example.com",
        "password": "Password1",
    })
    if login_res.status_code != 200:
        pytest.skip("Login required")
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    res = await client.get("/api/v1/questions?department=NURSING&limit=5", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data or isinstance(data, list)


# === Calendar (v0.8) ===


@pytest.mark.asyncio
async def test_calendar_crud(client: AsyncClient):
    """캘린더 일정 CRUD 플로우."""
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "inttest@example.com",
        "password": "Password1",
    })
    if login_res.status_code != 200:
        pytest.skip("Login required")
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # Create
    create_res = await client.post("/api/v1/calendar/events", headers=headers, json={
        "title": "Integration Test Event",
        "event_type": "custom",
        "start_at": "2026-05-01T10:00:00Z",
    })
    assert create_res.status_code == 201
    event_id = create_res.json()["id"]

    # List
    list_res = await client.get("/api/v1/calendar/events", headers=headers)
    assert list_res.status_code == 200

    # Update
    update_res = await client.patch(
        f"/api/v1/calendar/events/{event_id}",
        headers=headers,
        json={"title": "Updated Title"},
    )
    assert update_res.status_code == 200

    # Delete
    del_res = await client.delete(f"/api/v1/calendar/events/{event_id}", headers=headers)
    assert del_res.status_code == 200
