"""learning_history table

Revision ID: 0005_learning_history
Revises: 0004_diagnostic_ai_profile
Create Date: 2026-04-13 09:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005_learning_history"
down_revision: str | None = "0004_diagnostic_ai_profile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    error_type_enum = postgresql.ENUM(
        "CONCEPT_GAP",
        "CONFUSION",
        "CARELESS",
        "APPLICATION_GAP",
        name="error_type_enum",
        create_type=True,
    )
    error_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "learning_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("selected_choice", sa.Integer(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column(
            "solving_time_sec", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "error_type",
            postgresql.ENUM(
                "CONCEPT_GAP",
                "CONFUSION",
                "CARELESS",
                "APPLICATION_GAP",
                name="error_type_enum",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("attempt_no", sa.Integer(), server_default="1", nullable=False),
        sa.Column("ai_feedback", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["question_id"], ["questions.id"], ondelete="RESTRICT"
        ),
    )
    op.create_index(
        "ix_learning_history_created_at", "learning_history", ["created_at"]
    )
    op.create_index(
        "ix_learning_history_user_created",
        "learning_history",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_learning_history_user_question",
        "learning_history",
        ["user_id", "question_id", "created_at"],
    )
    op.create_index(
        "ix_learning_history_user_correct",
        "learning_history",
        ["user_id", "is_correct"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_learning_history_user_correct", table_name="learning_history"
    )
    op.drop_index(
        "ix_learning_history_user_question", table_name="learning_history"
    )
    op.drop_index("ix_learning_history_user_created", table_name="learning_history")
    op.drop_index("ix_learning_history_created_at", table_name="learning_history")
    op.drop_table("learning_history")

    bind = op.get_bind()
    postgresql.ENUM(name="error_type_enum").drop(bind, checkfirst=True)
