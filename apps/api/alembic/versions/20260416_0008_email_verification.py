"""add email_verified fields to users

Revision ID: 0008_email_verification
Revises: 0007_kb_documents
Create Date: 2026-04-16 09:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_email_verification"
down_revision: str | None = "0007_kb_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            server_default="false",
            nullable=False,
            comment="이메일 인증 완료 여부",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "email_verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="이메일 인증 완료 시각",
        ),
    )
    # 기존 ACTIVE 사용자는 이미 인증된 것으로 처리
    op.execute("UPDATE users SET email_verified = true WHERE status = 'ACTIVE'")


def downgrade() -> None:
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "email_verified")
