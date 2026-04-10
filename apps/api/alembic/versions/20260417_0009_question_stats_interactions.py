"""question_stats + answer_interactions tables

Revision ID: 0009_stats_interactions
Revises: 0008_email_verification
Create Date: 2026-04-17 09:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_stats_interactions"
down_revision: str | None = "0008_email_verification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- question_stats ---
    op.create_table(
        "question_stats",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("total_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("correct_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("accuracy", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("choice_distribution", postgresql.JSONB(), server_default="'{}'", nullable=False),
        sa.Column("avg_time_sec", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("avg_choice_changes", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("question_id", name="uq_question_stats_question_id"),
    )
    op.create_index("ix_question_stats_accuracy", "question_stats", ["accuracy"])

    # --- answer_interactions ---
    op.create_table(
        "answer_interactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("history_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("time_spent_sec", sa.Integer(), server_default="0", nullable=False),
        sa.Column("time_to_first_click_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("first_choice", sa.Integer(), server_default="-1", nullable=False),
        sa.Column("final_choice", sa.Integer(), nullable=False),
        sa.Column("choice_changes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("choice_sequence", postgresql.JSONB(), server_default="'[]'", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["history_id"], ["learning_history.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("history_id", name="uq_answer_interactions_history_id"),
    )
    op.create_index("ix_answer_interactions_user_question", "answer_interactions", ["user_id", "question_id"])
    op.create_index("ix_answer_interactions_question", "answer_interactions", ["question_id"])


def downgrade() -> None:
    op.drop_index("ix_answer_interactions_question", table_name="answer_interactions")
    op.drop_index("ix_answer_interactions_user_question", table_name="answer_interactions")
    op.drop_table("answer_interactions")
    op.drop_index("ix_question_stats_accuracy", table_name="question_stats")
    op.drop_table("question_stats")
