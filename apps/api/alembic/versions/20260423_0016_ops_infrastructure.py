"""v0.6 운영 인프라: background_jobs, notifications, cost_daily 테이블 추가.

Revision ID: 0016
Revises: 0015
Create Date: 2026-04-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Enums ---
    job_type_enum = postgresql.ENUM(
        "PDF_EXTRACT", "CHUNKING", "EMBEDDING", "BULK_QUESTION_GEN",
        "STATS_AGGREGATE", "RECOMMENDATION", "PRACTICUM_POST",
        "AI_LOG_ANALYSIS", "EMAIL_SEND", "COST_AGGREGATE",
        name="job_type_enum", create_type=True,
    )
    job_type_enum.create(op.get_bind(), checkfirst=True)

    job_status_enum = postgresql.ENUM(
        "PENDING", "RUNNING", "SUCCESS", "FAILED", "RETRYING", "DEAD_LETTER",
        name="job_status_enum", create_type=True,
    )
    job_status_enum.create(op.get_bind(), checkfirst=True)

    notification_category_enum = postgresql.ENUM(
        "ASSIGNMENT_DUE", "DIAGNOSTIC_REMINDER", "PROFESSOR_FEEDBACK",
        "WEAK_AREA_REVIEW", "PRACTICUM_SCHEDULE", "ANNOUNCEMENT",
        "KB_UPDATE", "SYSTEM",
        name="notification_category_enum", create_type=True,
    )
    notification_category_enum.create(op.get_bind(), checkfirst=True)

    # --- background_jobs ---
    op.create_table(
        "background_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("job_type", job_type_enum, nullable=False),
        sa.Column("status", job_status_enum, nullable=False, server_default="PENDING"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("progress", sa.Float, default=0.0),
        sa.Column("progress_message", sa.String(500), nullable=True),
        sa.Column("input_params", postgresql.JSONB, nullable=True),
        sa.Column("result", postgresql.JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, default=0),
        sa.Column("max_retries", sa.Integer, default=3),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_bg_jobs_status", "background_jobs", ["status"])
    op.create_index("ix_bg_jobs_type_status", "background_jobs", ["job_type", "status"])
    op.create_index("ix_bg_jobs_created_by", "background_jobs", ["created_by"])
    op.create_index("ix_bg_jobs_created_at", "background_jobs", ["created_at"])

    # --- notifications ---
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", notification_category_enum, nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("link", sa.String(500), nullable=True),
        sa.Column("extra_data", postgresql.JSONB, nullable=True),
        sa.Column("is_read", sa.Boolean, default=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_sent", sa.Boolean, default=False),
        sa.Column("push_sent", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_notifications_user_read", "notifications", ["user_id", "is_read"])
    op.create_index("ix_notifications_user_created", "notifications", ["user_id", "created_at"])
    op.create_index("ix_notifications_category", "notifications", ["category"])

    # --- cost_daily ---
    op.create_table(
        "cost_daily",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("department", sa.String(50), nullable=True),
        sa.Column("request_count", sa.Integer, default=0),
        sa.Column("success_count", sa.Integer, default=0),
        sa.Column("error_count", sa.Integer, default=0),
        sa.Column("input_tokens", sa.BigInteger, default=0),
        sa.Column("output_tokens", sa.BigInteger, default=0),
        sa.Column("total_tokens", sa.BigInteger, default=0),
        sa.Column("estimated_cost_usd", sa.Float, default=0.0),
        sa.Column("avg_latency_ms", sa.Integer, default=0),
        sa.Column("p95_latency_ms", sa.Integer, default=0),
        sa.Column("cache_hit_count", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_cost_daily_date", "cost_daily", ["date"])
    op.create_index("ix_cost_daily_provider", "cost_daily", ["provider"])
    op.create_unique_constraint("uq_cost_daily_key", "cost_daily", ["date", "provider", "model", "role", "department"])


def downgrade() -> None:
    op.drop_table("cost_daily")
    op.drop_table("notifications")
    op.drop_table("background_jobs")
    op.execute("DROP TYPE IF EXISTS notification_category_enum")
    op.execute("DROP TYPE IF EXISTS job_status_enum")
    op.execute("DROP TYPE IF EXISTS job_type_enum")
