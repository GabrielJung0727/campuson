"""Questions 라우터 — CRUD + 검색 + CSV 일괄 업로드.

권한 정책
---------
- **조회 (GET)** : 인증된 모든 사용자 (학생 포함)
- **단건 조회 (학생용)** : 정답/해설 제외 응답 (`/questions/{id}/play`)
- **생성/수정/삭제** : ADMIN, DEVELOPER만
- **CSV 일괄 업로드** : ADMIN, DEVELOPER만
"""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, require_roles
from app.db.session import get_db
from app.models.enums import Department, Difficulty, QuestionType, Role
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.question import (
    BulkUploadResult,
    QuestionCreate,
    QuestionListResponse,
    QuestionPublic,
    QuestionResponse,
    QuestionUpdate,
)
from app.services.question_service import (
    QuestionNotFoundError,
    bulk_upload_csv,
    create_question,
    delete_question,
    get_question,
    list_distinct_subjects,
    search_questions,
    update_question,
)

router = APIRouter(prefix="/questions", tags=["questions"])

# --- 검색/목록 ---


@router.get(
    "",
    response_model=QuestionListResponse,
    summary="문제 검색/필터링",
    description=(
        "다중 조건으로 문제은행을 검색합니다. "
        "tags 파라미터는 여러 번 전달할 수 있으며 (예: `?tags=호흡기&tags=응급`), "
        "`tags_match_all=true`이면 모든 태그를 포함하는 문제만 반환합니다."
    ),
)
async def list_questions(
    department: Department | None = Query(default=None),
    subject: str | None = Query(default=None),
    unit: str | None = Query(default=None),
    difficulty: Difficulty | None = Query(default=None),
    question_type: QuestionType | None = Query(default=None),
    tags: list[str] | None = Query(default=None),
    tags_match_all: bool = Query(default=False),
    keyword: str | None = Query(default=None, description="본문/해설 부분일치"),
    source_year: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> QuestionListResponse:
    items, total = await search_questions(
        db,
        department=department,
        subject=subject,
        unit=unit,
        difficulty=difficulty,
        question_type=question_type,
        tags=tags,
        tags_match_all=tags_match_all,
        keyword=keyword,
        source_year=source_year,
        page=page,
        page_size=page_size,
    )
    return QuestionListResponse(
        items=[QuestionResponse.model_validate(q) for q in items],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


@router.get(
    "/subjects",
    response_model=list[str],
    summary="과목 목록 조회 (distinct)",
)
async def list_subjects(
    department: Department | None = Query(default=None),
    _user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    return await list_distinct_subjects(db, department)


# --- 단건 조회 ---


@router.get("/{question_id}", response_model=QuestionResponse)
async def get_question_full(
    question_id: uuid.UUID,
    _user: User = Depends(
        require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)
    ),
    db: AsyncSession = Depends(get_db),
) -> QuestionResponse:
    """전체 정보(정답/해설 포함) 조회 — 교수 이상."""
    try:
        question = await get_question(db, question_id)
    except QuestionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return QuestionResponse.model_validate(question)


@router.get(
    "/{question_id}/play",
    response_model=QuestionPublic,
    summary="학생 풀이용 문제 조회 (정답/해설 제외)",
)
async def get_question_for_play(
    question_id: uuid.UUID,
    _user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> QuestionPublic:
    try:
        question = await get_question(db, question_id)
    except QuestionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return QuestionPublic.model_validate(question)


# --- 생성/수정/삭제 ---


@router.post(
    "",
    response_model=QuestionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_question_endpoint(
    payload: QuestionCreate,
    _user: User = Depends(require_roles(Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> QuestionResponse:
    question = await create_question(db, payload)
    return QuestionResponse.model_validate(question)


@router.patch("/{question_id}", response_model=QuestionResponse)
async def update_question_endpoint(
    question_id: uuid.UUID,
    payload: QuestionUpdate,
    _user: User = Depends(require_roles(Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> QuestionResponse:
    try:
        question = await update_question(db, question_id, payload)
    except QuestionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return QuestionResponse.model_validate(question)


@router.delete("/{question_id}", response_model=MessageResponse)
async def delete_question_endpoint(
    question_id: uuid.UUID,
    _user: User = Depends(require_roles(Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    try:
        await delete_question(db, question_id)
    except QuestionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return MessageResponse(message=f"Question {question_id} deleted")


# --- CSV 일괄 업로드 ---


@router.post(
    "/bulk-upload",
    response_model=BulkUploadResult,
    summary="CSV 일괄 업로드",
    description=(
        "CSV 파일을 업로드하여 문제를 일괄 등록합니다.\n\n"
        "**필수 헤더**: `department, subject, question_text, choices, correct_answer`\n\n"
        "**선택 헤더**: `unit, difficulty, question_type, explanation, tags, source, source_year`\n\n"
        "**choices** 형식: JSON 배열(`[\"a\",\"b\"]`) 또는 파이프 구분(`a|b|c`).\n\n"
        "**tags** 형식: JSON 배열 또는 콤마 구분.\n\n"
        "`?dry_run=true`로 전송하면 검증만 수행하고 DB에 저장하지 않습니다."
    ),
)
async def bulk_upload_endpoint(
    file: UploadFile = File(..., description="UTF-8 또는 CP949 CSV 파일"),
    dry_run: bool = Query(default=False),
    _user: User = Depends(require_roles(Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> BulkUploadResult:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .csv files are accepted.",
        )
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB cap
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="CSV exceeds 10MB limit.",
        )
    return await bulk_upload_csv(db, content, dry_run=dry_run)
