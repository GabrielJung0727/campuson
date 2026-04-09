"""SQLAlchemy ORM 모델 패키지.

Alembic autogenerate가 모든 모델을 인식할 수 있도록 여기서 import합니다.
"""

from app.models.ai_profile import AIProfile, ExplanationPreference
from app.models.audit_log import AuditLog
from app.models.diagnostic import DiagnosticAnswer, DiagnosticTest
from app.models.enums import (
    Department,
    Difficulty,
    ErrorType,
    Level,
    QuestionType,
    Role,
    UserStatus,
)
from app.models.learning_history import LearningHistory
from app.models.question import Question
from app.models.user import User

__all__ = [
    "AIProfile",
    "AuditLog",
    "Department",
    "DiagnosticAnswer",
    "DiagnosticTest",
    "Difficulty",
    "ErrorType",
    "ExplanationPreference",
    "LearningHistory",
    "Level",
    "Question",
    "QuestionType",
    "Role",
    "User",
    "UserStatus",
]
