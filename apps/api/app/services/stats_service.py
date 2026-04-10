"""통계 서비스 — 문항별 응답 통계 + 백분위 + 트래킹 저장.

v0.2 핵심 기능
-----------
1. **문항별 통계 갱신**: 풀이 제출 시마다 question_stats 캐시 업데이트
2. **문항별 통계 조회**: 정답률, 선택지별 선택률, 응시자 수
3. **학생 백분위**: 전체/과목별 정답률 기준 상위 몇% 계산
4. **트래킹 저장**: answer_interactions 1건 INSERT
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import Float, case, cast, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Department
from app.models.learning_history import LearningHistory
from app.models.question import Question
from app.models.question_stats import AnswerInteraction, QuestionStats

logger = logging.getLogger(__name__)


# === 트래킹 저장 ===
async def save_interaction(
    db: AsyncSession,
    *,
    history_id: uuid.UUID,
    question_id: uuid.UUID,
    user_id: uuid.UUID,
    time_spent_sec: int,
    time_to_first_click_ms: int,
    first_choice: int,
    final_choice: int,
    choice_changes: int,
    choice_sequence: list[dict],
) -> AnswerInteraction:
    """학생 행동 트래킹 1건 저장."""
    interaction = AnswerInteraction(
        history_id=history_id,
        question_id=question_id,
        user_id=user_id,
        time_spent_sec=time_spent_sec,
        time_to_first_click_ms=time_to_first_click_ms,
        first_choice=first_choice,
        final_choice=final_choice,
        choice_changes=choice_changes,
        choice_sequence=choice_sequence,
    )
    db.add(interaction)
    await db.flush()
    return interaction


# === 문항별 통계 갱신 ===
async def update_question_stats(
    db: AsyncSession,
    question_id: uuid.UUID,
) -> QuestionStats:
    """learning_history에서 해당 문항의 통계를 재집계하여 question_stats 갱신."""
    # 집계
    agg_stmt = select(
        func.count(LearningHistory.id).label("total"),
        func.coalesce(
            func.sum(case((LearningHistory.is_correct.is_(True), 1), else_=0)), 0
        ).label("correct"),
        func.coalesce(func.avg(LearningHistory.solving_time_sec), 0).label("avg_time"),
    ).where(LearningHistory.question_id == question_id)
    agg = (await db.execute(agg_stmt)).one()
    total = int(agg.total)
    correct = int(agg.correct)
    accuracy = round(correct / total, 4) if total > 0 else 0.0

    # 선택지별 분포
    dist_stmt = (
        select(
            LearningHistory.selected_choice,
            func.count(LearningHistory.id).label("cnt"),
        )
        .where(LearningHistory.question_id == question_id)
        .group_by(LearningHistory.selected_choice)
    )
    dist_rows = (await db.execute(dist_stmt)).all()
    choice_distribution = {str(r.selected_choice): int(r.cnt) for r in dist_rows}

    # 평균 선택 변경 횟수 (answer_interactions에서)
    avg_changes_stmt = select(
        func.coalesce(func.avg(AnswerInteraction.choice_changes), 0)
    ).where(AnswerInteraction.question_id == question_id)
    avg_changes = float((await db.execute(avg_changes_stmt)).scalar_one())

    # Upsert
    existing = await db.scalar(
        select(QuestionStats).where(QuestionStats.question_id == question_id)
    )
    if existing is None:
        stats = QuestionStats(
            question_id=question_id,
            total_attempts=total,
            correct_count=correct,
            accuracy=accuracy,
            choice_distribution=choice_distribution,
            avg_time_sec=round(float(agg.avg_time), 2),
            avg_choice_changes=round(avg_changes, 2),
        )
        db.add(stats)
    else:
        existing.total_attempts = total
        existing.correct_count = correct
        existing.accuracy = accuracy
        existing.choice_distribution = choice_distribution
        existing.avg_time_sec = round(float(agg.avg_time), 2)
        existing.avg_choice_changes = round(avg_changes, 2)
        stats = existing

    await db.flush()
    return stats


# === 문항별 통계 조회 ===
async def get_question_stats(
    db: AsyncSession,
    question_id: uuid.UUID,
) -> dict | None:
    """문항별 통계 조회. 없으면 실시간 집계."""
    stats = await db.scalar(
        select(QuestionStats).where(QuestionStats.question_id == question_id)
    )
    if stats is None:
        # 캐시 없으면 실시간 갱신
        stats = await update_question_stats(db, question_id)

    return {
        "question_id": str(stats.question_id),
        "total_attempts": stats.total_attempts,
        "correct_count": stats.correct_count,
        "accuracy": stats.accuracy,
        "choice_distribution": stats.choice_distribution,
        "avg_time_sec": stats.avg_time_sec,
        "avg_choice_changes": stats.avg_choice_changes,
    }


# === 학생 백분위 ===
async def get_student_percentile(
    db: AsyncSession,
    user_id: uuid.UUID,
    department: Department,
) -> dict:
    """학생의 전체/과목별 백분위 계산.

    백분위 = (나보다 정답률이 낮은 학생 수 / 전체 학생 수) × 100

    Returns
    -------
    dict
        {
            "overall_percentile": 77,  # 상위 23%
            "overall_accuracy": 0.72,
            "total_students": 150,
            "subject_percentiles": {
                "성인간호학": {"percentile": 85, "accuracy": 0.80, "total": 120},
                ...
            }
        }
    """
    # 학과 내 전체 학생별 정답률
    student_accuracy_stmt = (
        select(
            LearningHistory.user_id,
            (
                cast(
                    func.sum(case((LearningHistory.is_correct.is_(True), 1), else_=0)),
                    Float,
                )
                / func.count(LearningHistory.id)
            ).label("acc"),
        )
        .join(Question, Question.id == LearningHistory.question_id)
        .where(Question.department == department)
        .group_by(LearningHistory.user_id)
        .having(func.count(LearningHistory.id) >= 5)  # 최소 5문항 이상 풀어야
    )
    rows = (await db.execute(student_accuracy_stmt)).all()
    if not rows:
        return {
            "overall_percentile": 0,
            "overall_accuracy": 0.0,
            "total_students": 0,
            "subject_percentiles": {},
        }

    accuracies = {r.user_id: float(r.acc) for r in rows}
    my_acc = accuracies.get(user_id, 0.0)
    total = len(accuracies)
    below_me = sum(1 for a in accuracies.values() if a < my_acc)
    overall_percentile = round(below_me / total * 100) if total > 0 else 0

    # 과목별
    subject_stmt = (
        select(
            Question.subject,
            LearningHistory.user_id,
            (
                cast(
                    func.sum(case((LearningHistory.is_correct.is_(True), 1), else_=0)),
                    Float,
                )
                / func.count(LearningHistory.id)
            ).label("acc"),
        )
        .join(Question, Question.id == LearningHistory.question_id)
        .where(Question.department == department)
        .group_by(Question.subject, LearningHistory.user_id)
        .having(func.count(LearningHistory.id) >= 3)
    )
    subj_rows = (await db.execute(subject_stmt)).all()

    from collections import defaultdict

    by_subject: dict[str, dict[uuid.UUID, float]] = defaultdict(dict)
    for r in subj_rows:
        by_subject[r.subject][r.user_id] = float(r.acc)

    subject_percentiles = {}
    for subj, accs in by_subject.items():
        my_subj_acc = accs.get(user_id, 0.0)
        subj_total = len(accs)
        subj_below = sum(1 for a in accs.values() if a < my_subj_acc)
        subject_percentiles[subj] = {
            "percentile": round(subj_below / subj_total * 100) if subj_total > 0 else 0,
            "accuracy": round(my_subj_acc, 4),
            "total": subj_total,
        }

    return {
        "overall_percentile": overall_percentile,
        "overall_accuracy": round(my_acc, 4),
        "total_students": total,
        "subject_percentiles": subject_percentiles,
    }
