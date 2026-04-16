"""문항 검수 라우터 (v0.5).

엔드포인트
---------
- GET  /reviews/queue      — 검수 대기 문항 목록 (교수)
- POST /reviews/{question_id}  — 검수 제출 (승인/반려/수정요청)
- GET  /reviews/{question_id}/history — 문항 검수 이력
- GET  /reviews/{question_id}/edits   — 문항 수정 이력
- GET  /reviews/{question_id}/compare — AI vs 교수 해설 비교
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, require_roles
from app.db.session import get_db
from app.models.enums import QuestionReviewStatus, Role
from app.models.user import User
from app.services.question_review_service import (
    ReviewNotFoundError,
    ReviewPermissionError,
    get_comparison,
    get_edit_history,
    get_review_history,
    get_review_queue,
    submit_review,
)

router = APIRouter(prefix="/reviews", tags=["question-reviews"])


# === Schemas ===
class ReviewSubmitRequest(BaseModel):
    status: QuestionReviewStatus
    comment: str | None = None
    professor_explanation: str | None = Field(
        default=None,
        description="교수가 직접 작성/수정한 공식 해설",
    )


class ReviewQueueItem(BaseModel):
    question_id: str
    department: str
    subject: str
    unit: str | None
    difficulty: str
    question_text: str
    review_status: str
    created_at: str
    reviewer_comment: str | None = None


class ReviewQueueResponse(BaseModel):
    items: list[ReviewQueueItem]
    total: int
    page: int
    page_size: int
    has_next: bool


class ReviewHistoryItem(BaseModel):
    id: str
    status: str
    comment: str | None
    ai_explanation: str | None
    professor_explanation: str | None
    review_version: int
    reviewed_at: str | None
    created_at: str


class EditHistoryItem(BaseModel):
    id: str
    editor_id: str | None
    edit_type: str
    changes: dict | None
    comment: str | None
    created_at: str


# === Endpoints ===

@router.get(
    "/queue",
    response_model=ReviewQueueResponse,
    summary="검수 대기 문항 목록 (교수/관리자)",
)
async def list_review_queue(
    department: str | None = Query(default=None),
    review_status: QuestionReviewStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> ReviewQueueResponse:
    rows, total = await get_review_queue(
        db,
        department=department,
        status=review_status,
        page=page,
        page_size=page_size,
    )
    items = []
    for row in rows:
        q = row["question"]
        r = row["review"]
        items.append(ReviewQueueItem(
            question_id=str(q.id),
            department=q.department.value,
            subject=q.subject,
            unit=q.unit,
            difficulty=q.difficulty.value,
            question_text=q.question_text[:200],
            review_status=q.review_status.value,
            created_at=q.created_at.isoformat(),
            reviewer_comment=r.comment if r else None,
        ))
    return ReviewQueueResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


@router.post(
    "/{question_id}",
    status_code=status.HTTP_200_OK,
    summary="문항 검수 제출 (승인/반려/수정요청)",
)
async def submit_question_review(
    question_id: uuid.UUID,
    payload: ReviewSubmitRequest,
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        review = await submit_review(
            db,
            question_id=question_id,
            reviewer=current_user,
            status=payload.status,
            comment=payload.comment,
            professor_explanation=payload.professor_explanation,
        )
    except ReviewNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ReviewPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return {
        "review_id": str(review.id),
        "status": review.status.value,
        "review_version": review.review_version,
        "message": f"문항이 {review.status.label_ko} 처리되었습니다.",
    }


@router.get(
    "/{question_id}/history",
    response_model=list[ReviewHistoryItem],
    summary="문항 검수 이력",
)
async def list_review_history(
    question_id: uuid.UUID,
    _user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> list[ReviewHistoryItem]:
    reviews = await get_review_history(db, question_id)
    return [
        ReviewHistoryItem(
            id=str(r.id),
            status=r.status.value,
            comment=r.comment,
            ai_explanation=r.ai_explanation[:200] if r.ai_explanation else None,
            professor_explanation=r.professor_explanation[:200] if r.professor_explanation else None,
            review_version=r.review_version,
            reviewed_at=r.reviewed_at.isoformat() if r.reviewed_at else None,
            created_at=r.created_at.isoformat(),
        )
        for r in reviews
    ]


@router.get(
    "/{question_id}/edits",
    response_model=list[EditHistoryItem],
    summary="문항 수정 이력",
)
async def list_edit_history(
    question_id: uuid.UUID,
    _user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> list[EditHistoryItem]:
    edits = await get_edit_history(db, question_id)
    return [
        EditHistoryItem(
            id=str(e.id),
            editor_id=str(e.editor_id) if e.editor_id else None,
            edit_type=e.edit_type,
            changes=e.changes,
            comment=e.comment,
            created_at=e.created_at.isoformat(),
        )
        for e in edits
    ]


@router.get(
    "/{question_id}/compare",
    summary="AI 해설 vs 교수 공식 해설 비교",
)
async def compare_explanations(
    question_id: uuid.UUID,
    _user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await get_comparison(db, question_id)
    except ReviewNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
