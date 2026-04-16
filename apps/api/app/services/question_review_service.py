"""문항 검수 워크플로우 서비스 (v0.5).

교수가 AI 생성 문제 및 해설을 검수하는 비즈니스 로직.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import QuestionReviewStatus, Role
from app.models.question import Question
from app.models.question_review import QuestionEditHistory, QuestionReview
from app.models.user import User


class ReviewNotFoundError(Exception):
    pass


class ReviewPermissionError(Exception):
    pass


async def get_review_queue(
    db: AsyncSession,
    *,
    department: str | None = None,
    status: QuestionReviewStatus | None = None,
    reviewer_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """검수 대기 문항 목록 조회 (교수용)."""
    base = (
        select(Question, QuestionReview)
        .outerjoin(
            QuestionReview,
            (QuestionReview.question_id == Question.id)
            & (QuestionReview.review_version == select(func.max(QuestionReview.review_version)).where(QuestionReview.question_id == Question.id).correlate(Question).scalar_subquery()),
        )
    )

    filters = []
    if department:
        filters.append(Question.department == department)
    if status:
        filters.append(Question.review_status == status)
    else:
        # 기본: PENDING_REVIEW + REVISION_REQUESTED
        filters.append(
            Question.review_status.in_([
                QuestionReviewStatus.PENDING_REVIEW,
                QuestionReviewStatus.REVISION_REQUESTED,
            ])
        )
    if reviewer_id:
        filters.append(QuestionReview.reviewer_id == reviewer_id)
    if filters:
        base = base.where(*filters)

    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar_one()

    items_q = (
        base.order_by(desc(Question.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(items_q)).all()

    results = []
    for question, review in rows:
        results.append({
            "question": question,
            "review": review,
        })
    return results, total


async def submit_review(
    db: AsyncSession,
    *,
    question_id: uuid.UUID,
    reviewer: User,
    status: QuestionReviewStatus,
    comment: str | None = None,
    professor_explanation: str | None = None,
) -> QuestionReview:
    """교수가 문항을 검수 (승인/반려/수정요청)."""
    if reviewer.role not in (Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER):
        raise ReviewPermissionError("교수/관리자만 검수할 수 있습니다.")

    question = await db.get(Question, question_id)
    if question is None:
        raise ReviewNotFoundError(f"Question {question_id} not found")

    # 최신 리뷰 버전 조회
    latest_version = (
        await db.scalar(
            select(func.max(QuestionReview.review_version)).where(
                QuestionReview.question_id == question_id
            )
        )
    ) or 0

    now = datetime.now(timezone.utc)
    review = QuestionReview(
        question_id=question_id,
        reviewer_id=reviewer.id,
        status=status,
        comment=comment,
        ai_explanation=question.explanation,
        professor_explanation=professor_explanation,
        review_version=latest_version + 1,
        reviewed_at=now,
    )
    db.add(review)

    # 문항 상태 업데이트
    question.review_status = status
    if professor_explanation:
        question.professor_explanation = professor_explanation

    # 수정 이력 기록
    edit_history = QuestionEditHistory(
        question_id=question_id,
        editor_id=reviewer.id,
        edit_type=f"REVIEW_{status.value}",
        changes={
            "review_status": {"old": question.review_status.value if hasattr(question.review_status, 'value') else str(question.review_status), "new": status.value},
            "professor_explanation_added": professor_explanation is not None,
        },
        comment=comment,
    )
    db.add(edit_history)

    await db.flush()
    await db.refresh(review)
    return review


async def get_review_history(
    db: AsyncSession,
    question_id: uuid.UUID,
) -> list[QuestionReview]:
    """문항의 전체 검수 이력."""
    stmt = (
        select(QuestionReview)
        .where(QuestionReview.question_id == question_id)
        .order_by(desc(QuestionReview.review_version))
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_edit_history(
    db: AsyncSession,
    question_id: uuid.UUID,
) -> list[QuestionEditHistory]:
    """문항의 전체 수정 이력."""
    stmt = (
        select(QuestionEditHistory)
        .where(QuestionEditHistory.question_id == question_id)
        .order_by(desc(QuestionEditHistory.created_at))
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_comparison(
    db: AsyncSession,
    question_id: uuid.UUID,
) -> dict:
    """AI 해설 vs 교수 공식 해설 비교 데이터."""
    question = await db.get(Question, question_id)
    if question is None:
        raise ReviewNotFoundError(f"Question {question_id} not found")

    latest_review = await db.scalar(
        select(QuestionReview)
        .where(QuestionReview.question_id == question_id)
        .order_by(desc(QuestionReview.review_version))
        .limit(1)
    )

    return {
        "question_id": str(question_id),
        "ai_explanation": question.explanation,
        "professor_explanation": question.professor_explanation,
        "review_status": question.review_status.value,
        "latest_review": {
            "id": str(latest_review.id),
            "status": latest_review.status.value,
            "comment": latest_review.comment,
            "ai_explanation": latest_review.ai_explanation,
            "professor_explanation": latest_review.professor_explanation,
            "reviewed_at": latest_review.reviewed_at.isoformat() if latest_review.reviewed_at else None,
        } if latest_review else None,
    }
