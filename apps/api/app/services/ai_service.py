"""AI 서비스 — 문제 해설/QA + RAG + 호출 로깅 + latency 측정 + 신뢰성.

v0.5 신뢰성 강화
----------------
- explain / qa 모두 RAG 통합 (KB 검색 결과�� 프롬프트에 주입)
- 학생 프로파일(level/취약영역) 동적 주입
- 인용(citation) 추출 및 로그 저장
- **확신도(confidence) 판정** — RAG 근거 유무 기반
- **위험 문장 패턴 필터링** — 의료 위험 표현 경고 태그 삽입
- **교수 승인 지식 우선 검색** — PUBLISHED 상태 문서 최우선
- **RAG 결과 없을 시 단정 답변 방지 로직**
- **AI 생성 결과 평가 로그** — confidence, has_citations, content_warnings 메타데이터 저장
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import LLMGatewayError, get_llm_gateway
from app.core.llm.base import LLMGenerationResult
from app.models.ai_profile import AIProfile
from app.models.ai_request_log import AIRequestLog
from app.models.enums import AIRequestType
from app.models.learning_history import LearningHistory
from app.models.question import Question
from app.models.user import User
from app.services.prompt_templates import (
    build_explain_context,
    build_qa_context,
    get_template,
)
from app.services.rag_service import (
    Citation,
    RAGContext,
    StudentContext,
    extract_used_citations,
    format_student_context_block,
    load_student_context,
    retrieve,
)


class ConfidenceLevel(str, Enum):
    """AI 답변 확신도 — RAG 근거 유무 기반."""
    HIGH = "HIGH"          # RAG 출처 있음 + 인용 사용됨
    MEDIUM = "MEDIUM"      # RAG 출처 있으나 인용 불충분
    LOW = "LOW"            # RAG 출처 없음, 일반 지식 기반
    UNVERIFIED = "UNVERIFIED"  # RAG 미사용 또는 실패


@dataclass
class ContentWarning:
    """위험 문장 패턴 탐지 결과."""
    pattern_name: str
    matched_text: str
    severity: str  # "info" | "warning" | "critical"


@dataclass
class AIExplainResult:
    """Explain/QA 서비스 결과 컨테이너 (v0.5 확장)."""

    log: AIRequestLog
    output_text: str
    citations: list[Citation]
    rag_context_used: bool
    # v0.5 신뢰성 필드
    confidence: ConfidenceLevel = ConfidenceLevel.UNVERIFIED
    content_warnings: list[ContentWarning] = field(default_factory=list)
    disclaimer: str = "📚 본 답변은 학습 참고용이며, 최종 판단은 담당 교수님 또는 공식 교재를 기준으로 하세요."


logger = logging.getLogger(__name__)


# === 위험 문장 패턴 (v0.5) ===
_CONTENT_SAFETY_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    (
        "drug_dosage",
        re.compile(r"\d+\s*(mg|ml|cc|mcg|iu|unit|단위)\s*(투여|주사|복용|투입)", re.IGNORECASE),
        "critical",
    ),
    (
        "clinical_instruction",
        re.compile(r"(즉시|바로|직접)\s*(투여|시행|수행|실시)하", re.IGNORECASE),
        "warning",
    ),
    (
        "definitive_diagnosis",
        re.compile(r"(확정\s*진단|~로\s*진단됩니다|진단할\s*수\s*있습니다)", re.IGNORECASE),
        "warning",
    ),
    (
        "absolute_statement",
        re.compile(r"(반드시|절대로|무조건|항상)\s+.{2,20}(해야|합니다|입니다)", re.IGNORECASE),
        "info",
    ),
]


def _detect_content_warnings(text: str) -> list[ContentWarning]:
    """응답에서 위험 문장 패턴을 감지."""
    warnings: list[ContentWarning] = []
    for name, pattern, severity in _CONTENT_SAFETY_PATTERNS:
        for match in pattern.finditer(text):
            warnings.append(ContentWarning(
                pattern_name=name,
                matched_text=match.group()[:100],
                severity=severity,
            ))
    return warnings


def _compute_confidence(
    rag_used: bool,
    citations: list[Citation],
    output_text: str,
) -> ConfidenceLevel:
    """RAG 사용 여부와 인용 수를 기반으로 확신도를 판정."""
    if not rag_used:
        return ConfidenceLevel.UNVERIFIED
    if not citations:
        return ConfidenceLevel.LOW
    # 인용이 실제 응답에 사용되었는지 검사
    citation_refs_in_text = len(re.findall(r"\[\d+\]", output_text))
    if citation_refs_in_text >= 2:
        return ConfidenceLevel.HIGH
    if citation_refs_in_text >= 1 or len(citations) >= 1:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


class AIServiceError(Exception):
    pass


class QuestionNotFoundError(AIServiceError):
    pass


class HistoryNotFoundError(AIServiceError):
    pass


async def _get_user_level(db: AsyncSession, user_id: uuid.UUID):
    """학생의 AI 프로파일에서 level을 best-effort로 가져온다."""
    profile = await db.scalar(select(AIProfile).where(AIProfile.user_id == user_id))
    return profile.level if profile else None


async def _persist_log(
    db: AsyncSession,
    *,
    user: User,
    request_type: AIRequestType,
    template_name: str,
    question_id: uuid.UUID | None,
    input_text: str,
    rendered_user_prompt: str,
    result: LLMGenerationResult | None,
    latency_ms: int,
    success: bool,
    error_message: str | None,
    provider_enum,
    retrieved_docs: list[dict] | None = None,
) -> AIRequestLog:
    """AIRequestLog 1건 INSERT — 성공/실패 모두 기록. retrieved_docs는 citation 메타."""
    log = AIRequestLog(
        user_id=user.id,
        request_type=request_type,
        template_name=template_name,
        question_id=question_id,
        input_text=input_text,
        rendered_prompt=rendered_user_prompt,
        retrieved_docs=retrieved_docs,
        output_text=result.output_text if result else None,
        finish_reason=result.finish_reason if result else None,
        provider=provider_enum,
        model=(result.model if result else "unknown"),
        input_tokens=(result.input_tokens if result else 0),
        output_tokens=(result.output_tokens if result else 0),
        latency_ms=latency_ms,
        success=success,
        error_message=error_message,
    )
    db.add(log)
    await db.flush()
    await db.refresh(log)
    return log


async def explain_question(
    db: AsyncSession,
    user: User,
    question_id: uuid.UUID,
    history_id: uuid.UUID | None = None,
    *,
    use_rag: bool = True,
) -> AIExplainResult:
    """문제 해설 생성 + RAG.

    `history_id`가 있으면 학생의 풀이 결과(선택지/정오답)를 컨텍스트로 사용하고,
    없으면 정답만으로 일반 해설을 생성한다.

    `use_rag=True` (기본) 이면 KB에서 유사 자료를 검색해 프롬프트에 주입한다.
    """
    question = await db.get(Question, question_id)
    if question is None:
        raise QuestionNotFoundError(f"Question {question_id} not found")

    selected_answer: int | None = None
    is_correct: bool | None = None
    if history_id is not None:
        history = await db.get(LearningHistory, history_id)
        if history is None or history.user_id != user.id:
            raise HistoryNotFoundError(
                f"LearningHistory {history_id} not found for current user"
            )
        if history.question_id != question_id:
            raise AIServiceError(
                "history_id가 question_id와 일치하지 않습니다."
            )
        selected_answer = history.selected_choice
        is_correct = history.is_correct

    # Day 10: 학생 프로파일 동적 주입
    student_ctx: StudentContext = await load_student_context(
        db, user.id, department=user.department
    )

    # Day 10: RAG 컨텍스트 조회
    rag_ctx: RAGContext | None = None
    if use_rag:
        rag_query = f"{question.subject} {question.unit or ''} {question.question_text[:200]}"
        rag_ctx = await retrieve(db, rag_query, department=user.department, top_k=4)

    template = get_template(AIRequestType.EXPLAIN)
    context = build_explain_context(
        question_text=question.question_text,
        choices=question.choices,
        correct_answer=question.correct_answer,
        selected_answer=selected_answer,
        is_correct=is_correct,
        explanation=question.explanation,
        department=user.department,
        level=student_ctx.level,
    )
    system, user_prompt = template.render(**context)

    # 학생 컨텍스트 블록 주입
    student_block = format_student_context_block(student_ctx)
    if student_block:
        user_prompt = f"{student_block}\n\n{user_prompt}"

    # RAG 컨텍스트 주입 + source-grounded 강제 (v0.5)
    rag_available = bool(rag_ctx and rag_ctx.formatted_text)
    if rag_available:
        rag_block = (
            "## 참고 자료 (KB에서 검색됨)\n"
            "답변에서 해당 자료를 참조할 때 반드시 [숫자] 형태로 인용하세요.\n"
            "참고 자료에 없는 내용은 추측하지 말고, '교재를 확인해 주세요'로 안내하세요.\n\n"
            f"{rag_ctx.formatted_text}"
        )
        user_prompt = f"{user_prompt}\n\n{rag_block}"
    else:
        # RAG 없을 시 단정 방지 블록 삽입
        no_rag_block = (
            "\n\n## ⚠️ 참고 자료 없음\n"
            "지식베이스에서 관련 자료를 찾지 못했습니다. "
            "일반적인 교과서 지식으로만 답하되, 단정적으로 서술하지 마세요. "
            "답변 끝에 반드시 '⚠️ 검토 필요 — 교수 또는 교재로 확인하세요'를 포함하세요."
        )
        user_prompt = f"{user_prompt}{no_rag_block}"

    gateway = get_llm_gateway()
    start = time.monotonic()
    result: LLMGenerationResult | None = None
    error_message: str | None = None
    try:
        result = await gateway.generate(system=system, user=user_prompt)
        success = True
    except LLMGatewayError as exc:
        success = False
        error_message = str(exc)[:1000]
        logger.exception("LLM explain failed for question=%s", question_id)
    latency_ms = int((time.monotonic() - start) * 1000)

    # citation 추출
    used_citations: list[Citation] = []
    retrieved_docs_meta: list[dict] | None = None
    if rag_ctx and rag_ctx.citations:
        if success and result:
            used_citations = extract_used_citations(result.output_text, rag_ctx.citations)
        retrieved_docs_meta = [
            {
                "number": c.number,
                "chunk_id": c.chunk_id,
                "document_id": c.document_id,
                "document_title": c.document_title,
                "source": c.source,
                "snippet": c.snippet,
            }
            for c in rag_ctx.citations
        ]

    # v0.5: 확신도 판정 + 위험 문장 감지
    confidence = ConfidenceLevel.UNVERIFIED
    content_warnings: list[ContentWarning] = []
    if success and result:
        confidence = _compute_confidence(rag_available, used_citations, result.output_text)
        content_warnings = _detect_content_warnings(result.output_text)

    # v0.5: 평가 메타데이터를 로그에 포함
    eval_metadata = {
        "confidence": confidence.value,
        "has_citations": len(used_citations) > 0,
        "citation_count": len(used_citations),
        "rag_available": rag_available,
        "content_warning_count": len(content_warnings),
        "content_warnings": [
            {"pattern": w.pattern_name, "severity": w.severity}
            for w in content_warnings[:10]
        ],
    }
    if retrieved_docs_meta is None:
        retrieved_docs_meta = []
    # eval_metadata를 retrieved_docs에 합쳐서 저장 (기존 스키마 호환)
    log_retrieved = retrieved_docs_meta + [{"_eval_metadata": eval_metadata}]

    log = await _persist_log(
        db,
        user=user,
        request_type=AIRequestType.EXPLAIN,
        template_name=template.name,
        question_id=question_id,
        input_text=f"explain question_id={question_id} history_id={history_id}",
        rendered_user_prompt=user_prompt,
        result=result,
        latency_ms=latency_ms,
        success=success,
        error_message=error_message,
        provider_enum=gateway.provider_name,
        retrieved_docs=log_retrieved,
    )
    if not success:
        raise AIServiceError(error_message or "LLM 호출 실패")

    return AIExplainResult(
        log=log,
        output_text=result.output_text,  # type: ignore[union-attr]
        citations=used_citations,
        rag_context_used=rag_available,
        confidence=confidence,
        content_warnings=content_warnings,
    )


async def answer_question(
    db: AsyncSession,
    user: User,
    user_question: str,
    *,
    use_rag: bool = True,
) -> AIExplainResult:
    """자유 질의응답 + RAG."""
    student_ctx: StudentContext = await load_student_context(
        db, user.id, department=user.department
    )

    rag_ctx: RAGContext | None = None
    if use_rag:
        rag_ctx = await retrieve(db, user_question, department=user.department, top_k=4)

    template = get_template(AIRequestType.QA)
    context = build_qa_context(
        user_question=user_question,
        department=user.department,
        level=student_ctx.level,
    )
    system, user_prompt = template.render(**context)

    student_block = format_student_context_block(student_ctx)
    if student_block:
        user_prompt = f"{student_block}\n\n{user_prompt}"

    # v0.5: source-grounded + 단정 방지
    rag_available = bool(rag_ctx and rag_ctx.formatted_text)
    if rag_available:
        rag_block = (
            "## 참고 자료 (KB에서 검색됨)\n"
            "답변에서 해당 자료를 참조할 때 반드시 [숫자] 형태로 인용하세요. "
            "참고 자료에 없는 내용은 일반 지식으로 답하되, 불확실하면 모른다고 말하세요.\n\n"
            f"{rag_ctx.formatted_text}"
        )
        user_prompt = f"{user_prompt}\n\n{rag_block}"
    else:
        no_rag_block = (
            "\n\n## ⚠️ 참고 자료 없음\n"
            "지식베이스에서 관련 자료를 찾지 못했습니다. "
            "일반적인 교과서 지식으로만 답하되, 단정적으로 서술하지 마세요. "
            "답변 끝에 반드시 '⚠️ 검토 필요 — 교수 또는 교재로 확인하세요'를 포함하세요."
        )
        user_prompt = f"{user_prompt}{no_rag_block}"

    gateway = get_llm_gateway()
    start = time.monotonic()
    result: LLMGenerationResult | None = None
    error_message: str | None = None
    try:
        result = await gateway.generate(system=system, user=user_prompt)
        success = True
    except LLMGatewayError as exc:
        success = False
        error_message = str(exc)[:1000]
        logger.exception("LLM QA failed")
    latency_ms = int((time.monotonic() - start) * 1000)

    used_citations: list[Citation] = []
    retrieved_docs_meta: list[dict] | None = None
    if rag_ctx and rag_ctx.citations:
        if success and result:
            used_citations = extract_used_citations(result.output_text, rag_ctx.citations)
        retrieved_docs_meta = [
            {
                "number": c.number,
                "chunk_id": c.chunk_id,
                "document_id": c.document_id,
                "document_title": c.document_title,
                "source": c.source,
                "snippet": c.snippet,
            }
            for c in rag_ctx.citations
        ]

    # v0.5: 확신도 + 위험 문장 감지
    confidence = ConfidenceLevel.UNVERIFIED
    content_warnings: list[ContentWarning] = []
    if success and result:
        confidence = _compute_confidence(rag_available, used_citations, result.output_text)
        content_warnings = _detect_content_warnings(result.output_text)

    eval_metadata = {
        "confidence": confidence.value,
        "has_citations": len(used_citations) > 0,
        "citation_count": len(used_citations),
        "rag_available": rag_available,
        "content_warning_count": len(content_warnings),
        "content_warnings": [
            {"pattern": w.pattern_name, "severity": w.severity}
            for w in content_warnings[:10]
        ],
    }
    if retrieved_docs_meta is None:
        retrieved_docs_meta = []
    log_retrieved = retrieved_docs_meta + [{"_eval_metadata": eval_metadata}]

    log = await _persist_log(
        db,
        user=user,
        request_type=AIRequestType.QA,
        template_name=template.name,
        question_id=None,
        input_text=user_question,
        rendered_user_prompt=user_prompt,
        result=result,
        latency_ms=latency_ms,
        success=success,
        error_message=error_message,
        provider_enum=gateway.provider_name,
        retrieved_docs=log_retrieved,
    )
    if not success:
        raise AIServiceError(error_message or "LLM 호출 실패")

    return AIExplainResult(
        log=log,
        output_text=result.output_text,  # type: ignore[union-attr]
        citations=used_citations,
        rag_context_used=rag_available,
        confidence=confidence,
        content_warnings=content_warnings,
    )


async def list_request_logs(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    request_type: AIRequestType | None = None,
    success_only: bool | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[AIRequestLog], int]:
    """관리자/개발자용 AIRequestLog 페이지네이션 조회."""
    from sqlalchemy import desc, func

    page = max(1, page)
    page_size = max(1, min(200, page_size))

    base = select(AIRequestLog)
    filters = []
    if user_id:
        filters.append(AIRequestLog.user_id == user_id)
    if request_type:
        filters.append(AIRequestLog.request_type == request_type)
    if success_only is not None:
        filters.append(AIRequestLog.success.is_(success_only))
    if filters:
        base = base.where(*filters)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    items_stmt = (
        base.order_by(desc(AIRequestLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list((await db.execute(items_stmt)).scalars().all())
    return items, total
