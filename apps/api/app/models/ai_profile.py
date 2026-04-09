"""AIProfile 모델 — 학생별 AI 튜터링 개인화 프로파일.

진단 테스트 직후 자동 생성되며, 이후 학습 이력으로 점진적 업데이트된다.
사용자와 1:1 관계.
"""

import enum
import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import String

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import Level


class ExplanationPreference(str, enum.Enum):
    """AI 설명 난이도 선호도."""

    SIMPLE = "SIMPLE"
    DETAILED = "DETAILED"
    EXPERT = "EXPERT"


class AIProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """학생별 AI 튜터링 프로파일."""

    __tablename__ = "ai_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    level: Mapped[Level] = mapped_column(
        SAEnum(Level, name="level_enum", native_enum=True, create_type=False),
        nullable=False,
        default=Level.BEGINNER,
    )

    weak_priority: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        comment='취약영역 우선순위 — [{"subject": "...", "unit": "...", "score": 0.42, "priority": 1}]',
    )

    learning_path: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        comment='추천 학습 경로 — [{"step": 1, "subject": "...", "unit": "...", "rationale": "..."}]',
    )

    explanation_pref: Mapped[ExplanationPreference] = mapped_column(
        SAEnum(
            ExplanationPreference,
            name="explanation_pref_enum",
            native_enum=True,
            create_type=True,
        ),
        nullable=False,
        default=ExplanationPreference.DETAILED,
    )

    frequent_topics: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)),
        nullable=False,
        server_default="{}",
        comment="자주 질문하는 주제 — Day 6 LLM 연동 후 채워짐",
    )

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_ai_profiles_user_id"),
    )

    def __repr__(self) -> str:
        return f"<AIProfile id={self.id} user={self.user_id} level={self.level.value}>"
