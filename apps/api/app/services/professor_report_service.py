"""교수용 학습 분석 리포트 서비스 (v0.7).

- 학생별 성취도 추적
- 학습목표별 성취도 시각화 데이터
- 분반 단위 비교 분석
- 취약 학생 자동 탐지
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Float, case, cast, desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Department
from app.models.learning_history import LearningHistory
from app.models.professor_class import ClassStudent, ProfessorClass
from app.models.question import Question

logger = logging.getLogger(__name__)


# === 1. 학생별 성취도 추적 ===


async def get_student_achievement(
    db: AsyncSession,
    professor_id: uuid.UUID,
    class_id: uuid.UUID,
) -> list[dict]:
    """분반 내 학생별 성취도 요약.

    각 학생의 전체 정답률, 최근 2주 정답률, 풀이 문항 수, 학습 일수를 반환.
    """
    # 클래스 소유 확인
    cls = await db.scalar(
        select(ProfessorClass).where(
            ProfessorClass.id == class_id,
            ProfessorClass.professor_id == professor_id,
        )
    )
    if not cls:
        return []

    # 클래스 학생 목록
    students_stmt = (
        select(ClassStudent.student_id)
        .where(ClassStudent.class_id == class_id)
    )
    student_ids = [r[0] for r in (await db.execute(students_stmt)).all()]
    if not student_ids:
        return []

    # 학생별 통계
    result = await db.execute(text("""
        WITH student_stats AS (
            SELECT
                lh.user_id,
                COUNT(*) as total_attempts,
                SUM(CASE WHEN lh.is_correct THEN 1 ELSE 0 END) as correct,
                AVG(lh.solving_time_sec) as avg_time,
                COUNT(DISTINCT DATE(lh.created_at)) as active_days,
                MAX(lh.created_at) as last_activity
            FROM learning_history lh
            JOIN questions q ON q.id = lh.question_id
            WHERE lh.user_id = ANY(:student_ids) AND q.department = :dept
            GROUP BY lh.user_id
        ),
        recent_stats AS (
            SELECT
                lh.user_id,
                COUNT(*) as recent_total,
                SUM(CASE WHEN lh.is_correct THEN 1 ELSE 0 END) as recent_correct
            FROM learning_history lh
            JOIN questions q ON q.id = lh.question_id
            WHERE lh.user_id = ANY(:student_ids) AND q.department = :dept
              AND lh.created_at >= NOW() - INTERVAL '14 days'
            GROUP BY lh.user_id
        )
        SELECT
            u.id as user_id,
            u.name,
            u.student_no,
            COALESCE(ss.total_attempts, 0) as total_attempts,
            COALESCE(ss.correct, 0) as correct,
            COALESCE(ss.avg_time, 0) as avg_time,
            COALESCE(ss.active_days, 0) as active_days,
            ss.last_activity,
            COALESCE(rs.recent_total, 0) as recent_total,
            COALESCE(rs.recent_correct, 0) as recent_correct
        FROM users u
        LEFT JOIN student_stats ss ON ss.user_id = u.id
        LEFT JOIN recent_stats rs ON rs.user_id = u.id
        WHERE u.id = ANY(:student_ids)
        ORDER BY COALESCE(ss.correct::float / NULLIF(ss.total_attempts, 0), 0) DESC
    """), {
        "student_ids": student_ids,
        "dept": cls.department.value,
    })
    rows = result.all()

    return [
        {
            "user_id": str(r.user_id),
            "name": r.name,
            "student_no": r.student_no,
            "total_attempts": r.total_attempts,
            "accuracy": round(r.correct / r.total_attempts, 4) if r.total_attempts > 0 else 0,
            "avg_time_sec": round(float(r.avg_time), 1),
            "active_days": r.active_days,
            "last_activity": r.last_activity.isoformat() if r.last_activity else None,
            "recent_14d": {
                "attempts": r.recent_total,
                "accuracy": round(r.recent_correct / r.recent_total, 4) if r.recent_total > 0 else 0,
            },
        }
        for r in rows
    ]


# === 2. 학습목표별 성취도 ===


async def get_objective_achievement(
    db: AsyncSession,
    professor_id: uuid.UUID,
    class_id: uuid.UUID,
) -> list[dict]:
    """학습목표(learning_objective)별 분반 평균 성취도.

    Question.learning_objective 기준으로 분반 학생의 평균 정답률을 집계한다.
    """
    cls = await db.scalar(
        select(ProfessorClass).where(
            ProfessorClass.id == class_id,
            ProfessorClass.professor_id == professor_id,
        )
    )
    if not cls:
        return []

    student_ids_stmt = select(ClassStudent.student_id).where(ClassStudent.class_id == class_id)
    student_ids = [r[0] for r in (await db.execute(student_ids_stmt)).all()]
    if not student_ids:
        return []

    result = await db.execute(text("""
        SELECT
            q.learning_objective,
            q.subject,
            COUNT(lh.id) as attempts,
            SUM(CASE WHEN lh.is_correct THEN 1 ELSE 0 END) as correct,
            COUNT(DISTINCT lh.user_id) as student_count
        FROM learning_history lh
        JOIN questions q ON q.id = lh.question_id
        WHERE lh.user_id = ANY(:student_ids)
          AND q.department = :dept
          AND q.learning_objective IS NOT NULL
        GROUP BY q.learning_objective, q.subject
        ORDER BY SUM(CASE WHEN lh.is_correct THEN 1 ELSE 0 END)::float / COUNT(lh.id) ASC
    """), {
        "student_ids": student_ids,
        "dept": cls.department.value,
    })
    rows = result.all()

    return [
        {
            "learning_objective": r.learning_objective,
            "subject": r.subject,
            "attempts": r.attempts,
            "accuracy": round(int(r.correct) / r.attempts, 4) if r.attempts > 0 else 0,
            "student_count": r.student_count,
            "status": "달성" if int(r.correct) / r.attempts >= 0.7 else "미달",
        }
        for r in rows
    ]


# === 3. 분반 단위 비교 분석 ===


async def compare_classes(
    db: AsyncSession,
    professor_id: uuid.UUID,
) -> list[dict]:
    """교수의 전체 분반 간 비교 분석.

    각 분반의 평균 정답률, 활동율, 평균 풀이 시간을 비교한다.
    """
    classes = list((await db.execute(
        select(ProfessorClass)
        .where(ProfessorClass.professor_id == professor_id)
        .order_by(ProfessorClass.year.desc(), ProfessorClass.semester.desc())
    )).scalars().all())

    results = []
    for cls in classes:
        student_ids_stmt = select(ClassStudent.student_id).where(ClassStudent.class_id == cls.id)
        student_ids = [r[0] for r in (await db.execute(student_ids_stmt)).all()]

        if not student_ids:
            results.append({
                "class_id": str(cls.id),
                "class_name": cls.class_name,
                "department": cls.department.value,
                "year": cls.year,
                "semester": cls.semester,
                "student_count": 0,
                "avg_accuracy": 0,
                "avg_time_sec": 0,
                "total_attempts": 0,
                "active_rate": 0,
            })
            continue

        stats = (await db.execute(text("""
            SELECT
                COUNT(DISTINCT lh.user_id) as active_students,
                COUNT(lh.id) as total_attempts,
                AVG(CASE WHEN lh.is_correct THEN 1.0 ELSE 0.0 END) as avg_accuracy,
                AVG(lh.solving_time_sec) as avg_time
            FROM learning_history lh
            JOIN questions q ON q.id = lh.question_id
            WHERE lh.user_id = ANY(:sids) AND q.department = :dept
        """), {"sids": student_ids, "dept": cls.department.value})).one()

        results.append({
            "class_id": str(cls.id),
            "class_name": cls.class_name,
            "department": cls.department.value,
            "year": cls.year,
            "semester": cls.semester,
            "student_count": len(student_ids),
            "active_students": int(stats.active_students or 0),
            "active_rate": round(int(stats.active_students or 0) / len(student_ids), 4),
            "total_attempts": int(stats.total_attempts or 0),
            "avg_accuracy": round(float(stats.avg_accuracy or 0), 4),
            "avg_time_sec": round(float(stats.avg_time or 0), 1),
        })

    return results


# === 4. 취약 학생 자동 탐지 ===


async def detect_at_risk_students(
    db: AsyncSession,
    professor_id: uuid.UUID,
    class_id: uuid.UUID,
    *,
    accuracy_threshold: float = 0.4,
    inactivity_days: int = 7,
) -> dict:
    """취약 학생 자동 탐지.

    기준:
    1. 정답률 < threshold (학습 부진)
    2. 최근 N일 학습 기록 없음 (이탈 위험)
    3. 정답률 하락 추세 (최근 vs 이전)
    """
    cls = await db.scalar(
        select(ProfessorClass).where(
            ProfessorClass.id == class_id,
            ProfessorClass.professor_id == professor_id,
        )
    )
    if not cls:
        return {"low_accuracy": [], "inactive": [], "declining": []}

    student_ids_stmt = select(ClassStudent.student_id).where(ClassStudent.class_id == class_id)
    student_ids = [r[0] for r in (await db.execute(student_ids_stmt)).all()]
    if not student_ids:
        return {"low_accuracy": [], "inactive": [], "declining": []}

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=inactivity_days)

    # 1. 학습 부진 (정답률 < threshold)
    low_acc_result = await db.execute(text("""
        SELECT
            u.id as user_id, u.name, u.student_no,
            COUNT(lh.id) as attempts,
            SUM(CASE WHEN lh.is_correct THEN 1 ELSE 0 END)::float / COUNT(lh.id) as accuracy
        FROM learning_history lh
        JOIN questions q ON q.id = lh.question_id
        JOIN users u ON u.id = lh.user_id
        WHERE lh.user_id = ANY(:sids) AND q.department = :dept
        GROUP BY u.id, u.name, u.student_no
        HAVING SUM(CASE WHEN lh.is_correct THEN 1 ELSE 0 END)::float / COUNT(lh.id) < :threshold
           AND COUNT(lh.id) >= 5
        ORDER BY accuracy ASC
    """), {"sids": student_ids, "dept": cls.department.value, "threshold": accuracy_threshold})

    low_accuracy = [
        {
            "user_id": str(r.user_id), "name": r.name, "student_no": r.student_no,
            "attempts": r.attempts, "accuracy": round(float(r.accuracy), 4),
            "risk_type": "학습부진",
        }
        for r in low_acc_result.all()
    ]

    # 2. 이탈 위험 (최근 N일 학습 없음)
    inactive_result = await db.execute(text("""
        SELECT u.id as user_id, u.name, u.student_no,
               MAX(lh.created_at) as last_activity
        FROM users u
        LEFT JOIN learning_history lh ON lh.user_id = u.id
        LEFT JOIN questions q ON q.id = lh.question_id AND q.department = :dept
        WHERE u.id = ANY(:sids)
        GROUP BY u.id, u.name, u.student_no
        HAVING MAX(lh.created_at) IS NULL OR MAX(lh.created_at) < :cutoff
    """), {"sids": student_ids, "dept": cls.department.value, "cutoff": cutoff})

    inactive = [
        {
            "user_id": str(r.user_id), "name": r.name, "student_no": r.student_no,
            "last_activity": r.last_activity.isoformat() if r.last_activity else None,
            "risk_type": "이탈위험",
        }
        for r in inactive_result.all()
    ]

    # 3. 하락 추세 (최근 2주 vs 이전 2주)
    declining_result = await db.execute(text("""
        WITH recent AS (
            SELECT lh.user_id,
                   SUM(CASE WHEN lh.is_correct THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) as acc
            FROM learning_history lh
            JOIN questions q ON q.id = lh.question_id
            WHERE lh.user_id = ANY(:sids) AND q.department = :dept
              AND lh.created_at >= NOW() - INTERVAL '14 days'
            GROUP BY lh.user_id HAVING COUNT(*) >= 5
        ),
        older AS (
            SELECT lh.user_id,
                   SUM(CASE WHEN lh.is_correct THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) as acc
            FROM learning_history lh
            JOIN questions q ON q.id = lh.question_id
            WHERE lh.user_id = ANY(:sids) AND q.department = :dept
              AND lh.created_at >= NOW() - INTERVAL '28 days'
              AND lh.created_at < NOW() - INTERVAL '14 days'
            GROUP BY lh.user_id HAVING COUNT(*) >= 5
        )
        SELECT u.id as user_id, u.name, u.student_no,
               r.acc as recent_acc, o.acc as older_acc,
               r.acc - o.acc as delta
        FROM recent r
        JOIN older o ON o.user_id = r.user_id
        JOIN users u ON u.id = r.user_id
        WHERE r.acc < o.acc - 0.1
        ORDER BY delta ASC
    """), {"sids": student_ids, "dept": cls.department.value})

    declining = [
        {
            "user_id": str(r.user_id), "name": r.name, "student_no": r.student_no,
            "recent_accuracy": round(float(r.recent_acc), 4),
            "older_accuracy": round(float(r.older_acc), 4),
            "delta": round(float(r.delta), 4),
            "risk_type": "하락추세",
        }
        for r in declining_result.all()
    ]

    return {
        "class_id": str(class_id),
        "class_name": cls.class_name,
        "low_accuracy": low_accuracy,
        "inactive": inactive,
        "declining": declining,
        "total_at_risk": len(set(
            [s["user_id"] for s in low_accuracy]
            + [s["user_id"] for s in inactive]
            + [s["user_id"] for s in declining]
        )),
    }
