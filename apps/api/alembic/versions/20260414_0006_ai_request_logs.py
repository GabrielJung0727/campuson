"""ai_request_logs table

Revision ID: 0006_ai_request_logs
Revises: 0005_learning_history
Create Date: 2026-04-14 09:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006_ai_request_logs"
down_revision: str | None = "0005_learning_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    ai_request_type_enum = postgresql.ENUM(
        "QA",
        "EXPLAIN",
        "RECOMMEND",
        "WEAKNESS_ANALYSIS",
        name="ai_request_type_enum",
        create_type=True,
    )
    llm_provider_enum = postgresql.ENUM(
        "ANTHROPIC",
        "OPENAI",
        "MOCK",
        name="llm_provider_enum",
        create_type=True,
    )
    ai_request_type_enum.create(op.get_bind(), checkfirst=True)
    llm_provider_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "ai_request_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "request_type",
            postgresql.ENUM(
                "QA",
                "EXPLAIN",
                "RECOMMEND",
                "WEAKNESS_ANALYSIS",
                name="ai_request_type_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("template_name", sa.String(length=50), nullable=True),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("rendered_prompt", sa.Text(), nullable=True),
        sa.Column(
            "retrieved_docs", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("output_text", sa.Text(), nullable=True),
        sa.Column("finish_reason", sa.String(length=50), nullable=True),
        sa.Column(
            "provider",
            postgresql.ENUM(
                "ANTHROPIC",
                "OPENAI",
                "MOCK",
                name="llm_provider_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["question_id"], ["questions.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_ai_request_logs_created_at", "ai_request_logs", ["created_at"]
    )
    op.create_index(
        "ix_ai_request_logs_user_created",
        "ai_request_logs",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_ai_request_logs_type_created",
        "ai_request_logs",
        ["request_type", "created_at"],
    )
    op.create_index("ix_ai_request_logs_success", "ai_request_logs", ["success"])


def downgrade() -> None:
    op.drop_index("ix_ai_request_logs_success", table_name="ai_request_logs")
    op.drop_index("ix_ai_request_logs_type_created", table_name="ai_request_logs")
    op.drop_index("ix_ai_request_logs_user_created", table_name="ai_request_logs")
    op.drop_index("ix_ai_request_logs_created_at", table_name="ai_request_logs")
    op.drop_table("ai_request_logs")

    bind = op.get_bind()
    postgresql.ENUM(name="llm_provider_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="ai_request_type_enum").drop(bind, checkfirst=True)
