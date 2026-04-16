"""적응형 추천 엔진 고도화 (v0.7).

기존 recommendation_service를 확장:
- 최근 오답 패턴 반영
- 개념 태그별 취약도 반영
- 난이도 적응 로직
- 반복 노출 간격 (Spaced Repetition)
- 시험 일정 반영
- 교수 지정 과제 우선순위 반영
- 학습 시간대/집중도 패턴 반영
"""

from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, case, desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_profile import AIProfile
from app.models.assignment import Assignment, AssignmentSubmission
from app.models.enums import Department, Difficulty, Level
from app.models.learning_history import LearningHistory
from app.models.question import Question

logger = logging.getLogger(__name__)


# === Spaced Repetition 간격 (SM-2 변형) ===
# 복습 간격: 1일 → 3일 → 7일 → 14일 → 30일
SRS_INTERVALS_DAYS = [1, 3, 7, 14, 30, 60]


@dataclass
class ScoredQuestion:
    """추천 점수가 부여된 문제."""
    question: Question
    score: float
    signals: dict[str, float] = field(default_factory=dict)


def _srs_due(last_correct_at: datetime, correct_streak: int) -> bool:
    """Spaced Repetition 기반 복습 시점 도래 여부."""
    if correct_streak <= 0:
        return True
    interval_idx = min(correct_streak - 1, len(SRS_INTERVALS_DAYS) - 1)
    interval = timedelta(days=SRS_INTERVALS_DAYS[interval_idx])
    return datetime.now(timezone.utc) >= last_correct_at + interval


async def _get_recent_error_patterns(
    db: AsyncSession, user_id: uuid.UUID, days: int = 14,
) -> dict[str, float]:
    """최근 N일간 과목별 오답률."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            Question.subject,
            func.count(LearningHistory.id).label("total"),
            func.sum(case((LearningHistory.is_correct.is_(False), 1), else_=0)).label("wrong"),
        )
        .join(Question, Question.id == LearningHistory.question_id)
        .where(LearningHistory.user_id == user_id, LearningHistory.created_at >= since)
        .group_by(Question.subject)
    )
    rows = result.all()
    return {
        r.subject: (int(r.wrong or 0) / r.total) if r.total > 0 else 0
        for r in rows
    }


async def _get_tag_weakness_map(
    db: AsyncSession, user_id: uuid.UUID, department: Department,
) -> dict[str, float]:
    """개념 태그별 취약도 (1 - accuracy)."""
    query = text("""
        SELECT tag,
               ROUND(1.0 - AVG(CASE WHEN lh.is_correct THEN 1.0 ELSE 0.0 END)::numeric, 4) as weakness
        FROM learning_history lh
        JOIN questions q ON q.id = lh.question_id
        CROSS JOIN LATERAL unnest(q.concept_tags) AS tag
        WHERE lh.user_id = :uid AND q.department = :dept
        GROUP BY tag HAVING COUNT(*) >= 2
    """)
    result = await db.execute(query, {"uid": str(user_id), "dept": department.value})
    return {r.tag: float(r.weakness) for r in result.all()}


async def _get_srs_candidates(
    db: AsyncSession, user_id: uuid.UUID, department: Department, limit: int = 50,
) -> list[uuid.UUID]:
    """SRS 기반 복습 대상 문제 ID — 정답 맞춘 문제 중 복습 시점 도래."""
    # 문제별 마지막 정답 시점 + 연속 정답 수
    stmt = (
        select(
            LearningHistory.question_id,
            func.max(LearningHistory.created_at).label("last_correct_at"),
            func.count().label("correct_streak"),
        )
        .join(Question, Question.id == LearningHistory.question_id)
        .where(
            LearningHistory.user_id == user_id,
            LearningHistory.is_correct.is_(True),
            Question.department == department,
        )
        .group_by(LearningHistory.question_id)
    )
    rows = (await db.execute(stmt)).all()

    due_ids = []
    for row in rows:
        if _srs_due(row.last_correct_at, row.correct_streak):
            due_ids.append(row.question_id)

    return due_ids[:limit]


async def _get_assignment_question_ids(
    db: AsyncSession, user_id: uuid.UUID,
) -> set[uuid.UUID]:
    """교수 지정 과제 중 미제출 문제 ID."""
    # 미제출 과제의 문제 ID 추출
    submitted_ids = select(AssignmentSubmission.assignment_id).where(
        AssignmentSubmission.student_id == user_id
    )
    stmt = (
        select(Assignment)
        .where(
            Assignment.status == "PUBLISHED",
            Assignment.id.notin_(submitted_ids),
        )
    )
    assignments = list((await db.execute(stmt)).scalars().all())

    question_ids: set[uuid.UUID] = set()
    for a in assignments:
        if a.question_ids:
            for qid_str in a.question_ids:
                try:
                    question_ids.add(uuid.UUID(qid_str) if isinstance(qid_str, str) else qid_str)
                except (ValueError, TypeError):
                    pass
    return question_ids


async def _get_study_time_pattern(
    db: AsyncSession, user_id: uuid.UUID,
) -> dict:
    """학습 시간대/집중도 패턴 분석."""
    result = await db.execute(text("""
        SELECT
            EXTRACT(HOUR FROM created_at) as hour,
            COUNT(*) as attempts,
            AVG(CASE WHEN is_correct THEN 1.0 ELSE 0.0 END) as accuracy,
            AVG(solving_time_sec) as avg_time
        FROM learning_history
        WHERE user_id = :uid
        GROUP BY EXTRACT(HOUR FROM created_at)
        ORDER BY attempts DESC
    """), {"uid": str(user_id)})
    rows = result.all()

    if not rows:
        return {"peak_hours": [], "avg_accuracy_by_hour": {}}

    hours_data = [
        {"hour": int(r.hour), "attempts": r.attempts, "accuracy": float(r.accuracy or 0), "avg_time": float(r.avg_time or 0)}
        for r in rows
    ]

    # 집중도 높은 시간대 (accuracy가 높은 시간)
    best_hours = sorted(hours_data, key=lambda x: x["accuracy"], reverse=True)[:3]

    return {
        "peak_hours": [h["hour"] for h in best_hours],
        "by_hour": hours_data,
    }


async def build_adaptive_set(
    db: AsyncSession,
    user_id: uuid.UUID,
    department: Department,
    *,
    set_size: int = 20,
    exam_date: datetime | None = None,
) -> dict:
    """적응형 추천 문제 세트 구성 (v0.7 고도화).

    점수 = Σ(signal * weight)
    signals:
    1. error_pattern: 최근 오답 패턴 과목 가중 (0.25)
    2. tag_weakness: 개념 태그 취약도 가중 (0.20)
    3. srs_due: 복습 시점 도래 보너스 (0.15)
    4. assignment: 미제출 과제 문제 보너스 (0.15)
    5. difficulty_fit: 학생 레벨 대비 난이도 적합성 (0.10)
    6. exam_urgency: 시험 임박도 반영 — 시험 가까울수록 취약 영역 가중 (0.10)
    7. recency_penalty: 최근 풀었던 문제 감점 (0.05)
    """

    # 프로파일
    profile = await db.scalar(select(AIProfile).where(AIProfile.user_id == user_id))
    level = profile.level if profile else Level.INTERMEDIATE

    # 1. 최근 오답 패턴
    error_patterns = await _get_recent_error_patterns(db, user_id)

    # 2. 개념 태그 취약도
    tag_weakness = await _get_tag_weakness_map(db, user_id, department)

    # 3. SRS 복습 대상
    srs_ids = set(await _get_srs_candidates(db, user_id, department))

    # 4. 과제 문제
    assignment_ids = await _get_assignment_question_ids(db, user_id)

    # 5. 시험 임박도
    exam_urgency = 0.0
    if exam_date:
        days_until = max(0, (exam_date - datetime.now(timezone.utc)).days)
        exam_urgency = max(0, 1.0 - days_until / 60)  # 60일 이내부터 점진 증가

    # 최근 정답 문제 (감점용)
    recent_correct = set()
    stmt = (
        select(LearningHistory.question_id)
        .where(
            LearningHistory.user_id == user_id,
            LearningHistory.is_correct.is_(True),
            LearningHistory.created_at >= datetime.now(timezone.utc) - timedelta(days=3),
        )
        .distinct()
    )
    recent_correct = {r[0] for r in (await db.execute(stmt)).all()}

    # 후보 문제 풀 (학과 전체)
    candidates = list((await db.execute(
        select(Question)
        .where(Question.department == department)
        .order_by(func.random())
        .limit(set_size * 5)
    )).scalars().all())

    # 점수 계산
    scored: list[ScoredQuestion] = []
    for q in candidates:
        signals: dict[str, float] = {}

        # 1. 오답 패턴 (0.25)
        error_rate = error_patterns.get(q.subject, 0)
        signals["error_pattern"] = error_rate * 0.25

        # 2. 태그 취약도 (0.20)
        tag_scores = [tag_weakness.get(t, 0) for t in (q.concept_tags or [])]
        signals["tag_weakness"] = (sum(tag_scores) / max(1, len(tag_scores))) * 0.20 if tag_scores else 0

        # 3. SRS (0.15)
        signals["srs_due"] = 0.15 if q.id in srs_ids else 0

        # 4. 과제 (0.15)
        signals["assignment"] = 0.15 if q.id in assignment_ids else 0

        # 5. 난이도 적합성 (0.10)
        diff_fit = _difficulty_fit(level, q.difficulty)
        signals["difficulty_fit"] = diff_fit * 0.10

        # 6. 시험 임박도 (0.10)
        signals["exam_urgency"] = exam_urgency * error_rate * 0.10

        # 7. 최근 정답 감점 (0.05)
        signals["recency_penalty"] = -0.05 if q.id in recent_correct else 0

        total = sum(signals.values())
        scored.append(ScoredQuestion(question=q, score=total, signals=signals))

    scored.sort(key=lambda s: s.score, reverse=True)
    selected = scored[:set_size]

    # 난이도 분포
    dist: dict[str, int] = {}
    for sq in selected:
        d = sq.question.difficulty.value
        dist[d] = dist.get(d, 0) + 1

    return {
        "questions": [
            {
                "id": str(sq.question.id),
                "subject": sq.question.subject,
                "unit": sq.question.unit,
                "difficulty": sq.question.difficulty.value,
                "score": round(sq.score, 4),
                "signals": {k: round(v, 4) for k, v in sq.signals.items()},
            }
            for sq in selected
        ],
        "total": len(selected),
        "strategy": "adaptive_v2",
        "level": level.value,
        "difficulty_distribution": dist,
        "study_pattern": await _get_study_time_pattern(db, user_id),
    }


def _difficulty_fit(level: Level, difficulty: Difficulty) -> float:
    """학생 레벨 대비 문제 난이도 적합성 (0~1)."""
    fit_matrix = {
        Level.BEGINNER: {Difficulty.EASY: 1.0, Difficulty.MEDIUM: 0.6, Difficulty.HARD: 0.2},
        Level.INTERMEDIATE: {Difficulty.EASY: 0.4, Difficulty.MEDIUM: 1.0, Difficulty.HARD: 0.6},
        Level.ADVANCED: {Difficulty.EASY: 0.2, Difficulty.MEDIUM: 0.6, Difficulty.HARD: 1.0},
    }
    return fit_matrix.get(level, {}).get(difficulty, 0.5)
