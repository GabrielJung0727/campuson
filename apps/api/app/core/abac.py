"""ABAC (Attribute-Based Access Control) — v0.9.

RBAC 위에 추가되는 속성 기반 권한 가드:
- 학교(school_id) 단위 격리
- 학과(department) 단위 격리
- 클래스(class_id) 단위 격리
- 본인/위임 권한

사용 예
-------
```python
from app.core.abac import require_school_access, require_department_access

@router.get("/classes/{class_id}/students")
async def list_students(
    class_id: uuid.UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_class_access(db, user, class_id)
    ...
```
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Department, Role
from app.models.user import User

logger = logging.getLogger(__name__)


@dataclass
class AccessContext:
    """접근 제어 컨텍스트 — 정책 평가용 속성 모음."""
    actor: User
    resource_type: str  # "class" | "assignment" | "student_data" | "document"
    resource_owner_id: uuid.UUID | None = None
    resource_department: Department | None = None
    resource_school_id: uuid.UUID | None = None
    resource_class_id: uuid.UUID | None = None


class AccessDeniedError(HTTPException):
    """권한 거부 표준 예외 (403)."""
    def __init__(self, reason: str):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=reason)


# === 정책 평가 함수 ===


def is_same_school(actor: User, school_id: uuid.UUID | None) -> bool:
    """학교 일치 여부. 둘 다 None이면 True (싱글테넌트)."""
    if school_id is None and actor.school_id is None:
        return True
    return actor.school_id == school_id


def is_same_department(actor: User, department: Department | None) -> bool:
    """학과 일치 여부."""
    if department is None:
        return True
    return actor.department == department


def is_self(actor: User, owner_id: uuid.UUID | None) -> bool:
    """본인 소유 리소스 여부."""
    return owner_id is not None and actor.id == owner_id


# === 고수준 가드 ===


def evaluate_access(ctx: AccessContext) -> tuple[bool, str]:
    """ABAC 정책 평가 — (allowed, reason) 반환.

    정책 순서:
    1. DEVELOPER: 전체 허용
    2. ADMIN: 같은 학교 내 전체 허용
    3. 본인 데이터: 허용
    4. PROFESSOR: 같은 학교 + 같은 학과
    5. STUDENT: 본인 리소스만
    """
    actor = ctx.actor

    # 1. DEVELOPER — 전역 접근
    if actor.role == Role.DEVELOPER:
        return True, "developer_global"

    # 2. 학교 스코프 검증 (ADMIN/PROFESSOR)
    if actor.role in (Role.ADMIN, Role.PROFESSOR):
        if not is_same_school(actor, ctx.resource_school_id):
            return False, "cross_school_access_denied"

    # 3. ADMIN — 학교 내 전체
    if actor.role == Role.ADMIN:
        return True, "admin_within_school"

    # 4. 본인 리소스 — 허용
    if is_self(actor, ctx.resource_owner_id):
        return True, "self_resource"

    # 5. PROFESSOR — 같은 학과 제한
    if actor.role == Role.PROFESSOR:
        if is_same_department(actor, ctx.resource_department):
            return True, "professor_same_department"
        return False, "professor_cross_department_denied"

    # 6. STUDENT — 본인 외 접근 거부
    if actor.role == Role.STUDENT:
        return False, "student_other_user_denied"

    return False, "no_policy_matched"


def enforce_access(ctx: AccessContext) -> None:
    """정책 평가 후 거부 시 403 예외."""
    allowed, reason = evaluate_access(ctx)
    if not allowed:
        logger.warning(
            "ABAC denied: actor=%s role=%s resource=%s reason=%s",
            ctx.actor.id, ctx.actor.role.value, ctx.resource_type, reason,
        )
        raise AccessDeniedError(f"Access denied: {reason}")


# === 리소스별 헬퍼 ===


async def ensure_class_access(
    db: AsyncSession, actor: User, class_id: uuid.UUID,
) -> None:
    """클래스 접근 권한 확인."""
    from app.models.class_ import Class  # type: ignore

    cls = await db.get(Class, class_id)
    if cls is None:
        raise HTTPException(status_code=404, detail="Class not found")

    ctx = AccessContext(
        actor=actor,
        resource_type="class",
        resource_owner_id=getattr(cls, "professor_id", None),
        resource_department=getattr(cls, "department", None),
        resource_school_id=getattr(cls, "school_id", None),
        resource_class_id=class_id,
    )

    # 학생은 수강 중인 클래스만 접근 — 별도 로직 필요
    if actor.role == Role.STUDENT:
        # ClassEnrollment 확인 (Class 모델에 따라 다름)
        # 간단화: 같은 학과면 우선 허용 (세부는 enrollment 조회로 확장)
        if not is_same_department(actor, ctx.resource_department):
            raise AccessDeniedError("student_not_enrolled")
        return

    enforce_access(ctx)


async def ensure_student_data_access(
    db: AsyncSession, actor: User, target_student_id: uuid.UUID,
) -> User:
    """학생 데이터 접근 확인 (본인/교수/관리자)."""
    target = await db.get(User, target_student_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Student not found")

    ctx = AccessContext(
        actor=actor,
        resource_type="student_data",
        resource_owner_id=target.id,
        resource_department=target.department,
        resource_school_id=target.school_id,
    )
    enforce_access(ctx)
    return target


def ensure_department_scope(
    actor: User, target_department: Department,
) -> None:
    """학과 스코프 빠른 검증 — 교수/학생이 다른 학과 접근 차단."""
    if actor.role in (Role.ADMIN, Role.DEVELOPER):
        return
    if actor.department != target_department:
        raise AccessDeniedError("cross_department_access_denied")
