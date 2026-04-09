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


class ErrorType(str, enum.Enum):
    """오답 분류 — Day 5 룰 베이스, Day 9 이후 LLM으로 정교화 예정."""

    CONCEPT_GAP = "CONCEPT_GAP"  # 개념 부족형 — 같은 문제 반복 오답
    CONFUSION = "CONFUSION"  # 헷갈림형 — 일반 오답 (기본값)
    CARELESS = "CARELESS"  # 실수형 — 매우 짧은 풀이 시간
    APPLICATION_GAP = "APPLICATION_GAP"  # 응용 부족형 — 매우 긴 풀이 시간

    @property
    def label_ko(self) -> str:
        return {
            ErrorType.CONCEPT_GAP: "개념 부족형",
            ErrorType.CONFUSION: "헷갈림형",
            ErrorType.CARELESS: "실수형",
            ErrorType.APPLICATION_GAP: "응용 부족형",
        }[self]
