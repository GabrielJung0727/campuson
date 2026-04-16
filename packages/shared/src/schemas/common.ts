/**
 * 공통 Zod 스키마 — Pydantic 모델과 1:1 대응.
 *
 * 프론트엔드 폼 검증 + API 요청/응답 타이핑에 사용.
 */

import { z } from 'zod';

// === Base field schemas ===

export const uuidSchema = z.string().uuid();
export const emailSchema = z.string().email();
export const dateTimeSchema = z.string().datetime();

// === Auth ===

export const LoginRequestSchema = z.object({
  email: emailSchema,
  password: z.string().min(8, '비밀번호는 8자 이상이어야 합니다'),
});

export const RegisterRequestSchema = z.object({
  email: emailSchema,
  password: z
    .string()
    .min(8, '비밀번호는 8자 이상이어야 합니다')
    .regex(/[a-zA-Z]/, '영문자를 포함해야 합니다')
    .regex(/\d/, '숫자를 포함해야 합니다')
    .refine((s) => !s.includes(' '), '공백은 포함할 수 없습니다'),
  name: z.string().min(1).max(50),
  department: z.enum(['NURSING', 'PHYSICAL_THERAPY', 'DENTAL_HYGIENE']),
  role: z.enum(['STUDENT', 'PROFESSOR', 'ADMIN', 'DEVELOPER']).default('STUDENT'),
  student_no: z.string().max(20).optional(),
});

export const PasswordChangeSchema = z.object({
  current_password: z.string().min(1),
  new_password: z
    .string()
    .min(8)
    .regex(/[a-zA-Z]/)
    .regex(/\d/)
    .refine((s) => !s.includes(' ')),
});

// === Calendar ===

export const CalendarEventCreateSchema = z.object({
  title: z.string().min(1).max(200),
  event_type: z.enum([
    'assignment_due', 'exam', 'practicum', 'diagnostic', 'review', 'custom',
  ]).default('custom'),
  start_at: dateTimeSchema,
  end_at: dateTimeSchema.optional(),
  all_day: z.boolean().default(false),
  description: z.string().max(2000).optional(),
  color: z.string().optional(),
  reminder_minutes: z.number().int().nonnegative().optional(),
});

// === Professor Comment ===

export const CommentCreateSchema = z.object({
  student_id: uuidSchema,
  target_type: z.enum([
    'learning_history', 'assignment_submission', 'practicum_session', 'general',
  ]),
  content: z.string().min(1).max(2000),
  target_id: uuidSchema.optional(),
  is_private: z.boolean().default(false),
});

// === OSCE ===

export const StationInputSchema = z.object({
  scenario_id: uuidSchema,
  station_name: z.string().optional(),
  time_limit_sec: z.number().int().positive().optional(),
  weight: z.number().positive().default(1.0),
  instructions: z.string().optional(),
});

export const OSCEExamCreateSchema = z.object({
  department: z.enum(['NURSING', 'PHYSICAL_THERAPY', 'DENTAL_HYGIENE']),
  name: z.string().min(1).max(200),
  description: z.string().optional(),
  time_per_station_sec: z.number().int().min(60).default(600),
  transition_time_sec: z.number().int().nonnegative().default(60),
  stations: z.array(StationInputSchema).min(1),
});

export const RubricCreateSchema = z.object({
  department: z.enum(['NURSING', 'PHYSICAL_THERAPY', 'DENTAL_HYGIENE']),
  name: z.string().min(1).max(200),
  description: z.string().optional(),
  criteria: z.array(z.record(z.unknown())).min(1),
  total_score: z.number().int().positive().default(100),
  scenario_id: uuidSchema.optional(),
});

// === School ===

export const SchoolCreateSchema = z.object({
  name: z.string().min(1).max(200),
  code: z.string().min(2).max(50),
  domain: z.string().optional(),
  logo_url: z.string().url().optional(),
  primary_color: z.string().default('#2563EB'),
  secondary_color: z.string().default('#1E40AF'),
});

// === Question Answer ===

export const AnswerSubmitSchema = z.object({
  question_id: uuidSchema,
  user_answer: z.string().min(1),
  time_spent_sec: z.number().nonnegative().optional(),
  source: z.string().optional(),
});

// === Types ===

export type LoginRequest = z.infer<typeof LoginRequestSchema>;
export type RegisterRequest = z.infer<typeof RegisterRequestSchema>;
export type PasswordChangeRequest = z.infer<typeof PasswordChangeSchema>;
export type CalendarEventCreate = z.infer<typeof CalendarEventCreateSchema>;
export type CommentCreate = z.infer<typeof CommentCreateSchema>;
export type OSCEExamCreate = z.infer<typeof OSCEExamCreateSchema>;
export type RubricCreate = z.infer<typeof RubricCreateSchema>;
export type SchoolCreate = z.infer<typeof SchoolCreateSchema>;
export type AnswerSubmit = z.infer<typeof AnswerSubmitSchema>;
