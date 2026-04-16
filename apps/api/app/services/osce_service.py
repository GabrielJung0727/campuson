"""OSCE 스테이션 + 루브릭 + 이벤트 서비스 (v0.8).

- OSCE 시험 CRUD
- 루브릭 관리
- 실습 이벤트 기록 (시간초과/순서오류/위험행위)
- 리플레이 데이터 저장/조회
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import Department
from app.models.osce import (
    OSCEExam,
    OSCEStation,
    PracticumEvent,
    PracticumReplay,
    PracticumRubric,
)
from app.models.practicum import PracticumScenario, PracticumSession

logger = logging.getLogger(__name__)


# === OSCE Exam CRUD ===


async def create_osce_exam(
    db: AsyncSession,
    *,
    department: Department,
    name: str,
    description: str | None = None,
    time_per_station_sec: int = 600,
    transition_time_sec: int = 60,
    stations: list[dict],
    created_by: uuid.UUID | None = None,
    school_id: uuid.UUID | None = None,
) -> dict:
    """OSCE 시험 생성 + 스테이션 일괄 등록.

    stations: [{scenario_id, station_name, time_limit_sec, weight, instructions}]
    """
    exam = OSCEExam(
        school_id=school_id,
        department=department,
        name=name,
        description=description,
        total_stations=len(stations),
        time_per_station_sec=time_per_station_sec,
        transition_time_sec=transition_time_sec,
        created_by=created_by,
    )
    db.add(exam)
    await db.flush()

    for i, s in enumerate(stations, start=1):
        station = OSCEStation(
            exam_id=exam.id,
            scenario_id=uuid.UUID(s["scenario_id"]) if isinstance(s["scenario_id"], str) else s["scenario_id"],
            station_order=i,
            station_name=s.get("station_name", f"Station {i}"),
            time_limit_sec=s.get("time_limit_sec"),
            weight=s.get("weight", 1.0),
            instructions=s.get("instructions"),
        )
        db.add(station)

    await db.flush()
    await db.refresh(exam)
    return await _exam_to_dict(db, exam)


async def get_osce_exam(db: AsyncSession, exam_id: uuid.UUID) -> dict | None:
    """OSCE 시험 상세 조회 (스테이션 ��함)."""
    exam = await db.scalar(
        select(OSCEExam)
        .options(selectinload(OSCEExam.stations))
        .where(OSCEExam.id == exam_id)
    )
    if not exam:
        return None
    return await _exam_to_dict(db, exam)


async def list_osce_exams(
    db: AsyncSession, department: Department, *, active_only: bool = True,
) -> list[dict]:
    """OSCE 시험 목록."""
    stmt = select(OSCEExam).where(OSCEExam.department == department)
    if active_only:
        stmt = stmt.where(OSCEExam.is_active.is_(True))
    stmt = stmt.order_by(OSCEExam.created_at.desc())

    exams = list((await db.execute(stmt)).scalars().all())
    return [
        {
            "id": str(e.id),
            "name": e.name,
            "department": e.department.value,
            "total_stations": e.total_stations,
            "time_per_station_sec": e.time_per_station_sec,
            "is_active": e.is_active,
            "created_at": e.created_at.isoformat(),
        }
        for e in exams
    ]


async def _exam_to_dict(db: AsyncSession, exam: OSCEExam) -> dict:
    """OSCE 시험을 dict로 변환."""
    stations = list((await db.execute(
        select(OSCEStation)
        .where(OSCEStation.exam_id == exam.id)
        .order_by(OSCEStation.station_order)
    )).scalars().all())

    return {
        "id": str(exam.id),
        "name": exam.name,
        "description": exam.description,
        "department": exam.department.value,
        "total_stations": exam.total_stations,
        "time_per_station_sec": exam.time_per_station_sec,
        "transition_time_sec": exam.transition_time_sec,
        "is_active": exam.is_active,
        "stations": [
            {
                "id": str(s.id),
                "station_order": s.station_order,
                "station_name": s.station_name,
                "scenario_id": str(s.scenario_id),
                "time_limit_sec": s.time_limit_sec,
                "weight": s.weight,
                "instructions": s.instructions,
            }
            for s in stations
        ],
    }


# === Rubric CRUD ===


async def create_rubric(
    db: AsyncSession,
    *,
    department: Department,
    name: str,
    criteria: list[dict],
    total_score: int = 100,
    description: str | None = None,
    scenario_id: uuid.UUID | None = None,
    created_by: uuid.UUID | None = None,
) -> dict:
    """루브릭 템플릿 생성."""
    rubric = PracticumRubric(
        department=department,
        name=name,
        description=description,
        criteria=criteria,
        total_score=total_score,
        scenario_id=scenario_id,
        created_by=created_by,
    )
    db.add(rubric)
    await db.flush()
    await db.refresh(rubric)
    return _rubric_to_dict(rubric)


async def list_rubrics(
    db: AsyncSession, department: Department,
) -> list[dict]:
    """루브릭 목록."""
    rows = list((await db.execute(
        select(PracticumRubric)
        .where(PracticumRubric.department == department)
        .order_by(PracticumRubric.created_at.desc())
    )).scalars().all())
    return [_rubric_to_dict(r) for r in rows]


async def get_rubric(db: AsyncSession, rubric_id: uuid.UUID) -> dict | None:
    """루브릭 상세."""
    r = await db.get(PracticumRubric, rubric_id)
    return _rubric_to_dict(r) if r else None


def _rubric_to_dict(r: PracticumRubric) -> dict:
    return {
        "id": str(r.id),
        "name": r.name,
        "description": r.description,
        "department": r.department.value,
        "criteria": r.criteria,
        "total_score": r.total_score,
        "scenario_id": str(r.scenario_id) if r.scenario_id else None,
        "created_at": r.created_at.isoformat(),
    }


# === Practicum Events ===


async def record_event(
    db: AsyncSession,
    session_id: uuid.UUID,
    *,
    event_type: str,
    timestamp_sec: float,
    severity: str = "warning",
    event_data: dict | None = None,
) -> PracticumEvent:
    """실습 이벤트 기록."""
    event = PracticumEvent(
        session_id=session_id,
        event_type=event_type,
        timestamp_sec=timestamp_sec,
        severity=severity,
        event_data=event_data,
    )
    db.add(event)
    await db.flush()
    return event


async def get_session_events(
    db: AsyncSession, session_id: uuid.UUID,
) -> list[dict]:
    """세션의 이벤트 목록."""
    rows = list((await db.execute(
        select(PracticumEvent)
        .where(PracticumEvent.session_id == session_id)
        .order_by(PracticumEvent.timestamp_sec)
    )).scalars().all())
    return [
        {
            "id": str(e.id),
            "event_type": e.event_type,
            "timestamp_sec": e.timestamp_sec,
            "severity": e.severity,
            "event_data": e.event_data,
            "created_at": e.created_at.isoformat(),
        }
        for e in rows
    ]


def detect_timing_issues(
    checklist_items: list[dict],
    replay_steps: list[dict],
    time_limit_sec: int,
) -> list[dict]:
    """시간 초과 / 순서 오류 자동 탐지.

    Returns list of detected events.
    """
    events = []

    # 순서 체크 — checklist_items의 순서와 실제 수행 순서 비교
    expected_order = [item["id"] for item in checklist_items]
    actual_order = [step["item_id"] for step in replay_steps if step.get("action") == "check"]

    for i, (expected, actual) in enumerate(zip(expected_order, actual_order)):
        if expected != actual:
            events.append({
                "event_type": "order_error",
                "severity": "warning",
                "timestamp_sec": replay_steps[i]["timestamp_sec"] if i < len(replay_steps) else 0,
                "event_data": {
                    "step": i + 1,
                    "expected_item": expected,
                    "actual_item": actual,
                },
            })

    # 시간 초과 체크
    if replay_steps:
        total_time = replay_steps[-1].get("timestamp_sec", 0)
        if total_time > time_limit_sec:
            events.append({
                "event_type": "timeout",
                "severity": "critical",
                "timestamp_sec": total_time,
                "event_data": {
                    "time_limit_sec": time_limit_sec,
                    "actual_sec": total_time,
                    "overtime_sec": total_time - time_limit_sec,
                },
            })

    return events


# === Replay ===


async def save_replay(
    db: AsyncSession,
    session_id: uuid.UUID,
    *,
    steps: list[dict],
    total_duration_sec: float,
    video_url: str | None = None,
    video_thumbnail_url: str | None = None,
) -> PracticumReplay:
    """리플레이 데이터 저장."""
    replay = PracticumReplay(
        session_id=session_id,
        total_duration_sec=total_duration_sec,
        steps=steps,
        video_url=video_url,
        video_thumbnail_url=video_thumbnail_url,
    )
    db.add(replay)
    await db.flush()
    return replay


async def get_replay(
    db: AsyncSession, session_id: uuid.UUID,
) -> dict | None:
    """리플레이 조회."""
    replay = await db.scalar(
        select(PracticumReplay).where(PracticumReplay.session_id == session_id)
    )
    if not replay:
        return None
    return {
        "session_id": str(replay.session_id),
        "total_duration_sec": replay.total_duration_sec,
        "steps": replay.steps,
        "video_url": replay.video_url,
        "video_thumbnail_url": replay.video_thumbnail_url,
        "created_at": replay.created_at.isoformat(),
    }
