/**
 * 통합 에러 응답 스키마 — Zod + TypeScript.
 *
 * 백엔드 Pydantic ErrorResponse와 1:1 대응.
 * 프론트엔드에서 API 에러 파싱 시 사용.
 */

import { z } from 'zod';

// === Error Codes ===

export const ErrorCode = {
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  NOT_FOUND: 'NOT_FOUND',
  UNAUTHORIZED: 'UNAUTHORIZED',
  FORBIDDEN: 'FORBIDDEN',
  CONFLICT: 'CONFLICT',
  RATE_LIMITED: 'RATE_LIMITED',
  INTERNAL_ERROR: 'INTERNAL_ERROR',
  SERVICE_UNAVAILABLE: 'SERVICE_UNAVAILABLE',
  BAD_REQUEST: 'BAD_REQUEST',
} as const;
export type ErrorCode = (typeof ErrorCode)[keyof typeof ErrorCode];

// === Zod Schemas ===

export const ErrorDetailSchema = z.object({
  field: z.string(),
  message: z.string(),
  type: z.string().nullish(),
});

export const ErrorBodySchema = z.object({
  code: z.string(),
  message: z.string(),
  details: z.array(ErrorDetailSchema).nullish(),
  request_id: z.string().nullish(),
});

export const ErrorResponseSchema = z.object({
  error: ErrorBodySchema,
});

// === TypeScript types (Zod에서 추론) ===

export type ErrorDetail = z.infer<typeof ErrorDetailSchema>;
export type ErrorBody = z.infer<typeof ErrorBodySchema>;
export type ApiErrorResponse = z.infer<typeof ErrorResponseSchema>;

// === Helper ===

/**
 * API 에러 응답을 파싱합니다.
 * 파싱 실패 시 null 반환 (예: 네트워크 에러).
 */
export function parseApiError(body: unknown): ApiErrorResponse | null {
  const result = ErrorResponseSchema.safeParse(body);
  return result.success ? result.data : null;
}
