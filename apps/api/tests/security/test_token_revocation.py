"""v1.0 보안: JWT 토큰 폐기 시스템 테스트.

커버리지:
- unit: 블랙리스트 hit 시 401
- integration: refresh rotation → 구 token 거부
- security: reuse 시나리오 → family 전체 revoke

완료 조건 검증
--------------
1. 로그아웃 후 이전 access token으로 API 호출 시 100% 401
2. refresh token 재사용 시도 시 family 전체 revoke 로그 기록
3. `/auth/logout-all` 호출 시 해당 사용자 모든 세션 무효화
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, decode_token, hash_password
from app.core.token_blacklist import (
    add_to_blacklist,
    cleanup_expired_tokens,
    is_blacklisted,
    revoke_refresh_family,
    revoke_user_all_tokens,
)
from app.models.enums import Department, Role, UserStatus
from app.models.token_blacklist import RefreshToken, RevocationReason, TokenBlacklist
from app.models.user import User


@pytest_asyncio.fixture
async def student_user(db_session: AsyncSession) -> User:
    """테스트용 학생 사용자 — 비밀번호 Test1234, email_verified."""
    unique = uuid.uuid4().hex[:8]
    user = User(
        email=f"student-{unique}@test.local",
        password_hash=hash_password("Test1234"),
        name=f"Test{unique}",
        student_no=f"99{unique[:5]}",
        department=Department.NURSING,
        role=Role.STUDENT,
        status=UserStatus.ACTIVE,
        email_verified=True,
        email_verified_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


# ------------------------------------------------------------------
# UNIT — token_blacklist 서비스
# ------------------------------------------------------------------
class TestBlacklistService:
    @pytest.mark.asyncio
    async def test_add_and_check(self, db_session: AsyncSession, student_user: User) -> None:
        """블랙리스트 추가 후 즉시 hit."""
        jti = f"test-jti-{uuid.uuid4().hex[:8]}"
        expires = datetime.now(UTC) + timedelta(hours=1)

        await add_to_blacklist(
            db_session,
            jti=jti,
            user_id=student_user.id,
            expires_at=expires,
            reason=RevocationReason.LOGOUT,
        )
        assert await is_blacklisted(db_session, jti) is True

    @pytest.mark.asyncio
    async def test_not_blacklisted(self, db_session: AsyncSession) -> None:
        """블랙리스트에 없는 jti는 False."""
        assert await is_blacklisted(db_session, "nonexistent-jti") is False

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, db_session: AsyncSession, student_user: User) -> None:
        """만료된 블랙리스트 엔트리 GC."""
        expired_jti = f"expired-{uuid.uuid4().hex[:8]}"
        past = datetime.now(UTC) - timedelta(hours=1)
        db_session.add(TokenBlacklist(
            jti=expired_jti,
            user_id=student_user.id,
            expires_at=past,
            reason=RevocationReason.LOGOUT,
        ))
        await db_session.flush()

        result = await cleanup_expired_tokens(db_session)
        assert result["blacklist_deleted"] >= 1

        # 만료된 건 더 이상 조회 안 됨
        stmt = select(TokenBlacklist).where(TokenBlacklist.jti == expired_jti)
        assert (await db_session.execute(stmt)).scalar_one_or_none() is None


# ------------------------------------------------------------------
# INTEGRATION — /auth/logout, /auth/refresh 회전, /auth/logout-all
# ------------------------------------------------------------------
class TestLogoutEndpoints:
    @pytest.mark.asyncio
    async def test_logout_blacklists_access_token(
        self, client: AsyncClient, student_user: User, db_session: AsyncSession,
    ) -> None:
        """로그아웃 후 동일 access token으로 API 호출 시 401."""
        # 로그인
        login = await client.post("/api/v1/auth/login", json={
            "email": student_user.email, "password": "Test1234",
        })
        assert login.status_code == 200
        access = login.json()["access_token"]
        refresh = login.json()["refresh_token"]
        auth = {"Authorization": f"Bearer {access}"}

        # 로그아웃 전엔 /users/me 정상
        me = await client.get("/api/v1/users/me", headers=auth)
        assert me.status_code == 200

        # 로그아웃
        logout = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh},
            headers=auth,
        )
        assert logout.status_code == 200

        # 동일 access token으로 요청 → 401
        me2 = await client.get("/api/v1/users/me", headers=auth)
        assert me2.status_code == 401
        assert "revoked" in me2.json()["detail"].lower() or "credentials" in me2.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_refresh_rotation_invalidates_old_token(
        self, client: AsyncClient, student_user: User,
    ) -> None:
        """refresh token 회전: 한 번 사용된 refresh는 다시 못 씀."""
        login = await client.post("/api/v1/auth/login", json={
            "email": student_user.email, "password": "Test1234",
        })
        old_refresh = login.json()["refresh_token"]

        # 첫 refresh 호출 — 성공
        first = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        assert first.status_code == 200
        new_refresh = first.json()["refresh_token"]
        assert new_refresh != old_refresh

        # 같은 old_refresh를 다시 사용 → 재사용 탐지로 401
        second = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        assert second.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_all_terminates_all_sessions(
        self, client: AsyncClient, student_user: User, db_session: AsyncSession,
    ) -> None:
        """logout-all은 사용자의 모든 토큰을 무효화."""
        # 2개 세션 동시 로그인
        s1 = await client.post("/api/v1/auth/login", json={
            "email": student_user.email, "password": "Test1234",
        })
        s2 = await client.post("/api/v1/auth/login", json={
            "email": student_user.email, "password": "Test1234",
        })
        token1 = s1.json()["access_token"]
        token2 = s2.json()["access_token"]

        # logout-all (token1로 호출)
        out = await client.post(
            "/api/v1/auth/logout-all",
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert out.status_code == 200

        # 두 세션 모두 무효: token2도 거부
        # (전역 로그아웃 마커가 두 토큰의 iat보다 이후에 설정되므로)
        r1 = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token1}"})
        r2 = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token2}"})
        assert r1.status_code == 401
        assert r2.status_code == 401


# ------------------------------------------------------------------
# SECURITY — refresh reuse 탐지 → family 전체 revoke
# ------------------------------------------------------------------
class TestRefreshReuseDetection:
    @pytest.mark.asyncio
    async def test_reuse_revokes_entire_family(
        self, client: AsyncClient, student_user: User, db_session: AsyncSession,
    ) -> None:
        """재사용 탐지 시 family 전체가 revoke되어, 정상 새 토큰도 무효화."""
        # 로그인
        login = await client.post("/api/v1/auth/login", json={
            "email": student_user.email, "password": "Test1234",
        })
        rt_gen0 = login.json()["refresh_token"]

        # 정상 rotation: gen0 → gen1
        r1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": rt_gen0})
        assert r1.status_code == 200
        rt_gen1 = r1.json()["refresh_token"]

        # 공격자가 gen0 재사용 시도 → family 전체 revoke
        attack = await client.post("/api/v1/auth/refresh", json={"refresh_token": rt_gen0})
        assert attack.status_code == 401

        # 정상 사용자의 gen1도 이제 거부됨 (family 전체 revoke)
        r2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": rt_gen1})
        assert r2.status_code == 401

    @pytest.mark.asyncio
    async def test_family_revoke_logs_reason(
        self, db_session: AsyncSession, student_user: User,
    ) -> None:
        """family revoke 시 DB에 REUSE_DETECTED 사유로 기록."""
        family_id = uuid.uuid4()
        # 같은 family의 토큰 2개 생성
        for i in range(2):
            db_session.add(RefreshToken(
                jti=f"fam-{family_id.hex[:8]}-{i}",
                family_id=family_id,
                user_id=student_user.id,
                expires_at=datetime.now(UTC) + timedelta(days=30),
            ))
        await db_session.flush()

        count = await revoke_refresh_family(
            db_session, family_id, RevocationReason.REUSE_DETECTED,
        )
        assert count == 2

        stmt = select(RefreshToken).where(RefreshToken.family_id == family_id)
        rows = (await db_session.execute(stmt)).scalars().all()
        for r in rows:
            assert r.revoked_at is not None
            assert r.revoke_reason == RevocationReason.REUSE_DETECTED


# ------------------------------------------------------------------
# SECURITY — password 변경 시 세션 종료 옵션 (추후 훅용)
# ------------------------------------------------------------------
class TestUserRevocation:
    @pytest.mark.asyncio
    async def test_revoke_user_all_tokens_counts_active(
        self, db_session: AsyncSession, student_user: User,
    ) -> None:
        """revoke_user_all_tokens는 유효한 refresh 수를 반환."""
        # 3개의 유효 refresh + 1개 만료
        for i in range(3):
            db_session.add(RefreshToken(
                jti=f"active-{i}-{uuid.uuid4().hex[:4]}",
                family_id=uuid.uuid4(),
                user_id=student_user.id,
                expires_at=datetime.now(UTC) + timedelta(days=30),
            ))
        db_session.add(RefreshToken(
            jti=f"expired-{uuid.uuid4().hex[:4]}",
            family_id=uuid.uuid4(),
            user_id=student_user.id,
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        ))
        await db_session.flush()

        count = await revoke_user_all_tokens(
            db_session, student_user.id, RevocationReason.LOGOUT_ALL,
        )
        # 유효한 3개만 revoke
        assert count == 3
