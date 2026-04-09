"""QuestionBank Pydantic 스키마."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import Department, Difficulty, QuestionType


class QuestionBase(BaseModel):
    """Question 공통 필드 (생성/업데이트 공유)."""

    department: Department
    subject: str = Field(..., min_length=1, max_length=100)
    unit: str | None = Field(default=None, max_length=100)
    difficulty: Difficulty = Difficulty.MEDIUM
    question_type: QuestionType = QuestionType.SINGLE_CHOICE
    question_text: str = Field(..., min_length=1)
    choices: list[str] = Field(..., min_length=2, max_length=10)
    correct_answer: int = Field(..., ge=0)
    explanation: str | None = None
    tags: list[str] = Field(default_factory=list, max_length=20)
    source: str | None = Field(default=None, max_length=200)
    source_year: int | None = Field(default=None, ge=1990, le=2100)

    @model_validator(mode="after")
    def _check_correct_answer_in_range(self) -> "QuestionBase":
        if self.correct_answer >= len(self.choices):
            raise ValueError(
                f"correct_answer({self.correct_answer}) must be less than "
                f"len(choices)({len(self.choices)})"
            )
        return self


class QuestionCreate(QuestionBase):
    """문제 생성 요청."""

    pass


class QuestionUpdate(BaseModel):
    """문제 부분 업데이트 요청 (PATCH 의미론)."""

    subject: str | None = Field(default=None, max_length=100)
    unit: str | None = Field(default=None, max_length=100)
    difficulty: Difficulty | None = None
    question_type: QuestionType | None = None
    question_text: str | None = None
    choices: list[str] | None = Field(default=None, min_length=2, max_length=10)
    correct_answer: int | None = Field(default=None, ge=0)
    explanation: str | None = None
    tags: list[str] | None = Field(default=None, max_length=20)
    source: str | None = Field(default=None, max_length=200)
    source_year: int | None = Field(default=None, ge=1990, le=2100)


class QuestionResponse(QuestionBase):
    """문제 응답 (학생/일반)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class QuestionPublic(BaseModel):
    """학생이 풀이 시 보는 안전한 표현 — 정답/해설 제외.

    학생용 엔드포인트에서 사용하여 정답 노출을 방지한다.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    department: Department
    subject: str
    unit: str | None
    difficulty: Difficulty
    question_type: QuestionType
    question_text: str
    choices: list[str]
    tags: list[str]


class QuestionListResponse(BaseModel):
    """페이지네이션 응답."""

    items: list[QuestionResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


class BulkUploadResult(BaseModel):
    """CSV/Excel 일괄 업로드 결과."""

    total_rows: int
    inserted: int
    failed: int
    errors: list[dict] = Field(
        default_factory=list,
        description="실패한 행의 인덱스/필드/메시지 — 최대 100건",
    )
