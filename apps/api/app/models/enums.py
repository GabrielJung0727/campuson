"""Domain enum 정의 — User/학과/역할 등.

PostgreSQL native enum으로 매핑되어 DB 무결성을 보장합니다.
"""

import enum


class Department(str, enum.Enum):
    """학과 코드."""

    NURSING = "NURSING"
    PHYSICAL_THERAPY = "PHYSICAL_THERAPY"
    DENTAL_HYGIENE = "DENTAL_HYGIENE"

    @property
    def label_ko(self) -> str:
        return {
            Department.NURSING: "간호학과",
            Department.PHYSICAL_THERAPY: "물리치료학과",
            Department.DENTAL_HYGIENE: "치위생과",
        }[self]


class Role(str, enum.Enum):
    """사용자 역할 — RBAC의 기본 단위."""

    STUDENT = "STUDENT"
    PROFESSOR = "PROFESSOR"
    ADMIN = "ADMIN"
    DEVELOPER = "DEVELOPER"


class UserStatus(str, enum.Enum):
    """계정 상태."""

    PENDING = "PENDING"  # 가입 직후, 학과 인증 대기
    ACTIVE = "ACTIVE"  # 정상 사용
    SUSPENDED = "SUSPENDED"  # 관리자에 의한 비활성화
    DELETED = "DELETED"  # 소프트 삭제


class Level(str, enum.Enum):
    """학생 학습 수준 — 진단 테스트 및 AI 프로파일에서 사용."""

    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"


class Difficulty(str, enum.Enum):
    """문제 난이도."""

    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


class QuestionType(str, enum.Enum):
    """문제 유형 — 객관식/단답형 등."""

    SINGLE_CHOICE = "SINGLE_CHOICE"  # 객관식 단일 정답 (국시 대부분)
    MULTI_CHOICE = "MULTI_CHOICE"  # 객관식 복수 정답
    SHORT_ANSWER = "SHORT_ANSWER"  # 단답형 (현재 미사용, 향후)
