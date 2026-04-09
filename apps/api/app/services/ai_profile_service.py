"""AI 프로파일 서비스 — 진단 결과 기반 자동 생성/업데이트.

진단 테스트 직후 호출되어 학생별 1:1 AI 프로파일을 생성한다.
이후 Day 11(추천 엔진)에서 학습 이력을 누적 반영해 점진적으로 업데이트된다.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_profile import AIProfile, ExplanationPreference
from app.models.diagnostic import DiagnosticTest
from app.models.enums import Level

logger = logging.getLogger(__name__)


def _build_learning_path(weak_areas: list[dict], level: Level) -> list[dict]:
    """약점을 우선순위로 학습 경로 생성.

    경로는 priority 순으로 단계화되며, 각 단계에 권장 액션을 포함한다.

    Returns
    -------
    list[dict]
        예: [{"step": 1, "subject": "기본간호학", "unit": "투약",
              "score": 0.42, "rationale": "..."}]
    """
    if not weak_areas:
        return [
            {
                "step": 1,
                "subject": "전반",
                "unit": None,
                "score": None,
                "rationale": "취약 영역이 발견되지 않았습니다. 균형 있는 복습을 진행하세요.",
            }
        ]

    path = []
    for i, area in enumerate(weak_areas, start=1):
        score_pct = int(round(area["score"] * 100))
        rationale = (
            f"진단 정답률 {score_pct}% — "
            f"{'기초 개념 복습' if level == Level.BEGINNER else '심화 문제 풀이'}부터 시작하세요."
        )
        path.append(
            {
                "step": i,
                "subject": area["subject"],
                "unit": area.get("unit"),
                "score": area["score"],
                "rationale": rationale,
            }
        )
    return path


def _default_explanation_pref(level: Level) -> ExplanationPreference:
    """학습 수준에 따른 기본 설명 난이도 매핑."""
    return {
        Level.BEGINNER: ExplanationPreference.SIMPLE,
        Level.INTERMEDIATE: ExplanationPreference.DETAILED,
        Level.ADVANCED: ExplanationPreference.EXPERT,
    }[level]


async def create_or_replace_profile_from_diagnostic(
    db: AsyncSession, test: DiagnosticTest
) -> AIProfile:
    """진단 결과로부터 AI 프로파일을 자동 생성하거나 교체한다.

    프로파일은 사용자당 1개 (UNIQUE). 이미 있으면 진단 결과로 덮어쓴다.
    """
    if test.completed_at is None or test.level is None:
        raise ValueError("Diagnostic test is not completed yet")

    weak_areas = test.weak_areas or []
    learning_path = _build_learning_path(weak_areas, test.level)
    explanation_pref = _default_explanation_pref(test.level)

    existing = await db.scalar(
        select(AIProfile).where(AIProfile.user_id == test.user_id)
    )
    if existing is None:
        profile = AIProfile(
            user_id=test.user_id,
            level=test.level,
            weak_priority=weak_areas,
            learning_path=learning_path,
            explanation_pref=explanation_pref,
            frequent_topics=[],
        )
        db.add(profile)
    else:
        existing.level = test.level
        existing.weak_priority = weak_areas
        existing.learning_path = learning_path
        existing.explanation_pref = explanation_pref
        profile = existing

    await db.flush()
    await db.refresh(profile)
    logger.info(
        "AIProfile %s for user=%s level=%s, weak=%d, path_steps=%d",
        "created" if existing is None else "updated",
        test.user_id,
        test.level.value,
        len(weak_areas),
        len(learning_path),
    )
    return profile


async def get_profile_for_user(
    db: AsyncSession, user_id: uuid.UUID
) -> AIProfile | None:
    return await db.scalar(select(AIProfile).where(AIProfile.user_id == user_id))
