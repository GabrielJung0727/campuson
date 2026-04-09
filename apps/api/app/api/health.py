"""헬스체크 엔드포인트."""

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> dict[str, str]:
    """리브니스 프로브 — 단순 200 응답."""
    return {"status": "ok", "service": "campuson-api"}


@router.get("/health/db", status_code=status.HTTP_200_OK)
async def health_check_db(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """레디니스 프로브 — DB 연결 확인."""
    result = await db.execute(text("SELECT 1"))
    return {"status": "ok", "db": "connected", "result": str(result.scalar())}
