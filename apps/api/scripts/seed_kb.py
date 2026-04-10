"""KB 지식베이스 시드 스크립트.

Day 9 — 학과별 문서를 적재하고 청킹 + 임베딩까지 수행.

사용법
------
```bash
cd apps/api

# 1) 마이그레이션 적용 (kb_documents, kb_chunks 테이블 생성)
alembic upgrade head

# 2) 시드 실행 (Mock 임베딩 기본)
python -m scripts.seed_kb

# 옵션
python -m scripts.seed_kb --truncate   # 기존 KB 비우고 재시드
python -m scripts.seed_kb --publish     # 모든 문서를 PUBLISHED 상태로 적재
```

환경 변수
--------
- `EMBEDDING_PROVIDER=openai` + `OPENAI_API_KEY` 가 있으면 실제 OpenAI 임베딩 사용.
- 기본은 Mock provider (결정론적 L2 정규화 벡터).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("seed_kb")


async def main_async(args: argparse.Namespace) -> int:
    # Lazy imports — asyncpg 필요
    from sqlalchemy import delete

    from app.db.session import AsyncSessionLocal, engine
    from app.models.enums import Department, KBReviewStatus
    from app.models.kb_document import KBChunk, KBDocument
    from app.services.kb_ingest_service import IngestRequest, ingest_document
    from scripts.seed_data.kb_dental_hygiene import DH_KB_DOCUMENTS
    from scripts.seed_data.kb_nursing import NURSING_KB_DOCUMENTS
    from scripts.seed_data.kb_physical_therapy import PT_KB_DOCUMENTS

    all_docs = [
        (Department.NURSING, NURSING_KB_DOCUMENTS),
        (Department.PHYSICAL_THERAPY, PT_KB_DOCUMENTS),
        (Department.DENTAL_HYGIENE, DH_KB_DOCUMENTS),
    ]

    total_docs = sum(len(docs) for _, docs in all_docs)
    logger.info("=" * 60)
    logger.info("KB Seed — total %d documents across %d departments", total_docs, len(all_docs))
    logger.info("=" * 60)

    async with AsyncSessionLocal() as session:
        if args.truncate:
            logger.warning("--truncate: DELETE FROM kb_chunks, kb_documents")
            await session.execute(delete(KBChunk))
            await session.execute(delete(KBDocument))
            await session.commit()

        total_inserted = 0
        total_chunks = 0
        total_embedded = 0
        failed = []
        default_status = (
            KBReviewStatus.PUBLISHED if args.publish else KBReviewStatus.DRAFT
        )

        for dept, docs in all_docs:
            logger.info("[%s] %d documents", dept.value, len(docs))
            for i, doc in enumerate(docs, start=1):
                try:
                    req = IngestRequest(
                        department=dept,
                        title=doc["title"],
                        content=doc["content"],
                        source=doc.get("source"),
                        source_year=doc.get("source_year"),
                        tags=doc.get("tags", []),
                        extra_metadata={"doc_type": doc.get("doc_type")},
                        review_status=default_status,
                    )
                    result = await ingest_document(session, req)
                    await session.commit()
                    total_inserted += 1
                    total_chunks += result.total_chunks
                    total_embedded += result.embedded_chunks
                    if i % 10 == 0 or i == len(docs):
                        logger.info(
                            "  [%s] %d/%d — chunks=%d embedded=%d",
                            dept.value,
                            i,
                            len(docs),
                            result.total_chunks,
                            result.embedded_chunks,
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.exception("  Failed: [%s] %s — %s", dept.value, doc.get("title"), exc)
                    failed.append((dept.value, doc.get("title"), str(exc)))
                    await session.rollback()

    await engine.dispose()

    logger.info("=" * 60)
    logger.info("✅ KB Seed complete")
    logger.info("   Documents inserted: %d / %d", total_inserted, total_docs)
    logger.info("   Total chunks:       %d", total_chunks)
    logger.info("   Embedded chunks:    %d", total_embedded)
    if failed:
        logger.warning("   Failed: %d", len(failed))
        for f in failed[:5]:
            logger.warning("     %s", f)
    logger.info("=" * 60)
    return 0 if total_inserted else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the knowledge base with sample documents")
    parser.add_argument("--truncate", action="store_true", help="기존 KB 데이터 삭제 후 재시드")
    parser.add_argument(
        "--publish",
        action="store_true",
        help="모든 문서를 PUBLISHED 상태로 적재 (기본은 DRAFT)",
    )
    args = parser.parse_args()

    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
