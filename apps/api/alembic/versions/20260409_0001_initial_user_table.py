"""initial user table with department/role/status enums

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-09 09:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Enum types ---
    department_enum = postgresql.ENUM(
        "NURSING",
        "PHYSICAL_THERAPY",
        "DENTAL_HYGIENE",
        name="department_enum",
        create_type=True,
    )
    role_enum = postgresql.ENUM(
        "STUDENT",
        "PROFESSOR",
        "ADMIN",
        "DEVELOPER",
        name="role_enum",
        create_type=True,
    )
    user_status_enum = postgresql.ENUM(
        "PENDING",
        "ACTIVE",
        "SUSPENDED",
        "DELETED",
        name="user_status_enum",
        create_type=True,
    )
    department_enum.create(op.get_bind(), checkfirst=True)
    role_enum.create(op.get_bind(), checkfirst=True)
    user_status_enum.create(op.get_bind(), checkfirst=True)

    # --- users table ---
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column(
            "student_no",
            sa.String(length=20),
            nullable=True,
            comment="학번 — 학생만 해당, 교수/관리자는 NULL",
        ),
        sa.Column(
            "department",
            postgresql.ENUM(
                "NURSING",
                "PHYSICAL_THERAPY",
                "DENTAL_HYGIENE",
                name="department_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "role",
            postgresql.ENUM(
                "STUDENT",
                "PROFESSOR",
                "ADMIN",
                "DEVELOPER",
                name="role_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING",
                "ACTIVE",
                "SUSPENDED",
                "DELETED",
                name="user_status_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("student_no", name="uq_users_student_no"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_department_role", "users", ["department", "role"])
    op.create_index("ix_users_status", "users", ["status"])


def downgrade() -> None:
    op.drop_index("ix_users_status", table_name="users")
    op.drop_index("ix_users_department_role", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    postgresql.ENUM(name="user_status_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="role_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="department_enum").drop(bind, checkfirst=True)
