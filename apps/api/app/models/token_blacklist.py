"""JWT 토큰 폐기 시스템 모델 (v1.0 보안).

- TokenBlacklist: 명시적으로 폐기된 access token jti 저장 (Redis가 다운되어도 체크 가능)
- RefreshToken: family 기반 회전(rotation) 추적 — 재사용 탐지 시 family 전체 revoke
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RevocationReason(str, enum.Enum):
    """토큰 폐기 사유."""

    LOGOUT = "LOGOUT"              # 사용자 자발적 로그아웃
    LOGOUT_ALL = "LOGOUT_ALL"      # 전체 세션 종료
    REUSE_DETECTED = "REUSE_DETECTED"  # refresh token 재사용 → family 전체 폐기
    ADMIN_REVOKE = "ADMIN_REVOKE"  # 관리자 강제 폐기
    PASSWORD_CHANGED = "PASSWORD_CHANGED"  # 비밀번호 변경 시 기존 세션 종료
    ROTATED = "ROTATED"            # refresh rotation으로 교체됨


class TokenBlacklist(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """폐기된 JWT jti 저장.

    Redis가 primary cache이고, 이 테이블은 Redis 다운 시 fallback.
    GC 잡이 expires_at이 지난 행을 주기적으로 정리.
    """

    __tablename__ = "token_blacklist"
    __table_args__ = (
        Index("ix_token_blacklist_jti", "jti", unique=True),
        Index("ix_token_blacklist_user", "user_id"),
        Index("ix_token_blacklist_expires", "expires_at"),
    )

    jti: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[RevocationReason] = mapped_column(
        SAEnum(RevocationReason, name="revocation_reason_enum", native_enum=True, create_type=True),
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class RefreshToken(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Refresh token 회전 추적.

    - family_id: 동일 로그인 세션의 모든 refresh token을 묶는 그룹 ID
    - parent_jti: 이 토큰을 만들어낸 직전 refresh token의 jti (rotation chain)
    - used_at: rotation으로 사용되어 새 토큰으로 교체된 시점
    - revoked_at: 명시적으로 폐기된 시점

    재사용 탐지: parent_jti가 이미 used_at이 설정된 토큰을 가리키면
    해당 family 전체를 REUSE_DETECTED로 revoke.
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_tokens_jti", "jti", unique=True),
        Index("ix_refresh_tokens_family", "family_id"),
        Index("ix_refresh_tokens_user", "user_id"),
        Index("ix_refresh_tokens_expires", "expires_at"),
    )

    jti: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    parent_jti: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[RevocationReason | None] = mapped_column(
        SAEnum(RevocationReason, name="revocation_reason_enum", native_enum=True, create_type=False),
        nullable=True,
    )
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
