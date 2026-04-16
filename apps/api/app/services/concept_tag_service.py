"""개념 태그 체계 서비스 (v0.7).

- 과목-단원-개념 3단계 태그 구조 관리
- 태그 기반 취약도 분석
- 태그 간 연관 관계 매핑
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Department
from app.models.exam_blueprint import ConceptNode, ConceptRelation
from app.models.learning_history import LearningHistory
from app.models.question import Question

logger = logging.getLogger(__name__)


# === CRUD ===


async def create_concept_node(
    db: AsyncSession,
    *,
    department: Department,
    name: str,
    level: int,
    parent_id: uuid.UUID | None = None,
    description: str | None = None,
    blueprint_area: str | None = None,
    sort_order: int = 0,
) -> ConceptNode:
    """개념 노드 생성."""
    node = ConceptNode(
        department=department,
        name=name,
        level=level,
        parent_id=parent_id,
        description=description,
        blueprint_area=blueprint_area,
        sort_order=sort_order,
    )
    db.add(node)
    await db.flush()
    await db.refresh(node)
    return node


async def get_concept_tree(
    db: AsyncSession, department: Department,
) -> list[dict]:
    """학과별 전체 개념 트리 조회 (3단계)."""
    nodes = list((await db.execute(
        select(ConceptNode)
        .where(ConceptNode.department == department)
        .order_by(ConceptNode.level, ConceptNode.sort_order, ConceptNode.name)
    )).scalars().all())

    # 트리 구조로 변환
    node_map: dict[uuid.UUID, dict] = {}
    roots = []

    for n in nodes:
        entry = {
            "id": str(n.id),
            "name": n.name,
            "level": n.level,
            "description": n.description,
            "blueprint_area": n.blueprint_area,
            "children": [],
        }
        node_map[n.id] = entry
        if n.parent_id and n.parent_id in node_map:
            node_map[n.parent_id]["children"].append(entry)
        elif not n.parent_id:
            roots.append(entry)

    return roots


async def create_concept_relation(
    db: AsyncSession,
    source_id: uuid.UUID,
    target_id: uuid.UUID,
    relation_type: str,
    strength: float = 1.0,
) -> ConceptRelation:
    """개념 간 관계 생성."""
    rel = ConceptRelation(
        source_id=source_id,
        target_id=target_id,
        relation_type=relation_type,
        strength=strength,
    )
    db.add(rel)
    await db.flush()
    return rel


async def get_related_concepts(
    db: AsyncSession, concept_id: uuid.UUID,
) -> list[dict]:
    """특정 개념의 연관 개념 조회."""
    rels = list((await db.execute(
        select(ConceptRelation, ConceptNode)
        .join(ConceptNode, ConceptNode.id == ConceptRelation.target_id)
        .where(ConceptRelation.source_id == concept_id)
        .order_by(desc(ConceptRelation.strength))
    )).all())

    return [
        {
            "concept_id": str(rel.target_id),
            "concept_name": node.name,
            "relation_type": rel.relation_type,
            "strength": rel.strength,
        }
        for rel, node in rels
    ]


# === 태그 기반 취약도 분석 ===


async def analyze_tag_weakness(
    db: AsyncSession,
    user_id: uuid.UUID,
    department: Department,
) -> list[dict]:
    """개념 태그별 취약도 분석.

    Question.concept_tags를 기반으로 태그별 정답률을 계산하고,
    취약한 태그를 우선순위로 정렬한다.
    """
    # concept_tags는 ARRAY이므로 unnest로 개별 태그로 풀어서 집계
    from sqlalchemy import text

    query = text("""
        SELECT
            tag,
            COUNT(*) as attempts,
            SUM(CASE WHEN lh.is_correct THEN 1 ELSE 0 END) as correct,
            ROUND(SUM(CASE WHEN lh.is_correct THEN 1 ELSE 0 END)::numeric / COUNT(*)::numeric, 4) as accuracy
        FROM learning_history lh
        JOIN questions q ON q.id = lh.question_id
        CROSS JOIN LATERAL unnest(q.concept_tags) AS tag
        WHERE lh.user_id = :user_id AND q.department = :department
        GROUP BY tag
        HAVING COUNT(*) >= 2
        ORDER BY accuracy ASC, attempts DESC
    """)

    result = await db.execute(query, {"user_id": str(user_id), "department": department.value})
    rows = result.all()

    return [
        {
            "tag": row.tag,
            "attempts": row.attempts,
            "correct": row.correct,
            "accuracy": float(row.accuracy),
            "weakness_level": "심각" if float(row.accuracy) < 0.4 else "취약" if float(row.accuracy) < 0.6 else "보통",
        }
        for row in rows
    ]


async def get_tag_stats(
    db: AsyncSession, department: Department,
) -> list[dict]:
    """전체 개념 태그 통계 (교수용)."""
    from sqlalchemy import text

    query = text("""
        SELECT
            tag,
            COUNT(DISTINCT q.id) as question_count,
            COUNT(lh.id) as attempt_count,
            ROUND(AVG(CASE WHEN lh.is_correct THEN 1.0 ELSE 0.0 END)::numeric, 4) as avg_accuracy
        FROM questions q
        CROSS JOIN LATERAL unnest(q.concept_tags) AS tag
        LEFT JOIN learning_history lh ON lh.question_id = q.id
        WHERE q.department = :department
        GROUP BY tag
        ORDER BY question_count DESC
    """)

    result = await db.execute(query, {"department": department.value})
    rows = result.all()

    return [
        {
            "tag": row.tag,
            "question_count": row.question_count,
            "attempt_count": row.attempt_count or 0,
            "avg_accuracy": float(row.avg_accuracy) if row.avg_accuracy else None,
        }
        for row in rows
    ]
