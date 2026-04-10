/**
 * API 클라이언트 — FastAPI 백엔드와 통신.
 *
 * 특징:
 * - 베이스 URL은 환경 변수에서 로드 (NEXT_PUBLIC_API_URL)
 * - 자동 토큰 주입 (localStorage에서 access_token 읽기)
 * - 401 시 토큰 refresh 자동 시도
 * - JSON 자동 파싱
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(`[${status}] ${detail}`);
  }
}

function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('access_token');
}

function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('refresh_token');
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem('access_token', access);
  localStorage.setItem('refresh_token', refresh);
}

export function clearTokens() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('user');
}

async function refreshAccessToken(): Promise<string | null> {
  const rt = getRefreshToken();
  if (!rt) return null;
  try {
    const res = await fetch(`${BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: rt }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    localStorage.setItem('access_token', data.access_token);
    return data.access_token;
  } catch {
    return null;
  }
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  const token = getAccessToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  // 401이면 refresh 시도 후 재요청
  if (res.status === 401 && token) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      headers['Authorization'] = `Bearer ${newToken}`;
      res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
    }
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || body.message || detail;
    } catch {
      /* ignore parse error */
    }
    throw new ApiError(res.status, detail);
  }

  return res.json();
}

// === Typed API helpers ===

export const api = {
  // Auth
  register: (body: Record<string, unknown>) =>
    apiFetch('/auth/register', { method: 'POST', body: JSON.stringify(body) }),
  login: (body: { email: string; password: string }) =>
    apiFetch('/auth/login', { method: 'POST', body: JSON.stringify(body) }),
  getMe: () => apiFetch('/users/me'),

  // Diagnostic
  startDiagnostic: () => apiFetch('/diagnostic/start', { method: 'POST' }),
  submitDiagnostic: (testId: string, answers: unknown[]) =>
    apiFetch(`/diagnostic/${testId}/submit`, {
      method: 'POST',
      body: JSON.stringify({ answers }),
    }),
  getMyDiagnostic: () => apiFetch('/diagnostic/me'),
  getMyProfile: () => apiFetch('/diagnostic/me/profile'),

  // Questions
  searchQuestions: (params: string) => apiFetch(`/questions?${params}`),
  getQuestionPlay: (id: string) => apiFetch(`/questions/${id}/play`),

  // History
  submitAnswer: (body: Record<string, unknown>) =>
    apiFetch('/history/answer', { method: 'POST', body: JSON.stringify(body) }),
  getMyHistory: (params: string) => apiFetch(`/history/me?${params}`),
  getWrongAnswers: (params: string) => apiFetch(`/history/wrong-answers?${params}`),
  getMyStats: (params: string) => apiFetch(`/history/stats?${params}`),

  // AI
  aiQA: (question: string) =>
    apiFetch('/ai/qa', { method: 'POST', body: JSON.stringify({ question }) }),
  aiExplain: (questionId: string, historyId?: string) =>
    apiFetch('/ai/explain', {
      method: 'POST',
      body: JSON.stringify({ question_id: questionId, history_id: historyId }),
    }),

  // Recommendation
  getRecommendedSet: (setSize = 20) =>
    apiFetch('/recommendation/set', {
      method: 'POST',
      body: JSON.stringify({ set_size: setSize }),
    }),

  // Stats (v0.2)
  getQuestionStats: (questionId: string) => apiFetch(`/stats/question/${questionId}`),
  getMyPercentile: () => apiFetch('/stats/percentile'),

  // Classes (v0.2 교수)
  getMyClasses: () => apiFetch('/classes'),
  createClass: (body: Record<string, unknown>) =>
    apiFetch('/classes', { method: 'POST', body: JSON.stringify(body) }),
  getClassDetail: (id: string) => apiFetch(`/classes/${id}`),
  addStudentToClass: (classId: string, body: Record<string, unknown>) =>
    apiFetch(`/classes/${classId}/students`, { method: 'POST', body: JSON.stringify(body) }),
  removeStudentFromClass: (classId: string, studentId: string) =>
    apiFetch(`/classes/${classId}/students/${studentId}`, { method: 'DELETE' }),
  getClassStats: (classId: string) => apiFetch(`/classes/${classId}/stats`),
  getStudentDetail: (studentId: string) => apiFetch(`/classes/student-detail/${studentId}`),
  deleteClass: (classId: string) => apiFetch(`/classes/${classId}`, { method: 'DELETE' }),

  // Assignments (v0.2)
  getAssignments: () => apiFetch('/assignments'),
  createAssignment: (body: Record<string, unknown>) =>
    apiFetch('/assignments', { method: 'POST', body: JSON.stringify(body) }),
  getAssignment: (id: string) => apiFetch(`/assignments/${id}`),
  submitAssignment: (id: string, answers: unknown[]) =>
    apiFetch(`/assignments/${id}/submit`, { method: 'POST', body: JSON.stringify({ answers }) }),

  // AI Generate (v0.2)
  generateQuestions: (body: Record<string, unknown>) =>
    apiFetch('/ai/generate-questions', { method: 'POST', body: JSON.stringify(body) }),

  // Announcements (v0.3)
  getAnnouncements: () => apiFetch('/announcements'),
  createAnnouncement: (body: Record<string, unknown>) =>
    apiFetch('/announcements', { method: 'POST', body: JSON.stringify(body) }),
  deleteAnnouncement: (id: string) =>
    apiFetch(`/announcements/${id}`, { method: 'DELETE' }),

  // Dev Center (v0.3)
  devHealthCheck: () => apiFetch('/dev/health-check'),
  devStats: () => apiFetch('/dev/stats'),
  devSettings: () => apiFetch('/dev/settings'),
  updateUserRole: (userId: string, body: Record<string, unknown>) =>
    apiFetch(`/users/${userId}/role`, { method: 'PATCH', body: JSON.stringify(body) }),
};
