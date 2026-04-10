"""AI 서비스 — 문제 해설/QA + RAG + 호출 로깅 + latency 측정.

Day 10 업그레이드
----------------
- explain / qa 모두 RAG 통합 (KB 검색 결과를 프롬프트에 주입)
- 학생 프로파일(level/취약영역) 동적 주입
- 인용(citation) 추출 및 로그 저장

LLM Gateway를 호출하고 결과를 AIRequestLog에 기록한다.
실패해도 로그는 남긴다.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass

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


@dataclass
class AIExplainResult:
    """Explain/QA 서비스 결과 컨테이너."""

    log: AIRequestLog
    output_text: str
    citations: list[Citation]
    rag_context_used: bool

logger = logging.getLogger(__name__)


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

    # RAG 컨텍스트 주입
    if rag_ctx and rag_ctx.formatted_text:
        rag_block = (
            "## 참고 자료 (KB에서 검색됨)\n"
            "답변에서 해당 자료를 참조할 때 [숫자] 형태로 인용하세요.\n\n"
            f"{rag_ctx.formatted_text}"
        )
        user_prompt = f"{user_prompt}\n\n{rag_block}"

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
        retrieved_docs=retrieved_docs_meta,
    )
    if not success:
        raise AIServiceError(error_message or "LLM 호출 실패")

    return AIExplainResult(
        log=log,
        output_text=result.output_text,  # type: ignore[union-attr]
        citations=used_citations,
        rag_context_used=bool(rag_ctx and rag_ctx.formatted_text),
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

    if rag_ctx and rag_ctx.formatted_text:
        rag_block = (
            "## 참고 자료 (KB에서 검색됨)\n"
            "답변에서 해당 자료를 참조할 때 [숫자] 형태로 인용하세요. "
            "참고 자료에 없는 내용은 일반 지식으로 답하되, 불확실하면 모른다고 말하세요.\n\n"
            f"{rag_ctx.formatted_text}"
        )
        user_prompt = f"{user_prompt}\n\n{rag_block}"

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
        retrieved_docs=retrieved_docs_meta,
    )
    if not success:
        raise AIServiceError(error_message or "LLM 호출 실패")

    return AIExplainResult(
        log=log,
        output_text=result.output_text,  # type: ignore[union-attr]
        citations=used_citations,
        rag_context_used=bool(rag_ctx and rag_ctx.formatted_text),
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
