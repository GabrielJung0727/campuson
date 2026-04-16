/**
 * @campuson/shared/questions — 문제은행 DTO.
 */

import type { Department, Difficulty, QuestionType } from './enums';

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
