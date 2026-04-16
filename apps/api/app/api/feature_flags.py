"""Feature flag 관리 라우터 (v0.9 — admin/dev 전용)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.dependencies import require_roles
from app.core.feature_flags import (
    REGISTRY,
    clear_flag,
    is_enabled,
    list_flags,
    set_flag,
)
from app.models.enums import Role
from app.models.user import User

router = APIRouter(prefix="/admin/feature-flags", tags=["feature-flags"])


class FlagSetRequest(BaseModel):
    enabled: bool | None = None
    rollout_pct: int | None = Field(None, ge=0, le=100)


@router.get("")
async def list_all_flags(
    _user: User = Depends(require_roles(Role.ADMIN, Role.DEVELOPER)),
):
    """등록된 모든 feature flag 조회."""
    return {"flags": list_flags()}


@router.get("/{key}/check")
async def check_flag(
    key: str,
    user: User = Depends(require_roles(Role.STUDENT, Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
):
    """현재 사용자 기준 flag 활성 여부."""
    if key not in REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown flag: {key}")
    enabled = await is_enabled(key, user=user)
    return {"key": key, "enabled": enabled}


@router.put("/{key}")
async def update_flag(
    key: str,
    body: FlagSetRequest,
    _user: User = Depends(require_roles(Role.ADMIN, Role.DEVELOPER)),
):
    """flag override 설정."""
    if key not in REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown flag: {key}")

    if body.rollout_pct is not None:
        await set_flag(key, body.rollout_pct)
    elif body.enabled is not None:
        await set_flag(key, body.enabled)
    else:
        raise HTTPException(status_code=400, detail="Either enabled or rollout_pct required")

    return {"key": key, "updated": True}


@router.delete("/{key}")
async def delete_flag_override(
    key: str,
    _user: User = Depends(require_roles(Role.ADMIN, Role.DEVELOPER)),
):
    """flag override 제거 — 기본값으로 복귀."""
    if key not in REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown flag: {key}")
    await clear_flag(key)
    return {"key": key, "cleared": True}
