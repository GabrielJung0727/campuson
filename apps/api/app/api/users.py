"""Users 라우터 — 본인 조회/변경 + RBAC 가드 사용 예시."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_current_active_user,
    require_roles,
    require_self_or_roles,
)
from app.db.session import get_db
from app.models.enums import Role
from app.models.user import User
from app.schemas.auth import PasswordChangeRequest
from app.schemas.common import MessageResponse
from app.schemas.user import UserMe, UserPublic
from app.services.auth_service import (
    AuthError,
    InvalidCredentialsError,
    change_password,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserMe)
async def get_me(
    current_user: User = Depends(get_current_active_user),
) -> UserMe:
    """내 정보 조회."""
    return UserMe.model_validate(current_user)


@router.post(
    "/me/password",
    response_model=MessageResponse,
    responses={
        400: {"description": "비밀번호 정책 위반"},
        401: {"description": "현재 비밀번호 불일치"},
    },
)
async def change_my_password(
    payload: PasswordChangeRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """본인 비밀번호 변경."""
    try:
        await change_password(
            db, current_user, payload.current_password, payload.new_password
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return MessageResponse(message="비밀번호가 변경되었습니다.")


@router.get(
    "/{user_id}",
    response_model=UserPublic,
    responses={
        403: {"description": "권한 없음"},
        404: {"description": "사용자 없음"},
    },
)
async def get_user_by_id(
    user_id: uuid.UUID,
    requester: User = Depends(
        require_self_or_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)
    ),
    db: AsyncSession = Depends(get_db),
) -> UserPublic:
    """특정 사용자 조회 — 본인 또는 권한자만 가능.

    교수는 본인 학과 학생만 조회 가능 (require_self_or_roles에서 검증).
    """
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserPublic.model_validate(target)


@router.get(
    "",
    response_model=list[UserPublic],
    summary="학과 학생 목록 조회",
    description="교수/관리자가 본인 학과(또는 전체) 사용자를 조회.",
)
async def list_users(
    current_user: User = Depends(
        require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)
    ),
    db: AsyncSession = Depends(get_db),
) -> list[UserPublic]:
    """RBAC 스코프 적용 사용자 목록.

    - PROFESSOR: 본인 학과 사용자만
    - ADMIN/DEVELOPER: 전체
    """
    stmt = select(User)
    if current_user.role == Role.PROFESSOR:
        stmt = stmt.where(User.department == current_user.department)
    stmt = stmt.order_by(User.created_at.desc()).limit(200)

    result = await db.execute(stmt)
    users = result.scalars().all()
    return [UserPublic.model_validate(u) for u in users]
