"""관리자 운영 대시보드 서비스 (v0.6).

10개 메트릭 패널 데이터를 집계:
1. 학과별 활성 사용자 수
2. 주간 학습량 지표
3. 진단 테스트 완료율
4. AI 사용량/비용 표시
5. 과목별 정답률
6. 교수별 과제 수행률
7. 학생 이탈 위험군 탐지
8. 지식베이스 문서 최신성
9. 실습 시험 참여율
10. 장애/실패율 모니터
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import case, desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_request_log import AIRequestLog
from app.models.assignment import Assignment, AssignmentSubmission
from app.models.diagnostic import DiagnosticTest
from app.models.enums import Department, Role, UserStatus
from app.models.kb_document import KBDocument
from app.models.learning_history import LearningHistory
from app.models.practicum import PracticumSession
from app.models.user import User

logger = logging.getLogger(__name__)


async def get_active_users_by_department(db: AsyncSession) -> list[dict]:
    """1. 학과별 활성 사용자 수."""
    result = await db.execute(
        select(
            User.department,
            User.role,
            func.count().label("count"),
        )
        .where(User.status == UserStatus.ACTIVE)
        .group_by(User.department, User.role)
        .order_by(User.department, User.role)
    )
    rows = result.all()

    dept_data: dict[str, dict] = {}
    for row in rows:
        dept = row.department.value if row.department else "UNKNOWN"
        if dept not in dept_data:
            dept_data[dept] = {"department": dept, "total": 0, "by_role": {}}
        dept_data[dept]["by_role"][row.role.value] = row.count
        dept_data[dept]["total"] += row.count

    return list(dept_data.values())


async def get_weekly_learning_metrics(db: AsyncSession, weeks: int = 4) -> list[dict]:
    """2. 주간 학습량 지표 (최근 N주)."""
    results = []
    now = datetime.now(timezone.utc)

    for i in range(weeks):
        week_end = now - timedelta(weeks=i)
        week_start = week_end - timedelta(weeks=1)

        row = (await db.execute(
            select(
                func.count().label("total_attempts"),
                func.sum(func.cast(LearningHistory.is_correct, type(1))).label("correct"),
                func.count(func.distinct(LearningHistory.user_id)).label("active_students"),
            )
            .where(LearningHistory.created_at.between(week_start, week_end))
        )).one()

        total = row.total_attempts or 0
        correct = int(row.correct or 0)

        results.append({
            "week_start": week_start.date().isoformat(),
            "week_end": week_end.date().isoformat(),
            "total_attempts": total,
            "correct_count": correct,
            "accuracy": correct / total if total else 0,
            "active_students": row.active_students or 0,
        })

    return list(reversed(results))


async def get_diagnostic_completion_rate(db: AsyncSession) -> dict:
    """3. 진단 테스트 완료율."""
    total_students = (await db.execute(
        select(func.count()).where(User.role == Role.STUDENT, User.status == UserStatus.ACTIVE)
    )).scalar_one()

    completed = (await db.execute(
        select(func.count()).where(DiagnosticTest.completed_at.isnot(None))
    )).scalar_one()

    return {
        "total_students": total_students,
        "completed": completed,
        "completion_rate": completed / total_students if total_students else 0,
    }


async def get_ai_usage_summary(db: AsyncSession, days: int = 30) -> dict:
    """4. AI 사용량/비용 표시."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = (await db.execute(
        select(
            func.count().label("total_calls"),
            func.sum(func.cast(AIRequestLog.success, type(1))).label("success"),
            func.sum(AIRequestLog.input_tokens).label("input_tokens"),
            func.sum(AIRequestLog.output_tokens).label("output_tokens"),
            func.avg(AIRequestLog.latency_ms).label("avg_latency"),
        )
        .where(AIRequestLog.created_at >= since)
    )).one()

    from app.services.cost_service import estimate_cost
    in_tok = int(result.input_tokens or 0)
    out_tok = int(result.output_tokens or 0)
    cost = estimate_cost("ANTHROPIC", settings.llm_model, in_tok, out_tok)

    from app.core.config import settings
    return {
        "period_days": days,
        "total_calls": result.total_calls or 0,
        "success_rate": (int(result.success or 0) / result.total_calls) if result.total_calls else 0,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "total_tokens": in_tok + out_tok,
        "estimated_cost_usd": round(cost, 4),
        "avg_latency_ms": int(result.avg_latency or 0),
    }


async def get_accuracy_by_subject(db: AsyncSession) -> list[dict]:
    """5. 과목별 정답률."""
    from app.models.question import Question

    result = await db.execute(
        select(
            Question.subject,
            Question.department,
            func.count(LearningHistory.id).label("attempts"),
            func.sum(func.cast(LearningHistory.is_correct, type(1))).label("correct"),
        )
        .join(Question, LearningHistory.question_id == Question.id)
        .group_by(Question.subject, Question.department)
        .having(func.count(LearningHistory.id) >= 5)
        .order_by(desc("attempts"))
    )
    rows = result.all()

    return [
        {
            "subject": r.subject,
            "department": r.department.value if r.department else None,
            "attempts": r.attempts,
            "correct": int(r.correct or 0),
            "accuracy": int(r.correct or 0) / r.attempts if r.attempts else 0,
        }
        for r in rows
    ]


async def get_assignment_completion_by_professor(db: AsyncSession) -> list[dict]:
    """6. 교수별 과제 수행률."""
    result = await db.execute(
        select(
            User.name.label("professor_name"),
            User.department,
            func.count(func.distinct(Assignment.id)).label("total_assignments"),
            func.count(AssignmentSubmission.id).label("total_submissions"),
        )
        .join(Assignment, Assignment.professor_id == User.id)
        .outerjoin(AssignmentSubmission, AssignmentSubmission.assignment_id == Assignment.id)
        .where(User.role == Role.PROFESSOR)
        .group_by(User.id, User.name, User.department)
        .order_by(desc("total_assignments"))
    )
    rows = result.all()

    return [
        {
            "professor_name": r.professor_name,
            "department": r.department.value if r.department else None,
            "total_assignments": r.total_assignments,
            "total_submissions": r.total_submissions,
        }
        for r in rows
    ]


async def get_at_risk_students(db: AsyncSession, days: int = 14) -> list[dict]:
    """7. 학생 이탈 위험군 탐지.

    기준: 최근 N일간 학습 활동 없는 활성 학생
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # 활성 학생 중 최근 활동이 없는 학생
    active_students = select(User.id).where(
        User.role == Role.STUDENT, User.status == UserStatus.ACTIVE
    ).subquery()

    recent_active = select(func.distinct(LearningHistory.user_id)).where(
        LearningHistory.created_at >= cutoff
    ).subquery()

    result = await db.execute(
        select(User.id, User.name, User.email, User.department)
        .where(
            User.id.in_(select(active_students.c.id)),
            User.id.notin_(select(recent_active.c.user_id)),
        )
        .limit(50)
    )
    rows = result.all()

    return [
        {
            "user_id": str(r.id),
            "name": r.name,
            "email": r.email,
            "department": r.department.value if r.department else None,
            "inactive_days": days,
        }
        for r in rows
    ]


async def get_kb_freshness(db: AsyncSession) -> list[dict]:
    """8. 지식베이스 문서 최신성."""
    result = await db.execute(
        select(
            KBDocument.department,
            KBDocument.review_status,
            func.count().label("doc_count"),
            func.max(KBDocument.updated_at).label("latest_update"),
            func.min(KBDocument.updated_at).label("oldest_update"),
        )
        .group_by(KBDocument.department, KBDocument.review_status)
        .order_by(KBDocument.department, KBDocument.review_status)
    )
    rows = result.all()

    return [
        {
            "department": r.department.value if r.department else None,
            "review_status": r.review_status.value if r.review_status else None,
            "doc_count": r.doc_count,
            "latest_update": r.latest_update.isoformat() if r.latest_update else None,
            "oldest_update": r.oldest_update.isoformat() if r.oldest_update else None,
        }
        for r in rows
    ]


async def get_practicum_participation(db: AsyncSession, days: int = 30) -> dict:
    """9. 실습 시험 참여율."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    total_students = (await db.execute(
        select(func.count()).where(User.role == Role.STUDENT, User.status == UserStatus.ACTIVE)
    )).scalar_one()

    participated = (await db.execute(
        select(func.count(func.distinct(PracticumSession.student_id)))
        .where(PracticumSession.created_at >= since)
    )).scalar_one()

    total_sessions = (await db.execute(
        select(func.count()).where(PracticumSession.created_at >= since)
    )).scalar_one()

    return {
        "period_days": days,
        "total_students": total_students,
        "participated": participated,
        "participation_rate": participated / total_students if total_students else 0,
        "total_sessions": total_sessions,
    }


async def get_failure_rates(db: AsyncSession, hours: int = 24) -> dict:
    """10. 장애/실패율 모니터."""
    from app.models.audit_log import AuditLog

    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    # API 에러율
    api_result = (await db.execute(
        select(
            func.count().label("total"),
            func.sum(case((AuditLog.status_code >= 500, 1), else_=0)).label("server_errors"),
            func.sum(case((AuditLog.status_code >= 400, 1), else_=0)).label("client_errors"),
            func.avg(AuditLog.latency_ms).label("avg_latency"),
        )
        .where(AuditLog.created_at >= since)
    )).one()

    # LLM 실패율
    llm_result = (await db.execute(
        select(
            func.count().label("total"),
            func.sum(func.cast(AIRequestLog.success, type(1))).label("success"),
        )
        .where(AIRequestLog.created_at >= since)
    )).one()

    api_total = api_result.total or 0
    llm_total = llm_result.total or 0

    return {
        "period_hours": hours,
        "api": {
            "total_requests": api_total,
            "server_errors": int(api_result.server_errors or 0),
            "client_errors": int(api_result.client_errors or 0),
            "error_rate": int(api_result.server_errors or 0) / api_total if api_total else 0,
            "avg_latency_ms": int(api_result.avg_latency or 0),
        },
        "llm": {
            "total_calls": llm_total,
            "success_count": int(llm_result.success or 0),
            "failure_rate": (llm_total - int(llm_result.success or 0)) / llm_total if llm_total else 0,
        },
    }


async def get_full_dashboard(db: AsyncSession) -> dict:
    """전체 운영 대시보드 데이터."""
    return {
        "active_users": await get_active_users_by_department(db),
        "weekly_learning": await get_weekly_learning_metrics(db),
        "diagnostic_completion": await get_diagnostic_completion_rate(db),
        "ai_usage": await get_ai_usage_summary(db),
        "accuracy_by_subject": await get_accuracy_by_subject(db),
        "assignment_completion": await get_assignment_completion_by_professor(db),
        "at_risk_students": await get_at_risk_students(db),
        "kb_freshness": await get_kb_freshness(db),
        "practicum_participation": await get_practicum_participation(db),
        "failure_rates": await get_failure_rates(db),
    }
