/**
 * @campuson/shared/history — 학습 이력/오답노트/통계 DTO.
 */

import type { Difficulty, ErrorType } from './enums';

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
  period_start: string;
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
