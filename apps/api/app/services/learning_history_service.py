"""학습 이력 서비스 — 채점/오답 분류/오답노트/통계.

핵심 로직
--------
1. **submit_answer**: 풀이 채점 + 오답 분류 + LearningHistory 1건 INSERT.
   동일 (user, question)의 attempt_no를 자동 increment.
2. **classify_error**: Day 5는 룰 베이스. Day 9 이후 LLM으로 정교화 예정.
3. **list_wrong_answers**: 문제별 누적 오답 횟수 + 마지막 풀이가 정답인지 (resolved)
4. **aggregate_stats**: PostgreSQL `date_trunc`로 일/주/월 버킷 집계.

분류 룰 (Day 5 룰 베이스)
-----------------------
- `solving_time_sec < 10`        → CARELESS (실수형)
- `solving_time_sec >= 180`      → APPLICATION_GAP (응용 부족형)
- 같은 문제 누적 오답 ≥ 2회      → CONCEPT_GAP (개념 부족형)
- 그 외                          → CONFUSION (헷갈림형, 기본값)
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Difficulty, ErrorType
from app.models.learning_history import LearningHistory
from app.models.question import Question
from app.models.user import User
from app.schemas.learning_history import (
    LearningHistoryItem,
    LearningStatsResponse,
    StatsBucket,
    SubjectBreakdown,
    WrongAnswerItem,
)

logger = logging.getLogger(__name__)

# === 분류 임계값 ===
CARELESS_TIME_THRESHOLD_SEC = 10
APPLICATION_GAP_TIME_THRESHOLD_SEC = 180
CONCEPT_GAP_REPEAT_THRESHOLD = 2


# === 예외 ===
class HistoryError(Exception):
    pass


class QuestionNotFoundError(HistoryError):
    pass


# === 분류 로직 (순수 함수) ===
def classify_error(
    *,
    is_correct: bool,
    solving_time_sec: int,
    prior_wrong_count: int,
) -> ErrorType | None:
    """오답 분류 — 정답이면 None.

    Parameters
    ----------
    is_correct : bool
    solving_time_sec : int
    prior_wrong_count : int
        이전에 같은 문제를 틀린 횟수 (이번 풀이는 미포함).
    """
    if is_correct:
        return None
    if solving_time_sec < CARELESS_TIME_THRESHOLD_SEC:
        return ErrorType.CARELESS
    if prior_wrong_count + 1 >= CONCEPT_GAP_REPEAT_THRESHOLD:
        return ErrorType.CONCEPT_GAP
    if solving_time_sec >= APPLICATION_GAP_TIME_THRESHOLD_SEC:
        return ErrorType.APPLICATION_GAP
    return ErrorType.CONFUSION


# === 풀이 제출 ===
async def submit_answer(
    db: AsyncSession,
    user: User,
    question_id: uuid.UUID,
    selected_choice: int,
    solving_time_sec: int,
) -> tuple[LearningHistory, Question]:
    """풀이 채점 + 분류 + 저장."""
    question = await db.get(Question, question_id)
    if question is None:
        raise QuestionNotFoundError(f"Question {question_id} not found")

    if selected_choice >= len(question.choices):
        raise HistoryError(
            f"selected_choice({selected_choice})는 선택지 길이({len(question.choices)})를 초과합니다."
        )

    is_correct = selected_choice == question.correct_answer

    # 동일 (user, question) 누적 풀이 횟수 + 누적 오답 횟수
    counts_stmt = select(
        func.count(LearningHistory.id).label("total"),
        func.coalesce(
            func.sum(case((LearningHistory.is_correct.is_(False), 1), else_=0)), 0
        ).label("wrong"),
    ).where(
        LearningHistory.user_id == user.id,
        LearningHistory.question_id == question_id,
    )
    row = (await db.execute(counts_stmt)).one()
    prior_attempts = int(row.total)
    prior_wrong = int(row.wrong)

    error_type = classify_error(
        is_correct=is_correct,
        solving_time_sec=solving_time_sec,
        prior_wrong_count=prior_wrong,
    )

    history = LearningHistory(
        user_id=user.id,
        question_id=question_id,
        selected_choice=selected_choice,
        is_correct=is_correct,
        solving_time_sec=solving_time_sec,
        error_type=error_type,
        attempt_no=prior_attempts + 1,
        ai_feedback=None,  # Day 6/10에 채워짐
    )
    db.add(history)
    await db.flush()
    await db.refresh(history)
    return history, question


# === 학습 이력 조회 ===
async def list_history_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    only_wrong: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[LearningHistoryItem], int]:
    """사용자의 풀이 이력 페이지네이션 조회 — 문제 메타와 함께."""
    page = max(1, page)
    page_size = max(1, min(100, page_size))

    base = (
        select(
            LearningHistory.id,
            LearningHistory.question_id,
            LearningHistory.selected_choice,
            LearningHistory.is_correct,
            LearningHistory.solving_time_sec,
            LearningHistory.error_type,
            LearningHistory.attempt_no,
            LearningHistory.created_at,
            Question.subject,
            Question.unit,
            Question.difficulty,
            func.substring(Question.question_text, 1, 80).label(
                "question_text_preview"
            ),
        )
        .join(Question, Question.id == LearningHistory.question_id)
        .where(LearningHistory.user_id == user_id)
    )
    if only_wrong:
        base = base.where(LearningHistory.is_correct.is_(False))

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    items_stmt = (
        base.order_by(desc(LearningHistory.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(items_stmt)).all()
    items = [
        LearningHistoryItem(
            id=r.id,
            question_id=r.question_id,
            selected_choice=r.selected_choice,
            is_correct=r.is_correct,
            solving_time_sec=r.solving_time_sec,
            error_type=r.error_type,
            attempt_no=r.attempt_no,
            created_at=r.created_at,
            subject=r.subject,
            unit=r.unit,
            difficulty=r.difficulty,
            question_text_preview=r.question_text_preview,
        )
        for r in rows
    ]
    return items, total


# === 오답노트 ===
async def list_wrong_answers(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    subject: str | None = None,
    unit: str | None = None,
    difficulty: Difficulty | None = None,
    error_type: ErrorType | None = None,
    include_resolved: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[WrongAnswerItem], int]:
    """문제별 오답 누적 집계 — 반복 오답이 많은 순으로 정렬.

    가장 최근 풀이가 정답이면 `is_resolved=True`로 표시한다.
    `include_resolved=False` (기본)이면 resolved 항목은 제외.
    """
    page = max(1, page)
    page_size = max(1, min(100, page_size))

    # 가장 최근 풀이의 is_correct 추출 — 윈도우 함수 대신 distinct on
    latest_subq = (
        select(
            LearningHistory.question_id,
            LearningHistory.is_correct.label("latest_is_correct"),
            LearningHistory.error_type.label("latest_error_type"),
            LearningHistory.created_at.label("latest_at"),
            func.row_number()
            .over(
                partition_by=LearningHistory.question_id,
                order_by=desc(LearningHistory.created_at),
            )
            .label("rn"),
        )
        .where(LearningHistory.user_id == user_id)
        .subquery()
    )
    latest_only = select(
        latest_subq.c.question_id,
        latest_subq.c.latest_is_correct,
        latest_subq.c.latest_error_type,
        latest_subq.c.latest_at,
    ).where(latest_subq.c.rn == 1).subquery()

    # 누적 오답/총 시도 집계
    agg_subq = (
        select(
            LearningHistory.question_id,
            func.count(LearningHistory.id).label("total_attempts"),
            func.coalesce(
                func.sum(
                    case((LearningHistory.is_correct.is_(False), 1), else_=0)
                ),
                0,
            ).label("wrong_count"),
        )
        .where(LearningHistory.user_id == user_id)
        .group_by(LearningHistory.question_id)
        .having(
            func.coalesce(
                func.sum(
                    case((LearningHistory.is_correct.is_(False), 1), else_=0)
                ),
                0,
            )
            > 0
        )
        .subquery()
    )

    base = (
        select(
            agg_subq.c.question_id,
            agg_subq.c.total_attempts,
            agg_subq.c.wrong_count,
            latest_only.c.latest_is_correct,
            latest_only.c.latest_error_type,
            latest_only.c.latest_at,
            Question.subject,
            Question.unit,
            Question.difficulty,
            func.substring(Question.question_text, 1, 80).label(
                "question_text_preview"
            ),
        )
        .join(Question, Question.id == agg_subq.c.question_id)
        .join(latest_only, latest_only.c.question_id == agg_subq.c.question_id)
    )

    filters = []
    if subject:
        filters.append(Question.subject == subject)
    if unit:
        filters.append(Question.unit == unit)
    if difficulty:
        filters.append(Question.difficulty == difficulty)
    if error_type:
        filters.append(latest_only.c.latest_error_type == error_type)
    if not include_resolved:
        filters.append(latest_only.c.latest_is_correct.is_(False))

    if filters:
        base = base.where(*filters)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    items_stmt = (
        base.order_by(
            desc(agg_subq.c.wrong_count),
            desc(latest_only.c.latest_at),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(items_stmt)).all()
    items = [
        WrongAnswerItem(
            question_id=r.question_id,
            subject=r.subject,
            unit=r.unit,
            difficulty=r.difficulty,
            question_text_preview=r.question_text_preview,
            last_error_type=r.latest_error_type,
            wrong_count=int(r.wrong_count),
            total_attempts=int(r.total_attempts),
            last_attempted_at=r.latest_at,
            is_resolved=bool(r.latest_is_correct),
        )
        for r in rows
    ]
    return items, total


# === 학습 통계 ===
_PERIOD_TRUNC = {"daily": "day", "weekly": "week", "monthly": "month"}
_PERIOD_DEFAULT_DAYS = {"daily": 30, "weekly": 84, "monthly": 365}


async def aggregate_stats(
    db: AsyncSession,
    user_id: uuid.UUID,
    period: Literal["daily", "weekly", "monthly"] = "daily",
    days: int | None = None,
) -> LearningStatsResponse:
    """학습 통계 집계 — 시계열 버킷 + 과목별 breakdown + 오답 분포."""
    trunc_unit = _PERIOD_TRUNC[period]
    window_days = days or _PERIOD_DEFAULT_DAYS[period]
    since = datetime.now(UTC) - timedelta(days=window_days)

    # 시계열 버킷
    bucket_col = func.date_trunc(trunc_unit, LearningHistory.created_at).label(
        "bucket"
    )
    bucket_stmt = (
        select(
            bucket_col,
            func.count(LearningHistory.id).label("total"),
            func.coalesce(
                func.sum(case((LearningHistory.is_correct.is_(True), 1), else_=0)),
                0,
            ).label("correct"),
            func.coalesce(
                func.avg(LearningHistory.solving_time_sec), 0
            ).label("avg_time"),
        )
        .where(
            LearningHistory.user_id == user_id,
            LearningHistory.created_at >= since,
        )
        .group_by(bucket_col)
        .order_by(bucket_col)
    )
    bucket_rows = (await db.execute(bucket_stmt)).all()
    buckets = []
    for r in bucket_rows:
        total = int(r.total)
        correct = int(r.correct)
        buckets.append(
            StatsBucket(
                period_start=r.bucket.date(),
                total_attempts=total,
                correct_count=correct,
                wrong_count=total - correct,
                accuracy=round(correct / total, 4) if total else 0.0,
                avg_solving_time_sec=round(float(r.avg_time or 0), 2),
            )
        )

    # 과목별 breakdown (전체 기간, 시간 제한 없음)
    subj_stmt = (
        select(
            Question.subject,
            func.count(LearningHistory.id).label("total"),
            func.coalesce(
                func.sum(case((LearningHistory.is_correct.is_(True), 1), else_=0)),
                0,
            ).label("correct"),
        )
        .join(Question, Question.id == LearningHistory.question_id)
        .where(LearningHistory.user_id == user_id)
        .group_by(Question.subject)
        .order_by(Question.subject)
    )
    subj_rows = (await db.execute(subj_stmt)).all()
    subject_breakdown = []
    for r in subj_rows:
        total = int(r.total)
        correct = int(r.correct)
        subject_breakdown.append(
            SubjectBreakdown(
                subject=r.subject,
                total_attempts=total,
                correct_count=correct,
                wrong_count=total - correct,
                accuracy=round(correct / total, 4) if total else 0.0,
            )
        )

    # 전체 통계
    overall_stmt = select(
        func.count(LearningHistory.id).label("total"),
        func.coalesce(
            func.sum(case((LearningHistory.is_correct.is_(True), 1), else_=0)), 0
        ).label("correct"),
    ).where(LearningHistory.user_id == user_id)
    overall = (await db.execute(overall_stmt)).one()
    total_attempts = int(overall.total)
    total_correct = int(overall.correct)

    # 오답 분류 분포 (전체 기간)
    err_stmt = (
        select(
            LearningHistory.error_type,
            func.count(LearningHistory.id).label("cnt"),
        )
        .where(
            LearningHistory.user_id == user_id,
            LearningHistory.is_correct.is_(False),
        )
        .group_by(LearningHistory.error_type)
    )
    err_rows = (await db.execute(err_stmt)).all()
    error_type_distribution = {
        (r.error_type.value if r.error_type else "UNCLASSIFIED"): int(r.cnt)
        for r in err_rows
    }

    return LearningStatsResponse(
        period=period,
        buckets=buckets,
        subject_breakdown=subject_breakdown,
        overall_accuracy=(
            round(total_correct / total_attempts, 4) if total_attempts else 0.0
        ),
        total_attempts=total_attempts,
        total_correct=total_correct,
        total_wrong=total_attempts - total_correct,
        error_type_distribution=error_type_distribution,
    )
