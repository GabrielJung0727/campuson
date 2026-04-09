"""진단 테스트 서비스 — 시작/채점/영역별 점수/취약영역 추출.

핵심 로직
--------
1. **start_diagnostic_test**: 학과별 문항셋을 자동 구성 (과목 균등 + 난이도 균형).
   1회 제한 정책은 DB unique 제약과 서비스 레이어에서 함께 검증한다.
2. **submit_diagnostic_test**: 응답을 채점하고 section_scores/weak_areas/level을 산출.
3. **계산 로직 순수 함수**는 단위 테스트가 가능하도록 분리한다.
"""

from __future__ import annotations

import logging
import random
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.diagnostic import DiagnosticAnswer, DiagnosticTest
from app.models.enums import Department, Difficulty, Level
from app.models.question import Question
from app.models.user import User
from app.schemas.diagnostic import DiagnosticAnswerInput

logger = logging.getLogger(__name__)


# === 문항셋 구성 정책 ===
DIAGNOSTIC_TEST_SIZE = 30  # 학과별 진단 테스트 문항 수 (조정 가능)
DIFFICULTY_RATIO = {
    Difficulty.EASY: 0.30,
    Difficulty.MEDIUM: 0.50,
    Difficulty.HARD: 0.20,
}


# === 예외 ===
class DiagnosticError(Exception):
    """진단 테스트 비즈니스 예외."""

    pass


class AlreadyTakenError(DiagnosticError):
    """이미 진단 테스트를 응시한 사용자."""

    pass


class TestNotFoundError(DiagnosticError):
    pass


class TestAlreadyCompletedError(DiagnosticError):
    pass


class InsufficientQuestionsError(DiagnosticError):
    """문제은행에 충분한 문항이 없을 때."""

    pass


# === 내부 헬퍼 ===
class _ScoreBreakdown(TypedDict):
    correct: int
    total: int


def _compute_section_scores(
    answers: list[tuple[Question, bool]],
) -> dict[str, float]:
    """과목별 정답률 계산.

    Returns
    -------
    dict[str, float]
        예: {"성인간호학": 0.72, "기본간호학": 0.55}
    """
    bucket: dict[str, _ScoreBreakdown] = defaultdict(
        lambda: {"correct": 0, "total": 0}
    )
    for q, is_correct in answers:
        b = bucket[q.subject]
        b["total"] += 1
        if is_correct:
            b["correct"] += 1
    return {
        subject: round(b["correct"] / b["total"], 4) if b["total"] else 0.0
        for subject, b in bucket.items()
    }


def _extract_weak_areas(
    answers: list[tuple[Question, bool]],
    *,
    threshold: float = 0.6,
    max_items: int = 8,
) -> list[dict]:
    """취약영역 추출 — 과목+단원 단위로 정답률이 낮은 순으로 정렬.

    Parameters
    ----------
    threshold : float
        이 값 미만인 영역만 weak로 분류 (기본 60%).
    max_items : int
        최대 반환 개수.

    Returns
    -------
    list[dict]
        [{subject, unit, score, priority, correct_count, total_count}]
    """
    bucket: dict[tuple[str, str | None], _ScoreBreakdown] = defaultdict(
        lambda: {"correct": 0, "total": 0}
    )
    for q, is_correct in answers:
        key = (q.subject, q.unit)
        b = bucket[key]
        b["total"] += 1
        if is_correct:
            b["correct"] += 1

    items = []
    for (subject, unit), b in bucket.items():
        if b["total"] == 0:
            continue
        score = b["correct"] / b["total"]
        if score < threshold:
            items.append(
                {
                    "subject": subject,
                    "unit": unit,
                    "score": round(score, 4),
                    "correct_count": b["correct"],
                    "total_count": b["total"],
                }
            )

    items.sort(key=lambda x: (x["score"], -x["total_count"]))
    items = items[:max_items]
    for i, item in enumerate(items, start=1):
        item["priority"] = i
    return items


def _determine_level(total_score: float) -> Level:
    """전체 정답률 기반 학습 수준 결정."""
    if total_score >= 0.80:
        return Level.ADVANCED
    if total_score >= 0.50:
        return Level.INTERMEDIATE
    return Level.BEGINNER


async def _build_diagnostic_question_set(
    db: AsyncSession, department: Department
) -> list[Question]:
    """학과별 진단 문항셋 자동 구성.

    전략
    ----
    1. 학과 내 모든 과목 distinct를 가져온다.
    2. 과목당 균등 배분 (`DIAGNOSTIC_TEST_SIZE / num_subjects`).
    3. 각 과목 안에서 난이도 비율(EASY 30 / MEDIUM 50 / HARD 20)을 맞춰 무작위 추출.
    4. 부족분은 다른 난이도/과목에서 채운다.
    """
    # 학과 내 과목 distinct
    subjects_stmt = (
        select(Question.subject)
        .where(Question.department == department)
        .distinct()
        .order_by(Question.subject)
    )
    subjects = [r[0] for r in (await db.execute(subjects_stmt)).all()]
    if not subjects:
        raise InsufficientQuestionsError(
            f"학과 {department.value}에 등록된 문제가 없습니다."
        )

    per_subject = max(1, DIAGNOSTIC_TEST_SIZE // len(subjects))
    selected: list[Question] = []
    seen_ids: set[uuid.UUID] = set()

    for subject in subjects:
        # 과목 내 모든 문제 로드
        q_stmt = select(Question).where(
            Question.department == department,
            Question.subject == subject,
        )
        all_questions = list((await db.execute(q_stmt)).scalars().all())

        # 난이도별 분리
        by_difficulty: dict[Difficulty, list[Question]] = defaultdict(list)
        for q in all_questions:
            by_difficulty[q.difficulty].append(q)

        # 과목별 목표 개수에서 난이도 배분
        chosen: list[Question] = []
        for diff, ratio in DIFFICULTY_RATIO.items():
            want = max(1, round(per_subject * ratio))
            pool = by_difficulty.get(diff, [])
            if pool:
                chosen.extend(random.sample(pool, k=min(want, len(pool))))

        # 과목 내 부족분은 무작위로 채움
        remaining = per_subject - len(chosen)
        if remaining > 0:
            extras = [q for q in all_questions if q not in chosen]
            random.shuffle(extras)
            chosen.extend(extras[:remaining])

        for q in chosen:
            if q.id not in seen_ids:
                selected.append(q)
                seen_ids.add(q.id)

    # 전체 부족분은 학과 내 무작위로 채움 (또는 초과분 자르기)
    if len(selected) < DIAGNOSTIC_TEST_SIZE:
        leftover_stmt = (
            select(Question)
            .where(
                Question.department == department,
                Question.id.notin_(seen_ids) if seen_ids else True,
            )
            .limit(DIAGNOSTIC_TEST_SIZE * 2)
        )
        leftovers = list((await db.execute(leftover_stmt)).scalars().all())
        random.shuffle(leftovers)
        for q in leftovers:
            if len(selected) >= DIAGNOSTIC_TEST_SIZE:
                break
            if q.id not in seen_ids:
                selected.append(q)
                seen_ids.add(q.id)

    if not selected:
        raise InsufficientQuestionsError(
            f"학과 {department.value}에 등록된 문제가 없습니다."
        )

    selected = selected[:DIAGNOSTIC_TEST_SIZE]
    random.shuffle(selected)
    return selected


# === Public API ===
async def start_diagnostic_test(db: AsyncSession, user: User) -> DiagnosticTest:
    """진단 테스트 1회 시작.

    이미 응시한 학생은 AlreadyTakenError를 발생시킨다.
    """
    existing = await db.scalar(
        select(DiagnosticTest).where(DiagnosticTest.user_id == user.id)
    )
    if existing is not None:
        raise AlreadyTakenError(
            "이미 진단 테스트를 응시했습니다. (사용자당 1회)"
        )

    questions = await _build_diagnostic_question_set(db, user.department)

    test = DiagnosticTest(user_id=user.id, started_at=datetime.now(UTC))
    db.add(test)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise AlreadyTakenError("이미 진단 테스트를 응시했습니다.") from exc

    # 문항을 메모리에 부착해두고 라우터에서 응답에 사용
    test._questions_for_response = questions  # type: ignore[attr-defined]
    return test


async def submit_diagnostic_test(
    db: AsyncSession,
    user: User,
    test_id: uuid.UUID,
    answers_input: list[DiagnosticAnswerInput],
) -> DiagnosticTest:
    """진단 테스트 응답 제출 → 채점 → 결과 저장.

    검증
    ----
    - 본인의 테스트인지 확인
    - 이미 완료된 테스트는 거부
    - 선택지 인덱스 범위 검증

    Returns
    -------
    DiagnosticTest
        채점된 진단 테스트.
    """
    test = await db.get(
        DiagnosticTest,
        test_id,
        options=[selectinload(DiagnosticTest.answers)],
    )
    if test is None:
        raise TestNotFoundError(f"DiagnosticTest {test_id} not found")
    if test.user_id != user.id:
        raise TestNotFoundError("Forbidden — not your diagnostic test")
    if test.completed_at is not None:
        raise TestAlreadyCompletedError(
            "이미 완료된 진단 테스트입니다."
        )

    # 응답 문항 일괄 로드
    question_ids = [a.question_id for a in answers_input]
    if not question_ids:
        raise DiagnosticError("응답이 비어있습니다.")

    q_stmt = select(Question).where(Question.id.in_(question_ids))
    q_map = {q.id: q for q in (await db.execute(q_stmt)).scalars().all()}

    # 누락 확인
    missing = [qid for qid in question_ids if qid not in q_map]
    if missing:
        raise DiagnosticError(f"존재하지 않는 문항 ID: {missing[:3]}...")

    scored: list[tuple[Question, bool]] = []
    for ans in answers_input:
        q = q_map[ans.question_id]
        if ans.selected_choice >= len(q.choices):
            raise DiagnosticError(
                f"문항 {q.id}: 선택지 인덱스({ans.selected_choice})가 범위를 벗어났습니다."
            )
        is_correct = ans.selected_choice == q.correct_answer
        scored.append((q, is_correct))

        db.add(
            DiagnosticAnswer(
                test_id=test.id,
                question_id=q.id,
                selected_choice=ans.selected_choice,
                is_correct=is_correct,
                time_spent_sec=ans.time_spent_sec,
            )
        )

    # 채점
    total_count = len(scored)
    correct_count = sum(1 for _, c in scored if c)
    total_score = round(correct_count / total_count, 4) if total_count else 0.0

    test.completed_at = datetime.now(UTC)
    test.total_score = total_score
    test.section_scores = _compute_section_scores(scored)
    test.weak_areas = _extract_weak_areas(scored)
    test.level = _determine_level(total_score)

    await db.flush()
    await db.refresh(test, ["answers"])
    logger.info(
        "Diagnostic completed: user=%s score=%.2f level=%s weak=%d",
        user.id,
        total_score,
        test.level.value,
        len(test.weak_areas or []),
    )
    return test


async def get_diagnostic_test_for_user(
    db: AsyncSession, user_id: uuid.UUID
) -> DiagnosticTest | None:
    """특정 사용자의 진단 테스트(있다면) 조회."""
    return await db.scalar(
        select(DiagnosticTest)
        .where(DiagnosticTest.user_id == user_id)
        .options(selectinload(DiagnosticTest.answers))
    )
