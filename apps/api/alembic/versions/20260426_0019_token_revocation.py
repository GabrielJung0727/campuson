"""token revocation (blacklist + refresh rotation)

Revision ID: 0019_token_revocation
Revises: 0018_scalability_infrastructure
Create Date: 2026-04-26 09:00:00

보안 1순위: JWT 로그아웃/재사용 방지.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019_token_revocation"
down_revision: str | None = "0018_scalability_infrastructure"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Enums ---
    revocation_reason_enum = postgresql.ENUM(
        "LOGOUT", "LOGOUT_ALL", "REUSE_DETECTED", "ADMIN_REVOKE",
        "PASSWORD_CHANGED", "ROTATED",
        name="revocation_reason_enum",
    )
    revocation_reason_enum.create(op.get_bind(), checkfirst=True)

    # --- Add CLEANUP_EXPIRED_TOKENS to existing JobType enum ---
    # PostgreSQL requires ALTER TYPE ... ADD VALUE for enum expansion
    op.execute("ALTER TYPE job_type_enum ADD VALUE IF NOT EXISTS 'CLEANUP_EXPIRED_TOKENS'")

    # --- token_blacklist ---
    op.create_table(
        "token_blacklist",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("jti", sa.String(64), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", postgresql.ENUM(name="revocation_reason_enum", create_type=False),
                  nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
    )
    op.create_index("ix_token_blacklist_jti", "token_blacklist", ["jti"], unique=True)
    op.create_index("ix_token_blacklist_user", "token_blacklist", ["user_id"])
    op.create_index("ix_token_blacklist_expires", "token_blacklist", ["expires_at"])

    # --- refresh_tokens (rotation chain) ---
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("jti", sa.String(64), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_jti", sa.String(64), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", postgresql.ENUM(name="revocation_reason_enum", create_type=False),
                  nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
    )
    op.create_index("ix_refresh_tokens_jti", "refresh_tokens", ["jti"], unique=True)
    op.create_index("ix_refresh_tokens_family", "refresh_tokens", ["family_id"])
    op.create_index("ix_refresh_tokens_user", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_expires", "refresh_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_expires", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_family", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_jti", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("ix_token_blacklist_expires", table_name="token_blacklist")
    op.drop_index("ix_token_blacklist_user", table_name="token_blacklist")
    op.drop_index("ix_token_blacklist_jti", table_name="token_blacklist")
    op.drop_table("token_blacklist")

    postgresql.ENUM(name="revocation_reason_enum").drop(op.get_bind(), checkfirst=True)
