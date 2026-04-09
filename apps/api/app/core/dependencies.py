"""FastAPI 의존성 — 인증/RBAC 가드.

사용 예
-------
```python
from app.core.dependencies import get_current_user, require_roles
from app.models.enums import Role

@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return user

@router.get("/admin/users")
async def admin_only(user: User = Depends(require_roles(Role.ADMIN, Role.DEVELOPER))):
    ...
```
"""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import TokenError, decode_token
from app.db.session import get_db
from app.models.enums import Role, UserStatus
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.api_prefix}/auth/login",
    auto_error=False,
)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """유효한 액세스 토큰에서 현재 사용자를 로드합니다.

    Raises
    ------
    HTTPException 401
        토큰이 없거나 유효하지 않을 때.
    HTTPException 404
        토큰의 사용자가 존재하지 않을 때.
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exc

    try:
        payload = decode_token(token, expected_type="access")
    except TokenError as exc:
        raise credentials_exc from exc

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise credentials_exc
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError as exc:
        raise credentials_exc from exc

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """ACTIVE 상태인 사용자만 통과시킵니다."""
    if current_user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {current_user.status.value.lower()}, not active",
        )
    return current_user


def require_roles(*allowed_roles: Role):
    """역할 기반 가드 팩토리.

    Parameters
    ----------
    *allowed_roles : Role
        허용할 역할 목록. 하나라도 매칭되면 통과.

    Returns
    -------
    Callable
        FastAPI Depends에 전달할 의존성 함수.
    """

    async def _dep(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            allowed = ", ".join(r.value for r in allowed_roles)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: [{allowed}]",
            )
        return current_user

    return _dep


def require_self_or_roles(*allowed_roles: Role):
    """본인 데이터이거나 특정 역할인 경우 통과.

    경로 파라미터 `user_id`가 있을 때, current_user.id == user_id 또는
    current_user.role이 allowed_roles에 포함되면 통과한다.

    교수(Professor)는 같은 학과 학생만 조회 가능하도록 추가 검증을 수행한다.
    """

    async def _dep(
        user_id: uuid.UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        # 본인 접근 → 즉시 통과
        if current_user.id == user_id:
            return current_user

        # 역할 체크
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden — not allowed to access this resource",
            )

        # 교수: 같은 학과 학생만 접근 가능
        if current_user.role == Role.PROFESSOR:
            target_user = await db.get(User, user_id)
            if target_user is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found"
                )
            if target_user.department != current_user.department:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Professors can only access students in their own department",
                )

        return current_user

    return _dep
