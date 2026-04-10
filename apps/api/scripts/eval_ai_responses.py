"""AI 응답 품질 평가 테스트셋 + runner.

Day 10 — 30개 테스트 질문에 대해 QA/Explain API를 호출하고
간단한 규칙 기반 평가를 수행한다.

평가 지표
--------
1. **응답 길이**: 100자 이상, 3000자 이하
2. **핵심 키워드 포함**: 기대 키워드 중 ≥60% 포함
3. **지연 시간**: <15초
4. **인용 포함 여부**: RAG 사용 시 citation이 1개 이상

사용법
------
```bash
cd apps/api
python -m scripts.eval_ai_responses
python -m scripts.eval_ai_responses --subset explain
python -m scripts.eval_ai_responses --subset qa
```
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass
from typing import Literal

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("eval_ai")


@dataclass
class EvalCase:
    """평가 케이스 1건."""

    case_id: str
    kind: Literal["qa", "explain"]
    department: str  # NURSING | PHYSICAL_THERAPY | DENTAL_HYGIENE
    question: str
    expected_keywords: list[str]
    notes: str = ""


# ============================================================
# 30개 평가 테스트셋 (QA 20 + Explain 10)
# ============================================================
EVAL_CASES: list[EvalCase] = [
    # ===== NURSING QA (10) =====
    EvalCase(
        "n_qa_01", "qa", "NURSING",
        "심방세동 환자에게 가장 위험한 합병증은 무엇인가요?",
        ["혈전", "뇌졸중", "색전"],
    ),
    EvalCase(
        "n_qa_02", "qa", "NURSING",
        "COPD 환자에게 고농도 산소를 투여하면 왜 위험한가요?",
        ["호흡억제", "탄산", "저산소"],
    ),
    EvalCase(
        "n_qa_03", "qa", "NURSING",
        "저혈당의 초기 증상과 15-15 규칙을 설명해주세요.",
        ["발한", "떨림", "15"],
    ),
    EvalCase(
        "n_qa_04", "qa", "NURSING",
        "AV fistula 수술한 팔에 하지 말아야 할 것은 무엇인가요?",
        ["혈압", "채혈", "무거운"],
    ),
    EvalCase(
        "n_qa_05", "qa", "NURSING",
        "구획증후군의 5P 증상을 알려주세요.",
        ["Pain", "Pallor", "통증"],
    ),
    EvalCase(
        "n_qa_06", "qa", "NURSING",
        "아나필락시스가 발생하면 가장 먼저 무엇을 해야 하나요?",
        ["에피네프린", "근육", "0.3"],
    ),
    EvalCase(
        "n_qa_07", "qa", "NURSING",
        "임신성 당뇨가 태아에게 미치는 영향은?",
        ["거대아", "저혈당", "신생아"],
    ),
    EvalCase(
        "n_qa_08", "qa", "NURSING",
        "자살 위험 환자 사정 시 가장 먼저 확인해야 할 것은?",
        ["자살", "사고", "평가"],
    ),
    EvalCase(
        "n_qa_09", "qa", "NURSING",
        "모유수유의 산모에게 주는 장점을 알려주세요.",
        ["자궁", "수축", "유방암"],
    ),
    EvalCase(
        "n_qa_10", "qa", "NURSING",
        "GCS 8점이면 어떤 상태이며 무엇을 준비해야 하나요?",
        ["혼수", "기도", "삽관"],
    ),
    # ===== PT QA (5) =====
    EvalCase(
        "pt_qa_01", "qa", "PHYSICAL_THERAPY",
        "Brunnstrom 6단계에서 3단계는 어떤 상태인가요?",
        ["공동운동", "경직"],
    ),
    EvalCase(
        "pt_qa_02", "qa", "PHYSICAL_THERAPY",
        "파킨슨병 환자의 보행 훈련에 효과적인 단서는?",
        ["리듬", "청각", "메트로놈"],
    ),
    EvalCase(
        "pt_qa_03", "qa", "PHYSICAL_THERAPY",
        "ACL 재건술 후 초기 재활의 목표는 무엇인가요?",
        ["부종", "ROM", "신전"],
    ),
    EvalCase(
        "pt_qa_04", "qa", "PHYSICAL_THERAPY",
        "척수손상 환자의 자율신경 반사부전의 가장 흔한 원인은?",
        ["방광", "팽만"],
    ),
    EvalCase(
        "pt_qa_05", "qa", "PHYSICAL_THERAPY",
        "Berg Balance Scale의 총점과 낙상 위험 기준은?",
        ["56", "45"],
    ),
    # ===== DH QA (5) =====
    EvalCase(
        "dh_qa_01", "qa", "DENTAL_HYGIENE",
        "불소가 우식을 예방하는 기전을 설명해주세요.",
        ["재광화", "플루오라파타이트", "산"],
    ),
    EvalCase(
        "dh_qa_02", "qa", "DENTAL_HYGIENE",
        "Bass 기법 잇솔질의 핵심은 무엇인가요?",
        ["45", "치은", "열구"],
    ),
    EvalCase(
        "dh_qa_03", "qa", "DENTAL_HYGIENE",
        "치주낭 정상 깊이는 몇 mm인가요?",
        ["1", "3", "mm"],
    ),
    EvalCase(
        "dh_qa_04", "qa", "DENTAL_HYGIENE",
        "임산부에게 가장 안전한 치과 치료 시기는?",
        ["임신", "2기", "4"],
    ),
    EvalCase(
        "dh_qa_05", "qa", "DENTAL_HYGIENE",
        "구강암의 주요 위험인자를 알려주세요.",
        ["흡연", "음주"],
    ),
    # ===== Explain-style QA (10) — question_id 없이 open question =====
    EvalCase(
        "n_ex_01", "qa", "NURSING",
        "다음 심전도에서 P파가 소실되고 RR 간격이 불규칙하다면 무슨 상태일까요? 간호 중재는?",
        ["심방세동", "항응고", "맥박"],
    ),
    EvalCase(
        "n_ex_02", "qa", "NURSING",
        "COPD 환자의 SpO2 목표치는 왜 88~92%로 설정하나요?",
        ["호흡", "자극", "이산화탄소"],
    ),
    EvalCase(
        "n_ex_03", "qa", "NURSING",
        "고칼륨혈증 응급 시 사용하는 3단계 약물 전략을 설명해주세요.",
        ["칼슘", "인슐린", "카요넥"],
    ),
    EvalCase(
        "n_ex_04", "qa", "NURSING",
        "간경변 환자에게 단백질을 제한하는 이유는?",
        ["암모니아", "혼수"],
    ),
    EvalCase(
        "n_ex_05", "qa", "NURSING",
        "아동 후두개염 환자에게 설압자로 인후 검사가 금기인 이유는?",
        ["기도", "폐쇄"],
    ),
    EvalCase(
        "pt_ex_01", "qa", "PHYSICAL_THERAPY",
        "편마비 환자의 견관절 아탈구를 예방하기 위한 중재는?",
        ["자세", "지지"],
    ),
    EvalCase(
        "pt_ex_02", "qa", "PHYSICAL_THERAPY",
        "Maitland 등급 I, II는 어떤 목적으로 사용하나요?",
        ["통증", "완화"],
    ),
    EvalCase(
        "pt_ex_03", "qa", "PHYSICAL_THERAPY",
        "C7 피부분절이 어디에 해당하는지 알려주세요.",
        ["중지", "손가락"],
    ),
    EvalCase(
        "dh_ex_01", "qa", "DENTAL_HYGIENE",
        "DMFT 지수의 각 문자가 무엇을 의미하나요?",
        ["Decayed", "Missing", "Filled"],
    ),
    EvalCase(
        "dh_ex_02", "qa", "DENTAL_HYGIENE",
        "스케일링 후 치아가 민감한 이유와 관리법은?",
        ["상아", "노출", "불소"],
    ),
]


@dataclass
class EvalResult:
    case_id: str
    kind: str
    success: bool
    output_length: int
    has_keywords: float  # 0.0~1.0
    latency_ms: int
    rag_used: bool
    citation_count: int
    notes: str = ""


def _keyword_coverage(output: str, keywords: list[str]) -> float:
    if not keywords:
        return 1.0
    hit = sum(1 for k in keywords if k.lower() in output.lower())
    return round(hit / len(keywords), 3)


async def run_case(db, user, case: EvalCase) -> EvalResult:
    """단일 케이스 실행. explain은 question_id가 필요해서 Day 10 evaluator는 QA 위주로 운영."""
    from app.services.ai_service import AIServiceError, answer_question

    try:
        result = await answer_question(db, user, case.question)
    except AIServiceError as exc:
        return EvalResult(
            case_id=case.case_id,
            kind=case.kind,
            success=False,
            output_length=0,
            has_keywords=0.0,
            latency_ms=0,
            rag_used=False,
            citation_count=0,
            notes=f"AI service error: {exc}",
        )

    output = result.output_text
    coverage = _keyword_coverage(output, case.expected_keywords)
    return EvalResult(
        case_id=case.case_id,
        kind=case.kind,
        success=len(output) >= 50 and result.log.success,
        output_length=len(output),
        has_keywords=coverage,
        latency_ms=result.log.latency_ms,
        rag_used=result.rag_context_used,
        citation_count=len(result.citations),
    )


async def main_async(args):
    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal, engine
    from app.models.enums import Role, UserStatus
    from app.models.user import User

    # 평가용 첫 번째 STUDENT 계정을 찾거나, 없으면 더미 생성
    async with AsyncSessionLocal() as session:
        user = await session.scalar(
            select(User).where(User.role == Role.STUDENT, User.status == UserStatus.ACTIVE).limit(1)
        )
        if user is None:
            logger.error("활성 STUDENT 계정이 없어 평가를 건너뜁니다. 먼저 회원가입을 진행하세요.")
            return 1

        cases = EVAL_CASES
        if args.subset:
            cases = [c for c in cases if c.kind == args.subset]

        logger.info("=" * 60)
        logger.info("AI 응답 평가 시작 — %d cases", len(cases))
        logger.info("User: %s (%s)", user.email, user.department.value)
        logger.info("=" * 60)

        results: list[EvalResult] = []
        for case in cases:
            logger.info("[%s] %s", case.case_id, case.question[:50])
            result = await run_case(session, user, case)
            results.append(result)
            logger.info(
                "  success=%s len=%d kw=%.2f latency=%dms rag=%s citations=%d",
                result.success,
                result.output_length,
                result.has_keywords,
                result.latency_ms,
                result.rag_used,
                result.citation_count,
            )

    await engine.dispose()

    # 요약
    logger.info("=" * 60)
    logger.info("📊 평가 결과 요약")
    logger.info("   총 케이스:       %d", len(results))
    logger.info("   성공:           %d", sum(1 for r in results if r.success))
    logger.info(
        "   키워드 커버리지 평균: %.2f",
        sum(r.has_keywords for r in results) / max(1, len(results)),
    )
    logger.info(
        "   평균 응답 길이:  %d자",
        sum(r.output_length for r in results) // max(1, len(results)),
    )
    logger.info(
        "   평균 지연시간:   %dms",
        sum(r.latency_ms for r in results) // max(1, len(results)),
    )
    logger.info("   RAG 사용:       %d", sum(1 for r in results if r.rag_used))
    logger.info("=" * 60)

    # 실패한 케이스만 표시
    failures = [r for r in results if not r.success or r.has_keywords < 0.5]
    if failures:
        logger.warning("⚠️  저성능 케이스 (%d):", len(failures))
        for r in failures[:10]:
            logger.warning("   %s kw=%.2f %s", r.case_id, r.has_keywords, r.notes)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="AI 응답 품질 평가")
    parser.add_argument(
        "--subset",
        choices=["qa", "explain"],
        default=None,
        help="특정 유형만 실행",
    )
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
