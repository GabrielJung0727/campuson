"""OSCE 시험 + 루브릭 + 이벤트 라우터 (v0.8).

엔드포인트
---------
- POST   /osce/exams               — OSCE 시험 생성
- GET    /osce/exams               — OSCE 시험 목록
- GET    /osce/exams/{id}          — OSCE 시험 상세
- POST   /osce/rubrics             — 루브릭 생성
- GET    /osce/rubrics             — 루브릭 목록
- GET    /osce/rubrics/{id}        — 루브릭 상세
- POST   /osce/events              — 실습 이벤트 기록
- GET    /osce/events/{session_id} — 세션 이벤트 목록
- POST   /osce/events/detect       — 시간초과/순서오류 자동 탐지
- POST   /osce/replay              — 리플레이 저장
- GET    /osce/replay/{session_id} — 리플레이 조회
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, require_roles
from app.db.session import get_db
from app.models.enums import Department, Role
from app.models.user import User
from app.services import osce_service

router = APIRouter(prefix="/osce", tags=["osce"])


# === Schemas ===


class StationInput(BaseModel):
    scenario_id: str
    station_name: str | None = None
    time_limit_sec: int | None = None
    weight: float = 1.0
    instructions: str | None = None


class OSCEExamCreateRequest(BaseModel):
    department: Department
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    time_per_station_sec: int = Field(600, ge=60)
    transition_time_sec: int = Field(60, ge=0)
    stations: list[StationInput] = Field(..., min_length=1)


class RubricCreateRequest(BaseModel):
    department: Department
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    criteria: list[dict] = Field(..., min_length=1)
    total_score: int = Field(100, ge=1)
    scenario_id: uuid.UUID | None = None


class EventRecordRequest(BaseModel):
    session_id: uuid.UUID
    event_type: str = Field(..., pattern="^(timeout|order_error|critical_miss|danger|custom)$")
    timestamp_sec: float
    severity: str = Field("warning", pattern="^(info|warning|critical)$")
    event_data: dict | None = None


class TimingDetectRequest(BaseModel):
    checklist_items: list[dict]
    replay_steps: list[dict]
    time_limit_sec: int


class ReplaySaveRequest(BaseModel):
    session_id: uuid.UUID
    steps: list[dict]
    total_duration_sec: float
    video_url: str | None = None
    video_thumbnail_url: str | None = None


# === Endpoints ===


@router.post("/exams", status_code=status.HTTP_201_CREATED)
async def create_osce_exam(
    body: OSCEExamCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
):
    """OSCE 시험 생성 + 스테이션 일괄 등록."""
    result = await osce_service.create_osce_exam(
        db,
        department=body.department,
        name=body.name,
        description=body.description,
        time_per_station_sec=body.time_per_station_sec,
        transition_time_sec=body.transition_time_sec,
        stations=[s.model_dump() for s in body.stations],
        created_by=user.id,
        school_id=user.school_id,
    )
    await db.commit()
    return result


@router.get("/exams")
async def list_osce_exams(
    department: Department = Query(...),
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_active_user),
):
    """OSCE 시험 목록."""
    return await osce_service.list_osce_exams(db, department, active_only=active_only)


@router.get("/exams/{exam_id}")
async def get_osce_exam(
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_active_user),
):
    """OSCE 시험 상세."""
    result = await osce_service.get_osce_exam(db, exam_id)
    if not result:
        raise HTTPException(status_code=404, detail="OSCE exam not found")
    return result


@router.post("/rubrics", status_code=status.HTTP_201_CREATED)
async def create_rubric(
    body: RubricCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
):
    """루브릭 생성."""
    result = await osce_service.create_rubric(
        db, **body.model_dump(), created_by=user.id,
    )
    await db.commit()
    return result


@router.get("/rubrics")
async def list_rubrics(
    department: Department = Query(...),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_active_user),
):
    """루브릭 목록."""
    return await osce_service.list_rubrics(db, department)


@router.get("/rubrics/{rubric_id}")
async def get_rubric(
    rubric_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_active_user),
):
    """루브릭 상세."""
    result = await osce_service.get_rubric(db, rubric_id)
    if not result:
        raise HTTPException(status_code=404, detail="Rubric not found")
    return result


@router.post("/events", status_code=status.HTTP_201_CREATED)
async def record_event(
    body: EventRecordRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_active_user),
):
    """실습 이벤트 기록."""
    event = await osce_service.record_event(
        db, body.session_id,
        event_type=body.event_type,
        timestamp_sec=body.timestamp_sec,
        severity=body.severity,
        event_data=body.event_data,
    )
    await db.commit()
    return {"id": str(event.id), "event_type": event.event_type}


@router.get("/events/{session_id}")
async def get_session_events(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_active_user),
):
    """세션 이벤트 목록."""
    return await osce_service.get_session_events(db, session_id)


@router.post("/events/detect")
async def detect_timing_issues(
    body: TimingDetectRequest,
    _user: User = Depends(get_current_active_user),
):
    """시간초과/순서오류 자동 탐지 (DB 미접근, 순수 계산)."""
    return osce_service.detect_timing_issues(
        body.checklist_items, body.replay_steps, body.time_limit_sec,
    )


@router.post("/replay", status_code=status.HTTP_201_CREATED)
async def save_replay(
    body: ReplaySaveRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_active_user),
):
    """리플레이 데이터 저장."""
    replay = await osce_service.save_replay(
        db, body.session_id,
        steps=body.steps,
        total_duration_sec=body.total_duration_sec,
        video_url=body.video_url,
        video_thumbnail_url=body.video_thumbnail_url,
    )
    await db.commit()
    return {"session_id": str(replay.session_id)}


@router.get("/replay/{session_id}")
async def get_replay(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_active_user),
):
    """리플레이 조회."""
    result = await osce_service.get_replay(db, session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Replay not found")
    return result
