"""practicum modes (live/video/self)

Revision ID: 0014_practicum_modes
Revises: 0013_practicum
Create Date: 2026-04-21 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_practicum_modes"
down_revision: str | None = "0013_practicum"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    practicum_mode_enum = postgresql.ENUM(
        "SELF", "VIDEO", "LIVE",
        name="practicum_mode_enum",
    )
    practicum_mode_enum.create(op.get_bind(), checkfirst=True)

    op.add_column("practicum_sessions", sa.Column(
        "mode",
        postgresql.ENUM(name="practicum_mode_enum", create_type=False),
        nullable=False,
        server_default=sa.text("'SELF'"),
    ))
    op.add_column("practicum_sessions", sa.Column("join_code", sa.String(6), nullable=True))
    op.add_column("practicum_sessions", sa.Column("video_description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("practicum_sessions", "video_description")
    op.drop_column("practicum_sessions", "join_code")
    op.drop_column("practicum_sessions", "mode")
    postgresql.ENUM(name="practicum_mode_enum").drop(op.get_bind(), checkfirst=True)
