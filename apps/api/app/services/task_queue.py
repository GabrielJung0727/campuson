"""Redis 기반 비동기 작업 큐 (v0.6).

ARQ(Async Redis Queue)를 사용한 백그라운드 작업 관리:
- 작업 등록 → Redis 큐 → Worker 소비
- BackgroundJob 테이블로 상태 추적
- 재시도 / 실패 알림 / dead-letter 처리

사용 예
------
job = await enqueue_job(db, JobType.EMBEDDING, user_id=user.id, params={"doc_id": str(doc.id)})
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.models.background_job import BackgroundJob
from app.models.enums import JobStatus, JobType

logger = logging.getLogger(__name__)

# ARQ 큐 이름
QUEUE_NAME = "campuson:jobs"


async def enqueue_job(
    db: AsyncSession,
    job_type: JobType,
    *,
    user_id: uuid.UUID | None = None,
    params: dict | None = None,
    max_retries: int = 3,
) -> BackgroundJob:
    """작업을 DB에 기록하고 Redis 큐에 등록."""
    job = BackgroundJob(
        job_type=job_type,
        status=JobStatus.PENDING,
        created_by=user_id,
        input_params=params,
        max_retries=max_retries,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)

    # Redis 큐에 job_id 등록
    redis = get_redis_client()
    await redis.rpush(QUEUE_NAME, str(job.id))
    logger.info("Enqueued job %s type=%s", job.id, job_type.value)
    return job


async def update_job_status(
    db: AsyncSession,
    job_id: uuid.UUID,
    *,
    status: JobStatus,
    progress: float | None = None,
    progress_message: str | None = None,
    result: dict | None = None,
    error_message: str | None = None,
) -> None:
    """작업 상태 업데이트."""
    values: dict = {"status": status}
    if progress is not None:
        values["progress"] = progress
    if progress_message is not None:
        values["progress_message"] = progress_message
    if result is not None:
        values["result"] = result
    if error_message is not None:
        values["error_message"] = error_message

    now = datetime.now(timezone.utc)
    if status == JobStatus.RUNNING:
        values["started_at"] = now
    elif status in (JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.DEAD_LETTER):
        values["completed_at"] = now

    await db.execute(
        update(BackgroundJob).where(BackgroundJob.id == job_id).values(**values)
    )
    await db.flush()


async def mark_dead_letter(db: AsyncSession, job_id: uuid.UUID, error: str) -> None:
    """최대 재시도 초과 → dead-letter 마킹."""
    await update_job_status(
        db, job_id, status=JobStatus.DEAD_LETTER, error_message=error
    )
    logger.error("Job %s moved to dead-letter: %s", job_id, error)


async def retry_job(db: AsyncSession, job_id: uuid.UUID) -> bool:
    """실패한 작업 재시도. 최대 재시도 초과 시 dead-letter."""
    job = await db.get(BackgroundJob, job_id)
    if not job:
        return False

    if job.retry_count >= job.max_retries:
        await mark_dead_letter(db, job_id, f"Max retries ({job.max_retries}) exceeded")
        return False

    await db.execute(
        update(BackgroundJob)
        .where(BackgroundJob.id == job_id)
        .values(
            status=JobStatus.RETRYING,
            retry_count=job.retry_count + 1,
            error_message=None,
        )
    )
    await db.flush()

    redis = get_redis_client()
    await redis.rpush(QUEUE_NAME, str(job_id))
    logger.info("Retrying job %s (attempt %d/%d)", job_id, job.retry_count + 1, job.max_retries)
    return True


async def get_job(db: AsyncSession, job_id: uuid.UUID) -> BackgroundJob | None:
    """작업 조회."""
    return await db.get(BackgroundJob, job_id)


async def list_jobs(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    job_type: JobType | None = None,
    status: JobStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[BackgroundJob], int]:
    """작업 목록 조회 (페이지네이션)."""
    from sqlalchemy import desc, func

    base = select(BackgroundJob)
    filters = []
    if user_id:
        filters.append(BackgroundJob.created_by == user_id)
    if job_type:
        filters.append(BackgroundJob.job_type == job_type)
    if status:
        filters.append(BackgroundJob.status == status)
    if filters:
        base = base.where(*filters)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    items = list(
        (
            await db.execute(
                base.order_by(desc(BackgroundJob.created_at))
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return items, total


async def get_queue_stats(db: AsyncSession) -> dict:
    """큐 상태 통계."""
    from sqlalchemy import case, func

    result = await db.execute(
        select(
            BackgroundJob.status,
            func.count().label("count"),
        )
        .group_by(BackgroundJob.status)
    )
    stats = {row.status.value: row.count for row in result.all()}

    redis = get_redis_client()
    queue_length = await redis.llen(QUEUE_NAME)

    return {
        "queue_length": queue_length,
        "by_status": stats,
        "pending": stats.get("PENDING", 0),
        "running": stats.get("RUNNING", 0),
        "success": stats.get("SUCCESS", 0),
        "failed": stats.get("FAILED", 0),
        "dead_letter": stats.get("DEAD_LETTER", 0),
    }
