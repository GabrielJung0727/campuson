"""v0.8 확장성: schools, school_settings, school_departments, lms_courses,
lms_grade_syncs, sso_sessions, osce_exams, osce_stations, practicum_rubrics,
practicum_events, practicum_replays, calendar_events, professor_comments 테이블 추가.

Revision ID: 0018
Revises: 0017
Create Date: 2026-04-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === schools ===
    op.create_table(
        "schools",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), unique=True, nullable=False),
        sa.Column("domain", sa.String(200), nullable=True),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("primary_color", sa.String(7), server_default="'#2563EB'", nullable=False),
        sa.Column("secondary_color", sa.String(7), server_default="'#1E40AF'", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_schools_code", "schools", ["code"])
    op.create_index("ix_schools_domain", "schools", ["domain"])

    # === school_settings ===
    op.create_table(
        "school_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("llm_provider", sa.String(50), server_default="'anthropic'", nullable=False),
        sa.Column("llm_model", sa.String(100), server_default="'claude-sonnet-4-6'", nullable=False),
        sa.Column("daily_token_limit_student", sa.Integer(), server_default="50000", nullable=False),
        sa.Column("daily_token_limit_professor", sa.Integer(), server_default="200000", nullable=False),
        sa.Column("monthly_cost_limit_usd", sa.Float(), server_default="500.0", nullable=False),
        sa.Column("sso_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("sso_provider", sa.String(50), nullable=True),
        sa.Column("sso_config", postgresql.JSONB(), nullable=True),
        sa.Column("lms_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("lms_platform", sa.String(50), nullable=True),
        sa.Column("lms_config", postgresql.JSONB(), nullable=True),
        sa.Column("custom_settings", postgresql.JSONB(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("school_id"),
    )

    # === school_departments ===
    op.create_table(
        "school_departments",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("department", sa.Enum("NURSING", "PHYSICAL_THERAPY", "DENTAL_HYGIENE", name="department_enum", create_type=False), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("head_professor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("student_count_limit", sa.Integer(), nullable=True),
        sa.Column("custom_blueprint", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["head_professor_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("school_id", "department", name="uq_school_department"),
    )
    op.create_index("ix_school_departments_school", "school_departments", ["school_id"])

    # === users.school_id ===
    op.add_column("users", sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_users_school", "users", "schools", ["school_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_users_school", "users", ["school_id"])

    # === lms_courses ===
    op.create_table(
        "lms_courses",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("class_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lms_course_id", sa.String(200), nullable=False),
        sa.Column("lms_course_name", sa.String(300), nullable=True),
        sa.Column("lms_platform", sa.String(50), nullable=False),
        sa.Column("sync_grades", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("grade_column_id", sa.String(200), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("config", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["class_id"], ["professor_classes.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("school_id", "lms_course_id", name="uq_lms_course"),
    )
    op.create_index("ix_lms_courses_school", "lms_courses", ["school_id"])
    op.create_index("ix_lms_courses_class", "lms_courses", ["class_id"])

    # === lms_grade_syncs ===
    op.create_table(
        "lms_grade_syncs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("lms_course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("score_type", sa.String(50), nullable=False),
        sa.Column("source_id", sa.String(100), nullable=True),
        sa.Column("lms_response", postgresql.JSONB(), nullable=True),
        sa.Column("success", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["lms_course_id"], ["lms_courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_lms_grade_syncs_course", "lms_grade_syncs", ["lms_course_id"])
    op.create_index("ix_lms_grade_syncs_student", "lms_grade_syncs", ["student_id"])

    # === sso_sessions ===
    op.create_table(
        "sso_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sso_provider", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(300), nullable=False),
        sa.Column("session_data", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_sso_sessions_school_user", "sso_sessions", ["school_id", "user_id"])
    op.create_index("ix_sso_sessions_external", "sso_sessions", ["school_id", "external_id"])

    # === osce_exams ===
    op.create_table(
        "osce_exams",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("department", sa.Enum("NURSING", "PHYSICAL_THERAPY", "DENTAL_HYGIENE", name="department_enum", create_type=False), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("total_stations", sa.Integer(), nullable=False),
        sa.Column("time_per_station_sec", sa.Integer(), server_default="600", nullable=False),
        sa.Column("transition_time_sec", sa.Integer(), server_default="60", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_osce_exams_dept", "osce_exams", ["department"])
    op.create_index("ix_osce_exams_school", "osce_exams", ["school_id"])

    # === osce_stations ===
    op.create_table(
        "osce_stations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("exam_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("station_order", sa.Integer(), nullable=False),
        sa.Column("station_name", sa.String(200), nullable=False),
        sa.Column("time_limit_sec", sa.Integer(), nullable=True),
        sa.Column("weight", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["exam_id"], ["osce_exams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scenario_id"], ["practicum_scenarios.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("exam_id", "station_order", name="uq_osce_station_order"),
    )
    op.create_index("ix_osce_stations_exam", "osce_stations", ["exam_id"])

    # === practicum_rubrics ===
    op.create_table(
        "practicum_rubrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("department", sa.Enum("NURSING", "PHYSICAL_THERAPY", "DENTAL_HYGIENE", name="department_enum", create_type=False), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("criteria", postgresql.JSONB(), server_default="'[]'::jsonb", nullable=False),
        sa.Column("total_score", sa.Integer(), server_default="100", nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["scenario_id"], ["practicum_scenarios.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_practicum_rubrics_dept", "practicum_rubrics", ["department"])
    op.create_index("ix_practicum_rubrics_scenario", "practicum_rubrics", ["scenario_id"])

    # === practicum_events ===
    op.create_table(
        "practicum_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("event_data", postgresql.JSONB(), nullable=True),
        sa.Column("timestamp_sec", sa.Float(), nullable=False),
        sa.Column("severity", sa.String(20), server_default="'warning'", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["session_id"], ["practicum_sessions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_practicum_events_session", "practicum_events", ["session_id"])
    op.create_index("ix_practicum_events_type", "practicum_events", ["event_type"])

    # === practicum_replays ===
    op.create_table(
        "practicum_replays",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), unique=True, nullable=False),
        sa.Column("total_duration_sec", sa.Float(), nullable=False),
        sa.Column("steps", postgresql.JSONB(), server_default="'[]'::jsonb", nullable=False),
        sa.Column("video_url", sa.String(500), nullable=True),
        sa.Column("video_thumbnail_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["session_id"], ["practicum_sessions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_practicum_replays_session", "practicum_replays", ["session_id"])

    # === calendar_events ===
    op.create_table(
        "calendar_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("all_day", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column("reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("reminder_minutes", sa.Integer(), nullable=True),
        sa.Column("is_completed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("meta", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_calendar_events_user_date", "calendar_events", ["user_id", "start_at"])
    op.create_index("ix_calendar_events_type", "calendar_events", ["event_type"])
    op.create_index("ix_calendar_events_school", "calendar_events", ["school_id"])

    # === professor_comments ===
    op.create_table(
        "professor_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("professor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_private", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["professor_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_professor_comments_student", "professor_comments", ["student_id"])
    op.create_index("ix_professor_comments_professor", "professor_comments", ["professor_id"])
    op.create_index("ix_professor_comments_target", "professor_comments", ["target_type", "target_id"])


def downgrade() -> None:
    op.drop_table("professor_comments")
    op.drop_table("calendar_events")
    op.drop_table("practicum_replays")
    op.drop_table("practicum_events")
    op.drop_table("practicum_rubrics")
    op.drop_table("osce_stations")
    op.drop_table("osce_exams")
    op.drop_table("sso_sessions")
    op.drop_table("lms_grade_syncs")
    op.drop_table("lms_courses")
    op.drop_index("ix_users_school", "users")
    op.drop_constraint("fk_users_school", "users", type_="foreignkey")
    op.drop_column("users", "school_id")
    op.drop_table("school_departments")
    op.drop_table("school_settings")
    op.drop_table("schools")
