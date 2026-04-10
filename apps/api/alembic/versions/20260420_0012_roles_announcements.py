"""role refinement + announcements table

Revision ID: 0012_roles_announcements
Revises: 0011_assignments
Create Date: 2026-04-20 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_roles_announcements"
down_revision: str | None = "0011_assignments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Enums ---
    for name, values in [
        ("professor_role_enum", ["FULL_TIME", "ADJUNCT", "DEPT_HEAD"]),
        ("admin_role_enum", ["ACADEMIC_AFFAIRS", "STUDENT_AFFAIRS", "GENERAL_ADMIN", "PLANNING", "IT_CENTER", "ADMISSIONS", "SUPER_ADMIN"]),
        ("nationality_enum", ["KOREAN", "INTERNATIONAL"]),
        ("announcement_target_enum", ["ALL", "STUDENT", "PROFESSOR", "ADMIN", "DEVELOPER"]),
        ("announcement_type_enum", ["GENERAL", "MAINTENANCE", "URGENT"]),
    ]:
        postgresql.ENUM(*values, name=name, create_type=True).create(op.get_bind(), checkfirst=True)

    # --- User model extensions ---
    op.add_column("users", sa.Column("professor_role", postgresql.ENUM("FULL_TIME", "ADJUNCT", "DEPT_HEAD", name="professor_role_enum", create_type=False), nullable=True))
    op.add_column("users", sa.Column("admin_role", postgresql.ENUM("ACADEMIC_AFFAIRS", "STUDENT_AFFAIRS", "GENERAL_ADMIN", "PLANNING", "IT_CENTER", "ADMISSIONS", "SUPER_ADMIN", name="admin_role_enum", create_type=False), nullable=True))
    op.add_column("users", sa.Column("nationality", postgresql.ENUM("KOREAN", "INTERNATIONAL", name="nationality_enum", create_type=False), nullable=True))
    op.add_column("users", sa.Column("grade", sa.Integer(), nullable=True))

    # --- Announcements ---
    op.create_table(
        "announcements",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("target_audience", postgresql.ENUM("ALL", "STUDENT", "PROFESSOR", "ADMIN", "DEVELOPER", name="announcement_target_enum", create_type=False), nullable=False),
        sa.Column("announcement_type", postgresql.ENUM("GENERAL", "MAINTENANCE", "URGENT", name="announcement_type_enum", create_type=False), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("send_email", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_announcements_active_target", "announcements", ["is_active", "target_audience"])
    op.create_index("ix_announcements_type", "announcements", ["announcement_type"])


def downgrade() -> None:
    op.drop_table("announcements")
    op.drop_column("users", "grade")
    op.drop_column("users", "nationality")
    op.drop_column("users", "admin_role")
    op.drop_column("users", "professor_role")
    for name in ["announcement_type_enum", "announcement_target_enum", "nationality_enum", "admin_role_enum", "professor_role_enum"]:
        postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)
