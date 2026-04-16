"""SQLAlchemy ORM 모델 패키지.

Alembic autogenerate가 모든 모델을 인식할 수 있도록 여기서 import합니다.
"""

from app.models.ai_profile import AIProfile, ExplanationPreference
from app.models.announcement import Announcement
from app.models.assignment import Assignment, AssignmentSubmission, AssignmentStatus
from app.models.ai_request_log import AIRequestLog
from app.models.audit_log import AuditLog
from app.models.background_job import BackgroundJob
from app.models.cost_daily import CostDaily
from app.models.diagnostic import DiagnosticAnswer, DiagnosticTest
from app.models.enums import (
    AIRequestType,
    Department,
    Difficulty,
    EmbeddingProvider,
    ErrorType,
    EvalGrade,
    EvalStatus,
    JobStatus,
    JobType,
    KBReviewStatus,
    LLMProvider,
    Level,
    NotificationCategory,
    PracticumCategory,
    QuestionType,
    Role,
    UserStatus,
)
from app.models.notification import Notification
from app.models.practicum import PracticumScenario, PracticumSession
from app.models.kb_document import KBChunk, KBDocument
from app.models.learning_history import LearningHistory
from app.models.professor_class import ClassStudent, ProfessorClass
from app.models.question import Question
from app.models.question_stats import AnswerInteraction, QuestionStats
from app.models.user import User

__all__ = [
    "AIProfile",
    "AIRequestLog",
    "AIRequestType",
    "AuditLog",
    "BackgroundJob",
    "CostDaily",
    "Department",
    "DiagnosticAnswer",
    "DiagnosticTest",
    "Difficulty",
    "EmbeddingProvider",
    "ErrorType",
    "ExplanationPreference",
    "JobStatus",
    "JobType",
    "KBChunk",
    "KBDocument",
    "KBReviewStatus",
    "LLMProvider",
    "LearningHistory",
    "Level",
    "Notification",
    "NotificationCategory",
    "Question",
    "QuestionType",
    "Role",
    "User",
    "UserStatus",
]
