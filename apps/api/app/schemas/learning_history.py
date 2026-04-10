"""학습 이력 Pydantic 스키마."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Difficulty, ErrorType
from app.schemas.question import QuestionPublic


# === 풀이 제출 ===
class ChoiceEvent(BaseModel):
    """선택지 클릭 이벤트 1건."""

    choice: int = Field(..., ge=0)
    ts: int = Field(..., ge=0, description="문제 진입 후 경과 시간 (ms)")


class AnswerSubmitRequest(BaseModel):
    """문제 풀이 제출 요청 (v0.2: 트래킹 포함)."""

    question_id: uuid.UUID
    selected_choice: int = Field(..., ge=0)
    solving_time_sec: int = Field(default=0, ge=0)
    # v0.2 트래킹 (선택적 — 없으면 무시)
    time_to_first_click_ms: int = Field(default=0, ge=0)
    first_choice: int = Field(default=-1, ge=-1)
    choice_changes: int = Field(default=0, ge=0)
    choice_sequence: list[ChoiceEvent] = Field(default_factory=list)


class AnswerSubmitResponse(BaseModel):
    """풀이 제출 응답 (채점 결과 + 분류)."""

    history_id: uuid.UUID
    question_id: uuid.UUID
    is_correct: bool
    correct_answer: int
    selected_choice: int
    error_type: ErrorType | None
    explanation: str | None
    attempt_no: int
    solving_time_sec: int


# === 학습 이력 조회 ===
class LearningHistoryItem(BaseModel):
    """학습 이력 1건 + 문제 메타 일부."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question_id: uuid.UUID
    selected_choice: int
    is_correct: bool
    solving_time_sec: int
    error_type: ErrorType | None
    attempt_no: int
    created_at: datetime
    # 문제 컨텍스트 (조인 결과)
    subject: str | None = None
    unit: str | None = None
    difficulty: Difficulty | None = None
    question_text_preview: str | None = None


class LearningHistoryListResponse(BaseModel):
    items: list[LearningHistoryItem]
    total: int
    page: int
    page_size: int
    has_next: bool


# === 오답노트 ===
class WrongAnswerItem(BaseModel):
    """오답노트 1건 — 누적 오답 집계 단위."""

    question_id: uuid.UUID
    subject: str
    unit: str | None
    difficulty: Difficulty
    question_text_preview: str
    last_error_type: ErrorType | None
    wrong_count: int = Field(..., description="해당 문제의 누적 오답 횟수")
    total_attempts: int
    last_attempted_at: datetime
    is_resolved: bool = Field(
        ..., description="가장 최근 풀이가 정답이면 True"
    )


class WrongAnswerListResponse(BaseModel):
    items: list[WrongAnswerItem]
    total: int
    page: int
    page_size: int
    has_next: bool


# === 학습 통계 ===
StatsPeriod = Literal["daily", "weekly", "monthly"]


class StatsBucket(BaseModel):
    """기간 1구간의 통계."""

    period_start: date
    total_attempts: int
    correct_count: int
    wrong_count: int
    accuracy: float = Field(..., ge=0.0, le=1.0)
    avg_solving_time_sec: float


class SubjectBreakdown(BaseModel):
    """과목별 누적 통계."""

    subject: str
    total_attempts: int
    correct_count: int
    accuracy: float
    wrong_count: int


class LearningStatsResponse(BaseModel):
    """학습 통계 집계 응답."""

    period: StatsPeriod
    buckets: list[StatsBucket]
    subject_breakdown: list[SubjectBreakdown]
    overall_accuracy: float
    total_attempts: int
    total_correct: int
    total_wrong: int
    error_type_distribution: dict[str, int]
