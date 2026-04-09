"""문제은행 시드 스크립트.

Day 3 — 학과별 샘플 200문항을 DB에 적재한다.

사용법
------
```bash
cd apps/api

# 1) DB 마이그레이션 적용 (questions 테이블 생성)
alembic upgrade head

# 2) 시드 실행
python -m scripts.seed_questions

# 옵션
python -m scripts.seed_questions --truncate   # 기존 questions 비우고 재시드
python -m scripts.seed_questions --csv-out ../../data/seed/questions.csv  # CSV export도 함께
```
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import sys
from pathlib import Path

from app.models.enums import Department, Difficulty, QuestionType
from scripts.seed_data.dental_hygiene import DH_QUESTIONS
from scripts.seed_data.nursing import NURSING_QUESTIONS
from scripts.seed_data.physical_therapy import PT_QUESTIONS

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("seed")

DEPT_MAP = {
    "nursing": (NURSING_QUESTIONS, Department.NURSING),
    "physical_therapy": (PT_QUESTIONS, Department.PHYSICAL_THERAPY),
    "dental_hygiene": (DH_QUESTIONS, Department.DENTAL_HYGIENE),
}

ALL_QUESTIONS = [
    (q, Department.NURSING) for q in NURSING_QUESTIONS
] + [
    (q, Department.PHYSICAL_THERAPY) for q in PT_QUESTIONS
] + [
    (q, Department.DENTAL_HYGIENE) for q in DH_QUESTIONS
]


def _build_question_model(payload: dict, department: Department):
    """dict 시드 항목 → Question ORM (lazy import)."""
    from app.models.question import Question  # local import — DB 의존성 회피

    return Question(
        department=department,
        subject=payload["subject"],
        unit=payload.get("unit"),
        difficulty=payload.get("difficulty", Difficulty.MEDIUM),
        question_type=payload.get("question_type", QuestionType.SINGLE_CHOICE),
        question_text=payload["question_text"],
        choices=payload["choices"],
        correct_answer=payload["correct_answer"],
        explanation=payload.get("explanation"),
        tags=payload.get("tags", []),
        source=payload.get("source", "샘플 시드 (Day 3)"),
        source_year=payload.get("source_year"),
    )


async def seed_database(*, truncate: bool) -> int:
    """DB에 시드 데이터를 삽입.

    Returns
    -------
    int
        삽입된 문제 개수.
    """
    # Lazy imports — csv-only 모드에서는 asyncpg가 필요 없도록
    from sqlalchemy import delete

    from app.db.session import AsyncSessionLocal
    from app.models.question import Question

    async with AsyncSessionLocal() as session:
        if truncate:
            logger.warning("--truncate: DELETE FROM questions")
            await session.execute(delete(Question))
            await session.commit()

        inserted = 0
        for payload, dept in ALL_QUESTIONS:
            session.add(_build_question_model(payload, dept))
            inserted += 1
            if inserted % 50 == 0:
                await session.flush()
                logger.info("  flushed %d questions...", inserted)

        await session.commit()
        logger.info("✅ Inserted %d questions", inserted)
        return inserted


def export_csv(out_path: Path) -> int:
    """CSV로 export — bulk-upload 엔드포인트 테스트용 샘플로 사용."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "department",
        "subject",
        "unit",
        "difficulty",
        "question_type",
        "question_text",
        "choices",
        "correct_answer",
        "explanation",
        "tags",
        "source",
        "source_year",
    ]
    count = 0
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for payload, dept in ALL_QUESTIONS:
            writer.writerow(
                {
                    "department": dept.value,
                    "subject": payload["subject"],
                    "unit": payload.get("unit", ""),
                    "difficulty": payload.get("difficulty", Difficulty.MEDIUM).value,
                    "question_type": payload.get(
                        "question_type", QuestionType.SINGLE_CHOICE
                    ).value,
                    "question_text": payload["question_text"],
                    "choices": json.dumps(payload["choices"], ensure_ascii=False),
                    "correct_answer": payload["correct_answer"],
                    "explanation": payload.get("explanation", ""),
                    "tags": json.dumps(payload.get("tags", []), ensure_ascii=False),
                    "source": payload.get("source", "샘플 시드 (Day 3)"),
                    "source_year": payload.get("source_year") or "",
                }
            )
            count += 1
    logger.info("📝 CSV exported → %s (%d rows)", out_path, count)
    return count


async def main_async(args: argparse.Namespace) -> int:
    if args.csv_out:
        export_csv(Path(args.csv_out))

    if args.csv_only:
        return 0

    inserted = await seed_database(truncate=args.truncate)
    # Lazy import — engine은 seed_database에서 import된 후 dispose
    from app.db.session import engine

    await engine.dispose()
    return 0 if inserted else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed QuestionBank with 200 sample questions")
    parser.add_argument(
        "--truncate", action="store_true", help="기존 questions 테이블을 비우고 재시드"
    )
    parser.add_argument(
        "--csv-out",
        type=str,
        default=None,
        help="CSV export 경로 (예: ../../data/seed/questions.csv)",
    )
    parser.add_argument(
        "--csv-only",
        action="store_true",
        help="DB에 적재하지 않고 CSV만 생성 (--csv-out 필수)",
    )
    args = parser.parse_args()

    if args.csv_only and not args.csv_out:
        print("❌ --csv-only requires --csv-out", file=sys.stderr)
        return 1

    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
