"""학습 추천 엔진 — 콘텐츠 기반 + 협업 필터링 기반 추천.

Day 11 설계
----------
1. **콘텐츠 기반**: 학생의 취약영역(AI Profile) + 오답 패턴에서 subject/unit/difficulty를 추출,
   아직 안 풀거나 오답인 문제를 우선 추천.
2. **난이도 점진**: 학생 level에 맞춰 EASY→MEDIUM→HARD 비율 조정.
3. **반복 오답 우선**: 같은 문제를 여러 번 틀린 경우 재풀이 추천.
4. **중복 방지**: 최근 N일 내 정답으로 풀이한 문제는 제외.

향후 확장 (Day 14+)
- 협업 필터링: 비슷한 취약영역을 가진 학생들이 효과적으로 학습한 문제를 추천.
- 간격 반복(SRS) 알고리즘 적용.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import and_, case, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_profile import AIProfile
from app.models.enums import Department, Difficulty, Level
from app.models.learning_history import LearningHistory
from app.models.question import Question

logger = logging.getLogger(__name__)

# === 난이도 배분 (level별) ===
DIFFICULTY_RATIO: dict[Level, dict[Difficulty, float]] = {
    Level.BEGINNER: {Difficulty.EASY: 0.50, Difficulty.MEDIUM: 0.40, Difficulty.HARD: 0.10},
    Level.INTERMEDIATE: {Difficulty.EASY: 0.20, Difficulty.MEDIUM: 0.55, Difficulty.HARD: 0.25},
    Level.ADVANCED: {Difficulty.EASY: 0.10, Difficulty.MEDIUM: 0.40, Difficulty.HARD: 0.50},
}
DEFAULT_SET_SIZE = 20
RECENT_CORRECT_EXCLUDE_DAYS = 7


@dataclass
class RecommendationResult:
    """추천 문제 세트 결과."""

    questions: list[Question]
    total_available: int
    strategy: str
    level: Level
    difficulty_distribution: dict[str, int]


class RecommendationError(Exception):
    pass


async def _get_weak_subjects(
    db: AsyncSession, user_id: uuid.UUID
) -> list[dict]:
    """AIProfile에서 취약영역 추출."""
    profile = await db.scalar(
        select(AIProfile).where(AIProfile.user_id == user_id)
    )
    if profile is None or not profile.weak_priority:
        return []
    return profile.weak_priority


async def _get_repeated_wrong_question_ids(
    db: AsyncSession, user_id: uuid.UUID, limit: int = 50
) -> list[uuid.UUID]:
    """같은 문제를 2회 이상 틀린 question_id를 반복횟수 내림차순으로 반환."""
    stmt = (
        select(
            LearningHistory.question_id,
            func.count(LearningHistory.id).label("wrong_count"),
        )
        .where(
            LearningHistory.user_id == user_id,
            LearningHistory.is_correct.is_(False),
        )
        .group_by(LearningHistory.question_id)
        .having(func.count(LearningHistory.id) >= 2)
        .order_by(desc("wrong_count"))
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [r.question_id for r in rows]


async def _get_recently_correct_ids(
    db: AsyncSession, user_id: uuid.UUID, days: int = RECENT_CORRECT_EXCLUDE_DAYS
) -> set[uuid.UUID]:
    """최근 N일 내 정답으로 풀이한 question_id 집합 (중복 제외 대상)."""
    from datetime import UTC, datetime, timedelta

    since = datetime.now(UTC) - timedelta(days=days)
    stmt = (
        select(LearningHistory.question_id)
        .where(
            LearningHistory.user_id == user_id,
            LearningHistory.is_correct.is_(True),
            LearningHistory.created_at >= since,
        )
        .distinct()
    )
    rows = (await db.execute(stmt)).all()
    return {r[0] for r in rows}


async def build_recommended_set(
    db: AsyncSession,
    user_id: uuid.UUID,
    department: Department,
    *,
    set_size: int = DEFAULT_SET_SIZE,
    level: Level | None = None,
) -> RecommendationResult:
    """학생 맞춤형 추천 문제 세트 구성.

    전략
    ----
    1. 반복 오답 문제 (최대 set_size의 30%) → 재학습 유도
    2. 취약영역 문제 (최대 40%) → 약점 보강
    3. 일반 문제 (나머지) → 균형 학습

    각 그룹 안에서 난이도 비율은 학생 level에 따라 자동 조정.
    """
    # Profile에서 level 가져오기
    profile = await db.scalar(select(AIProfile).where(AIProfile.user_id == user_id))
    if level is None:
        level = profile.level if profile else Level.INTERMEDIATE
    ratios = DIFFICULTY_RATIO[level]

    recently_correct = await _get_recently_correct_ids(db, user_id)
    exclude_ids = recently_correct  # 최근 정답 제외

    selected: list[Question] = []
    seen_ids: set[uuid.UUID] = set()

    def _add(q: Question) -> bool:
        if q.id not in seen_ids and q.id not in exclude_ids:
            selected.append(q)
            seen_ids.add(q.id)
            return True
        return False

    # --- 1단계: 반복 오답 문제 (30%) ---
    repeat_target = int(set_size * 0.3)
    repeat_ids = await _get_repeated_wrong_question_ids(db, user_id, limit=repeat_target * 2)
    if repeat_ids:
        valid_ids = [qid for qid in repeat_ids if qid not in exclude_ids][:repeat_target]
        if valid_ids:
            stmt = select(Question).where(Question.id.in_(valid_ids))
            questions = list((await db.execute(stmt)).scalars().all())
            for q in questions:
                _add(q)

    # --- 2단계: 취약영역 문제 (40%) ---
    weak_target = int(set_size * 0.4)
    weak_subjects = await _get_weak_subjects(db, user_id)
    if weak_subjects:
        for weak in weak_subjects[:5]:
            if len(selected) >= repeat_target + weak_target:
                break
            subj = weak.get("subject", "")
            unit_val = weak.get("unit")
            filters = [
                Question.department == department,
                Question.subject == subj,
                Question.id.notin_(seen_ids | exclude_ids) if (seen_ids | exclude_ids) else True,
            ]
            if unit_val:
                filters.append(Question.unit == unit_val)
            stmt = (
                select(Question)
                .where(and_(*filters))
                .order_by(func.random())
                .limit(weak_target // max(1, len(weak_subjects)))
            )
            rows = list((await db.execute(stmt)).scalars().all())
            for q in rows:
                _add(q)

    # --- 3단계: 일반 문제 (나머지) ---
    remaining = set_size - len(selected)
    if remaining > 0:
        stmt = (
            select(Question)
            .where(
                Question.department == department,
                Question.id.notin_(seen_ids | exclude_ids) if (seen_ids | exclude_ids) else True,
            )
            .order_by(func.random())
            .limit(remaining * 2)
        )
        pool = list((await db.execute(stmt)).scalars().all())

        # 난이도 비율에 맞춰 선택
        by_diff: dict[Difficulty, list[Question]] = {d: [] for d in Difficulty}
        for q in pool:
            by_diff[q.difficulty].append(q)

        for diff, ratio in ratios.items():
            want = max(1, round(remaining * ratio))
            for q in by_diff.get(diff, [])[:want]:
                if len(selected) >= set_size:
                    break
                _add(q)

        # 그래도 부족하면 아무거나
        for q in pool:
            if len(selected) >= set_size:
                break
            _add(q)

    # 난이도 분포 집계
    dist: dict[str, int] = {}
    for q in selected:
        dist[q.difficulty.value] = dist.get(q.difficulty.value, 0) + 1

    total_available_stmt = (
        select(func.count(Question.id))
        .where(Question.department == department)
    )
    total_available = (await db.execute(total_available_stmt)).scalar_one()

    return RecommendationResult(
        questions=selected[:set_size],
        total_available=total_available,
        strategy="weak_priority+repeat_wrong+random_fill",
        level=level,
        difficulty_distribution=dist,
    )
