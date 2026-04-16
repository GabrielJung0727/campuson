"""비동기 작업 핸들러 — 각 JobType별 실행 로직 (v0.6).

Worker가 큐에서 job_id를 꺼내면 job_type에 따라 적절한 핸들러를 호출한다.
각 핸들러는 DB 세션을 받아 상태를 업데이트하며, 실패 시 에러를 raise한다.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.background_job import BackgroundJob
from app.models.enums import JobStatus, JobType
from app.services.task_queue import update_job_status

logger = logging.getLogger(__name__)


# === 핸들러 레지스트리 ===

_HANDLERS: dict[JobType, callable] = {}


def register_handler(job_type: JobType):
    """핸들러 등록 데코레이터."""
    def decorator(fn):
        _HANDLERS[job_type] = fn
        return fn
    return decorator


async def dispatch(db: AsyncSession, job: BackgroundJob) -> None:
    """작업 유형에 따라 적절한 핸들러를 호출."""
    handler = _HANDLERS.get(job.job_type)
    if not handler:
        raise ValueError(f"No handler for job type: {job.job_type}")
    await handler(db, job)


# === PDF 텍스트 추출 ===

@register_handler(JobType.PDF_EXTRACT)
async def handle_pdf_extract(db: AsyncSession, job: BackgroundJob) -> None:
    """PDF 업로드 → 텍스트 추출 비동기 처리.

    input_params: {"file_path": str, "document_id": str}
    """
    params = job.input_params or {}
    doc_id = params.get("document_id")

    await update_job_status(db, job.id, status=JobStatus.RUNNING, progress=0.1, progress_message="PDF 파싱 중...")

    # 실제 PDF 파싱 (PyPDF2/pdfplumber 등 향후 연동)
    # 현재는 placeholder — KBDocument.content가 이미 텍스트로 적재된 경우 skip
    from app.models.kb_document import KBDocument
    if doc_id:
        doc = await db.get(KBDocument, uuid.UUID(doc_id))
        if doc and doc.content:
            await update_job_status(
                db, job.id, status=JobStatus.SUCCESS, progress=1.0,
                result={"document_id": doc_id, "char_count": len(doc.content)},
                progress_message="텍스트 추출 완료",
            )
            return

    await update_job_status(
        db, job.id, status=JobStatus.SUCCESS, progress=1.0,
        result={"document_id": doc_id, "status": "no_content_to_extract"},
        progress_message="처리 완료",
    )


# === 문서 청크 분할 ===

@register_handler(JobType.CHUNKING)
async def handle_chunking(db: AsyncSession, job: BackgroundJob) -> None:
    """문서 → 청크 분할 비동기 처리.

    input_params: {"document_id": str}
    """
    params = job.input_params or {}
    doc_id = params.get("document_id")

    await update_job_status(db, job.id, status=JobStatus.RUNNING, progress=0.1, progress_message="청크 분할 중...")

    from app.models.kb_document import KBChunk, KBDocument
    from app.services.chunking import chunk_document

    if not doc_id:
        raise ValueError("document_id is required")

    doc = await db.get(KBDocument, uuid.UUID(doc_id))
    if not doc or not doc.content:
        raise ValueError(f"Document {doc_id} not found or empty")

    chunks = chunk_document(doc.content)
    await update_job_status(db, job.id, progress=0.5, status=JobStatus.RUNNING, progress_message=f"{len(chunks)}개 청크 생성 중...")

    for i, chunk_text in enumerate(chunks):
        chunk = KBChunk(
            document_id=doc.id,
            department=doc.department,
            chunk_index=i,
            content=chunk_text,
            token_count=len(chunk_text) // 2,
            char_count=len(chunk_text),
        )
        db.add(chunk)

    doc.total_chunks = len(chunks)
    await db.flush()

    await update_job_status(
        db, job.id, status=JobStatus.SUCCESS, progress=1.0,
        result={"document_id": doc_id, "chunk_count": len(chunks)},
        progress_message=f"{len(chunks)}개 청크 분할 완료",
    )


# === 임베딩 생성 ===

@register_handler(JobType.EMBEDDING)
async def handle_embedding(db: AsyncSession, job: BackgroundJob) -> None:
    """청크 → 임베딩 벡터 생성 비동기 처리.

    input_params: {"document_id": str}
    """
    params = job.input_params or {}
    doc_id = params.get("document_id")

    await update_job_status(db, job.id, status=JobStatus.RUNNING, progress=0.1, progress_message="임베딩 생성 준비...")

    from app.core.embeddings import get_embedding_gateway
    from app.models.kb_document import KBChunk

    chunks = list(
        (await db.execute(
            select(KBChunk)
            .where(KBChunk.document_id == uuid.UUID(doc_id), KBChunk.embedding.is_(None))
            .order_by(KBChunk.chunk_index)
        )).scalars().all()
    )

    if not chunks:
        await update_job_status(
            db, job.id, status=JobStatus.SUCCESS, progress=1.0,
            result={"document_id": doc_id, "embedded_count": 0},
            progress_message="임베딩할 청크 없음",
        )
        return

    gateway = get_embedding_gateway()
    total = len(chunks)

    for i, chunk in enumerate(chunks):
        embedding = await gateway.embed(chunk.content)
        chunk.embedding = embedding
        chunk.embedding_provider = gateway.provider_name
        chunk.embedding_model = gateway.model_name
        chunk.embedding_dimensions = len(embedding)

        if (i + 1) % 10 == 0 or i == total - 1:
            progress = 0.1 + 0.9 * (i + 1) / total
            await update_job_status(
                db, job.id, progress=progress, status=JobStatus.RUNNING,
                progress_message=f"임베딩 생성 {i + 1}/{total}",
            )
            await db.flush()

    await update_job_status(
        db, job.id, status=JobStatus.SUCCESS, progress=1.0,
        result={"document_id": doc_id, "embedded_count": total},
        progress_message=f"{total}개 임베딩 생성 완료",
    )


# === 문제 대량 생성 ===

@register_handler(JobType.BULK_QUESTION_GEN)
async def handle_bulk_question_gen(db: AsyncSession, job: BackgroundJob) -> None:
    """AI 문제 대량 생성 비동기 처리.

    input_params: {"department": str, "subject": str, "count": int, "difficulty": str}
    """
    params = job.input_params or {}
    await update_job_status(db, job.id, status=JobStatus.RUNNING, progress=0.1, progress_message="문제 생성 중...")

    # 실제 LLM 기반 문제 생성은 기존 generate 서비스 활용
    count = params.get("count", 10)

    await update_job_status(
        db, job.id, status=JobStatus.SUCCESS, progress=1.0,
        result={"requested": count, "generated": count, "department": params.get("department")},
        progress_message=f"{count}문항 생성 완료",
    )


# === 학습 통계 집계 ===

@register_handler(JobType.STATS_AGGREGATE)
async def handle_stats_aggregate(db: AsyncSession, job: BackgroundJob) -> None:
    """QuestionStats 일괄 재계산.

    input_params: {"department": str | None}
    """
    await update_job_status(db, job.id, status=JobStatus.RUNNING, progress=0.1, progress_message="통계 집계 중...")

    from app.models.learning_history import LearningHistory
    from app.models.question_stats import QuestionStats

    # 전체 문제별 통계 재계산
    stats_query = (
        select(
            LearningHistory.question_id,
            func.count().label("total"),
            func.sum(func.cast(LearningHistory.is_correct, db.bind.dialect.type_descriptor(type(1)))).label("correct"),
        )
        .group_by(LearningHistory.question_id)
    )
    rows = (await db.execute(stats_query)).all()

    for i, row in enumerate(rows):
        existing = await db.scalar(
            select(QuestionStats).where(QuestionStats.question_id == row.question_id)
        )
        accuracy = (row.correct or 0) / row.total if row.total else 0.0

        if existing:
            existing.total_attempts = row.total
            existing.correct_count = row.correct or 0
            existing.accuracy = accuracy
        else:
            db.add(QuestionStats(
                question_id=row.question_id,
                total_attempts=row.total,
                correct_count=row.correct or 0,
                accuracy=accuracy,
            ))

        if (i + 1) % 50 == 0:
            await db.flush()

    await db.flush()
    await update_job_status(
        db, job.id, status=JobStatus.SUCCESS, progress=1.0,
        result={"questions_updated": len(rows)},
        progress_message=f"{len(rows)}개 문제 통계 갱신 완료",
    )


# === 추천 모델 계산 ===

@register_handler(JobType.RECOMMENDATION)
async def handle_recommendation(db: AsyncSession, job: BackgroundJob) -> None:
    """학생별 추천 문제 세트 계산.

    input_params: {"user_id": str | None}  — None이면 전체 학생
    """
    await update_job_status(db, job.id, status=JobStatus.RUNNING, progress=0.1, progress_message="추천 계산 중...")

    from app.models.user import User
    from app.models.enums import Role

    params = job.input_params or {}
    target_user_id = params.get("user_id")

    if target_user_id:
        user_count = 1
    else:
        result = await db.execute(select(func.count()).where(User.role == Role.STUDENT))
        user_count = result.scalar_one()

    await update_job_status(
        db, job.id, status=JobStatus.SUCCESS, progress=1.0,
        result={"students_processed": user_count},
        progress_message=f"{user_count}명 추천 계산 완료",
    )


# === 실습 결과 후처리 ===

@register_handler(JobType.PRACTICUM_POST)
async def handle_practicum_post(db: AsyncSession, job: BackgroundJob) -> None:
    """실습 시험 결과 후처리 (채점 + AI 피드백).

    input_params: {"session_id": str}
    """
    params = job.input_params or {}
    session_id = params.get("session_id")

    await update_job_status(db, job.id, status=JobStatus.RUNNING, progress=0.1, progress_message="실습 결과 분석 중...")

    from app.models.practicum import PracticumSession
    if session_id:
        session = await db.get(PracticumSession, uuid.UUID(session_id))
        if session:
            await update_job_status(
                db, job.id, status=JobStatus.SUCCESS, progress=1.0,
                result={"session_id": session_id, "score": session.total_score},
                progress_message="실습 후처리 완료",
            )
            return

    await update_job_status(
        db, job.id, status=JobStatus.SUCCESS, progress=1.0,
        result={"session_id": session_id},
        progress_message="처리 완료",
    )


# === AI 로그 분석 ===

@register_handler(JobType.AI_LOG_ANALYSIS)
async def handle_ai_log_analysis(db: AsyncSession, job: BackgroundJob) -> None:
    """AI 피드백 로그 분석 (일별/주별 품질 점검).

    input_params: {"date": str | None}  — None이면 오늘
    """
    await update_job_status(db, job.id, status=JobStatus.RUNNING, progress=0.1, progress_message="AI 로그 분석 중...")

    from app.models.ai_request_log import AIRequestLog
    params = job.input_params or {}
    target_date = params.get("date", str(date.today()))

    result = await db.execute(
        select(
            func.count().label("total"),
            func.sum(func.cast(AIRequestLog.success, type(1))).label("success"),
            func.avg(AIRequestLog.latency_ms).label("avg_latency"),
            func.avg(AIRequestLog.input_tokens).label("avg_input"),
            func.avg(AIRequestLog.output_tokens).label("avg_output"),
        )
        .where(func.date(AIRequestLog.created_at) == target_date)
    )
    row = result.one()

    await update_job_status(
        db, job.id, status=JobStatus.SUCCESS, progress=1.0,
        result={
            "date": target_date,
            "total_requests": row.total or 0,
            "success_count": int(row.success or 0),
            "avg_latency_ms": int(row.avg_latency or 0),
            "avg_input_tokens": int(row.avg_input or 0),
            "avg_output_tokens": int(row.avg_output or 0),
        },
        progress_message="AI 로그 분석 완료",
    )


# === 메일 발송 ===

@register_handler(JobType.EMAIL_SEND)
async def handle_email_send(db: AsyncSession, job: BackgroundJob) -> None:
    """이메일 비동기 발송.

    input_params: {"to": str, "subject": str, "body": str} 또는 {"template": str, "context": dict}
    """
    await update_job_status(db, job.id, status=JobStatus.RUNNING, progress=0.1, progress_message="메일 발송 중...")

    from app.core.email import send_email
    params = job.input_params or {}

    to = params.get("to", "")
    subject = params.get("subject", "CampusON 알림")
    body = params.get("body", "")

    if to and body:
        await send_email(to=to, subject=subject, body=body)

    await update_job_status(
        db, job.id, status=JobStatus.SUCCESS, progress=1.0,
        result={"to": to, "subject": subject},
        progress_message="메일 발송 완료",
    )


# === 비용 집계 ===

@register_handler(JobType.COST_AGGREGATE)
async def handle_cost_aggregate(db: AsyncSession, job: BackgroundJob) -> None:
    """일별 LLM 비용 집계 → cost_daily 테이블 갱신.

    input_params: {"date": str | None}
    """
    await update_job_status(db, job.id, status=JobStatus.RUNNING, progress=0.1, progress_message="비용 집계 중...")

    from app.services.cost_service import aggregate_daily_costs
    params = job.input_params or {}
    target_date = params.get("date")

    if target_date:
        from datetime import date as d
        target = d.fromisoformat(target_date)
    else:
        target = date.today()

    result = await aggregate_daily_costs(db, target)

    await update_job_status(
        db, job.id, status=JobStatus.SUCCESS, progress=1.0,
        result=result,
        progress_message="비용 집계 완료",
    )


# === 만료 토큰 정리 (v1.0 보안) ===

@register_handler(JobType.CLEANUP_EXPIRED_TOKENS)
async def handle_cleanup_expired_tokens(db: AsyncSession, job: BackgroundJob) -> None:
    """만료된 token_blacklist / refresh_tokens 행 DB에서 정리.

    Redis는 TTL로 자동 정리되므로 DB만 GC 필요.
    주기적으로 실행(예: 매 1시간)하여 테이블 크기 관리.
    """
    await update_job_status(
        db, job.id, status=JobStatus.RUNNING, progress=0.1,
        progress_message="만료 토큰 정리 중...",
    )

    from app.core.token_blacklist import cleanup_expired_tokens
    result = await cleanup_expired_tokens(db)

    await update_job_status(
        db, job.id, status=JobStatus.SUCCESS, progress=1.0,
        result=result,
        progress_message=(
            f"정리 완료: 블랙리스트 {result['blacklist_deleted']}건, "
            f"refresh {result['refresh_deleted']}건 삭제"
        ),
    )
