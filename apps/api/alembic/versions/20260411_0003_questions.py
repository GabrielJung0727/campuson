"""questions table

Revision ID: 0003_questions
Revises: 0002_audit_logs
Create Date: 2026-04-11 09:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003_questions"
down_revision: str | None = "0002_audit_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Enum types (department_enum is reused from 0001) ---
    difficulty_enum = postgresql.ENUM(
        "EASY", "MEDIUM", "HARD", name="difficulty_enum", create_type=True
    )
    question_type_enum = postgresql.ENUM(
        "SINGLE_CHOICE",
        "MULTI_CHOICE",
        "SHORT_ANSWER",
        name="question_type_enum",
        create_type=True,
    )
    difficulty_enum.create(op.get_bind(), checkfirst=True)
    question_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "questions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
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
        sa.Column("subject", sa.String(length=100), nullable=False),
        sa.Column("unit", sa.String(length=100), nullable=True),
        sa.Column(
            "difficulty",
            postgresql.ENUM(
                "EASY", "MEDIUM", "HARD", name="difficulty_enum", create_type=False
            ),
            nullable=False,
        ),
        sa.Column(
            "question_type",
            postgresql.ENUM(
                "SINGLE_CHOICE",
                "MULTI_CHOICE",
                "SHORT_ANSWER",
                name="question_type_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("choices", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("correct_answer", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String(length=50)),
            server_default=sa.text("'{}'::varchar[]"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=200), nullable=True),
        sa.Column("source_year", sa.Integer(), nullable=True),
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
        sa.CheckConstraint("correct_answer >= 0", name="ck_questions_correct_answer_nonneg"),
        sa.CheckConstraint(
            "jsonb_array_length(choices) >= 2", name="ck_questions_choices_min_length"
        ),
    )
    op.create_index(
        "ix_questions_department_subject", "questions", ["department", "subject"]
    )
    op.create_index("ix_questions_difficulty", "questions", ["difficulty"])
    op.create_index(
        "ix_questions_tags_gin", "questions", ["tags"], postgresql_using="gin"
    )


def downgrade() -> None:
    op.drop_index("ix_questions_tags_gin", table_name="questions")
    op.drop_index("ix_questions_difficulty", table_name="questions")
    op.drop_index("ix_questions_department_subject", table_name="questions")
    op.drop_table("questions")

    bind = op.get_bind()
    postgresql.ENUM(name="question_type_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="difficulty_enum").drop(bind, checkfirst=True)
