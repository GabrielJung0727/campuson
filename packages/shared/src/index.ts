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
