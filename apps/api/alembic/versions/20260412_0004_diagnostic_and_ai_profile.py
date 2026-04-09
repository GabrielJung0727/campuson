"""diagnostic_tests, diagnostic_answers, ai_profiles tables

Revision ID: 0004_diagnostic_ai_profile
Revises: 0003_questions
Create Date: 2026-04-12 09:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004_diagnostic_ai_profile"
down_revision: str | None = "0003_questions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- enums ---
    level_enum = postgresql.ENUM(
        "BEGINNER", "INTERMEDIATE", "ADVANCED", name="level_enum", create_type=True
    )
    explanation_pref_enum = postgresql.ENUM(
        "SIMPLE",
        "DETAILED",
        "EXPERT",
        name="explanation_pref_enum",
        create_type=True,
    )
    level_enum.create(op.get_bind(), checkfirst=True)
    explanation_pref_enum.create(op.get_bind(), checkfirst=True)

    # --- diagnostic_tests ---
    op.create_table(
        "diagnostic_tests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_score", sa.Float(), nullable=True),
        sa.Column(
            "section_scores", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("weak_areas", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "level",
            postgresql.ENUM(
                "BEGINNER",
                "INTERMEDIATE",
                "ADVANCED",
                name="level_enum",
                create_type=False,
            ),
            nullable=True,
        ),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_diagnostic_tests_user_id"),
    )

    # --- diagnostic_answers ---
    op.create_table(
        "diagnostic_answers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("test_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("selected_choice", sa.Integer(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column(
            "time_spent_sec", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "answered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["test_id"], ["diagnostic_tests.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["question_id"], ["questions.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "test_id", "question_id", name="uq_diagnostic_answers_test_question"
        ),
    )
    op.create_index(
        "ix_diagnostic_answers_test_id", "diagnostic_answers", ["test_id"]
    )

    # --- ai_profiles ---
    op.create_table(
        "ai_profiles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "level",
            postgresql.ENUM(
                "BEGINNER",
                "INTERMEDIATE",
                "ADVANCED",
                name="level_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "weak_priority", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "learning_path", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "explanation_pref",
            postgresql.ENUM(
                "SIMPLE",
                "DETAILED",
                "EXPERT",
                name="explanation_pref_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "frequent_topics",
            postgresql.ARRAY(sa.String(length=100)),
            server_default="{}",
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_ai_profiles_user_id"),
    )


def downgrade() -> None:
    op.drop_table("ai_profiles")
    op.drop_index("ix_diagnostic_answers_test_id", table_name="diagnostic_answers")
    op.drop_table("diagnostic_answers")
    op.drop_table("diagnostic_tests")

    bind = op.get_bind()
    postgresql.ENUM(name="explanation_pref_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="level_enum").drop(bind, checkfirst=True)
