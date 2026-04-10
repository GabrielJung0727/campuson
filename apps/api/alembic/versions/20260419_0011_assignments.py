"""assignments + assignment_submissions tables

Revision ID: 0011_assignments
Revises: 0010_professor_classes
Create Date: 2026-04-19 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_assignments"
down_revision: str | None = "0010_professor_classes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    assignment_status_enum = postgresql.ENUM("DRAFT", "PUBLISHED", "CLOSED", name="assignment_status_enum", create_type=True)
    assignment_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("professor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("class_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("department", postgresql.ENUM("NURSING", "PHYSICAL_THERAPY", "DENTAL_HYGIENE", name="department_enum", create_type=False), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", postgresql.ENUM("DRAFT", "PUBLISHED", "CLOSED", name="assignment_status_enum", create_type=False), nullable=False),
        sa.Column("question_ids", postgresql.JSONB(), nullable=False),
        sa.Column("total_questions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["professor_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["class_id"], ["professor_classes.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_assignments_professor", "assignments", ["professor_id"])
    op.create_index("ix_assignments_class", "assignments", ["class_id"])

    op.create_table(
        "assignment_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("answers", postgresql.JSONB(), nullable=False),
        sa.Column("total_correct", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_questions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("time_spent_sec", sa.Integer(), server_default="0", nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_assignment_submissions_student", "assignment_submissions", ["student_id"])
    op.create_index("ix_assignment_submissions_assignment", "assignment_submissions", ["assignment_id"])


def downgrade() -> None:
    op.drop_table("assignment_submissions")
    op.drop_table("assignments")
    postgresql.ENUM(name="assignment_status_enum").drop(op.get_bind(), checkfirst=True)
