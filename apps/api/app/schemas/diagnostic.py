"""진단 테스트 Pydantic 스키마."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Level
from app.schemas.question import QuestionPublic


class DiagnosticStartResponse(BaseModel):
    """진단 테스트 시작 응답.

    클라이언트는 `test_id`와 함께 받은 `questions` 리스트로 응시한 뒤,
    `test_id`에 결과를 제출한다.
    """

    test_id: uuid.UUID
    started_at: datetime
    total_questions: int
    questions: list[QuestionPublic]


class DiagnosticAnswerInput(BaseModel):
    """제출 시 1문항 응답."""

    question_id: uuid.UUID
    selected_choice: int = Field(..., ge=0)
    time_spent_sec: int = Field(default=0, ge=0)


class DiagnosticSubmitRequest(BaseModel):
    """진단 테스트 제출 요청."""

    answers: list[DiagnosticAnswerInput] = Field(..., min_length=1, max_length=200)


class WeakAreaItem(BaseModel):
    """취약영역 1건."""

    subject: str
    unit: str | None = None
    score: float = Field(..., ge=0.0, le=1.0)
    priority: int = Field(..., ge=1)
    correct_count: int
    total_count: int


class DiagnosticResultResponse(BaseModel):
    """진단 테스트 채점 결과."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    started_at: datetime
    completed_at: datetime | None
    total_score: float | None
    section_scores: dict[str, float] | None
    weak_areas: list[WeakAreaItem] | None
    level: Level | None
    answer_count: int = 0


class AIProfileResponse(BaseModel):
    """AI 프로파일 조회 응답."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    level: Level
    weak_priority: list[dict]
    learning_path: list[dict]
    explanation_pref: str
    frequent_topics: list[str]
    updated_at: datetime
