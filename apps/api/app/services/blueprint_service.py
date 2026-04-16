"""국가고시 블루프린트 서비스 (v0.7).

- 국가고시 과목 체계 매핑
- 출제 영역별 비중 반영
- 역량 단위 약점 분석
- 시험 직전 집중 모드 문제 세트
- 교수용 커리큘럼 커버리지 체크
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Department, Difficulty
from app.models.exam_blueprint import ExamBlueprint
from app.models.learning_history import LearningHistory
from app.models.question import Question

logger = logging.getLogger(__name__)


# === 국가고시 기본 블루프린트 데이터 ===
# 간호사 국시 8개 과목 비중 (실제 출제 비중 근사치)
NURSING_BLUEPRINT = [
    {"subject": "성인간호학", "weight": 0.30, "areas": ["호흡기계", "순환기계", "소화기계", "비뇨기계", "근골격계", "신경계", "내분비계", "혈액종양"]},
    {"subject": "기본간호학", "weight": 0.15, "areas": ["간호과정", "활력징후", "투약", "영양", "배설", "상처간호", "감염관리"]},
    {"subject": "모성간호학", "weight": 0.10, "areas": ["임신기", "분만기", "산욕기", "신생아", "여성건강"]},
    {"subject": "아동간호학", "weight": 0.10, "areas": ["성장발달", "영아기", "유아기", "학령기", "청소년기"]},
    {"subject": "정신간호학", "weight": 0.10, "areas": ["정신건강", "불안장애", "기분장애", "조현병", "인격장애", "물질관련장애"]},
    {"subject": "지역사회간호학", "weight": 0.10, "areas": ["보건사업", "역학", "가족간호", "산업간호", "환경보건"]},
    {"subject": "간호관리학", "weight": 0.10, "areas": ["간호관리", "리더십", "질관리", "법적윤리", "인적자원관리"]},
    {"subject": "보건의약관계법규", "weight": 0.05, "areas": ["의료법", "간호사법", "감염병관리법", "정신건강복지법"]},
]

PHYSICAL_THERAPY_BLUEPRINT = [
    {"subject": "물리치료학개론", "weight": 0.10, "areas": ["물리치료 역사", "물리치료 범위", "윤리"]},
    {"subject": "근골격계물리치료", "weight": 0.20, "areas": ["관절가동범위", "도수치료", "근력강화", "자세교정"]},
    {"subject": "신경계물리치료", "weight": 0.20, "areas": ["중추신경계", "말초신경계", "뇌졸중재활", "척수손상"]},
    {"subject": "전기광선치료학", "weight": 0.15, "areas": ["전기치료", "초음파", "레이저", "온열치료"]},
    {"subject": "운동치료학", "weight": 0.15, "areas": ["치료운동", "보행분석", "호흡재활", "심장재활"]},
    {"subject": "해부생리학", "weight": 0.10, "areas": ["골격계", "근육계", "신경계", "순환계"]},
    {"subject": "보건의약관계법규", "weight": 0.10, "areas": ["의료법", "물리치료사법", "장애인복지법"]},
]

DENTAL_HYGIENE_BLUEPRINT = [
    {"subject": "치위생학개론", "weight": 0.10, "areas": ["치위생 역사", "업무범위", "윤리"]},
    {"subject": "구강해부학", "weight": 0.15, "areas": ["치아해부", "두개골", "구강조직", "악관절"]},
    {"subject": "치주학", "weight": 0.15, "areas": ["치주조직", "치주질환", "스케일링", "치근활택"]},
    {"subject": "구강병리학", "weight": 0.10, "areas": ["구강질환", "구강암", "낭종", "감염"]},
    {"subject": "예방치학", "weight": 0.15, "areas": ["불소도포", "치면세마", "실란트", "구강보건교육"]},
    {"subject": "치과재료학", "weight": 0.10, "areas": ["인상재", "합착재", "수복재", "의치재료"]},
    {"subject": "치과방사선학", "weight": 0.10, "areas": ["방사선물리", "구내촬영", "파노라마", "방사선방어"]},
    {"subject": "보건의약관계법규", "weight": 0.15, "areas": ["의료법", "치위생사법", "구강보건법"]},
]

BLUEPRINT_DATA: dict[Department, list[dict]] = {
    Department.NURSING: NURSING_BLUEPRINT,
    Department.PHYSICAL_THERAPY: PHYSICAL_THERAPY_BLUEPRINT,
    Department.DENTAL_HYGIENE: DENTAL_HYGIENE_BLUEPRINT,
}


async def seed_blueprint(db: AsyncSession, department: Department) -> int:
    """블루프린트 시드 데이터 적재."""
    data = BLUEPRINT_DATA.get(department, [])
    count = 0
    exam_name = {
        Department.NURSING: "간호사 국가시험",
        Department.PHYSICAL_THERAPY: "물리치료사 국가시험",
        Department.DENTAL_HYGIENE: "치과위생사 국가시험",
    }.get(department, "국가시험")

    for item in data:
        for area in item["areas"]:
            existing = await db.scalar(
                select(ExamBlueprint).where(
                    ExamBlueprint.department == department,
                    ExamBlueprint.exam_name == exam_name,
                    ExamBlueprint.subject == item["subject"],
                    ExamBlueprint.area == area,
                )
            )
            if not existing:
                bp = ExamBlueprint(
                    department=department,
                    exam_name=exam_name,
                    subject=item["subject"],
                    area=area,
                    weight_pct=item["weight"] / len(item["areas"]),
                    keywords=[],
                )
                db.add(bp)
                count += 1
    await db.flush()
    return count


async def get_blueprint(db: AsyncSession, department: Department) -> list[dict]:
    """학과별 블루프린트 조회."""
    rows = (await db.execute(
        select(ExamBlueprint)
        .where(ExamBlueprint.department == department)
        .order_by(ExamBlueprint.subject, ExamBlueprint.area)
    )).scalars().all()

    return [
        {
            "id": str(bp.id),
            "subject": bp.subject,
            "area": bp.area,
            "sub_area": bp.sub_area,
            "weight_pct": bp.weight_pct,
            "question_count": bp.question_count,
            "competency": bp.competency,
            "keywords": bp.keywords,
        }
        for bp in rows
    ]


async def get_competency_weakness(
    db: AsyncSession, user_id: uuid.UUID, department: Department,
) -> list[dict]:
    """역량 단위 약점 분석 — 블루프린트 영역별 정답률."""
    # 문제의 national_exam_mapping을 블루프린트 영역과 매칭
    result = await db.execute(
        select(
            Question.subject,
            Question.national_exam_mapping,
            func.count(LearningHistory.id).label("attempts"),
            func.sum(func.cast(LearningHistory.is_correct, type(1))).label("correct"),
        )
        .join(LearningHistory, LearningHistory.question_id == Question.id)
        .where(
            LearningHistory.user_id == user_id,
            Question.department == department,
        )
        .group_by(Question.subject, Question.national_exam_mapping)
        .having(func.count(LearningHistory.id) >= 2)
        .order_by("attempts")
    )
    rows = result.all()

    # 블루프린트 비중 조회
    blueprints = await db.execute(
        select(ExamBlueprint).where(ExamBlueprint.department == department)
    )
    bp_weights = {}
    for bp in blueprints.scalars().all():
        key = f"{bp.subject}>{bp.area}"
        bp_weights[key] = bp.weight_pct

    weaknesses = []
    for row in rows:
        attempts = row.attempts
        correct = int(row.correct or 0)
        accuracy = correct / attempts if attempts else 0

        area_key = row.national_exam_mapping or row.subject
        weight = bp_weights.get(f"{row.subject}>{area_key}", 0.0)

        # 가중 약점 점수: 비중 높은데 정답률 낮은 영역이 위험
        weakness_score = weight * (1 - accuracy)

        weaknesses.append({
            "subject": row.subject,
            "area": row.national_exam_mapping or "일반",
            "attempts": attempts,
            "correct": correct,
            "accuracy": round(accuracy, 4),
            "blueprint_weight": round(weight, 4),
            "weakness_score": round(weakness_score, 4),
        })

    weaknesses.sort(key=lambda x: x["weakness_score"], reverse=True)
    return weaknesses


async def build_exam_focus_set(
    db: AsyncSession,
    user_id: uuid.UUID,
    department: Department,
    *,
    set_size: int = 30,
) -> dict:
    """시험 직전 집중 모드 — 블루프린트 비중 + 약점 기반 문제 세트.

    출제 비중에 따라 문항 배분, 약점 영역 가중.
    """
    weaknesses = await get_competency_weakness(db, user_id, department)
    weak_subjects = {w["subject"] for w in weaknesses[:5]}

    # 블루프린트 비중 기반 문항 배분
    blueprint = BLUEPRINT_DATA.get(department, [])
    allocation: dict[str, int] = {}
    for item in blueprint:
        base_count = max(1, round(set_size * item["weight"]))
        # 약점 과목은 추가 배분
        if item["subject"] in weak_subjects:
            base_count = min(set_size, int(base_count * 1.5))
        allocation[item["subject"]] = base_count

    # 과목별 문제 추출
    questions: list = []
    for subject, count in allocation.items():
        if len(questions) >= set_size:
            break
        stmt = (
            select(Question)
            .where(Question.department == department, Question.subject == subject)
            .order_by(func.random())
            .limit(count)
        )
        rows = list((await db.execute(stmt)).scalars().all())
        questions.extend(rows)

    return {
        "questions": [
            {
                "id": str(q.id),
                "subject": q.subject,
                "unit": q.unit,
                "difficulty": q.difficulty.value,
                "national_exam_mapping": q.national_exam_mapping,
            }
            for q in questions[:set_size]
        ],
        "total": len(questions[:set_size]),
        "allocation": allocation,
        "weaknesses_targeted": [w["subject"] for w in weaknesses[:5]],
    }


async def get_curriculum_coverage(
    db: AsyncSession, department: Department,
) -> list[dict]:
    """교수용 커리큘럼 커버리지 체크 — 블루프린트 영역 대비 문제은행 커버리지."""
    blueprint = await get_blueprint(db, department)

    # 과목-영역별 문제 수 집계
    question_counts = await db.execute(
        select(
            Question.subject,
            Question.national_exam_mapping,
            func.count().label("q_count"),
        )
        .where(Question.department == department)
        .group_by(Question.subject, Question.national_exam_mapping)
    )
    q_map: dict[str, int] = {}
    for row in question_counts.all():
        key = f"{row.subject}>{row.national_exam_mapping or '일반'}"
        q_map[key] = row.q_count

    result = []
    for bp in blueprint:
        key = f"{bp['subject']}>{bp['area']}"
        q_count = q_map.get(key, 0)
        # 비중 대비 충분한 문제가 있는지 평가
        expected = max(5, round(100 * bp["weight_pct"]))
        coverage = min(1.0, q_count / expected) if expected > 0 else 0

        result.append({
            **bp,
            "question_count_actual": q_count,
            "question_count_expected": expected,
            "coverage": round(coverage, 4),
            "status": "충분" if coverage >= 0.8 else "부족" if coverage >= 0.3 else "미비",
        })

    return result
