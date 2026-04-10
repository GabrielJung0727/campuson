"""교수 클래스 관리 라우터.

엔드포인트
---------
- POST   /classes                      — 클래스 생성 (PROFESSOR)
- GET    /classes                      — 내 클래스 목록
- GET    /classes/{id}                 — 클래스 상세 + 학생 목록
- POST   /classes/{id}/students        — 학생 추가
- DELETE /classes/{id}/students/{sid}   — 학생 제거
- GET    /classes/{id}/stats           — 클래스 학습 통계
- GET    /classes/student-detail/{sid}  — 학생 개인 학습 상세
- DELETE /classes/{id}                 — 클래스 삭제
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_active_user, require_roles
from app.db.session import get_db
from app.models.enums import Department, Role
from app.models.professor_class import ClassStudent, ProfessorClass
from app.models.user import User
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/classes", tags=["classes"])


# === Schemas ===
class ClassCreateRequest(BaseModel):
    class_name: str = Field(..., min_length=1, max_length=100)
    department: Department
    year: int = Field(..., ge=2020, le=2100)
    semester: int = Field(default=1, ge=1, le=2)


class ClassResponse(BaseModel):
    id: str
    class_name: str
    department: str
    year: int
    semester: int
    student_count: int
    created_at: str


class StudentInClass(BaseModel):
    id: str
    email: str
    name: str
    student_no: str | None
    department: str
    status: str
    joined_at: str


class ClassDetailResponse(BaseModel):
    id: str
    class_name: str
    department: str
    year: int
    semester: int
    students: list[StudentInClass]


class AddStudentRequest(BaseModel):
    student_id: str = Field(None)
    email: str = Field(None)
    student_no: str = Field(None)


# === 클래스 CRUD ===
@router.post("", status_code=status.HTTP_201_CREATED, summary="클래스 생성")
async def create_class(
    payload: ClassCreateRequest,
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ClassResponse:
    cls = ProfessorClass(
        professor_id=current_user.id,
        class_name=payload.class_name,
        department=payload.department,
        year=payload.year,
        semester=payload.semester,
    )
    db.add(cls)
    await db.flush()
    await db.refresh(cls)
    return ClassResponse(
        id=str(cls.id), class_name=cls.class_name,
        department=cls.department.value, year=cls.year, semester=cls.semester,
        student_count=0, created_at=cls.created_at.isoformat(),
    )


@router.get("", summary="내 클래스 목록 (학과장은 학과 전체)")
async def list_my_classes(
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[ClassResponse]:
    from app.models.enums import ProfessorRole

    # 학과장(DEPT_HEAD)은 같은 학과의 모든 교수 클래스를 볼 수 있음
    is_dept_head = (
        current_user.role == Role.PROFESSOR
        and current_user.professor_role == ProfessorRole.DEPT_HEAD
    )
    is_admin = current_user.role in (Role.ADMIN, Role.DEVELOPER)

    stmt = (
        select(
            ProfessorClass,
            func.count(ClassStudent.id).label("cnt"),
        )
        .outerjoin(ClassStudent, ClassStudent.class_id == ProfessorClass.id)
    )

    if is_dept_head:
        # 학과장: 같은 학과 모든 클래스
        stmt = stmt.where(ProfessorClass.department == current_user.department)
    elif is_admin:
        # 관리자/개발자: 전체
        pass
    else:
        # 일반 교수: 본인 클래스만
        stmt = stmt.where(ProfessorClass.professor_id == current_user.id)

    stmt = stmt.group_by(ProfessorClass.id).order_by(ProfessorClass.created_at.desc())
    rows = (await db.execute(stmt)).all()
    return [
        ClassResponse(
            id=str(r[0].id), class_name=r[0].class_name,
            department=r[0].department.value, year=r[0].year, semester=r[0].semester,
            student_count=int(r[1]), created_at=r[0].created_at.isoformat(),
        )
        for r in rows
    ]


@router.get("/{class_id}", summary="클래스 상세 + 학생 목록")
async def get_class_detail(
    class_id: uuid.UUID,
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ClassDetailResponse:
    from app.models.enums import ProfessorRole

    cls = await db.get(ProfessorClass, class_id, options=[selectinload(ProfessorClass.students)])
    if cls is None:
        raise HTTPException(status_code=404, detail="Class not found")

    # 접근 권한: 본인 클래스 OR 학과장(같은 학과) OR 관리자
    is_owner = cls.professor_id == current_user.id
    is_dept_head = (
        current_user.professor_role == ProfessorRole.DEPT_HEAD
        and cls.department == current_user.department
    )
    is_admin = current_user.role in (Role.ADMIN, Role.DEVELOPER)
    if not (is_owner or is_dept_head or is_admin):
        raise HTTPException(status_code=403, detail="Access denied")

    student_ids = [cs.student_id for cs in cls.students]
    students = []
    if student_ids:
        stmt = select(User).where(User.id.in_(student_ids))
        user_rows = (await db.execute(stmt)).scalars().all()
        user_map = {u.id: u for u in user_rows}
        for cs in cls.students:
            u = user_map.get(cs.student_id)
            if u:
                students.append(StudentInClass(
                    id=str(u.id), email=u.email, name=u.name,
                    student_no=u.student_no, department=u.department.value,
                    status=u.status.value, joined_at=cs.joined_at.isoformat(),
                ))

    return ClassDetailResponse(
        id=str(cls.id), class_name=cls.class_name,
        department=cls.department.value, year=cls.year, semester=cls.semester,
        students=students,
    )


# === 학생 추가/제거 ===
@router.post("/{class_id}/students", status_code=201, summary="클래스에 학생 추가")
async def add_student_to_class(
    class_id: uuid.UUID,
    payload: AddStudentRequest,
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    cls = await db.get(ProfessorClass, class_id)
    if cls is None or cls.professor_id != current_user.id:
        raise HTTPException(status_code=404, detail="Class not found")

    # 학생 찾기 (id, email, student_no 중 하나)
    student = None
    if payload.student_id:
        student = await db.get(User, uuid.UUID(payload.student_id))
    elif payload.email:
        student = await db.scalar(select(User).where(User.email == payload.email.lower()))
    elif payload.student_no:
        student = await db.scalar(select(User).where(User.student_no == payload.student_no))

    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    if student.role != Role.STUDENT:
        raise HTTPException(status_code=400, detail="User is not a student")

    # 중복 확인
    existing = await db.scalar(
        select(ClassStudent).where(
            ClassStudent.class_id == class_id,
            ClassStudent.student_id == student.id,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Student already in class")

    db.add(ClassStudent(class_id=class_id, student_id=student.id))
    await db.flush()
    return MessageResponse(message=f"{student.name} added to class")


@router.delete("/{class_id}/students/{student_id}", summary="클래스에서 학생 제거")
async def remove_student(
    class_id: uuid.UUID,
    student_id: uuid.UUID,
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    cls = await db.get(ProfessorClass, class_id)
    if cls is None or cls.professor_id != current_user.id:
        raise HTTPException(status_code=404, detail="Class not found")

    cs = await db.scalar(
        select(ClassStudent).where(
            ClassStudent.class_id == class_id,
            ClassStudent.student_id == student_id,
        )
    )
    if cs is None:
        raise HTTPException(status_code=404, detail="Student not in class")

    await db.delete(cs)
    await db.flush()
    return MessageResponse(message="Student removed")


@router.delete("/{class_id}", summary="클래스 삭제")
async def delete_class(
    class_id: uuid.UUID,
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    cls = await db.get(ProfessorClass, class_id)
    if cls is None or cls.professor_id != current_user.id:
        raise HTTPException(status_code=404, detail="Class not found")
    await db.delete(cls)
    await db.flush()
    return MessageResponse(message="Class deleted")


# === 클래스 통계 ===
@router.get("/{class_id}/stats", summary="클래스 학습 통계")
async def class_stats(
    class_id: uuid.UUID,
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from sqlalchemy import Float, case, cast
    from app.models.learning_history import LearningHistory

    cls = await db.get(ProfessorClass, class_id, options=[selectinload(ProfessorClass.students)])
    if cls is None or cls.professor_id != current_user.id:
        raise HTTPException(status_code=404, detail="Class not found")

    student_ids = [cs.student_id for cs in cls.students]
    if not student_ids:
        return {"class_name": cls.class_name, "student_count": 0, "stats": {}}

    # 학생별 정답률
    stmt = (
        select(
            LearningHistory.user_id,
            func.count(LearningHistory.id).label("total"),
            func.sum(case((LearningHistory.is_correct.is_(True), 1), else_=0)).label("correct"),
        )
        .where(LearningHistory.user_id.in_(student_ids))
        .group_by(LearningHistory.user_id)
    )
    rows = (await db.execute(stmt)).all()
    student_stats = []
    for r in rows:
        total = int(r.total)
        correct = int(r.correct)
        student_stats.append({
            "user_id": str(r.user_id),
            "total_attempts": total,
            "correct_count": correct,
            "accuracy": round(correct / total, 4) if total > 0 else 0.0,
        })

    avg_accuracy = (
        sum(s["accuracy"] for s in student_stats) / len(student_stats)
        if student_stats else 0.0
    )

    return {
        "class_name": cls.class_name,
        "student_count": len(student_ids),
        "active_students": len(student_stats),
        "avg_accuracy": round(avg_accuracy, 4),
        "student_stats": student_stats,
    }


# === 학생 개인 학습 상세 ===
@router.get("/student-detail/{student_id}", summary="학생 개인 학습 상세 (교수용)")
async def student_detail(
    student_id: uuid.UUID,
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.models.ai_profile import AIProfile
    from app.models.diagnostic import DiagnosticTest
    from app.services.stats_service import get_student_percentile

    student = await db.get(User, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")

    # 교수는 자기 학과만
    if current_user.role == Role.PROFESSOR and student.department != current_user.department:
        raise HTTPException(status_code=403, detail="Different department")

    result: dict = {
        "student": {
            "id": str(student.id), "name": student.name, "email": student.email,
            "student_no": student.student_no, "department": student.department.value,
        },
    }

    # 진단 결과
    diag = await db.scalar(select(DiagnosticTest).where(DiagnosticTest.user_id == student_id))
    if diag:
        result["diagnostic"] = {
            "total_score": diag.total_score,
            "section_scores": diag.section_scores,
            "weak_areas": diag.weak_areas,
            "level": diag.level.value if diag.level else None,
            "completed_at": diag.completed_at.isoformat() if diag.completed_at else None,
        }

    # AI 프로파일
    profile = await db.scalar(select(AIProfile).where(AIProfile.user_id == student_id))
    if profile:
        result["ai_profile"] = {
            "level": profile.level.value,
            "weak_priority": profile.weak_priority,
            "learning_path": profile.learning_path,
            "explanation_pref": profile.explanation_pref.value,
        }

    # 백분위
    percentile = await get_student_percentile(db, student_id, student.department)
    result["percentile"] = percentile

    return result
