"""오답 분석 고도화 서비스 (v0.7).

- 문항 난이도 보정 (실제 정답률 기반)
- 변별도 분석 (상위/하위 그룹 정답률 차이)
- 시험 블루프린트 기반 오답 분석
- 진단 리포트 해석 기준 마련
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import Float, case, cast, desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Department, Difficulty, ErrorType
from app.models.learning_history import LearningHistory
from app.models.question import Question
from app.models.question_stats import AnswerInteraction, QuestionStats

logger = logging.getLogger(__name__)


# === 1. 문항 난이도 보정 ===


async def calibrate_difficulty(
    db: AsyncSession, department: Department, *, min_attempts: int = 10,
) -> list[dict]:
    """실제 정답률 기반 문항 난이도 보정 제안.

    현재 설정된 난이도 vs 실제 정답률의 괴리를 분석하여
    난이도 조정이 필요한 문항 목록을 반환한다.

    Rules:
    - 정답률 >= 0.75 → EASY 권장
    - 0.40 <= 정답률 < 0.75 → MEDIUM 권장
    - 정답률 < 0.40 → HARD 권장
    """
    stmt = (
        select(
            Question.id,
            Question.subject,
            Question.unit,
            Question.difficulty,
            Question.question_text,
            func.count(LearningHistory.id).label("attempts"),
            func.sum(case((LearningHistory.is_correct.is_(True), 1), else_=0)).label("correct"),
        )
        .join(LearningHistory, LearningHistory.question_id == Question.id)
        .where(Question.department == department)
        .group_by(Question.id)
        .having(func.count(LearningHistory.id) >= min_attempts)
    )
    rows = (await db.execute(stmt)).all()

    suggestions = []
    for row in rows:
        accuracy = int(row.correct) / row.attempts
        if accuracy >= 0.75:
            suggested = Difficulty.EASY
        elif accuracy >= 0.40:
            suggested = Difficulty.MEDIUM
        else:
            suggested = Difficulty.HARD

        if suggested != row.difficulty:
            suggestions.append({
                "question_id": str(row.id),
                "subject": row.subject,
                "unit": row.unit,
                "question_preview": row.question_text[:60],
                "current_difficulty": row.difficulty.value,
                "suggested_difficulty": suggested.value,
                "actual_accuracy": round(accuracy, 4),
                "total_attempts": row.attempts,
            })

    suggestions.sort(key=lambda x: abs(x["actual_accuracy"] - 0.5), reverse=True)
    return suggestions


# === 2. 변별도 분석 ===


async def compute_discrimination_index(
    db: AsyncSession, department: Department, *, min_attempts: int = 20,
) -> list[dict]:
    """변별도 지수 산출 — 상위 27% vs 하위 27% 정답률 차이.

    변별도 = P_upper - P_lower
    - 0.40 이상: 우수
    - 0.30~0.39: 양호
    - 0.20~0.29: 보통 (개선 검토)
    - 0.20 미만: 불량 (폐기 또는 대폭 수정 권고)
    """
    # 학생별 전체 정답률 (학과)
    student_acc = (
        select(
            LearningHistory.user_id,
            (
                cast(
                    func.sum(case((LearningHistory.is_correct.is_(True), 1), else_=0)),
                    Float,
                ) / func.count(LearningHistory.id)
            ).label("overall_acc"),
        )
        .join(Question, Question.id == LearningHistory.question_id)
        .where(Question.department == department)
        .group_by(LearningHistory.user_id)
        .having(func.count(LearningHistory.id) >= 10)
    ).subquery()

    # 상위/하위 27% 기준 분위 계산
    quantile_query = text("""
        SELECT
            percentile_cont(0.73) WITHIN GROUP (ORDER BY sub.overall_acc) as lower_bound,
            percentile_cont(0.27) WITHIN GROUP (ORDER BY sub.overall_acc) as upper_bound
        FROM (
            SELECT user_id, CAST(SUM(CASE WHEN lh.is_correct THEN 1 ELSE 0 END) AS FLOAT)
                / COUNT(*) as overall_acc
            FROM learning_history lh
            JOIN questions q ON q.id = lh.question_id
            WHERE q.department = :dept
            GROUP BY user_id HAVING COUNT(*) >= 10
        ) sub
    """)
    bounds = (await db.execute(quantile_query, {"dept": department.value})).one()
    lower_cutoff = float(bounds.upper_bound or 0.3)  # 하위 27% 경계
    upper_cutoff = float(bounds.lower_bound or 0.7)  # 상위 27% 경계

    # 문항별 상위/하위 그룹 정답률
    disc_query = text("""
        WITH student_overall AS (
            SELECT user_id,
                   CAST(SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) as acc
            FROM learning_history lh
            JOIN questions q ON q.id = lh.question_id
            WHERE q.department = :dept
            GROUP BY user_id HAVING COUNT(*) >= 10
        ),
        upper_group AS (SELECT user_id FROM student_overall WHERE acc >= :upper_cutoff),
        lower_group AS (SELECT user_id FROM student_overall WHERE acc <= :lower_cutoff)
        SELECT
            q.id as question_id,
            q.subject,
            q.unit,
            q.difficulty,
            COUNT(lh.id) as total_attempts,
            COALESCE(AVG(CASE WHEN ug.user_id IS NOT NULL AND lh.is_correct THEN 1.0
                              WHEN ug.user_id IS NOT NULL THEN 0.0 END), 0) as p_upper,
            COALESCE(AVG(CASE WHEN lg.user_id IS NOT NULL AND lh.is_correct THEN 1.0
                              WHEN lg.user_id IS NOT NULL THEN 0.0 END), 0) as p_lower
        FROM learning_history lh
        JOIN questions q ON q.id = lh.question_id
        LEFT JOIN upper_group ug ON ug.user_id = lh.user_id
        LEFT JOIN lower_group lg ON lg.user_id = lh.user_id
        WHERE q.department = :dept
        GROUP BY q.id, q.subject, q.unit, q.difficulty
        HAVING COUNT(lh.id) >= :min_att
        ORDER BY (
            COALESCE(AVG(CASE WHEN ug.user_id IS NOT NULL AND lh.is_correct THEN 1.0
                              WHEN ug.user_id IS NOT NULL THEN 0.0 END), 0) -
            COALESCE(AVG(CASE WHEN lg.user_id IS NOT NULL AND lh.is_correct THEN 1.0
                              WHEN lg.user_id IS NOT NULL THEN 0.0 END), 0)
        ) ASC
    """)
    rows = (await db.execute(disc_query, {
        "dept": department.value,
        "upper_cutoff": upper_cutoff,
        "lower_cutoff": lower_cutoff,
        "min_att": min_attempts,
    })).all()

    results = []
    for r in rows:
        p_upper = float(r.p_upper)
        p_lower = float(r.p_lower)
        disc_index = round(p_upper - p_lower, 4)

        if disc_index >= 0.40:
            grade = "우수"
        elif disc_index >= 0.30:
            grade = "양호"
        elif disc_index >= 0.20:
            grade = "보통"
        else:
            grade = "불량"

        results.append({
            "question_id": str(r.question_id),
            "subject": r.subject,
            "unit": r.unit,
            "difficulty": r.difficulty,
            "total_attempts": r.total_attempts,
            "p_upper": round(p_upper, 4),
            "p_lower": round(p_lower, 4),
            "discrimination_index": disc_index,
            "grade": grade,
        })

    return results


# === 3. 블루프린트 기반 오답 분석 ===


async def analyze_errors_by_blueprint(
    db: AsyncSession,
    user_id: uuid.UUID,
    department: Department,
) -> dict:
    """시험 블루프린트 기반 오답 패턴 분석.

    과목별 + 출제 영역별로 오답 유형(ErrorType) 분포를 분석하여
    학생의 약점 패턴을 구조화한다.
    """
    stmt = (
        select(
            Question.subject,
            Question.national_exam_mapping,
            LearningHistory.error_type,
            func.count(LearningHistory.id).label("count"),
        )
        .join(Question, Question.id == LearningHistory.question_id)
        .where(
            LearningHistory.user_id == user_id,
            LearningHistory.is_correct.is_(False),
            Question.department == department,
        )
        .group_by(Question.subject, Question.national_exam_mapping, LearningHistory.error_type)
        .order_by(desc("count"))
    )
    rows = (await db.execute(stmt)).all()

    # 구조화
    by_subject: dict[str, dict] = {}
    for r in rows:
        subj = r.subject
        area = r.national_exam_mapping or "일반"
        error_t = r.error_type.value if r.error_type else "UNKNOWN"

        if subj not in by_subject:
            by_subject[subj] = {"total_errors": 0, "areas": {}, "error_types": {}}
        by_subject[subj]["total_errors"] += r.count

        if area not in by_subject[subj]["areas"]:
            by_subject[subj]["areas"][area] = {"total": 0, "error_types": {}}
        by_subject[subj]["areas"][area]["total"] += r.count
        by_subject[subj]["areas"][area]["error_types"][error_t] = (
            by_subject[subj]["areas"][area]["error_types"].get(error_t, 0) + r.count
        )

        by_subject[subj]["error_types"][error_t] = (
            by_subject[subj]["error_types"].get(error_t, 0) + r.count
        )

    # 전체 오답 유형 분포
    total_errors = sum(s["total_errors"] for s in by_subject.values())
    global_error_types: dict[str, int] = {}
    for s in by_subject.values():
        for et, cnt in s["error_types"].items():
            global_error_types[et] = global_error_types.get(et, 0) + cnt

    return {
        "user_id": str(user_id),
        "department": department.value,
        "total_errors": total_errors,
        "global_error_distribution": global_error_types,
        "by_subject": by_subject,
    }


# === 4. 진단 리포트 해석 기준 ===


async def generate_diagnostic_report(
    db: AsyncSession,
    user_id: uuid.UUID,
    department: Department,
) -> dict:
    """종합 진단 리포트 — 다면 분석 기반.

    아래 요소를 종합하여 학생의 학습 상태를 진단한다:
    - 전체 정답률 + 추이 (최근 2주 vs 이전)
    - 오답 유형 분포 (ErrorType)
    - 과목별 정답률
    - 풀이 시간 패턴 (과목별 평균 시간)
    - 학습 빈도
    - 개선 속도 (반복 풀이 시 정답률 변화)
    """
    # 1. 전체 + 최근 추이
    overall_stmt = (
        select(
            func.count(LearningHistory.id).label("total"),
            func.sum(case((LearningHistory.is_correct.is_(True), 1), else_=0)).label("correct"),
            func.avg(LearningHistory.solving_time_sec).label("avg_time"),
        )
        .join(Question, Question.id == LearningHistory.question_id)
        .where(LearningHistory.user_id == user_id, Question.department == department)
    )
    overall = (await db.execute(overall_stmt)).one()

    recent_stmt = text("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN lh.is_correct THEN 1 ELSE 0 END) as correct,
            AVG(lh.solving_time_sec) as avg_time
        FROM learning_history lh
        JOIN questions q ON q.id = lh.question_id
        WHERE lh.user_id = :uid AND q.department = :dept
          AND lh.created_at >= NOW() - INTERVAL '14 days'
    """)
    recent = (await db.execute(recent_stmt, {"uid": str(user_id), "dept": department.value})).one()

    older_stmt = text("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN lh.is_correct THEN 1 ELSE 0 END) as correct
        FROM learning_history lh
        JOIN questions q ON q.id = lh.question_id
        WHERE lh.user_id = :uid AND q.department = :dept
          AND lh.created_at < NOW() - INTERVAL '14 days'
    """)
    older = (await db.execute(older_stmt, {"uid": str(user_id), "dept": department.value})).one()

    total_all = int(overall.total or 0)
    correct_all = int(overall.correct or 0)
    overall_acc = round(correct_all / total_all, 4) if total_all > 0 else 0

    recent_total = int(recent.total or 0)
    recent_correct = int(recent.correct or 0)
    recent_acc = round(recent_correct / recent_total, 4) if recent_total > 0 else 0

    older_total = int(older.total or 0)
    older_correct = int(older.correct or 0)
    older_acc = round(older_correct / older_total, 4) if older_total > 0 else 0

    trend = "향상" if recent_acc > older_acc + 0.03 else "하락" if recent_acc < older_acc - 0.03 else "유지"

    # 2. 오답 유형 분포
    error_dist_stmt = (
        select(
            LearningHistory.error_type,
            func.count(LearningHistory.id).label("cnt"),
        )
        .join(Question, Question.id == LearningHistory.question_id)
        .where(
            LearningHistory.user_id == user_id,
            LearningHistory.is_correct.is_(False),
            Question.department == department,
        )
        .group_by(LearningHistory.error_type)
    )
    error_rows = (await db.execute(error_dist_stmt)).all()
    error_distribution = {
        (r.error_type.value if r.error_type else "UNKNOWN"): r.cnt for r in error_rows
    }

    # 주요 오답 패턴 해석
    dominant_error = max(error_distribution, key=error_distribution.get) if error_distribution else None
    error_interpretation = _interpret_error_pattern(dominant_error, error_distribution)

    # 3. 과목별 정답률 + 풀이 시간
    subject_stmt = (
        select(
            Question.subject,
            func.count(LearningHistory.id).label("attempts"),
            func.sum(case((LearningHistory.is_correct.is_(True), 1), else_=0)).label("correct"),
            func.avg(LearningHistory.solving_time_sec).label("avg_time"),
        )
        .join(Question, Question.id == LearningHistory.question_id)
        .where(LearningHistory.user_id == user_id, Question.department == department)
        .group_by(Question.subject)
    )
    subject_rows = (await db.execute(subject_stmt)).all()
    subject_analysis = [
        {
            "subject": r.subject,
            "attempts": r.attempts,
            "accuracy": round(int(r.correct) / r.attempts, 4) if r.attempts > 0 else 0,
            "avg_time_sec": round(float(r.avg_time or 0), 1),
        }
        for r in subject_rows
    ]
    subject_analysis.sort(key=lambda x: x["accuracy"])

    # 4. 학습 빈도 (일별)
    freq_stmt = text("""
        SELECT DATE(lh.created_at) as d, COUNT(*) as cnt
        FROM learning_history lh
        JOIN questions q ON q.id = lh.question_id
        WHERE lh.user_id = :uid AND q.department = :dept
          AND lh.created_at >= NOW() - INTERVAL '30 days'
        GROUP BY DATE(lh.created_at)
    """)
    freq_rows = (await db.execute(freq_stmt, {"uid": str(user_id), "dept": department.value})).all()
    active_days = len(freq_rows)
    avg_daily = round(sum(r.cnt for r in freq_rows) / max(1, active_days), 1)

    # 5. 개선 속도 (attempt_no별 정답률 변화)
    improvement_stmt = (
        select(
            LearningHistory.attempt_no,
            func.count(LearningHistory.id).label("total"),
            func.sum(case((LearningHistory.is_correct.is_(True), 1), else_=0)).label("correct"),
        )
        .join(Question, Question.id == LearningHistory.question_id)
        .where(LearningHistory.user_id == user_id, Question.department == department)
        .group_by(LearningHistory.attempt_no)
        .order_by(LearningHistory.attempt_no)
    )
    imp_rows = (await db.execute(improvement_stmt)).all()
    improvement_curve = [
        {
            "attempt": r.attempt_no,
            "accuracy": round(int(r.correct) / r.total, 4) if r.total > 0 else 0,
            "count": r.total,
        }
        for r in imp_rows
    ]

    # 6. 종합 등급
    grade = _compute_overall_grade(overall_acc, trend, active_days, avg_daily)

    return {
        "user_id": str(user_id),
        "department": department.value,
        "overall": {
            "total_attempts": total_all,
            "accuracy": overall_acc,
            "avg_time_sec": round(float(overall.avg_time or 0), 1),
        },
        "trend": {
            "recent_14d_accuracy": recent_acc,
            "older_accuracy": older_acc,
            "direction": trend,
        },
        "error_distribution": error_distribution,
        "error_interpretation": error_interpretation,
        "subject_analysis": subject_analysis,
        "study_frequency": {
            "active_days_last_30": active_days,
            "avg_problems_per_day": avg_daily,
        },
        "improvement_curve": improvement_curve,
        "grade": grade,
    }


def _interpret_error_pattern(dominant: str | None, dist: dict[str, int]) -> str:
    """오답 유형 분포를 해석하여 학습 조언을 생성."""
    if not dominant:
        return "오답 데이터가 충분하지 않습니다."

    interpretations = {
        "CONCEPT_GAP": "개념 이해가 부족한 문항이 많습니다. 교과서 핵심 개념 복습을 우선하세요.",
        "CONFUSION": "유사 개념을 혼동하는 패턴이 자주 나타납니다. 비교/대조 정리가 필요합니다.",
        "CARELESS": "실수로 인한 오답이 많습니다. 문제를 천천히 읽고 검토 시간을 확보하세요.",
        "APPLICATION_GAP": "개념은 알지만 응용이 부족합니다. 사례 기반 문제 연습이 필요합니다.",
    }
    return interpretations.get(dominant, "다양한 유형의 오답이 분포되어 있습니다.")


def _compute_overall_grade(
    accuracy: float, trend: str, active_days: int, avg_daily: float,
) -> dict:
    """종합 학습 등급 산출."""
    score = 0.0

    # 정답률 (40%)
    if accuracy >= 0.8:
        score += 40
    elif accuracy >= 0.6:
        score += 30
    elif accuracy >= 0.4:
        score += 20
    else:
        score += 10

    # 추이 (20%)
    if trend == "향상":
        score += 20
    elif trend == "유지":
        score += 12
    else:
        score += 5

    # 학습 빈도 (20%)
    if active_days >= 20:
        score += 20
    elif active_days >= 10:
        score += 14
    elif active_days >= 5:
        score += 8
    else:
        score += 3

    # 일일 문제 수 (20%)
    if avg_daily >= 15:
        score += 20
    elif avg_daily >= 8:
        score += 14
    elif avg_daily >= 3:
        score += 8
    else:
        score += 3

    if score >= 85:
        grade, label = "A", "우수"
    elif score >= 70:
        grade, label = "B", "양호"
    elif score >= 50:
        grade, label = "C", "보통"
    elif score >= 30:
        grade, label = "D", "노력 필요"
    else:
        grade, label = "F", "위험"

    return {"score": round(score, 1), "grade": grade, "label": label}
