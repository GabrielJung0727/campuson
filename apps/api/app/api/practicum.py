"""실습 평가 시스템 API.

v0.4 엔드포인트
--------------
시나리오:
- GET    /practicum/scenarios          — 시나리오 목록 (학과별 필터)
- POST   /practicum/scenarios          — 시나리오 생성 (교수/관리자)
- GET    /practicum/scenarios/{id}     — 시나리오 상세
- DELETE /practicum/scenarios/{id}     — 시나리오 삭제

세션:
- POST   /practicum/sessions           — 세션 시작 (학생)
- GET    /practicum/sessions           — 세션 목록 (본인/학과)
- GET    /practicum/sessions/{id}      — 세션 상세
- PATCH  /practicum/sessions/{id}      — 체크리스트 결과 제출
- POST   /practicum/sessions/{id}/feedback  — AI 피드백 생성
- PATCH  /practicum/sessions/{id}/review    — 교수 리뷰

통계:
- GET    /practicum/stats/student/{id} — 학생 실습 통계
"""

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_active_user, require_roles
from app.db.session import get_db
from app.models.enums import (
    Department,
    EvalGrade,
    EvalStatus,
    PracticumCategory,
    PracticumMode,
    Role,
)
from app.models.practicum import PracticumScenario, PracticumSession
from app.models.user import User
from app.schemas.common import MessageResponse
from app.services.practicum_service import (
    ai_evaluate_checklist,
    calculate_score,
    generate_feedback,
    generate_join_code,
    get_student_practicum_stats,
)

router = APIRouter(tags=["practicum"])


# ── Schemas ──


class ChecklistItemSchema(BaseModel):
    id: str
    label: str
    points: int = Field(ge=0)
    is_critical: bool = False


class ScenarioCreateRequest(BaseModel):
    name: str = Field(..., max_length=200)
    description: str | None = None
    department: Department
    category: PracticumCategory
    checklist_items: list[ChecklistItemSchema]
    total_points: int = Field(ge=1)


class ChecklistResultSchema(BaseModel):
    item_id: str
    status: Literal["success", "partial", "fail", "danger"]
    points_earned: int = Field(ge=0)


class SessionSubmitRequest(BaseModel):
    checklist_results: list[ChecklistResultSchema]


class ReviewRequest(BaseModel):
    professor_comment: str = ""
    grade_override: EvalGrade | None = None


class VideoSubmitRequest(BaseModel):
    video_description: str = Field(..., min_length=10, max_length=5000)
    video_url: str | None = None


class LiveSessionCheckRequest(BaseModel):
    """교수가 실시간으로 체크리스트 항목을 체크."""
    checklist_results: list[ChecklistResultSchema]


# ── 시나리오 CRUD ──


@router.get("/practicum/scenarios", summary="시나리오 목록")
async def list_scenarios(
    department: Department | None = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    stmt = select(PracticumScenario).where(PracticumScenario.is_active.is_(True))
    if department:
        stmt = stmt.where(PracticumScenario.department == department)
    elif current_user.role == Role.STUDENT:
        stmt = stmt.where(PracticumScenario.department == current_user.department)
    stmt = stmt.order_by(PracticumScenario.created_at.desc())
    rows = list((await db.execute(stmt)).scalars().all())
    return [_scenario_dict(s) for s in rows]


@router.post("/practicum/scenarios", status_code=201, summary="시나리오 생성")
async def create_scenario(
    payload: ScenarioCreateRequest,
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    scenario = PracticumScenario(
        department=payload.department,
        category=payload.category,
        name=payload.name,
        description=payload.description,
        checklist_items=[item.model_dump() for item in payload.checklist_items],
        total_points=payload.total_points,
        created_by=current_user.id,
    )
    db.add(scenario)
    await db.flush()
    await db.refresh(scenario)
    return _scenario_dict(scenario)


@router.get("/practicum/scenarios/{scenario_id}", summary="시나리오 상세")
async def get_scenario(
    scenario_id: uuid.UUID,
    _user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    s = await db.get(PracticumScenario, scenario_id)
    if not s:
        raise HTTPException(404, "Scenario not found")
    return _scenario_dict(s)


@router.delete("/practicum/scenarios/{scenario_id}", summary="시나리오 삭제")
async def delete_scenario(
    scenario_id: uuid.UUID,
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    s = await db.get(PracticumScenario, scenario_id)
    if not s:
        raise HTTPException(404, "Scenario not found")
    s.is_active = False
    await db.flush()
    return MessageResponse(message="Deleted")


# ── 세션 ──


@router.post("/practicum/sessions", status_code=201, summary="세션 시작")
async def create_session(
    scenario_id: str = Query(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    scenario = await db.get(PracticumScenario, uuid.UUID(scenario_id))
    if not scenario or not scenario.is_active:
        raise HTTPException(404, "Scenario not found or inactive")
    session = PracticumSession(
        student_id=current_user.id,
        scenario_id=scenario.id,
        status=EvalStatus.DRAFT,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return _session_dict(session, scenario)


@router.get("/practicum/sessions", summary="세션 목록")
async def list_sessions(
    status_filter: EvalStatus | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    stmt = select(PracticumSession).options(selectinload(PracticumSession.scenario))

    if current_user.role == Role.STUDENT:
        stmt = stmt.where(PracticumSession.student_id == current_user.id)
    elif current_user.role == Role.PROFESSOR:
        # 본인 학과 학생 세션만
        dept_students = select(User.id).where(User.department == current_user.department)
        stmt = stmt.where(PracticumSession.student_id.in_(dept_students))
    # ADMIN/DEVELOPER는 전체

    if status_filter:
        stmt = stmt.where(PracticumSession.status == status_filter)
    stmt = stmt.order_by(PracticumSession.created_at.desc()).limit(50)

    rows = list((await db.execute(stmt)).scalars().all())
    return [_session_dict(s, s.scenario) for s in rows]


@router.get("/practicum/sessions/{session_id}", summary="세션 상세")
async def get_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(PracticumSession)
        .options(selectinload(PracticumSession.scenario))
        .where(PracticumSession.id == session_id)
    )
    session = (await db.execute(stmt)).scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    # 권한 체크
    if current_user.role == Role.STUDENT and session.student_id != current_user.id:
        raise HTTPException(403, "Access denied")

    # 학생 이름 포함
    student = await db.get(User, session.student_id)
    result = _session_dict(session, session.scenario)
    result["student_name"] = student.name if student else ""
    result["student_email"] = student.email if student else ""
    return result


@router.patch("/practicum/sessions/{session_id}", summary="체크리스트 결과 제출")
async def submit_session(
    session_id: uuid.UUID,
    payload: SessionSubmitRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(PracticumSession)
        .options(selectinload(PracticumSession.scenario))
        .where(PracticumSession.id == session_id)
    )
    session = (await db.execute(stmt)).scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")
    if session.student_id != current_user.id:
        raise HTTPException(403, "Not your session")
    if session.status != EvalStatus.DRAFT:
        raise HTTPException(400, "Already submitted")

    results = [r.model_dump() for r in payload.checklist_results]
    score, grade, _ = calculate_score(
        session.scenario.checklist_items, results, session.scenario.total_points,
    )

    session.checklist_results = results
    session.total_score = score
    session.grade = grade
    session.status = EvalStatus.SUBMITTED
    session.evaluated_at = datetime.now(UTC)
    await db.flush()

    return _session_dict(session, session.scenario)


@router.post("/practicum/sessions/{session_id}/feedback", summary="AI 피드백 생성")
async def generate_session_feedback(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(PracticumSession)
        .options(selectinload(PracticumSession.scenario))
        .where(PracticumSession.id == session_id)
    )
    session = (await db.execute(stmt)).scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")
    if session.status == EvalStatus.DRAFT:
        raise HTTPException(400, "Submit checklist first")

    feedback = await generate_feedback(
        session.scenario, session.checklist_results or [],
        session.total_score or 0, session.grade or EvalGrade.FAIL,
    )
    session.ai_feedback = feedback
    await db.flush()

    return _session_dict(session, session.scenario)


@router.patch("/practicum/sessions/{session_id}/review", summary="교수 리뷰")
async def review_session(
    session_id: uuid.UUID,
    payload: ReviewRequest,
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(PracticumSession)
        .options(selectinload(PracticumSession.scenario))
        .where(PracticumSession.id == session_id)
    )
    session = (await db.execute(stmt)).scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    session.professor_comment = payload.professor_comment
    session.reviewed_by = current_user.id
    session.status = EvalStatus.REVIEWED
    if payload.grade_override:
        session.grade = payload.grade_override
    await db.flush()

    return _session_dict(session, session.scenario)


# ── 실시간 세션 (LIVE) ──


@router.post("/practicum/sessions/live", status_code=201, summary="교수 실시간 세션 생성")
async def create_live_session(
    scenario_id: str = Query(...),
    student_email: str | None = Query(default=None),
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    scenario = await db.get(PracticumScenario, uuid.UUID(scenario_id))
    if not scenario or not scenario.is_active:
        raise HTTPException(404, "Scenario not found")

    code = generate_join_code()

    # 학생 지정이 없으면 빈 세션 (학생이 코드로 참여)
    student_id = None
    if student_email:
        student = await db.scalar(select(User).where(User.email == student_email))
        if student:
            student_id = student.id

    session = PracticumSession(
        student_id=student_id or current_user.id,  # 임시로 교수 ID, 학생 참여 시 교체
        scenario_id=scenario.id,
        mode=PracticumMode.LIVE,
        status=EvalStatus.DRAFT,
        join_code=code,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    result = _session_dict(session, scenario)
    result["join_code"] = code
    return result


@router.post("/practicum/sessions/join", summary="학생 참여코드 입력")
async def join_live_session(
    join_code: str = Query(..., min_length=4, max_length=6),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(PracticumSession)
        .options(selectinload(PracticumSession.scenario))
        .where(
            PracticumSession.join_code == join_code,
            PracticumSession.mode == PracticumMode.LIVE,
            PracticumSession.status == EvalStatus.DRAFT,
        )
    )
    session = (await db.execute(stmt)).scalar_one_or_none()
    if not session:
        raise HTTPException(404, "유효하지 않은 참여 코드입니다.")

    session.student_id = current_user.id
    await db.flush()

    return _session_dict(session, session.scenario)


@router.patch("/practicum/sessions/{session_id}/live-check", summary="교수 실시간 체크")
async def live_check_session(
    session_id: uuid.UUID,
    payload: LiveSessionCheckRequest,
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """교수가 실시간으로 체크리스트를 체크. 학생 화면에 폴링으로 반영."""
    stmt = (
        select(PracticumSession)
        .options(selectinload(PracticumSession.scenario))
        .where(PracticumSession.id == session_id)
    )
    session = (await db.execute(stmt)).scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    results = [r.model_dump() for r in payload.checklist_results]
    session.checklist_results = results

    # 교수가 전체 항목 체크 완료 시 자동 점수 산출
    if len(results) >= len(session.scenario.checklist_items):
        score, grade, _ = calculate_score(
            session.scenario.checklist_items, results, session.scenario.total_points,
        )
        session.total_score = score
        session.grade = grade
        session.status = EvalStatus.SUBMITTED
        session.evaluated_at = datetime.now(UTC)
        session.reviewed_by = current_user.id

    await db.flush()
    return _session_dict(session, session.scenario)


# ── 영상 업로드 + AI 평가 ──


@router.post("/practicum/sessions/video", status_code=201, summary="영상 모드 세션 생성")
async def create_video_session(
    scenario_id: str = Query(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    scenario = await db.get(PracticumScenario, uuid.UUID(scenario_id))
    if not scenario or not scenario.is_active:
        raise HTTPException(404, "Scenario not found")

    session = PracticumSession(
        student_id=current_user.id,
        scenario_id=scenario.id,
        mode=PracticumMode.VIDEO,
        status=EvalStatus.DRAFT,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return _session_dict(session, scenario)


@router.post("/practicum/sessions/{session_id}/ai-evaluate", summary="AI 자동 평가")
async def ai_evaluate_session(
    session_id: uuid.UUID,
    payload: VideoSubmitRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """학생 영상 설명을 LLM에 보내서 체크리스트 자동 판정 + 피드백 생성."""
    stmt = (
        select(PracticumSession)
        .options(selectinload(PracticumSession.scenario))
        .where(PracticumSession.id == session_id)
    )
    session = (await db.execute(stmt)).scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")
    if session.student_id != current_user.id:
        raise HTTPException(403, "Not your session")

    session.video_description = payload.video_description
    if payload.video_url:
        session.video_url = payload.video_url

    # AI 체크리스트 판정
    results = await ai_evaluate_checklist(session.scenario, payload.video_description)
    score, grade, _ = calculate_score(
        session.scenario.checklist_items, results, session.scenario.total_points,
    )

    session.checklist_results = results
    session.total_score = score
    session.grade = grade
    session.status = EvalStatus.SUBMITTED
    session.evaluated_at = datetime.now(UTC)

    # AI 피드백도 바로 생성
    feedback = await generate_feedback(session.scenario, results, score, grade)
    session.ai_feedback = feedback

    await db.flush()
    return _session_dict(session, session.scenario)


# ── 통계 ──


@router.get("/practicum/stats/student/{student_id}", summary="학생 실습 통계")
async def student_stats(
    student_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # 본인이거나 교수/관리자
    if current_user.role == Role.STUDENT and current_user.id != student_id:
        raise HTTPException(403, "Access denied")
    return await get_student_practicum_stats(db, student_id)


# ── Helpers ──


def _scenario_dict(s: PracticumScenario) -> dict:
    return {
        "id": str(s.id),
        "department": s.department.value,
        "department_label": s.department.label_ko,
        "category": s.category.value,
        "category_label": s.category.label_ko,
        "name": s.name,
        "description": s.description,
        "checklist_items": s.checklist_items,
        "total_points": s.total_points,
        "is_active": s.is_active,
        "created_at": s.created_at.isoformat(),
    }


def _session_dict(s: PracticumSession, scenario: PracticumScenario | None = None) -> dict:
    d: dict = {
        "id": str(s.id),
        "student_id": str(s.student_id),
        "scenario_id": str(s.scenario_id),
        "mode": s.mode.value if s.mode else "SELF",
        "status": s.status.value,
        "join_code": s.join_code,
        "video_url": s.video_url,
        "video_description": s.video_description,
        "checklist_results": s.checklist_results,
        "total_score": s.total_score,
        "grade": s.grade.value if s.grade else None,
        "grade_label": s.grade.label_ko if s.grade else None,
        "ai_feedback": s.ai_feedback,
        "professor_comment": s.professor_comment,
        "evaluated_at": s.evaluated_at.isoformat() if s.evaluated_at else None,
        "reviewed_by": str(s.reviewed_by) if s.reviewed_by else None,
        "created_at": s.created_at.isoformat(),
    }
    if scenario:
        d["scenario_name"] = scenario.name
        d["scenario_category"] = scenario.category.value
        d["scenario_category_label"] = scenario.category.label_ko
        d["scenario_department"] = scenario.department.value
        d["total_points"] = scenario.total_points
        d["checklist_items"] = scenario.checklist_items
    return d
