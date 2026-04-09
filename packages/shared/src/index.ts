/**
 * @campuson/shared — 프론트엔드와 (잠재적) 다른 클라이언트가 공유하는 타입.
 *
 * Day 1 기준: User/Department/Role enum만 포함.
 * Day 2부터 API 응답 DTO가 추가됩니다.
 */

export const Department = {
  NURSING: 'NURSING',
  PHYSICAL_THERAPY: 'PHYSICAL_THERAPY',
  DENTAL_HYGIENE: 'DENTAL_HYGIENE',
} as const;
export type Department = (typeof Department)[keyof typeof Department];

export const DepartmentLabel: Record<Department, string> = {
  NURSING: '간호학과',
  PHYSICAL_THERAPY: '물리치료학과',
  DENTAL_HYGIENE: '치위생과',
};

export const Role = {
  STUDENT: 'STUDENT',
  PROFESSOR: 'PROFESSOR',
  ADMIN: 'ADMIN',
  DEVELOPER: 'DEVELOPER',
} as const;
export type Role = (typeof Role)[keyof typeof Role];

export const UserStatus = {
  PENDING: 'PENDING',
  ACTIVE: 'ACTIVE',
  SUSPENDED: 'SUSPENDED',
  DELETED: 'DELETED',
} as const;
export type UserStatus = (typeof UserStatus)[keyof typeof UserStatus];

export const Level = {
  BEGINNER: 'BEGINNER',
  INTERMEDIATE: 'INTERMEDIATE',
  ADVANCED: 'ADVANCED',
} as const;
export type Level = (typeof Level)[keyof typeof Level];

export const ExplanationPreference = {
  SIMPLE: 'SIMPLE',
  DETAILED: 'DETAILED',
  EXPERT: 'EXPERT',
} as const;
export type ExplanationPreference =
  (typeof ExplanationPreference)[keyof typeof ExplanationPreference];

export interface User {
  id: string;
  email: string;
  name: string;
  studentNo: string | null;
  department: Department;
  role: Role;
  status: UserStatus;
  createdAt: string;
  updatedAt: string;
  lastLoginAt: string | null;
}

// =====================================================
// Auth API DTOs (Day 2 추가)
// =====================================================

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
  department: Department;
  role?: Role;
  student_no?: string | null;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  user: User;
}

export interface AccessTokenResponse {
  access_token: string;
  token_type: 'bearer';
}

export interface RefreshTokenRequest {
  refresh_token: string;
}

export interface PasswordResetRequest {
  email: string;
}

export interface PasswordResetConfirm {
  token: string;
  new_password: string;
}

export interface PasswordChangeRequest {
  current_password: string;
  new_password: string;
}

export interface ApiError {
  detail: string;
}

export interface MessageResponse {
  message: string;
}

// =====================================================
// Question API DTOs (Day 3 추가)
// =====================================================

export const Difficulty = {
  EASY: 'EASY',
  MEDIUM: 'MEDIUM',
  HARD: 'HARD',
} as const;
export type Difficulty = (typeof Difficulty)[keyof typeof Difficulty];

export const QuestionType = {
  SINGLE_CHOICE: 'SINGLE_CHOICE',
  MULTI_CHOICE: 'MULTI_CHOICE',
  SHORT_ANSWER: 'SHORT_ANSWER',
} as const;
export type QuestionType = (typeof QuestionType)[keyof typeof QuestionType];

export interface Question {
  id: string;
  department: Department;
  subject: string;
  unit: string | null;
  difficulty: Difficulty;
  question_type: QuestionType;
  question_text: string;
  choices: string[];
  correct_answer: number;
  explanation: string | null;
  tags: string[];
  source: string | null;
  source_year: number | null;
  created_at: string;
  updated_at: string;
}

export interface QuestionPublic {
  id: string;
  department: Department;
  subject: string;
  unit: string | null;
  difficulty: Difficulty;
  question_type: QuestionType;
  question_text: string;
  choices: string[];
  tags: string[];
}

export interface QuestionListResponse {
  items: Question[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

export interface QuestionFilters {
  department?: Department;
  subject?: string;
  unit?: string;
  difficulty?: Difficulty;
  question_type?: QuestionType;
  tags?: string[];
  tags_match_all?: boolean;
  keyword?: string;
  source_year?: number;
  page?: number;
  page_size?: number;
}

export interface BulkUploadResult {
  total_rows: number;
  inserted: number;
  failed: number;
  errors: Array<{ row: number; error: string }>;
}

// =====================================================
// Diagnostic Test API DTOs (Day 4 추가)
// =====================================================

export interface DiagnosticStartResponse {
  test_id: string;
  started_at: string;
  total_questions: number;
  questions: QuestionPublic[];
}

export interface DiagnosticAnswerInput {
  question_id: string;
  selected_choice: number;
  time_spent_sec?: number;
}

export interface DiagnosticSubmitRequest {
  answers: DiagnosticAnswerInput[];
}

export interface WeakAreaItem {
  subject: string;
  unit: string | null;
  score: number;
  priority: number;
  correct_count: number;
  total_count: number;
}

export interface DiagnosticResultResponse {
  id: string;
  user_id: string;
  started_at: string;
  completed_at: string | null;
  total_score: number | null;
  section_scores: Record<string, number> | null;
  weak_areas: WeakAreaItem[] | null;
  level: Level | null;
  answer_count: number;
}

export interface LearningPathStep {
  step: number;
  subject: string;
  unit: string | null;
  score: number | null;
  rationale: string;
}

export interface AIProfileResponse {
  id: string;
  user_id: string;
  level: Level;
  weak_priority: WeakAreaItem[];
  learning_path: LearningPathStep[];
  explanation_pref: ExplanationPreference;
  frequent_topics: string[];
  updated_at: string;
}

// =====================================================
// Learning History API DTOs (Day 5 추가)
// =====================================================

export const ErrorType = {
  CONCEPT_GAP: 'CONCEPT_GAP',
  CONFUSION: 'CONFUSION',
  CARELESS: 'CARELESS',
  APPLICATION_GAP: 'APPLICATION_GAP',
} as const;
export type ErrorType = (typeof ErrorType)[keyof typeof ErrorType];

export const ErrorTypeLabel: Record<ErrorType, string> = {
  CONCEPT_GAP: '개념 부족형',
  CONFUSION: '헷갈림형',
  CARELESS: '실수형',
  APPLICATION_GAP: '응용 부족형',
};

export interface AnswerSubmitRequest {
  question_id: string;
  selected_choice: number;
  solving_time_sec?: number;
}

export interface AnswerSubmitResponse {
  history_id: string;
  question_id: string;
  is_correct: boolean;
  correct_answer: number;
  selected_choice: number;
  error_type: ErrorType | null;
  explanation: string | null;
  attempt_no: number;
  solving_time_sec: number;
}

export interface LearningHistoryItem {
  id: string;
  question_id: string;
  selected_choice: number;
  is_correct: boolean;
  solving_time_sec: number;
  error_type: ErrorType | null;
  attempt_no: number;
  created_at: string;
  subject: string | null;
  unit: string | null;
  difficulty: Difficulty | null;
  question_text_preview: string | null;
}

export interface LearningHistoryListResponse {
  items: LearningHistoryItem[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

export interface WrongAnswerItem {
  question_id: string;
  subject: string;
  unit: string | null;
  difficulty: Difficulty;
  question_text_preview: string;
  last_error_type: ErrorType | null;
  wrong_count: number;
  total_attempts: number;
  last_attempted_at: string;
  is_resolved: boolean;
}

export interface WrongAnswerListResponse {
  items: WrongAnswerItem[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

export type StatsPeriod = 'daily' | 'weekly' | 'monthly';

export interface StatsBucket {
  period_start: string; // ISO date
  total_attempts: number;
  correct_count: number;
  wrong_count: number;
  accuracy: number;
  avg_solving_time_sec: number;
}

export interface SubjectBreakdown {
  subject: string;
  total_attempts: number;
  correct_count: number;
  wrong_count: number;
  accuracy: number;
}

export interface LearningStatsResponse {
  period: StatsPeriod;
  buckets: StatsBucket[];
  subject_breakdown: SubjectBreakdown[];
  overall_accuracy: number;
  total_attempts: number;
  total_correct: number;
  total_wrong: number;
  error_type_distribution: Record<string, number>;
}
