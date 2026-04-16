"""파일 업로드 라우터 (v0.9).

엔드포인트
---------
- POST /kb/upload            — 파일 업로드 + 파이프라인 실행
- POST /kb/documents/{id}/reindex — 재색인
- DELETE /kb/documents/{id}/cascade — cascade 삭제
- POST /kb/evaluate          — 검색 품질 평가
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.enums import Department, Role
from app.models.user import User
from app.services import file_pipeline

router = APIRouter(prefix="/kb", tags=["kb"])


class EvaluationRequest(BaseModel):
    test_queries: list[dict]
    department: Department | None = None


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    department: Department = Form(...),
    title: str | None = Form(None),
    source: str | None = Form(None),
    source_url: str | None = Form(None),
    source_year: int | None = Form(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.DEVELOPER)),
):
    """KB 문서 파일 업로드 + 자동 처리 파이프라인.

    지원 형식: PDF, DOCX, HTML, Markdown, 텍스트
    """
    content = await file.read()
    result = await file_pipeline.process_file(
        db,
        content=content,
        filename=file.filename or "upload",
        content_type=file.content_type,
        department=department,
        title=title,
        source=source,
        source_url=source_url,
        source_year=source_year,
        uploaded_by=user.id,
    )

    if not result.success:
        raise HTTPException(
            status_code=400,
            detail={
                "error": result.error_message,
                "security_warnings": result.security_warnings,
                "extraction_errors": result.extraction_errors,
            },
        )

    await db.commit()
    return {
        "document_id": str(result.document_id),
        "file_name": result.file_name,
        "file_size": result.file_size,
        "format": result.format,
        "total_chunks": result.total_chunks,
        "total_tokens": result.total_tokens,
        "embedded_chunks": result.embedded_chunks,
        "detected_tables": result.detected_tables,
        "detected_images": result.detected_images,
        "auto_tags": result.auto_tags,
        "security_warnings": result.security_warnings,
    }


@router.post("/documents/{document_id}/reindex")
async def reindex_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(Role.ADMIN, Role.DEVELOPER)),
):
    """문서 재색인 (내용 변경 시)."""
    try:
        result = await file_pipeline.reindex_document(db, document_id)
    except file_pipeline.FilePipelineError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    await db.commit()
    return {
        "document_id": str(result.document_id),
        "total_chunks": result.total_chunks,
        "embedded_chunks": result.embedded_chunks,
    }


@router.delete("/documents/{document_id}/cascade")
async def cascade_delete(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(Role.ADMIN, Role.DEVELOPER)),
):
    """문서 + 청크 cascade 삭제."""
    ok = await file_pipeline.cascade_delete_document(db, document_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found")
    await db.commit()
    return {"deleted": True, "document_id": str(document_id)}


@router.post("/evaluate")
async def evaluate_quality(
    body: EvaluationRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(Role.ADMIN, Role.DEVELOPER)),
):
    """검색 품질 평가 (precision@k, recall@k, MRR)."""
    result = await file_pipeline.evaluate_search_quality(
        db, body.test_queries, department=body.department,
    )
    return result
