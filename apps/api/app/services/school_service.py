"""학교(테넌트) 관리 서비스 (v0.8).

- 학교 CRUD
- 학교 설정 관리 (브랜딩, LLM, SSO, LMS)
- 학교별 학과 관리
- 학교별 사용자 디렉터리
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import Department
from app.models.school import School, SchoolDepartment, SchoolSettings
from app.models.user import User

logger = logging.getLogger(__name__)


# === School CRUD ===


async def create_school(
    db: AsyncSession,
    *,
    name: str,
    code: str,
    domain: str | None = None,
    logo_url: str | None = None,
    primary_color: str = "#2563EB",
    secondary_color: str = "#1E40AF",
) -> School:
    """학교 생성."""
    school = School(
        name=name,
        code=code,
        domain=domain,
        logo_url=logo_url,
        primary_color=primary_color,
        secondary_color=secondary_color,
    )
    db.add(school)
    await db.flush()

    # 기본 ��정 생성
    settings = SchoolSettings(school_id=school.id)
    db.add(settings)
    await db.flush()
    await db.refresh(school)
    return school


async def get_school(db: AsyncSession, school_id: uuid.UUID) -> School | None:
    """학교 조회 (설정/학과 포함)."""
    return await db.scalar(
        select(School)
        .options(selectinload(School.settings), selectinload(School.departments))
        .where(School.id == school_id)
    )


async def list_schools(db: AsyncSession, *, active_only: bool = True) -> list[dict]:
    """전체 학교 목록."""
    stmt = select(School).order_by(School.name)
    if active_only:
        stmt = stmt.where(School.is_active.is_(True))
    schools = list((await db.execute(stmt)).scalars().all())
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "code": s.code,
            "domain": s.domain,
            "logo_url": s.logo_url,
            "primary_color": s.primary_color,
            "secondary_color": s.secondary_color,
            "is_active": s.is_active,
        }
        for s in schools
    ]


async def update_school(
    db: AsyncSession, school_id: uuid.UUID, **kwargs,
) -> School | None:
    """학교 정보 업데이트."""
    school = await db.get(School, school_id)
    if not school:
        return None
    for k, v in kwargs.items():
        if hasattr(school, k) and v is not None:
            setattr(school, k, v)
    await db.flush()
    return school


# === School Settings ===


async def get_school_settings(db: AsyncSession, school_id: uuid.UUID) -> dict | None:
    """학교 설정 조회."""
    settings = await db.scalar(
        select(SchoolSettings).where(SchoolSettings.school_id == school_id)
    )
    if not settings:
        return None
    return {
        "school_id": str(settings.school_id),
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "daily_token_limit_student": settings.daily_token_limit_student,
        "daily_token_limit_professor": settings.daily_token_limit_professor,
        "monthly_cost_limit_usd": settings.monthly_cost_limit_usd,
        "sso_enabled": settings.sso_enabled,
        "sso_provider": settings.sso_provider,
        "lms_enabled": settings.lms_enabled,
        "lms_platform": settings.lms_platform,
        "custom_settings": settings.custom_settings,
    }


async def update_school_settings(
    db: AsyncSession, school_id: uuid.UUID, **kwargs,
) -> SchoolSettings | None:
    """학교 설정 업데이트."""
    settings = await db.scalar(
        select(SchoolSettings).where(SchoolSettings.school_id == school_id)
    )
    if not settings:
        return None
    for k, v in kwargs.items():
        if hasattr(settings, k) and v is not None:
            setattr(settings, k, v)
    await db.flush()
    return settings


# === School Departments ===


async def add_department(
    db: AsyncSession,
    school_id: uuid.UUID,
    department: Department,
    *,
    head_professor_id: uuid.UUID | None = None,
    student_count_limit: int | None = None,
) -> SchoolDepartment:
    """학교에 학과 추가."""
    dept = SchoolDepartment(
        school_id=school_id,
        department=department,
        head_professor_id=head_professor_id,
        student_count_limit=student_count_limit,
    )
    db.add(dept)
    await db.flush()
    return dept


async def get_school_departments(
    db: AsyncSession, school_id: uuid.UUID,
) -> list[dict]:
    """학교의 활성 학과 목록."""
    rows = list((await db.execute(
        select(SchoolDepartment)
        .where(SchoolDepartment.school_id == school_id, SchoolDepartment.is_active.is_(True))
    )).scalars().all())

    return [
        {
            "id": str(d.id),
            "department": d.department.value,
            "department_label": d.department.label_ko,
            "is_active": d.is_active,
            "head_professor_id": str(d.head_professor_id) if d.head_professor_id else None,
            "student_count_limit": d.student_count_limit,
        }
        for d in rows
    ]


# === School User Directory ===


async def get_school_directory(
    db: AsyncSession,
    school_id: uuid.UUID,
    *,
    department: Department | None = None,
    role: str | None = None,
) -> dict:
    """학교별 교수/학생 디렉터리."""
    stmt = select(User).where(User.school_id == school_id)
    if department:
        stmt = stmt.where(User.department == department)
    if role:
        stmt = stmt.where(User.role == role)
    stmt = stmt.order_by(User.department, User.name)

    users = list((await db.execute(stmt)).scalars().all())

    # 학과별 그룹핑
    by_dept: dict[str, list] = {}
    for u in users:
        dept_key = u.department.value
        if dept_key not in by_dept:
            by_dept[dept_key] = []
        by_dept[dept_key].append({
            "id": str(u.id),
            "name": u.name,
            "email": u.email,
            "role": u.role.value,
            "student_no": u.student_no,
            "department": u.department.value,
            "status": u.status.value,
        })

    return {
        "school_id": str(school_id),
        "total_users": len(users),
        "by_department": by_dept,
    }
