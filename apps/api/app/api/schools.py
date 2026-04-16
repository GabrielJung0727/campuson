"""학교(멀티테넌트) 관리 라우터 (v0.8).

엔드포인트
---------
- POST   /schools                   — 학교 생성 (ADMIN)
- GET    /schools                   — 학교 목록
- GET    /schools/{id}              — 학교 상세
- PATCH  /schools/{id}              — 학교 수정
- GET    /schools/{id}/settings     — 학교 설정 조회
- PATCH  /schools/{id}/settings     — 학교 설정 수정
- POST   /schools/{id}/departments  — 학과 추가
- GET    /schools/{id}/departments  — 학과 목록
- GET    /schools/{id}/directory    — 사용자 디렉터리
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, require_roles
from app.db.session import get_db
from app.models.enums import Department, Role
from app.models.user import User
from app.schemas.common import MessageResponse
from app.services import school_service

router = APIRouter(prefix="/schools", tags=["schools"])


# === Schemas ===


class SchoolCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=2, max_length=50)
    domain: str | None = None
    logo_url: str | None = None
    primary_color: str = "#2563EB"
    secondary_color: str = "#1E40AF"


class SchoolUpdateRequest(BaseModel):
    name: str | None = None
    domain: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None


class SchoolSettingsUpdateRequest(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = None
    daily_token_limit_student: int | None = None
    daily_token_limit_professor: int | None = None
    monthly_cost_limit_usd: float | None = None
    sso_enabled: bool | None = None
    sso_provider: str | None = None
    lms_enabled: bool | None = None
    lms_platform: str | None = None


class DepartmentAddRequest(BaseModel):
    department: Department
    head_professor_id: uuid.UUID | None = None
    student_count_limit: int | None = None


# === Endpoints ===


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_school(
    body: SchoolCreateRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(Role.ADMIN, Role.DEVELOPER)),
):
    """학교 생성 (ADMIN 이상)."""
    school = await school_service.create_school(db, **body.model_dump())
    await db.commit()
    return {"id": str(school.id), "name": school.name, "code": school.code}


@router.get("")
async def list_schools(
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_active_user),
):
    """학교 목록."""
    return await school_service.list_schools(db, active_only=active_only)


@router.get("/{school_id}")
async def get_school(
    school_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_active_user),
):
    """학교 상세 조회."""
    school = await school_service.get_school(db, school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    return {
        "id": str(school.id),
        "name": school.name,
        "code": school.code,
        "domain": school.domain,
        "logo_url": school.logo_url,
        "primary_color": school.primary_color,
        "secondary_color": school.secondary_color,
        "is_active": school.is_active,
    }


@router.patch("/{school_id}")
async def update_school(
    school_id: uuid.UUID,
    body: SchoolUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(Role.ADMIN, Role.DEVELOPER)),
):
    """학교 정보 수정."""
    school = await school_service.update_school(
        db, school_id, **body.model_dump(exclude_none=True),
    )
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    await db.commit()
    return {"id": str(school.id), "name": school.name}


@router.get("/{school_id}/settings")
async def get_school_settings(
    school_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(Role.ADMIN, Role.DEVELOPER)),
):
    """학교 설정 조회."""
    settings = await school_service.get_school_settings(db, school_id)
    if not settings:
        raise HTTPException(status_code=404, detail="School settings not found")
    return settings


@router.patch("/{school_id}/settings")
async def update_school_settings(
    school_id: uuid.UUID,
    body: SchoolSettingsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(Role.ADMIN, Role.DEVELOPER)),
):
    """학교 설정 수정."""
    settings = await school_service.update_school_settings(
        db, school_id, **body.model_dump(exclude_none=True),
    )
    if not settings:
        raise HTTPException(status_code=404, detail="School settings not found")
    await db.commit()
    return MessageResponse(message="Settings updated")


@router.post("/{school_id}/departments", status_code=status.HTTP_201_CREATED)
async def add_department(
    school_id: uuid.UUID,
    body: DepartmentAddRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(Role.ADMIN, Role.DEVELOPER)),
):
    """학과 추가."""
    dept = await school_service.add_department(
        db, school_id, body.department,
        head_professor_id=body.head_professor_id,
        student_count_limit=body.student_count_limit,
    )
    await db.commit()
    return {"id": str(dept.id), "department": dept.department.value}


@router.get("/{school_id}/departments")
async def get_school_departments(
    school_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_active_user),
):
    """학과 목록."""
    return await school_service.get_school_departments(db, school_id)


@router.get("/{school_id}/directory")
async def get_school_directory(
    school_id: uuid.UUID,
    department: Department | None = Query(None),
    role: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
):
    """사용자 디렉터리 (교수 이상)."""
    return await school_service.get_school_directory(
        db, school_id, department=department, role=role,
    )
