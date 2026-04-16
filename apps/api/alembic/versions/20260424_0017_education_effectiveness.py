"""v0.7 교육 효과: exam_blueprints, concept_nodes, concept_relations 테이블 추가.

Revision ID: 0017
Revises: 0016
Create Date: 2026-04-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === exam_blueprints ===
    op.create_table(
        "exam_blueprints",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("department", sa.Enum("NURSING", "PHYSICAL_THERAPY", "DENTAL_HYGIENE", name="department_enum", create_type=False), nullable=False),
        sa.Column("exam_name", sa.String(200), nullable=False),
        sa.Column("exam_year", sa.Integer(), nullable=True),
        sa.Column("subject", sa.String(100), nullable=False),
        sa.Column("area", sa.String(200), nullable=False),
        sa.Column("sub_area", sa.String(200), nullable=True),
        sa.Column("weight_pct", sa.Float(), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=True),
        sa.Column("competency", sa.String(300), nullable=True),
        sa.Column("keywords", postgresql.ARRAY(sa.String(100)), server_default="'{}'::varchar[]", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("department", "exam_name", "subject", "area", "sub_area", name="uq_blueprint_entry"),
    )
    op.create_index("ix_blueprint_dept_subject", "exam_blueprints", ["department", "subject"])
    op.create_index("ix_blueprint_dept_area", "exam_blueprints", ["department", "area"])

    # === concept_nodes ===
    op.create_table(
        "concept_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("department", sa.Enum("NURSING", "PHYSICAL_THERAPY", "DENTAL_HYGIENE", name="department_enum", create_type=False), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False, comment="1=과목, 2=단원, 3=개념"),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("blueprint_area", sa.String(200), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["parent_id"], ["concept_nodes.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("department", "name", "level", "parent_id", name="uq_concept_node"),
    )
    op.create_index("ix_concept_dept_level", "concept_nodes", ["department", "level"])
    op.create_index("ix_concept_parent", "concept_nodes", ["parent_id"])

    # === concept_relations ===
    op.create_table(
        "concept_relations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relation_type", sa.String(50), nullable=False, comment="prerequisite | related | similar"),
        sa.Column("strength", sa.Float(), server_default="1.0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["source_id"], ["concept_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["concept_nodes.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("source_id", "target_id", "relation_type", name="uq_concept_relation"),
    )
    op.create_index("ix_concept_rel_source", "concept_relations", ["source_id"])
    op.create_index("ix_concept_rel_target", "concept_relations", ["target_id"])


def downgrade() -> None:
    op.drop_table("concept_relations")
    op.drop_table("concept_nodes")
    op.drop_table("exam_blueprints")
