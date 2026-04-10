"""professor_classes + class_students tables

Revision ID: 0010_professor_classes
Revises: 0009_stats_interactions
Create Date: 2026-04-18 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_professor_classes"
down_revision: str | None = "0009_stats_interactions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "professor_classes",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("professor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("class_name", sa.String(100), nullable=False),
        sa.Column("department", postgresql.ENUM("NURSING", "PHYSICAL_THERAPY", "DENTAL_HYGIENE", name="department_enum", create_type=False), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("semester", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["professor_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_professor_classes_professor", "professor_classes", ["professor_id"])

    op.create_table(
        "class_students",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("class_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["class_id"], ["professor_classes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("class_id", "student_id", name="uq_class_students"),
    )
    op.create_index("ix_class_students_student", "class_students", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_class_students_student", table_name="class_students")
    op.drop_table("class_students")
    op.drop_index("ix_professor_classes_professor", table_name="professor_classes")
    op.drop_table("professor_classes")
