"""추천 엔진 Pydantic 스키마."""

from pydantic import BaseModel, Field

from app.models.enums import Level
from app.schemas.question import QuestionPublic


class RecommendedSetRequest(BaseModel):
    """추천 문제 세트 요청."""

    set_size: int = Field(default=20, ge=5, le=50)
    level_override: Level | None = Field(
        default=None,
        description="None이면 AI Profile의 level 사용",
    )


class RecommendedSetResponse(BaseModel):
    """추천 문제 세트 응답 — 정답/해설 제외."""

    questions: list[QuestionPublic]
    total_questions: int
    total_available: int
    strategy: str
    level: Level
    difficulty_distribution: dict[str, int]
