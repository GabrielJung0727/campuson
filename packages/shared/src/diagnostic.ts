/**
 * @campuson/shared/diagnostic — 진단 테스트 DTO.
 */

import type { ExplanationPreference, Level } from './enums';
import type { QuestionPublic } from './questions';

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
