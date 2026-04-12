"""실습 평가 서비스 — 점수 계산, 등급 판정, LLM 피드백 생성."""

from __future__ import annotations

import json
import logging
import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EvalGrade, EvalStatus, PracticumCategory
from app.models.practicum import PracticumScenario, PracticumSession

logger = logging.getLogger(__name__)


def calculate_score(
    checklist_items: list[dict],
    checklist_results: list[dict],
    total_points: int,
) -> tuple[int, EvalGrade, bool]:
    """체크리스트 결과에서 점수·등급 산출.

    Returns (total_score, grade, has_critical_failure)
    """
    result_map = {r["item_id"]: r for r in checklist_results}
    item_map = {item["id"]: item for item in checklist_items}

    earned = 0
    has_critical_failure = False

    for item in checklist_items:
        result = result_map.get(item["id"])
        if not result:
            if item.get("is_critical"):
                has_critical_failure = True
            continue
        earned += result.get("points_earned", 0)
        if item.get("is_critical") and result.get("status") in ("fail", "danger"):
            has_critical_failure = True

    if has_critical_failure:
        return earned, EvalGrade.FAIL, True

    pct = (earned / total_points * 100) if total_points > 0 else 0
    if pct >= 90:
        grade = EvalGrade.EXCELLENT
    elif pct >= 75:
        grade = EvalGrade.GOOD
    elif pct >= 60:
        grade = EvalGrade.NEEDS_IMPROVEMENT
    else:
        grade = EvalGrade.FAIL

    return earned, grade, False


async def generate_feedback(
    scenario: PracticumScenario,
    checklist_results: list[dict],
    total_score: int,
    grade: EvalGrade,
) -> dict:
    """LLM Gateway로 3단 피드백 생성."""
    from app.core.llm import get_llm_gateway

    items_text = ""
    item_map = {item["id"]: item for item in scenario.checklist_items}
    for r in checklist_results:
        item = item_map.get(r["item_id"], {})
        label = item.get("label", r["item_id"])
        critical = " [필수]" if item.get("is_critical") else ""
        items_text += f"- {label}{critical}: {r['status']} ({r['points_earned']}/{item.get('points', 0)}점)\n"

    cat_label = PracticumCategory(scenario.category.value).label_ko if scenario.category else scenario.name

    system_prompt = (
        "당신은 한국 보건의료 실습 평가 전문 튜터입니다. "
        "학생의 실습 수행 체크리스트 결과를 바탕으로 3가지 관점의 피드백을 제공합니다: "
        "1) 잘한 점 (good) 2) 부족한 점 (needs_improvement) 3) 개선 방법 (suggestions). "
        "각 관점마다 2~4개 항목을 구체적이고 실무 중심으로 한국어로 작성합니다. "
        "반드시 JSON 형식으로만 응답하세요: "
        '{"good": ["...", "..."], "needs_improvement": ["...", "..."], "suggestions": ["...", "..."]}'
    )

    user_prompt = (
        f"실습 유형: {cat_label}\n"
        f"학과: {scenario.department.label_ko}\n"
        f"총점: {total_score}/{scenario.total_points} ({grade.label_ko})\n\n"
        f"체크리스트 결과:\n{items_text}"
    )

    try:
        gateway = get_llm_gateway()
        result = await gateway.generate(system=system_prompt, user=user_prompt)
        text = result.content

        # JSON 추출 (코드블록 or 직접)
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            return json.loads(json_match.group())
    except Exception:
        logger.exception("LLM feedback generation failed, using fallback")

    # Fallback: 체크리스트 결과로 자동 생성
    return _fallback_feedback(checklist_results, {item["id"]: item for item in scenario.checklist_items})


def _fallback_feedback(results: list[dict], item_map: dict) -> dict:
    """LLM 실패 시 규칙 기반 피드백."""
    good = []
    bad = []
    suggestions = []

    for r in results:
        item = item_map.get(r["item_id"], {})
        label = item.get("label", r["item_id"])
        if r["status"] == "success":
            good.append(f"{label} 항목을 정확하게 수행했습니다.")
        elif r["status"] == "partial":
            bad.append(f"{label} 항목이 부분적으로만 수행되었습니다.")
            suggestions.append(f"{label} 절차를 다시 복습하세요.")
        elif r["status"] in ("fail", "danger"):
            bad.append(f"{label} 항목이 누락되거나 부정확합니다.")
            suggestions.append(f"{label} 관련 실습을 반복 연습하세요.")

    return {
        "good": good[:4] or ["제출해주셔서 감사합니다."],
        "needs_improvement": bad[:4] or ["특이사항 없음"],
        "suggestions": suggestions[:4] or ["전반적으로 양호합니다."],
    }


async def ai_evaluate_checklist(
    scenario: PracticumScenario,
    video_description: str,
) -> list[dict]:
    """LLM이 영상 설명을 보고 체크리스트 항목별 자동 판정.

    Returns list of {item_id, status, points_earned}
    """
    from app.core.llm import get_llm_gateway

    items_text = ""
    for item in scenario.checklist_items:
        critical = " [필수항목]" if item.get("is_critical") else ""
        items_text += f'- id="{item["id"]}", label="{item["label"]}", points={item["points"]}{critical}\n'

    cat_label = PracticumCategory(scenario.category.value).label_ko

    system_prompt = (
        "당신은 한국 보건의료 실습 평가 AI입니다. "
        "학생이 촬영한 실습 영상에 대한 설명을 읽고, 체크리스트 각 항목을 평가합니다. "
        "각 항목에 대해 status와 points_earned를 판정하세요.\n"
        "status 옵션: success(완벽 수행, 만점), partial(부분 수행, 50%), fail(미수행, 0점), danger(위험행동, 0점)\n"
        "반드시 JSON 배열로만 응답하세요:\n"
        '[{"item_id": "...", "status": "success|partial|fail|danger", "points_earned": N}, ...]'
    )

    user_prompt = (
        f"실습 유형: {cat_label} ({scenario.name})\n"
        f"학과: {scenario.department.label_ko}\n\n"
        f"체크리스트 항목:\n{items_text}\n"
        f"학생 실습 수행 설명:\n{video_description}"
    )

    try:
        gateway = get_llm_gateway()
        result = await gateway.generate(system=system_prompt, user=user_prompt)
        text = result.content

        json_match = re.search(r"\[[\s\S]*\]", text)
        if json_match:
            parsed = json.loads(json_match.group())
            # 유효성 검증
            valid_ids = {item["id"] for item in scenario.checklist_items}
            return [
                r for r in parsed
                if r.get("item_id") in valid_ids and r.get("status") in ("success", "partial", "fail", "danger")
            ]
    except Exception:
        logger.exception("AI checklist evaluation failed, using fallback")

    # Fallback: 모두 partial로 처리
    return [
        {"item_id": item["id"], "status": "partial", "points_earned": item["points"] // 2}
        for item in scenario.checklist_items
    ]


def generate_join_code() -> str:
    """4자리 참여 코드 생성."""
    import random
    return str(random.randint(1000, 9999))


async def get_student_practicum_stats(
    db: AsyncSession, student_id: uuid.UUID,
) -> dict:
    """학생 실습 통계."""
    stmt = (
        select(PracticumSession)
        .where(
            PracticumSession.student_id == student_id,
            PracticumSession.status.in_([EvalStatus.SUBMITTED, EvalStatus.REVIEWED]),
        )
        .order_by(PracticumSession.created_at.desc())
    )
    rows = list((await db.execute(stmt)).scalars().all())

    if not rows:
        return {"total_sessions": 0, "avg_score": 0, "grades": {}, "by_category": {}}

    total = len(rows)
    avg = sum(s.total_score or 0 for s in rows) / total

    grades: dict[str, int] = {}
    by_cat: dict[str, list[int]] = {}
    for s in rows:
        g = s.grade.value if s.grade else "UNKNOWN"
        grades[g] = grades.get(g, 0) + 1

    return {
        "total_sessions": total,
        "avg_score": round(avg, 1),
        "grades": grades,
        "recent": [
            {
                "id": str(s.id),
                "scenario_id": str(s.scenario_id),
                "score": s.total_score,
                "grade": s.grade.value if s.grade else None,
                "status": s.status.value,
                "created_at": s.created_at.isoformat(),
            }
            for s in rows[:10]
        ],
    }
