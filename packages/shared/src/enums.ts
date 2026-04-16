/**
 * @campuson/shared/enums — 도메인 상수/라벨.
 *
 * v0.9 모노레포 정리: index.ts 분할의 일환으로 enum 전용 파일.
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

export const AIRequestType = {
  QA: 'QA',
  EXPLAIN: 'EXPLAIN',
  RECOMMEND: 'RECOMMEND',
  WEAKNESS_ANALYSIS: 'WEAKNESS_ANALYSIS',
} as const;
export type AIRequestType = (typeof AIRequestType)[keyof typeof AIRequestType];

export const LLMProvider = {
  ANTHROPIC: 'ANTHROPIC',
  OPENAI: 'OPENAI',
  MOCK: 'MOCK',
} as const;
export type LLMProvider = (typeof LLMProvider)[keyof typeof LLMProvider];

export const KBReviewStatus = {
  DRAFT: 'DRAFT',
  REVIEWED: 'REVIEWED',
  PUBLISHED: 'PUBLISHED',
  ARCHIVED: 'ARCHIVED',
} as const;
export type KBReviewStatus = (typeof KBReviewStatus)[keyof typeof KBReviewStatus];
