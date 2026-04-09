"""kb_documents + kb_chunks tables (pgvector)

Revision ID: 0007_kb_documents
Revises: 0006_ai_request_logs
Create Date: 2026-04-15 09:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.config import settings

# revision identifiers, used by Alembic.
revision: str = "0007_kb_documents"
down_revision: str | None = "0006_ai_request_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = settings.embedding_dimensions  # default 1536


def upgrade() -> None:
    # --- 0) pgvector 확장 (init-db.sql에서도 활성화하지만 안전하게 한 번 더) ---
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- 1) Enums ---
    kb_review_status_enum = postgresql.ENUM(
        "DRAFT",
        "REVIEWED",
        "PUBLISHED",
        "ARCHIVED",
        name="kb_review_status_enum",
        create_type=True,
    )
    embedding_provider_enum = postgresql.ENUM(
        "OPENAI",
        "MOCK",
        name="embedding_provider_enum",
        create_type=True,
    )
    kb_review_status_enum.create(op.get_bind(), checkfirst=True)
    embedding_provider_enum.create(op.get_bind(), checkfirst=True)

    # --- 2) kb_documents ---
    op.create_table(
        "kb_documents",
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
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=300), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("source_year", sa.Integer(), nullable=True),
        sa.Column(
            "version", sa.Integer(), server_default="1", nullable=False
        ),
        sa.Column(
            "review_status",
            postgresql.ENUM(
                "DRAFT",
                "REVIEWED",
                "PUBLISHED",
                "ARCHIVED",
                name="kb_review_status_enum",
                create_type=False,
            ),
            server_default="DRAFT",
            nullable=False,
        ),
        sa.Column(
            "reviewed_by", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String(length=50)),
            server_default=sa.text("'{}'::varchar[]"),
            nullable=False,
        ),
        sa.Column(
            "extra_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "total_chunks", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "total_tokens", sa.Integer(), server_default="0", nullable=False
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
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("version >= 1", name="ck_kb_documents_version_positive"),
    )
    op.create_index(
        "ix_kb_documents_department_status",
        "kb_documents",
        ["department", "review_status"],
    )
    op.create_index(
        "ix_kb_documents_tags_gin",
        "kb_documents",
        ["tags"],
        postgresql_using="gin",
    )

    # --- 3) kb_chunks (with vector column) ---
    op.execute(
        f"""
        CREATE TABLE kb_chunks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id UUID NOT NULL REFERENCES kb_documents(id) ON DELETE CASCADE,
            department department_enum NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding vector({EMBEDDING_DIM}),
            embedding_provider embedding_provider_enum,
            embedding_model VARCHAR(100),
            embedding_dimensions INTEGER,
            token_count INTEGER NOT NULL DEFAULT 0,
            char_count INTEGER NOT NULL DEFAULT 0,
            chunk_metadata JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.create_index(
        "ix_kb_chunks_document_index",
        "kb_chunks",
        ["document_id", "chunk_index"],
    )
    op.create_index("ix_kb_chunks_department", "kb_chunks", ["department"])

    # --- 4) pgvector HNSW index ---
    # HNSW(m=16, ef_construction=64)은 pgvector 기본값. 데이터가 쌓인 뒤 실제
    # 검색 성능을 보며 ivfflat/조합을 튜닝할 수 있다.
    op.execute(
        "CREATE INDEX ix_kb_chunks_embedding_hnsw "
        "ON kb_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_kb_chunks_embedding_hnsw")
    op.drop_index("ix_kb_chunks_department", table_name="kb_chunks")
    op.drop_index("ix_kb_chunks_document_index", table_name="kb_chunks")
    op.execute("DROP TABLE IF EXISTS kb_chunks")

    op.drop_index("ix_kb_documents_tags_gin", table_name="kb_documents")
    op.drop_index("ix_kb_documents_department_status", table_name="kb_documents")
    op.drop_table("kb_documents")

    bind = op.get_bind()
    postgresql.ENUM(name="embedding_provider_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="kb_review_status_enum").drop(bind, checkfirst=True)
