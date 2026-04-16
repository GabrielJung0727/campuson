/**
 * @campuson/shared/kb — Knowledge Base 적재/검색 DTO.
 */

import type { Department, KBReviewStatus } from './enums';

export interface KBIngestRequest {
  department: Department;
  title: string;
  content: string;
  source?: string | null;
  source_url?: string | null;
  source_year?: number | null;
  tags?: string[];
  extra_metadata?: Record<string, unknown> | null;
  review_status?: KBReviewStatus;
}

export interface KBIngestResponse {
  document_id: string;
  total_chunks: number;
  total_tokens: number;
  embedded_chunks: number;
  embedding_model: string;
  embedding_dimensions: number;
}

export interface KBDocumentResponse {
  id: string;
  department: Department;
  title: string;
  summary: string | null;
  source: string | null;
  source_url: string | null;
  source_year: number | null;
  version: number;
  review_status: KBReviewStatus;
  tags: string[];
  total_chunks: number;
  total_tokens: number;
  created_at: string;
  updated_at: string;
}

export interface KBDocumentListResponse {
  items: KBDocumentResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface KBSearchRequest {
  query: string;
  department?: Department;
  tags?: string[];
  source_year?: number;
  top_k?: number;
  candidate_limit?: number;
  use_vector?: boolean;
  use_lexical?: boolean;
  rerank?: boolean;
  include_unpublished?: boolean;
}

export interface KBSearchHit {
  chunk_id: string;
  document_id: string;
  document_title: string;
  department: Department;
  chunk_index: number;
  content: string;
  source: string | null;
  tags: string[];
  vector_score: number | null;
  lexical_score: number | null;
  vector_rank: number | null;
  lexical_rank: number | null;
  rrf_score: number;
  rerank_score?: number | null;
  rerank_signals?: Record<string, number> | null;
}

export interface KBSearchResponse {
  query: string;
  total: number;
  reranked: boolean;
  reranker_name: string | null;
  hits: KBSearchHit[];
}
