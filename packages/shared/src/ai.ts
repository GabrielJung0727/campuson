/**
 * @campuson/shared/ai — AI Gateway / LLM 요청 로그 DTO.
 */

import type { AIRequestType, LLMProvider } from './enums';

export interface ExplainRequest {
  question_id: string;
  history_id?: string | null;
}

export interface QARequest {
  question: string;
}

export interface AIGenerationMetadata {
  log_id: string;
  provider: LLMProvider;
  model: string;
  template_name: string | null;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
}

export interface AIGenerationResponse {
  request_type: AIRequestType;
  output_text: string;
  metadata: AIGenerationMetadata;
}

export interface AIRequestLogItem {
  id: string;
  user_id: string | null;
  request_type: AIRequestType;
  template_name: string | null;
  question_id: string | null;
  provider: LLMProvider;
  model: string;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
  success: boolean;
  error_message: string | null;
  created_at: string;
}

export interface AIRequestLogListResponse {
  items: AIRequestLogItem[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}
