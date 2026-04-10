"""SQLAlchemy ORM 모델 패키지.

Alembic autogenerate가 모든 모델을 인식할 수 있도록 여기서 import합니다.
"""

from app.models.ai_profile import AIProfile, ExplanationPreference
from app.models.ai_request_log import AIRequestLog
from app.models.audit_log import AuditLog
from app.models.diagnostic import DiagnosticAnswer, DiagnosticTest
from app.models.enums import (
    AIRequestType,
    Department,
    Difficulty,
    EmbeddingProvider,
    ErrorType,
    KBReviewStatus,
    LLMProvider,
    Level,
    QuestionType,
    Role,
    UserStatus,
)
from app.models.kb_document import KBChunk, KBDocument
from app.models.learning_history import LearningHistory
from app.models.question import Question
from app.models.question_stats import AnswerInteraction, QuestionStats
from app.models.user import User

__all__ = [
    "AIProfile",
    "AIRequestLog",
    "AIRequestType",
    "AuditLog",
    "Department",
    "DiagnosticAnswer",
    "DiagnosticTest",
    "Difficulty",
    "EmbeddingProvider",
    "ErrorType",
    "ExplanationPreference",
    "KBChunk",
    "KBDocument",
    "KBReviewStatus",
    "LLMProvider",
    "LearningHistory",
    "Level",
    "Question",
    "QuestionType",
    "Role",
    "User",
    "UserStatus",
]
