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


class AIRequestType(str, enum.Enum):
    """AI 요청 유형 — 프롬프트 템플릿과 1:1 매핑."""

    QA = "QA"  # 자유 질의응답
    EXPLAIN = "EXPLAIN"  # 문제 해설 생성
    RECOMMEND = "RECOMMEND"  # 학습 추천
    WEAKNESS_ANALYSIS = "WEAKNESS_ANALYSIS"  # 취약 영역 분석


class LLMProvider(str, enum.Enum):
    """LLM 제공자."""

    ANTHROPIC = "ANTHROPIC"
    OPENAI = "OPENAI"
    MOCK = "MOCK"


class EmbeddingProvider(str, enum.Enum):
    """임베딩 제공자 (Day 8)."""

    OPENAI = "OPENAI"
    MOCK = "MOCK"


class KBReviewStatus(str, enum.Enum):
    """지식베이스 문서 검수 상태 (Day 8)."""

    DRAFT = "DRAFT"
    REVIEWED = "REVIEWED"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


# === v0.3 역할 세분화 ===

class ProfessorRole(str, enum.Enum):
    """교수 세부 역할."""

    FULL_TIME = "FULL_TIME"  # 전임교수
    ADJUNCT = "ADJUNCT"  # 겸임교수
    DEPT_HEAD = "DEPT_HEAD"  # 학과장


class AdminRole(str, enum.Enum):
    """관리자 세부 역할 — 경복대 행정조직 반영."""

    ACADEMIC_AFFAIRS = "ACADEMIC_AFFAIRS"  # 교무처
    STUDENT_AFFAIRS = "STUDENT_AFFAIRS"  # 학생처
    GENERAL_ADMIN = "GENERAL_ADMIN"  # 사무국
    PLANNING = "PLANNING"  # 기획처
    IT_CENTER = "IT_CENTER"  # 디지털정보처
    ADMISSIONS = "ADMISSIONS"  # 입학홍보처
    SUPER_ADMIN = "SUPER_ADMIN"  # 총괄 관리자


class StudentNationality(str, enum.Enum):
    """학생 국적."""

    KOREAN = "KOREAN"
    INTERNATIONAL = "INTERNATIONAL"


class AnnouncementTarget(str, enum.Enum):
    """공지 대상."""

    ALL = "ALL"
    STUDENT = "STUDENT"
    PROFESSOR = "PROFESSOR"
    ADMIN = "ADMIN"
    DEVELOPER = "DEVELOPER"


class AnnouncementType(str, enum.Enum):
    """공지 유형."""

    GENERAL = "GENERAL"
    MAINTENANCE = "MAINTENANCE"
    URGENT = "URGENT"


# ── 문항 검수 (v0.5) ──


class QuestionReviewStatus(str, enum.Enum):
    """문항 검수 상태."""

    PENDING_REVIEW = "PENDING_REVIEW"  # 검수 대기
    APPROVED = "APPROVED"              # 교수 승인 → 학생 공개
    REJECTED = "REJECTED"              # 반려
    REVISION_REQUESTED = "REVISION_REQUESTED"  # 수정 요청

    @property
    def label_ko(self) -> str:
        return {
            QuestionReviewStatus.PENDING_REVIEW: "검수 대기",
            QuestionReviewStatus.APPROVED: "승인됨",
            QuestionReviewStatus.REJECTED: "반려됨",
            QuestionReviewStatus.REVISION_REQUESTED: "수정 요청",
        }[self]


# ── 실습 평가 (v0.4) ──


class PracticumCategory(str, enum.Enum):
    """실습 평가 유형."""

    # 간호학과
    HAND_HYGIENE = "HAND_HYGIENE"
    VITAL_SIGNS = "VITAL_SIGNS"
    INJECTION = "INJECTION"
    ASEPTIC_TECHNIQUE = "ASEPTIC_TECHNIQUE"
    BLS = "BLS"
    # 물리치료학과
    ROM_MEASUREMENT = "ROM_MEASUREMENT"
    GAIT_TRAINING = "GAIT_TRAINING"
    ELECTROTHERAPY = "ELECTROTHERAPY"
    PATIENT_TRANSFER = "PATIENT_TRANSFER"
    # 치위생학과
    SCALING = "SCALING"
    ORAL_EXAM = "ORAL_EXAM"
    INFECTION_CONTROL = "INFECTION_CONTROL"
    TOOTH_POLISHING = "TOOTH_POLISHING"

    @property
    def label_ko(self) -> str:
        return {
            PracticumCategory.HAND_HYGIENE: "손위생",
            PracticumCategory.VITAL_SIGNS: "활력징후 측정",
            PracticumCategory.INJECTION: "주사 술기",
            PracticumCategory.ASEPTIC_TECHNIQUE: "무균술",
            PracticumCategory.BLS: "기본 심폐소생술",
            PracticumCategory.ROM_MEASUREMENT: "ROM 측정",
            PracticumCategory.GAIT_TRAINING: "보행 훈련 지도",
            PracticumCategory.ELECTROTHERAPY: "전기치료 장비 세팅",
            PracticumCategory.PATIENT_TRANSFER: "환자 이동 보조",
            PracticumCategory.SCALING: "스케일링",
            PracticumCategory.ORAL_EXAM: "구강검진",
            PracticumCategory.INFECTION_CONTROL: "감염관리 절차",
            PracticumCategory.TOOTH_POLISHING: "치면세마",
        }[self]


class EvalGrade(str, enum.Enum):
    """실습 평가 등급."""

    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    NEEDS_IMPROVEMENT = "NEEDS_IMPROVEMENT"
    FAIL = "FAIL"

    @property
    def label_ko(self) -> str:
        return {
            EvalGrade.EXCELLENT: "우수",
            EvalGrade.GOOD: "양호",
            EvalGrade.NEEDS_IMPROVEMENT: "보완 필요",
            EvalGrade.FAIL: "불합격",
        }[self]


class EvalStatus(str, enum.Enum):
    """실습 세션 상태."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    REVIEWED = "REVIEWED"


class PracticumMode(str, enum.Enum):
    """실습 세션 모드."""

    SELF = "SELF"          # 학생 자체 체크
    VIDEO = "VIDEO"        # 영상 업로드 + AI 평가
    LIVE = "LIVE"          # 교수 실시간 세션


# ── 백그라운드 잡 (v0.6) ──


class JobType(str, enum.Enum):
    """백그라운드 작업 유형."""

    PDF_EXTRACT = "PDF_EXTRACT"          # PDF → 텍스트 추출
    CHUNKING = "CHUNKING"                # 문서 → 청크 분할
    EMBEDDING = "EMBEDDING"              # 청크 → 임베딩 생성
    BULK_QUESTION_GEN = "BULK_QUESTION_GEN"  # 문제 대량 생성
    STATS_AGGREGATE = "STATS_AGGREGATE"  # 학습 통계 집계
    RECOMMENDATION = "RECOMMENDATION"    # 추천 모델 계산
    PRACTICUM_POST = "PRACTICUM_POST"    # 실습 결과 후처리
    AI_LOG_ANALYSIS = "AI_LOG_ANALYSIS"  # AI 피드백 로그 분석
    EMAIL_SEND = "EMAIL_SEND"            # 메일/알림 발송
    COST_AGGREGATE = "COST_AGGREGATE"    # 비용 집계
    CLEANUP_EXPIRED_TOKENS = "CLEANUP_EXPIRED_TOKENS"  # 만료 토큰 GC (v1.0 보안)

    @property
    def label_ko(self) -> str:
        return {
            JobType.PDF_EXTRACT: "PDF 텍스트 추출",
            JobType.CHUNKING: "문서 청크 분할",
            JobType.EMBEDDING: "임베딩 생성",
            JobType.BULK_QUESTION_GEN: "문제 대량 생성",
            JobType.STATS_AGGREGATE: "학습 통계 집계",
            JobType.RECOMMENDATION: "추천 모델 계산",
            JobType.PRACTICUM_POST: "실습 결과 후처리",
            JobType.AI_LOG_ANALYSIS: "AI 로그 분석",
            JobType.EMAIL_SEND: "메일 발송",
            JobType.COST_AGGREGATE: "비용 집계",
            JobType.CLEANUP_EXPIRED_TOKENS: "만료 토큰 정리",
        }[self]


class JobStatus(str, enum.Enum):
    """백그라운드 작업 상태."""

    PENDING = "PENDING"        # 대기중
    RUNNING = "RUNNING"        # 실행중
    SUCCESS = "SUCCESS"        # 완료
    FAILED = "FAILED"          # 실패
    RETRYING = "RETRYING"      # 재시도중
    DEAD_LETTER = "DEAD_LETTER"  # 최종 실패 (dead-letter)


# ── 알림 (v0.6) ──


class NotificationCategory(str, enum.Enum):
    """알림 카테고리."""

    ASSIGNMENT_DUE = "ASSIGNMENT_DUE"          # 과제 마감 임박
    DIAGNOSTIC_REMINDER = "DIAGNOSTIC_REMINDER"  # 진단 테스트 미완료
    PROFESSOR_FEEDBACK = "PROFESSOR_FEEDBACK"  # 교수 피드백 도착
    WEAK_AREA_REVIEW = "WEAK_AREA_REVIEW"      # 취약 영역 복습 추천
    PRACTICUM_SCHEDULE = "PRACTICUM_SCHEDULE"  # 실습 시험 일정
    ANNOUNCEMENT = "ANNOUNCEMENT"              # 공지사항
    KB_UPDATE = "KB_UPDATE"                    # 지식베이스 업데이트
    SYSTEM = "SYSTEM"                          # 시스템 알림

    @property
    def label_ko(self) -> str:
        return {
            NotificationCategory.ASSIGNMENT_DUE: "과제 마감 임박",
            NotificationCategory.DIAGNOSTIC_REMINDER: "진단 테스트 미완료",
            NotificationCategory.PROFESSOR_FEEDBACK: "교수 피드백 도착",
            NotificationCategory.WEAK_AREA_REVIEW: "취약 영역 복습 추천",
            NotificationCategory.PRACTICUM_SCHEDULE: "실습 시험 일정",
            NotificationCategory.ANNOUNCEMENT: "공지사항",
            NotificationCategory.KB_UPDATE: "지식베이스 업데이트",
            NotificationCategory.SYSTEM: "시스템",
        }[self]
