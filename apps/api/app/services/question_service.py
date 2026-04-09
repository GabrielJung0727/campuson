"""QuestionBank 서비스 — CRUD + 필터링 + 일괄 업로드."""

import csv
import io
import json
import logging
import uuid
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Department, Difficulty, QuestionType
from app.models.question import Question
from app.schemas.question import BulkUploadResult, QuestionCreate, QuestionUpdate

logger = logging.getLogger(__name__)


class QuestionNotFoundError(Exception):
    pass


# --- CRUD ---
async def create_question(db: AsyncSession, payload: QuestionCreate) -> Question:
    """문제 1건 생성."""
    question = Question(
        department=payload.department,
        subject=payload.subject,
        unit=payload.unit,
        difficulty=payload.difficulty,
        question_type=payload.question_type,
        question_text=payload.question_text,
        choices=payload.choices,
        correct_answer=payload.correct_answer,
        explanation=payload.explanation,
        tags=payload.tags,
        source=payload.source,
        source_year=payload.source_year,
    )
    db.add(question)
    await db.flush()
    await db.refresh(question)
    return question


async def get_question(db: AsyncSession, question_id: uuid.UUID) -> Question:
    """문제 1건 조회 — 없으면 QuestionNotFoundError."""
    question = await db.get(Question, question_id)
    if question is None:
        raise QuestionNotFoundError(f"Question {question_id} not found")
    return question


async def update_question(
    db: AsyncSession, question_id: uuid.UUID, payload: QuestionUpdate
) -> Question:
    """문제 부분 업데이트.

    correct_answer/choices 정합성은 DB CheckConstraint와 함께,
    덮어쓴 값으로 재검증한다.
    """
    question = await get_question(db, question_id)

    update_data = payload.model_dump(exclude_unset=True)
    new_choices = update_data.get("choices", question.choices)
    new_correct = update_data.get("correct_answer", question.correct_answer)

    if new_correct >= len(new_choices):
        raise ValueError(
            f"correct_answer({new_correct}) must be less than len(choices)({len(new_choices)})"
        )

    for key, value in update_data.items():
        setattr(question, key, value)

    await db.flush()
    await db.refresh(question)
    return question


async def delete_question(db: AsyncSession, question_id: uuid.UUID) -> None:
    """문제 삭제."""
    question = await get_question(db, question_id)
    await db.delete(question)
    await db.flush()


# --- 검색/필터 ---
async def search_questions(
    db: AsyncSession,
    *,
    department: Department | None = None,
    subject: str | None = None,
    unit: str | None = None,
    difficulty: Difficulty | None = None,
    question_type: QuestionType | None = None,
    tags: list[str] | None = None,
    tags_match_all: bool = False,
    keyword: str | None = None,
    source_year: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Question], int]:
    """조건에 맞는 문제 목록 + 총 개수.

    Parameters
    ----------
    tags : list[str] | None
        태그 필터. 비어있지 않으면 매칭에 사용.
    tags_match_all : bool
        True면 모든 태그를 포함하는 문제(AND, ARRAY @> 연산),
        False면 하나라도 매칭되는 문제(OR, ARRAY && 연산).
    keyword : str | None
        question_text/explanation의 부분 일치 (ILIKE).

    Returns
    -------
    (items, total)
    """
    filters = []

    if department:
        filters.append(Question.department == department)
    if subject:
        filters.append(Question.subject == subject)
    if unit:
        filters.append(Question.unit == unit)
    if difficulty:
        filters.append(Question.difficulty == difficulty)
    if question_type:
        filters.append(Question.question_type == question_type)
    if source_year:
        filters.append(Question.source_year == source_year)
    if tags:
        if tags_match_all:
            filters.append(Question.tags.contains(tags))
        else:
            filters.append(Question.tags.overlap(tags))
    if keyword:
        like = f"%{keyword}%"
        filters.append(
            or_(
                Question.question_text.ilike(like),
                func.coalesce(Question.explanation, "").ilike(like),
            )
        )

    base_stmt = select(Question)
    if filters:
        base_stmt = base_stmt.where(and_(*filters))

    # total
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # paginated items
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    items_stmt = (
        base_stmt.order_by(Question.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = (await db.execute(items_stmt)).scalars().all()

    return list(items), total


async def list_distinct_subjects(
    db: AsyncSession, department: Department | None = None
) -> list[str]:
    """특정 학과의 distinct 과목 목록."""
    stmt = select(Question.subject).distinct().order_by(Question.subject)
    if department:
        stmt = stmt.where(Question.department == department)
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]


# --- CSV 일괄 업로드 ---
REQUIRED_CSV_COLUMNS = {
    "department",
    "subject",
    "question_text",
    "choices",
    "correct_answer",
}
OPTIONAL_CSV_COLUMNS = {
    "unit",
    "difficulty",
    "question_type",
    "explanation",
    "tags",
    "source",
    "source_year",
}


def _parse_csv_row(row: dict[str, str], row_index: int) -> QuestionCreate:
    """CSV 한 행을 QuestionCreate로 변환.

    선택지(`choices`)는 다음 형식 중 하나를 허용
    - JSON 배열: `["A", "B", "C"]`
    - 파이프 구분: `A|B|C`

    `tags`도 동일 (JSON 배열 또는 콤마 구분).
    """
    missing = REQUIRED_CSV_COLUMNS - set(row.keys())
    if missing:
        raise ValueError(f"row {row_index}: missing required columns {missing}")

    raw_choices = (row.get("choices") or "").strip()
    if raw_choices.startswith("["):
        choices = json.loads(raw_choices)
    else:
        choices = [c.strip() for c in raw_choices.split("|") if c.strip()]

    raw_tags = (row.get("tags") or "").strip()
    if raw_tags:
        if raw_tags.startswith("["):
            tags = json.loads(raw_tags)
        else:
            tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
    else:
        tags = []

    return QuestionCreate(
        department=Department(row["department"].strip().upper()),
        subject=row["subject"].strip(),
        unit=(row.get("unit") or "").strip() or None,
        difficulty=Difficulty((row.get("difficulty") or "MEDIUM").strip().upper()),
        question_type=QuestionType(
            (row.get("question_type") or "SINGLE_CHOICE").strip().upper()
        ),
        question_text=row["question_text"].strip(),
        choices=choices,
        correct_answer=int(row["correct_answer"]),
        explanation=(row.get("explanation") or "").strip() or None,
        tags=tags,
        source=(row.get("source") or "").strip() or None,
        source_year=int(row["source_year"]) if row.get("source_year") else None,
    )


async def bulk_upload_csv(
    db: AsyncSession, csv_bytes: bytes, *, dry_run: bool = False
) -> BulkUploadResult:
    """CSV 바이트를 파싱하여 일괄 등록.

    Parameters
    ----------
    csv_bytes : bytes
        UTF-8 또는 UTF-8-BOM CSV. 첫 행은 헤더.
    dry_run : bool
        True면 검증만 수행하고 DB에 저장하지 않는다.

    Returns
    -------
    BulkUploadResult
    """
    try:
        text = csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = csv_bytes.decode("cp949")

    reader = csv.DictReader(io.StringIO(text))
    inserted = 0
    failed = 0
    errors: list[dict[str, Any]] = []
    total = 0

    for i, row in enumerate(reader, start=2):  # start=2 because row 1 is header
        total += 1
        try:
            payload = _parse_csv_row(row, i)
            if not dry_run:
                await create_question(db, payload)
            inserted += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            if len(errors) < 100:
                errors.append({"row": i, "error": str(exc)[:300]})

    return BulkUploadResult(
        total_rows=total, inserted=inserted, failed=failed, errors=errors
    )
