"""QuestionBank 모델 — 국가고시 문제은행."""

from sqlalchemy import CheckConstraint, Index, Integer, String, Text, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import Department, Difficulty, QuestionType


class Question(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """국가고시 문제 1건.

    선택지(`choices`)는 JSONB 배열 형태로 저장하고, 정답(`correct_answer`)은
    0-indexed 배열 인덱스로 저장한다. (예: choices=["A","B","C","D"], correct_answer=2 → "C")

    `tags`는 PostgreSQL ARRAY로 저장되며 GIN 인덱스로 검색을 가속화한다.
    """

    __tablename__ = "questions"

    # --- 분류 ---
    department: Mapped[Department] = mapped_column(
        SAEnum(Department, name="department_enum", native_enum=True, create_type=False),
        nullable=False,
    )
    subject: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="과목명 (예: 성인간호학, 신경계물리치료, 구강해부학)",
    )
    unit: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="세부 단원 (예: 호흡기계, 근골격계)",
    )
    difficulty: Mapped[Difficulty] = mapped_column(
        SAEnum(Difficulty, name="difficulty_enum", native_enum=True, create_type=True),
        nullable=False,
        default=Difficulty.MEDIUM,
    )
    question_type: Mapped[QuestionType] = mapped_column(
        SAEnum(QuestionType, name="question_type_enum", native_enum=True, create_type=True),
        nullable=False,
        default=QuestionType.SINGLE_CHOICE,
    )

    # --- 본문 ---
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    choices: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        comment="선택지 배열 — 예: [\"심방세동\", \"심실세동\", \"동방결절차단\", \"방실차단\", \"좌각차단\"]",
    )
    correct_answer: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="0-indexed 정답 번호",
    )
    explanation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="공식 해설",
    )

    # --- 메타 ---
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)),
        nullable=False,
        server_default=text("'{}'::varchar[]"),
        comment="검색용 태그 — 예: ['혈액순환', '심전도', '응급간호']",
    )
    source: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="출처 — 예: '제66회 간호사 국가시험 1교시 #5'",
    )
    source_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        CheckConstraint("correct_answer >= 0", name="ck_questions_correct_answer_nonneg"),
        CheckConstraint(
            "jsonb_array_length(choices) >= 2", name="ck_questions_choices_min_length"
        ),
        Index("ix_questions_department_subject", "department", "subject"),
        Index("ix_questions_difficulty", "difficulty"),
        Index("ix_questions_tags_gin", "tags", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        preview = self.question_text[:30].replace("\n", " ")
        return f"<Question id={self.id} {self.department.value}/{self.subject} '{preview}...'>"
