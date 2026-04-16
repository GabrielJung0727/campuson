"""개념 태그 체계 라우터 (v0.7).

- GET  /concepts/tree         — 개념 트리 조회
- POST /concepts/nodes        — 개념 노드 생성 (교수)
- POST /concepts/relations    — 개념 관계 생성 (교수)
- GET  /concepts/{id}/related — 연관 개념 조회
- GET  /concepts/weakness     — 학생 태그별 취약도
- GET  /concepts/stats        — 전체 태그 통계 (교수)
"""

import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.enums import Department, Role
from app.models.user import User
from app.services.concept_tag_service import (
    analyze_tag_weakness,
    create_concept_node,
    create_concept_relation,
    get_concept_tree,
    get_related_concepts,
    get_tag_stats,
)

router = APIRouter(prefix="/concepts", tags=["concepts"])


@router.get("/tree", summary="개념 트리 조회")
async def tree(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_concept_tree(db, current_user.department)


@router.post("/nodes", summary="개념 노드 생성 (교수)")
async def create_node(
    name: str = Body(...),
    level: int = Body(..., ge=1, le=3),
    parent_id: uuid.UUID | None = Body(None),
    description: str | None = Body(None),
    blueprint_area: str | None = Body(None),
    sort_order: int = Body(0),
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
):
    node = await create_concept_node(
        db,
        department=current_user.department,
        name=name,
        level=level,
        parent_id=parent_id,
        description=description,
        blueprint_area=blueprint_area,
        sort_order=sort_order,
    )
    await db.commit()
    return {"id": str(node.id), "name": node.name, "level": node.level}


@router.post("/relations", summary="개념 관계 생성 (교수)")
async def create_relation(
    source_id: uuid.UUID = Body(...),
    target_id: uuid.UUID = Body(...),
    relation_type: str = Body(...),
    strength: float = Body(1.0, ge=0, le=1),
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
):
    rel = await create_concept_relation(
        db, source_id, target_id, relation_type, strength,
    )
    await db.commit()
    return {"id": str(rel.id), "relation_type": rel.relation_type}


@router.get("/{concept_id}/related", summary="연관 개념 조회")
async def related(
    concept_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_related_concepts(db, concept_id)


@router.get("/weakness", summary="학생 태그별 취약도")
async def weakness(
    current_user: User = Depends(require_roles(Role.STUDENT)),
    db: AsyncSession = Depends(get_db),
):
    return await analyze_tag_weakness(db, current_user.id, current_user.department)


@router.get("/stats", summary="전체 태그 통계 (교수)")
async def tag_stats(
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
):
    return await get_tag_stats(db, current_user.department)
