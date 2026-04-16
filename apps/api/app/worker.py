"""ARQ Worker — 백그라운드 작업 소비자 (v0.6).

실행 방법:
    python -m app.worker

또는 FastAPI 앱 내부에서 asyncio.create_task로 실행 가능 (개발 모드).
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from app.core.config import settings
from app.core.redis import get_redis_client
from app.db.session import AsyncSessionLocal
from app.models.enums import JobStatus
from app.services.task_handlers import dispatch
from app.services.task_queue import QUEUE_NAME, retry_job, update_job_status

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("campuson.worker")

# 워커 동시 실행 작업 수
MAX_CONCURRENT = 5
POLL_INTERVAL = 1.0  # 초


async def process_job(job_id_str: str) -> None:
    """단일 작업 처리."""
    job_id = uuid.UUID(job_id_str)
    async with AsyncSessionLocal() as db:
        try:
            from app.models.background_job import BackgroundJob
            job = await db.get(BackgroundJob, job_id)
            if not job:
                logger.warning("Job %s not found, skipping", job_id)
                return

            if job.status not in (JobStatus.PENDING, JobStatus.RETRYING):
                logger.info("Job %s status=%s, skipping", job_id, job.status.value)
                return

            await update_job_status(db, job_id, status=JobStatus.RUNNING)
            await db.commit()

            # DB 세션 재시작 (커밋 후)
            async with AsyncSessionLocal() as work_db:
                try:
                    job = await work_db.get(BackgroundJob, job_id)
                    await dispatch(work_db, job)
                    await work_db.commit()
                    logger.info("Job %s completed successfully", job_id)
                except Exception as exc:
                    await work_db.rollback()
                    logger.exception("Job %s failed: %s", job_id, exc)

                    async with AsyncSessionLocal() as err_db:
                        await update_job_status(
                            err_db, job_id,
                            status=JobStatus.FAILED,
                            error_message=str(exc)[:2000],
                        )
                        # 재시도 시도
                        retried = await retry_job(err_db, job_id)
                        await err_db.commit()
                        if retried:
                            logger.info("Job %s queued for retry", job_id)

        except Exception as exc:
            logger.exception("Fatal error processing job %s: %s", job_id, exc)
            try:
                await db.rollback()
            except Exception:
                pass


async def worker_loop() -> None:
    """메인 워커 루프 — Redis 큐에서 작업을 꺼내서 처리."""
    logger.info("🏗️ CampusON Worker started (concurrency=%d)", MAX_CONCURRENT)
    redis = get_redis_client()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    while True:
        try:
            # BLPOP으로 blocking 대기 (timeout=5초)
            result = await redis.blpop(QUEUE_NAME, timeout=5)
            if result is None:
                continue

            _, job_id_str = result

            async with semaphore:
                await process_job(job_id_str)

        except asyncio.CancelledError:
            logger.info("Worker shutting down...")
            break
        except Exception as exc:
            logger.exception("Worker loop error: %s", exc)
            await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(worker_loop())
