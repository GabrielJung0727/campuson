"""question review workflow + extended metadata (v0.5)

Adds:
- question_review_status_enum type
- questions: review_status, learning_objective, concept_tags, national_exam_mapping,
  answer_rationale, professor_explanation, created_by, discrimination_index
- question_reviews table (검수 큐)
- question_edit_history table (수정 이력)

Revision ID: 0015_question_review_metadata
Revises: 0014_practicum_modes
Create Date: 2026-04-22 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_question_review_metadata"
down_revision: str | None = "0014_practicum_modes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) Create question_review_status_enum
    review_status_enum = postgresql.ENUM(
        "PENDING_REVIEW", "APPROVED", "REJECTED", "REVISION_REQUESTED",
        name="question_review_status_enum",
        create_type=False,
    )
    review_status_enum.create(op.get_bind(), checkfirst=True)

    # 2) Add columns to questions table
    op.add_column(
        "questions",
        sa.Column(
            "review_status",
            sa.Enum(
                "PENDING_REVIEW", "APPROVED", "REJECTED", "REVISION_REQUESTED",
                name="question_review_status_enum",
                native_enum=True,
                create_type=False,
            ),
            server_default=sa.text("'PENDING_REVIEW'"),
            nullable=False,
        ),
    )
    op.add_column(
        "questions",
        sa.Column("learning_objective", sa.String(300), nullable=True),
    )
    op.add_column(
        "questions",
        sa.Column(
            "concept_tags",
            postgresql.ARRAY(sa.String(100)),
            server_default=sa.text("'{}'::varchar[]"),
            nullable=False,
        ),
    )
    op.add_column(
        "questions",
        sa.Column("national_exam_mapping", sa.String(200), nullable=True),
    )
    op.add_column(
        "questions",
        sa.Column("answer_rationale", sa.Text, nullable=True),
    )
    op.add_column(
        "questions",
        sa.Column("professor_explanation", sa.Text, nullable=True),
    )
    op.add_column(
        "questions",
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "questions",
        sa.Column("discrimination_index", sa.Float, nullable=True),
    )

    op.create_index("ix_questions_review_status", "questions", ["review_status"])
    op.create_index(
        "ix_questions_concept_tags_gin",
        "questions",
        ["concept_tags"],
        postgresql_using="gin",
    )

    # 3) Create question_reviews table
    op.create_table(
        "question_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "status",
            sa.Enum("PENDING_REVIEW", "APPROVED", "REJECTED", "REVISION_REQUESTED", name="question_review_status_enum", create_type=False),
            nullable=False,
            server_default=sa.text("'PENDING_REVIEW'"),
        ),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("ai_explanation", sa.Text, nullable=True),
        sa.Column("professor_explanation", sa.Text, nullable=True),
        sa.Column("review_version", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_question_reviews_question", "question_reviews", ["question_id"])
    op.create_index("ix_question_reviews_reviewer", "question_reviews", ["reviewer_id"])
    op.create_index("ix_question_reviews_status", "question_reviews", ["status"])

    # 4) Create question_edit_history table
    op.create_table(
        "question_edit_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("editor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("edit_type", sa.String(50), nullable=False),
        sa.Column("changes", postgresql.JSONB, nullable=True),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_question_edit_history_question", "question_edit_history", ["question_id"])
    op.create_index("ix_question_edit_history_editor", "question_edit_history", ["editor_id"])

    # 5) Mark all existing questions as APPROVED (backward compat)
    op.execute("UPDATE questions SET review_status = 'APPROVED' WHERE review_status = 'PENDING_REVIEW'")


def downgrade() -> None:
    op.drop_table("question_edit_history")
    op.drop_table("question_reviews")

    op.drop_index("ix_questions_concept_tags_gin", table_name="questions")
    op.drop_index("ix_questions_review_status", table_name="questions")
    op.drop_column("questions", "discrimination_index")
    op.drop_column("questions", "created_by")
    op.drop_column("questions", "professor_explanation")
    op.drop_column("questions", "answer_rationale")
    op.drop_column("questions", "national_exam_mapping")
    op.drop_column("questions", "concept_tags")
    op.drop_column("questions", "learning_objective")
    op.drop_column("questions", "review_status")

    sa.Enum(name="question_review_status_enum").drop(op.get_bind(), checkfirst=True)
