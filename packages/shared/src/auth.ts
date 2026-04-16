/**
 * @campuson/shared/auth — 인증/사용자 DTO.
 */

import type { Department, Role, UserStatus } from './enums';

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
