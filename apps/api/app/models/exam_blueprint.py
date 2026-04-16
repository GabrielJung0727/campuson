"""국가고시 블루프린트 + 개념 태그 모델 (v0.7).

1. ExamBlueprint: 국가고시 과목 체계 + 출제 영역별 비중
2. ConceptNode: 과목-단원-개념 3단계 태그 구조
3. ConceptRelation: 개념 간 연관 관계 (선행/관련)
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import Department


class ExamBlueprint(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """국가고시 출제 블루프린트 — 영역별 비중.

    예: 간호사 국시 → 성인간호학 30%, 기본간호학 15%, ...
    """

    __tablename__ = "exam_blueprints"

    department: Mapped[Department] = mapped_column(
        SAEnum(Department, name="department_enum", native_enum=True, create_type=False),
        nullable=False,
    )
    exam_name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="예: 간호사 국가시험, 물리치료사 국가시험"
    )
    exam_year: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="출제 기준 연도")
    subject: Mapped[str] = mapped_column(String(100), nullable=False, comment="과목명")
    area: Mapped[str] = mapped_column(String(200), nullable=False, comment="출제 영역 (예: 호흡기계 간호)")
    sub_area: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="세부 영역")
    weight_pct: Mapped[float] = mapped_column(
        Float, nullable=False, comment="출제 비중 (0.0~1.0)"
    )
    question_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="해당 영역 예상 출제 문항 수"
    )
    competency: Mapped[str | None] = mapped_column(
        String(300), nullable=True, comment="필요 역량 (예: 비판적 사고, 간호 중재)"
    )
    keywords: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), nullable=False, server_default="'{}'::varchar[]",
        comment="핵심 키워드",
    )

    __table_args__ = (
        Index("ix_blueprint_dept_subject", "department", "subject"),
        Index("ix_blueprint_dept_area", "department", "area"),
        UniqueConstraint("department", "exam_name", "subject", "area", "sub_area",
                         name="uq_blueprint_entry"),
    )


class ConceptNode(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """과목-단원-개념 3단계 태그 노드.

    트리 구조: level=1(과목), level=2(단원), level=3(개념)
    parent_id로 상위 노드 참조.
    """

    __tablename__ = "concept_nodes"

    department: Mapped[Department] = mapped_column(
        SAEnum(Department, name="department_enum", native_enum=True, create_type=False),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="노드 이름")
    level: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="1=과목, 2=단원, 3=개념"
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("concept_nodes.id", ondelete="CASCADE"),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    blueprint_area: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="블루프린트 영역 매핑"
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    children = relationship("ConceptNode", back_populates="parent", cascade="all, delete-orphan")
    parent = relationship("ConceptNode", back_populates="children", remote_side="ConceptNode.id")

    __table_args__ = (
        Index("ix_concept_dept_level", "department", "level"),
        Index("ix_concept_parent", "parent_id"),
        UniqueConstraint("department", "name", "level", "parent_id", name="uq_concept_node"),
    )


class ConceptRelation(Base, UUIDPrimaryKeyMixin):
    """개념 간 연관 관계.

    relation_type: prerequisite(선행), related(관련), similar(유사)
    """

    __tablename__ = "concept_relations"

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("concept_nodes.id", ondelete="CASCADE"), nullable=False,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("concept_nodes.id", ondelete="CASCADE"), nullable=False,
    )
    relation_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="prerequisite | related | similar"
    )
    strength: Mapped[float] = mapped_column(
        Float, default=1.0, comment="관계 강도 0.0~1.0"
    )

    __table_args__ = (
        UniqueConstraint("source_id", "target_id", "relation_type", name="uq_concept_relation"),
        Index("ix_concept_rel_source", "source_id"),
        Index("ix_concept_rel_target", "target_id"),
    )
