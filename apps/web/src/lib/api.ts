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

// v1.0 보안: refresh rotation — 새 refresh_token도 응답에 포함됨
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
    // rotation: 새 refresh_token도 저장 (이전 토큰은 서버에서 폐기됨)
    if (data.refresh_token) {
      localStorage.setItem('refresh_token', data.refresh_token);
    }
    return data.access_token;
  } catch {
    return null;
  }
}

/** 401 + refresh 실패 시 강제 로그아웃 처리 (UI에서 구독). */
function forceLogout(reason = 'session_expired') {
  if (typeof window === 'undefined') return;
  clearTokens();
  // 강제 로그아웃 이벤트 발행 — AuthContext에서 감지해 리다이렉트
  window.dispatchEvent(new CustomEvent('auth:force-logout', { detail: { reason } }));
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

  // 401이면 refresh 1회 시도 → 실패하면 강제 로그아웃
  if (res.status === 401 && token) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      headers['Authorization'] = `Bearer ${newToken}`;
      res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
      // 재요청도 401이면 (블랙리스트 등) 강제 로그아웃
      if (res.status === 401 && !path.startsWith('/auth/')) {
        forceLogout('token_revoked');
      }
    } else if (!path.startsWith('/auth/')) {
      forceLogout('refresh_failed');
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
  // v1.0 보안: 로그아웃 (서버 측 토큰 폐기)
  logout: () => {
    const refresh = typeof window !== 'undefined' ? localStorage.getItem('refresh_token') : null;
    return apiFetch('/auth/logout', {
      method: 'POST',
      body: JSON.stringify(refresh ? { refresh_token: refresh } : {}),
    });
  },
  logoutAll: () => apiFetch('/auth/logout-all', { method: 'POST' }),

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

  // Account
  changePassword: (body: { current_password: string; new_password: string }) =>
    apiFetch('/users/me/password', { method: 'POST', body: JSON.stringify(body) }),
  findEmail: (body: { name: string; student_no: string }) =>
    apiFetch('/auth/find-email', { method: 'POST', body: JSON.stringify(body) }),
  requestPasswordReset: (email: string) =>
    apiFetch('/auth/request-password-reset', { method: 'POST', body: JSON.stringify({ email }) }),
  confirmPasswordReset: (body: { token: string; new_password: string }) =>
    apiFetch('/auth/confirm-password-reset', { method: 'POST', body: JSON.stringify(body) }),

  // Practicum (v0.4)
  getPracticumScenarios: (dept?: string) =>
    apiFetch(`/practicum/scenarios${dept ? `?department=${dept}` : ''}`),
  createPracticumScenario: (body: Record<string, unknown>) =>
    apiFetch('/practicum/scenarios', { method: 'POST', body: JSON.stringify(body) }),
  getPracticumScenario: (id: string) => apiFetch(`/practicum/scenarios/${id}`),
  deletePracticumScenario: (id: string) =>
    apiFetch(`/practicum/scenarios/${id}`, { method: 'DELETE' }),
  createPracticumSession: (scenarioId: string) =>
    apiFetch(`/practicum/sessions?scenario_id=${scenarioId}`, { method: 'POST' }),
  getPracticumSessions: (params?: string) =>
    apiFetch(`/practicum/sessions${params ? `?${params}` : ''}`),
  getPracticumSession: (id: string) => apiFetch(`/practicum/sessions/${id}`),
  submitPracticumSession: (id: string, body: Record<string, unknown>) =>
    apiFetch(`/practicum/sessions/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  generatePracticumFeedback: (id: string) =>
    apiFetch(`/practicum/sessions/${id}/feedback`, { method: 'POST' }),
  reviewPracticumSession: (id: string, body: Record<string, unknown>) =>
    apiFetch(`/practicum/sessions/${id}/review`, { method: 'PATCH', body: JSON.stringify(body) }),
  getPracticumStudentStats: (studentId: string) =>
    apiFetch(`/practicum/stats/student/${studentId}`),
  // Live session
  createLiveSession: (scenarioId: string) =>
    apiFetch(`/practicum/sessions/live?scenario_id=${scenarioId}`, { method: 'POST' }),
  joinLiveSession: (code: string) =>
    apiFetch(`/practicum/sessions/join?join_code=${code}`, { method: 'POST' }),
  liveCheckSession: (id: string, body: Record<string, unknown>) =>
    apiFetch(`/practicum/sessions/${id}/live-check`, { method: 'PATCH', body: JSON.stringify(body) }),
  // Video session
  createVideoSession: (scenarioId: string) =>
    apiFetch(`/practicum/sessions/video?scenario_id=${scenarioId}`, { method: 'POST' }),
  aiEvaluateSession: (id: string, body: Record<string, unknown>) =>
    apiFetch(`/practicum/sessions/${id}/ai-evaluate`, { method: 'POST', body: JSON.stringify(body) }),

  // Question Reviews (v0.5)
  getReviewQueue: (params?: string) =>
    apiFetch(`/reviews/queue${params ? `?${params}` : ''}`),
  submitReview: (questionId: string, body: Record<string, unknown>) =>
    apiFetch(`/reviews/${questionId}`, { method: 'POST', body: JSON.stringify(body) }),
  getReviewHistory: (questionId: string) =>
    apiFetch(`/reviews/${questionId}/history`),
  getEditHistory: (questionId: string) =>
    apiFetch(`/reviews/${questionId}/edits`),
  compareExplanations: (questionId: string) =>
    apiFetch(`/reviews/${questionId}/compare`),

  // Dev Center (v0.3)
  devHealthCheck: () => apiFetch('/dev/health-check'),
  devStats: () => apiFetch('/dev/stats'),
  devSettings: () => apiFetch('/dev/settings'),
  updateUserRole: (userId: string, body: Record<string, unknown>) =>
    apiFetch(`/users/${userId}/role`, { method: 'PATCH', body: JSON.stringify(body) }),

  // Background Jobs (v0.6)
  createJob: (body: Record<string, unknown>) =>
    apiFetch('/jobs', { method: 'POST', body: JSON.stringify(body) }),
  getJob: (jobId: string) => apiFetch(`/jobs/${jobId}`),
  listJobs: (params?: string) => apiFetch(`/jobs${params ? `?${params}` : ''}`),
  retryJob: (jobId: string) =>
    apiFetch(`/jobs/${jobId}/retry`, { method: 'POST' }),
  getQueueStats: () => apiFetch('/jobs/stats/queue'),

  // Notifications (v0.6)
  getNotifications: (params?: string) =>
    apiFetch(`/notifications${params ? `?${params}` : ''}`),
  getUnreadCount: () => apiFetch('/notifications/unread-count'),
  markNotificationRead: (id: string) =>
    apiFetch(`/notifications/${id}/read`, { method: 'PUT' }),
  markAllNotificationsRead: () =>
    apiFetch('/notifications/read-all', { method: 'PUT' }),
  deleteNotification: (id: string) =>
    apiFetch(`/notifications/${id}`, { method: 'DELETE' }),

  // Ops Dashboard (v0.6)
  getOpsDashboard: () => apiFetch('/ops/dashboard'),
  getActiveUsers: () => apiFetch('/ops/active-users'),
  getWeeklyLearning: (weeks?: number) =>
    apiFetch(`/ops/weekly-learning${weeks ? `?weeks=${weeks}` : ''}`),
  getDiagnosticCompletion: () => apiFetch('/ops/diagnostic-completion'),
  getAiUsage: (days?: number) =>
    apiFetch(`/ops/ai-usage${days ? `?days=${days}` : ''}`),
  getAccuracyBySubject: () => apiFetch('/ops/accuracy-by-subject'),
  getAssignmentCompletion: () => apiFetch('/ops/assignment-completion'),
  getAtRiskStudents: (days?: number) =>
    apiFetch(`/ops/at-risk-students${days ? `?days=${days}` : ''}`),
  getKbFreshness: () => apiFetch('/ops/kb-freshness'),
  getPracticumParticipation: () => apiFetch('/ops/practicum-participation'),
  getFailureRates: (hours?: number) =>
    apiFetch(`/ops/failure-rates${hours ? `?hours=${hours}` : ''}`),
  getRealtimeMetrics: () => apiFetch('/ops/metrics'),

  // Cost Tracking (v0.6)
  getDailyCosts: (params?: string) =>
    apiFetch(`/cost/daily${params ? `?${params}` : ''}`),
  getCostByProvider: (params?: string) =>
    apiFetch(`/cost/by-provider${params ? `?${params}` : ''}`),
  getCostByRole: (params?: string) =>
    apiFetch(`/cost/by-role${params ? `?${params}` : ''}`),
  getMyUsage: (days?: number) =>
    apiFetch(`/cost/my-usage${days ? `?days=${days}` : ''}`),
  getMyQuota: () => apiFetch('/cost/my-quota'),
  getModelRouting: (requestType?: string) =>
    apiFetch(`/cost/routing${requestType ? `?request_type=${requestType}` : ''}`),
  triggerCostAggregation: (date?: string) =>
    apiFetch(`/cost/aggregate${date ? `?target_date=${date}` : ''}`, { method: 'POST' }),

  // Blueprint (v0.7)
  getBlueprint: () => apiFetch('/blueprint'),
  seedBlueprint: () => apiFetch('/blueprint/seed', { method: 'POST' }),
  getBlueprintWeakness: () => apiFetch('/blueprint/weakness'),
  getBlueprintFocusSet: (setSize = 30) =>
    apiFetch(`/blueprint/focus-set?set_size=${setSize}`, { method: 'POST' }),
  getCurriculumCoverage: () => apiFetch('/blueprint/coverage'),

  // Concept Tags (v0.7)
  getConceptTree: () => apiFetch('/concepts/tree'),
  createConceptNode: (body: Record<string, unknown>) =>
    apiFetch('/concepts/nodes', { method: 'POST', body: JSON.stringify(body) }),
  createConceptRelation: (body: Record<string, unknown>) =>
    apiFetch('/concepts/relations', { method: 'POST', body: JSON.stringify(body) }),
  getRelatedConcepts: (conceptId: string) => apiFetch(`/concepts/${conceptId}/related`),
  getConceptWeakness: () => apiFetch('/concepts/weakness'),
  getConceptStats: () => apiFetch('/concepts/stats'),

  // Advanced Recommendation (v0.7)
  getAdaptiveSet: (body: Record<string, unknown>) =>
    apiFetch('/recommendation/adaptive', { method: 'POST', body: JSON.stringify(body) }),

  // Error Analysis (v0.7)
  getDifficultyCalibration: (minAttempts = 10) =>
    apiFetch(`/analysis/difficulty-calibration?min_attempts=${minAttempts}`),
  getDiscrimination: (minAttempts = 20) =>
    apiFetch(`/analysis/discrimination?min_attempts=${minAttempts}`),
  getErrorBlueprint: (studentId?: string) =>
    apiFetch(`/analysis/error-blueprint${studentId ? `?student_id=${studentId}` : ''}`),
  getDiagnosticReport: (studentId?: string) =>
    apiFetch(`/analysis/diagnostic-report${studentId ? `?student_id=${studentId}` : ''}`),

  // Professor Reports (v0.7)
  getClassStudents: (classId: string) => apiFetch(`/reports/class/${classId}/students`),
  getClassObjectives: (classId: string) => apiFetch(`/reports/class/${classId}/objectives`),
  compareClasses: () => apiFetch('/reports/compare'),
  getAtRiskStudents: (classId: string, params?: string) =>
    apiFetch(`/reports/class/${classId}/at-risk${params ? `?${params}` : ''}`),

  // Schools (v0.8)
  createSchool: (body: Record<string, unknown>) =>
    apiFetch('/schools', { method: 'POST', body: JSON.stringify(body) }),
  getSchools: (activeOnly = true) =>
    apiFetch(`/schools?active_only=${activeOnly}`),
  getSchool: (id: string) => apiFetch(`/schools/${id}`),
  updateSchool: (id: string, body: Record<string, unknown>) =>
    apiFetch(`/schools/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  getSchoolSettings: (id: string) => apiFetch(`/schools/${id}/settings`),
  updateSchoolSettings: (id: string, body: Record<string, unknown>) =>
    apiFetch(`/schools/${id}/settings`, { method: 'PATCH', body: JSON.stringify(body) }),
  addSchoolDepartment: (schoolId: string, body: Record<string, unknown>) =>
    apiFetch(`/schools/${schoolId}/departments`, { method: 'POST', body: JSON.stringify(body) }),
  getSchoolDepartments: (schoolId: string) => apiFetch(`/schools/${schoolId}/departments`),
  getSchoolDirectory: (schoolId: string, params?: string) =>
    apiFetch(`/schools/${schoolId}/directory${params ? `?${params}` : ''}`),

  // LMS (v0.8)
  initiateSso: () => apiFetch('/lms/sso/initiate', { method: 'POST' }),
  getLti13Login: () => apiFetch('/lms/lti13/login'),
  createLmsCourse: (body: Record<string, unknown>) =>
    apiFetch('/lms/courses', { method: 'POST', body: JSON.stringify(body) }),
  getLmsCourses: () => apiFetch('/lms/courses'),
  syncGrade: (body: Record<string, unknown>) =>
    apiFetch('/lms/grades/sync', { method: 'POST', body: JSON.stringify(body) }),
  getGradeHistory: (lmsCourseId: string, params?: string) =>
    apiFetch(`/lms/grades/history/${lmsCourseId}${params ? `?${params}` : ''}`),

  // OSCE (v0.8)
  createOsceExam: (body: Record<string, unknown>) =>
    apiFetch('/osce/exams', { method: 'POST', body: JSON.stringify(body) }),
  getOsceExams: (department: string, activeOnly = true) =>
    apiFetch(`/osce/exams?department=${department}&active_only=${activeOnly}`),
  getOsceExam: (id: string) => apiFetch(`/osce/exams/${id}`),
  createRubric: (body: Record<string, unknown>) =>
    apiFetch('/osce/rubrics', { method: 'POST', body: JSON.stringify(body) }),
  getRubrics: (department: string) => apiFetch(`/osce/rubrics?department=${department}`),
  getRubric: (id: string) => apiFetch(`/osce/rubrics/${id}`),
  recordPracticumEvent: (body: Record<string, unknown>) =>
    apiFetch('/osce/events', { method: 'POST', body: JSON.stringify(body) }),
  getSessionEvents: (sessionId: string) => apiFetch(`/osce/events/${sessionId}`),
  detectTimingIssues: (body: Record<string, unknown>) =>
    apiFetch('/osce/events/detect', { method: 'POST', body: JSON.stringify(body) }),
  saveReplay: (body: Record<string, unknown>) =>
    apiFetch('/osce/replay', { method: 'POST', body: JSON.stringify(body) }),
  getReplay: (sessionId: string) => apiFetch(`/osce/replay/${sessionId}`),

  // Calendar & Comments (v0.8)
  createCalendarEvent: (body: Record<string, unknown>) =>
    apiFetch('/calendar/events', { method: 'POST', body: JSON.stringify(body) }),
  getCalendarEvents: (params?: string) =>
    apiFetch(`/calendar/events${params ? `?${params}` : ''}`),
  updateCalendarEvent: (id: string, body: Record<string, unknown>) =>
    apiFetch(`/calendar/events/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteCalendarEvent: (id: string) =>
    apiFetch(`/calendar/events/${id}`, { method: 'DELETE' }),
  syncAssignmentDeadlines: () =>
    apiFetch('/calendar/sync-assignments', { method: 'POST' }),
  createComment: (body: Record<string, unknown>) =>
    apiFetch('/comments', { method: 'POST', body: JSON.stringify(body) }),
  getStudentComments: (studentId: string, includePrivate = false) =>
    apiFetch(`/comments/student/${studentId}?include_private=${includePrivate}`),
  getTargetComments: (targetType: string, targetId: string, includePrivate = false) =>
    apiFetch(`/comments/target/${targetType}/${targetId}?include_private=${includePrivate}`),
};
