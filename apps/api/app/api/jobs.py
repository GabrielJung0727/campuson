"""백그라운드 작업 API (v0.6)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.enums import JobStatus, JobType, Role
from app.models.user import User
from app.services.task_queue import (
    enqueue_job,
    get_job,
    get_queue_stats,
    list_jobs,
    retry_job,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobCreateRequest(BaseModel):
    job_type: JobType
    params: dict | None = None
    max_retries: int = 3


class JobResponse(BaseModel):
    id: uuid.UUID
    job_type: str
    status: str
    progress: float
    progress_message: str | None
    result: dict | None
    error_message: str | None
    retry_count: int
    max_retries: int
    created_at: str
    started_at: str | None
    completed_at: str | None


def _job_to_response(job) -> JobResponse:
    return JobResponse(
        id=job.id,
        job_type=job.job_type.value,
        status=job.status.value,
        progress=job.progress,
        progress_message=job.progress_message,
        result=job.result,
        error_message=job.error_message,
        retry_count=job.retry_count,
        max_retries=job.max_retries,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )


@router.post("", response_model=JobResponse)
async def create_job(
    body: JobCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """작업 등록. PROFESSOR 이상만 가능."""
    if user.role not in (Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER):
        raise HTTPException(403, "권한이 없습니다")
    job = await enqueue_job(
        db, body.job_type, user_id=user.id,
        params=body.params, max_retries=body.max_retries,
    )
    return _job_to_response(job)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_status(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """작업 상태 조회."""
    job = await get_job(db, job_id)
    if not job:
        raise HTTPException(404, "작업을 찾을 수 없습니다")
    if user.role == Role.STUDENT and job.created_by != user.id:
        raise HTTPException(403, "권한이 없습니다")
    return _job_to_response(job)


@router.post("/{job_id}/retry", response_model=dict)
async def retry_failed_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """실패한 작업 재시도. ADMIN 이상만."""
    if user.role not in (Role.ADMIN, Role.DEVELOPER):
        raise HTTPException(403, "권한이 없습니다")
    success = await retry_job(db, job_id)
    return {"retried": success}


@router.get("", response_model=dict)
async def list_all_jobs(
    job_type: JobType | None = None,
    status: JobStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """작업 목록 조회."""
    uid = user.id if user.role == Role.STUDENT else None
    items, total = await list_jobs(
        db, user_id=uid, job_type=job_type, status=status,
        page=page, page_size=page_size,
    )
    return {
        "items": [_job_to_response(j) for j in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/stats/queue", response_model=dict)
async def queue_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """큐 상태 통계. ADMIN 이상만."""
    if user.role not in (Role.ADMIN, Role.DEVELOPER):
        raise HTTPException(403, "권한이 없습니다")
    return await get_queue_stats(db)
