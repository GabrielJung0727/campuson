"""practicum evaluation system

Revision ID: 0013_practicum
Revises: 0012_roles_announcements
Create Date: 2026-04-21 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_practicum"
down_revision: str | None = "0012_roles_announcements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enums
    practicum_category_enum = postgresql.ENUM(
        "HAND_HYGIENE", "VITAL_SIGNS", "INJECTION", "ASEPTIC_TECHNIQUE", "BLS",
        "ROM_MEASUREMENT", "GAIT_TRAINING", "ELECTROTHERAPY", "PATIENT_TRANSFER",
        "SCALING", "ORAL_EXAM", "INFECTION_CONTROL", "TOOTH_POLISHING",
        name="practicum_category_enum",
    )
    practicum_category_enum.create(op.get_bind(), checkfirst=True)

    eval_grade_enum = postgresql.ENUM(
        "EXCELLENT", "GOOD", "NEEDS_IMPROVEMENT", "FAIL",
        name="eval_grade_enum",
    )
    eval_grade_enum.create(op.get_bind(), checkfirst=True)

    eval_status_enum = postgresql.ENUM(
        "DRAFT", "SUBMITTED", "REVIEWED",
        name="eval_status_enum",
    )
    eval_status_enum.create(op.get_bind(), checkfirst=True)

    # practicum_scenarios
    op.create_table(
        "practicum_scenarios",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("department", postgresql.ENUM(name="department_enum", create_type=False), nullable=False),
        sa.Column("category", postgresql.ENUM(name="practicum_category_enum", create_type=False), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("checklist_items", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("total_points", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.create_index("ix_practicum_scenarios_dept_cat", "practicum_scenarios", ["department", "category"])

    # practicum_sessions
    op.create_table(
        "practicum_sessions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("student_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scenario_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("practicum_scenarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", postgresql.ENUM(name="eval_status_enum", create_type=False), nullable=False, server_default=sa.text("'DRAFT'")),
        sa.Column("video_url", sa.String(500), nullable=True),
        sa.Column("checklist_results", postgresql.JSONB(), nullable=True),
        sa.Column("total_score", sa.Integer(), nullable=True),
        sa.Column("grade", postgresql.ENUM(name="eval_grade_enum", create_type=False), nullable=True),
        sa.Column("ai_feedback", postgresql.JSONB(), nullable=True),
        sa.Column("professor_comment", sa.Text(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_practicum_sessions_student", "practicum_sessions", ["student_id"])
    op.create_index("ix_practicum_sessions_scenario", "practicum_sessions", ["scenario_id"])
    op.create_index("ix_practicum_sessions_status", "practicum_sessions", ["status"])


def downgrade() -> None:
    op.drop_table("practicum_sessions")
    op.drop_table("practicum_scenarios")
    postgresql.ENUM(name="eval_status_enum").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="eval_grade_enum").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="practicum_category_enum").drop(op.get_bind(), checkfirst=True)
