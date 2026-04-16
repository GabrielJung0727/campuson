'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';

interface DashboardData {
  active_users: Array<{ department: string; total: number; by_role: Record<string, number> }>;
  weekly_learning: Array<{
    week_start: string; week_end: string;
    total_attempts: number; correct_count: number; accuracy: number; active_students: number;
  }>;
  diagnostic_completion: { total_students: number; completed: number; completion_rate: number };
  ai_usage: {
    period_days: number; total_calls: number; success_rate: number;
    total_tokens: number; estimated_cost_usd: number; avg_latency_ms: number;
  };
  accuracy_by_subject: Array<{ subject: string; department: string; attempts: number; accuracy: number }>;
  assignment_completion: Array<{
    professor_name: string; department: string;
    total_assignments: number; total_submissions: number;
  }>;
  at_risk_students: Array<{ name: string; email: string; department: string; inactive_days: number }>;
  kb_freshness: Array<{
    department: string; review_status: string;
    doc_count: number; latest_update: string; oldest_update: string;
  }>;
  practicum_participation: {
    total_students: number; participated: number;
    participation_rate: number; total_sessions: number;
  };
  failure_rates: {
    api: { total_requests: number; server_errors: number; error_rate: number; avg_latency_ms: number };
    llm: { total_calls: number; success_count: number; failure_rate: number };
  };
}

const DEPT_LABEL: Record<string, string> = {
  NURSING: '간호학과', PHYSICAL_THERAPY: '물리치료학과', DENTAL_HYGIENE: '치위생과',
};

export default function OpsDashboardPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'overview' | 'learning' | 'ai' | 'risk'>('overview');

  useEffect(() => {
    if (!user || !['ADMIN', 'DEVELOPER'].includes(user.role)) {
      router.push('/dashboard');
      return;
    }
    api.getOpsDashboard().then((d: any) => { setData(d); setLoading(false); }).catch(() => setLoading(false));
  }, [user, router]);

  if (loading) return <div className="p-8 text-center text-slate-500">로딩 중...</div>;
  if (!data) return <div className="p-8 text-center text-red-500">데이터를 불러올 수 없습니다.</div>;

  const tabs = [
    { id: 'overview', label: '개요' },
    { id: 'learning', label: '학습 지표' },
    { id: 'ai', label: 'AI / 비용' },
    { id: 'risk', label: '위험 / 장애' },
  ] as const;

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">운영 대시보드</h1>
            <p className="text-sm text-slate-500 mt-1">CampusON 플랫폼 운영 현황</p>
          </div>
          <button onClick={() => router.push('/dashboard')} className="text-sm text-brand-600 hover:underline">&larr; 대시보드</button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 border-b border-slate-200">
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition ${tab === t.id ? 'border-brand-600 text-brand-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
            >{t.label}</button>
          ))}
        </div>

        {/* Overview Tab */}
        {tab === 'overview' && (
          <div className="space-y-6">
            {/* Active Users */}
            <section>
              <h2 className="text-lg font-semibold text-slate-800 mb-3">학과별 활성 사용자</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {data.active_users.map(dept => (
                  <div key={dept.department} className="bg-white rounded-xl border border-slate-200 p-4">
                    <div className="text-sm font-medium text-slate-500">{DEPT_LABEL[dept.department] || dept.department}</div>
                    <div className="text-3xl font-bold text-slate-900 mt-1">{dept.total}</div>
                    <div className="flex gap-3 mt-2 text-xs text-slate-500">
                      {Object.entries(dept.by_role).map(([role, count]) => (
                        <span key={role}>{role}: <strong>{count as number}</strong></span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* Diagnostic Completion */}
            <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <div className="text-sm font-medium text-slate-500">진단 테스트 완료율</div>
                <div className="text-3xl font-bold text-emerald-600 mt-1">
                  {(data.diagnostic_completion.completion_rate * 100).toFixed(1)}%
                </div>
                <div className="text-xs text-slate-400 mt-1">
                  {data.diagnostic_completion.completed} / {data.diagnostic_completion.total_students}명
                </div>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <div className="text-sm font-medium text-slate-500">실습 참여율</div>
                <div className="text-3xl font-bold text-blue-600 mt-1">
                  {(data.practicum_participation.participation_rate * 100).toFixed(1)}%
                </div>
                <div className="text-xs text-slate-400 mt-1">
                  {data.practicum_participation.participated} / {data.practicum_participation.total_students}명
                </div>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <div className="text-sm font-medium text-slate-500">이탈 위험 학생</div>
                <div className="text-3xl font-bold text-red-600 mt-1">{data.at_risk_students.length}명</div>
                <div className="text-xs text-slate-400 mt-1">14일 이상 미접속</div>
              </div>
            </section>

            {/* KB Freshness */}
            <section>
              <h2 className="text-lg font-semibold text-slate-800 mb-3">지식베이스 문서 최신성</h2>
              <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs text-slate-500">학과</th>
                      <th className="px-4 py-2 text-left text-xs text-slate-500">상태</th>
                      <th className="px-4 py-2 text-right text-xs text-slate-500">문서 수</th>
                      <th className="px-4 py-2 text-right text-xs text-slate-500">최종 업데이트</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.kb_freshness.map((kb, i) => (
                      <tr key={i} className="border-b border-slate-100">
                        <td className="px-4 py-2">{DEPT_LABEL[kb.department] || kb.department || '-'}</td>
                        <td className="px-4 py-2">
                          <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                            kb.review_status === 'PUBLISHED' ? 'bg-emerald-50 text-emerald-700' :
                            kb.review_status === 'DRAFT' ? 'bg-amber-50 text-amber-700' : 'bg-slate-50 text-slate-600'
                          }`}>{kb.review_status}</span>
                        </td>
                        <td className="px-4 py-2 text-right">{kb.doc_count}</td>
                        <td className="px-4 py-2 text-right text-xs text-slate-400">
                          {kb.latest_update ? new Date(kb.latest_update).toLocaleDateString('ko') : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        )}

        {/* Learning Tab */}
        {tab === 'learning' && (
          <div className="space-y-6">
            {/* Weekly Learning */}
            <section>
              <h2 className="text-lg font-semibold text-slate-800 mb-3">주간 학습량</h2>
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <div className="grid grid-cols-4 gap-4">
                  {data.weekly_learning.map((w, i) => (
                    <div key={i} className="text-center">
                      <div className="text-xs text-slate-400 mb-1">{w.week_start.slice(5)}</div>
                      <div className="h-24 bg-slate-100 rounded relative overflow-hidden">
                        <div
                          className="absolute bottom-0 left-0 right-0 bg-brand-500 rounded-t transition-all"
                          style={{ height: `${Math.min(100, (w.total_attempts / Math.max(1, ...data.weekly_learning.map(x => x.total_attempts))) * 100)}%` }}
                        />
                      </div>
                      <div className="text-sm font-bold mt-1">{w.total_attempts}</div>
                      <div className="text-xs text-slate-400">{(w.accuracy * 100).toFixed(0)}% 정답</div>
                      <div className="text-xs text-slate-400">{w.active_students}명 활동</div>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            {/* Accuracy by Subject */}
            <section>
              <h2 className="text-lg font-semibold text-slate-800 mb-3">과목별 정답률</h2>
              <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 border-b">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs text-slate-500">과목</th>
                      <th className="px-4 py-2 text-left text-xs text-slate-500">학과</th>
                      <th className="px-4 py-2 text-right text-xs text-slate-500">시도</th>
                      <th className="px-4 py-2 text-right text-xs text-slate-500">정답률</th>
                      <th className="px-4 py-2 text-xs text-slate-500 w-40"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.accuracy_by_subject.slice(0, 15).map((s, i) => (
                      <tr key={i} className="border-b border-slate-100">
                        <td className="px-4 py-2 font-medium">{s.subject}</td>
                        <td className="px-4 py-2 text-xs text-slate-500">{DEPT_LABEL[s.department] || '-'}</td>
                        <td className="px-4 py-2 text-right">{s.attempts}</td>
                        <td className="px-4 py-2 text-right font-medium">{(s.accuracy * 100).toFixed(1)}%</td>
                        <td className="px-4 py-2">
                          <div className="w-full bg-slate-100 rounded-full h-2">
                            <div
                              className={`h-2 rounded-full ${s.accuracy >= 0.7 ? 'bg-emerald-500' : s.accuracy >= 0.5 ? 'bg-amber-500' : 'bg-red-500'}`}
                              style={{ width: `${s.accuracy * 100}%` }}
                            />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            {/* Assignment Completion */}
            <section>
              <h2 className="text-lg font-semibold text-slate-800 mb-3">교수별 과제 수행률</h2>
              <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 border-b">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs text-slate-500">교수명</th>
                      <th className="px-4 py-2 text-left text-xs text-slate-500">학과</th>
                      <th className="px-4 py-2 text-right text-xs text-slate-500">과제 수</th>
                      <th className="px-4 py-2 text-right text-xs text-slate-500">제출 수</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.assignment_completion.map((a, i) => (
                      <tr key={i} className="border-b border-slate-100">
                        <td className="px-4 py-2 font-medium">{a.professor_name}</td>
                        <td className="px-4 py-2 text-xs text-slate-500">{DEPT_LABEL[a.department] || '-'}</td>
                        <td className="px-4 py-2 text-right">{a.total_assignments}</td>
                        <td className="px-4 py-2 text-right">{a.total_submissions}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        )}

        {/* AI / Cost Tab */}
        {tab === 'ai' && (
          <div className="space-y-6">
            <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <div className="text-sm text-slate-500">AI 호출 수 (30일)</div>
                <div className="text-3xl font-bold text-slate-900 mt-1">{data.ai_usage.total_calls.toLocaleString()}</div>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <div className="text-sm text-slate-500">성공률</div>
                <div className="text-3xl font-bold text-emerald-600 mt-1">{(data.ai_usage.success_rate * 100).toFixed(1)}%</div>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <div className="text-sm text-slate-500">총 토큰</div>
                <div className="text-3xl font-bold text-blue-600 mt-1">{(data.ai_usage.total_tokens / 1000).toFixed(0)}K</div>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <div className="text-sm text-slate-500">추정 비용</div>
                <div className="text-3xl font-bold text-amber-600 mt-1">${data.ai_usage.estimated_cost_usd.toFixed(2)}</div>
              </div>
            </section>

            <section className="bg-white rounded-xl border border-slate-200 p-4">
              <h3 className="text-sm font-semibold text-slate-700 mb-2">평균 응답 시간</h3>
              <div className="text-4xl font-bold text-slate-900">{data.ai_usage.avg_latency_ms.toLocaleString()}ms</div>
            </section>
          </div>
        )}

        {/* Risk Tab */}
        {tab === 'risk' && (
          <div className="space-y-6">
            {/* Failure Rates */}
            <section className="grid grid-cols-2 gap-4">
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <h3 className="text-sm font-semibold text-slate-700 mb-3">API 상태 (24h)</h3>
                <div className="space-y-2">
                  <div className="flex justify-between"><span className="text-sm text-slate-500">총 요청</span><span className="font-medium">{data.failure_rates.api.total_requests.toLocaleString()}</span></div>
                  <div className="flex justify-between"><span className="text-sm text-slate-500">서버 에러</span><span className="font-medium text-red-600">{data.failure_rates.api.server_errors}</span></div>
                  <div className="flex justify-between"><span className="text-sm text-slate-500">에러율</span><span className="font-medium">{(data.failure_rates.api.error_rate * 100).toFixed(2)}%</span></div>
                  <div className="flex justify-between"><span className="text-sm text-slate-500">평균 지연</span><span className="font-medium">{data.failure_rates.api.avg_latency_ms}ms</span></div>
                </div>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <h3 className="text-sm font-semibold text-slate-700 mb-3">LLM 상태 (24h)</h3>
                <div className="space-y-2">
                  <div className="flex justify-between"><span className="text-sm text-slate-500">총 호출</span><span className="font-medium">{data.failure_rates.llm.total_calls}</span></div>
                  <div className="flex justify-between"><span className="text-sm text-slate-500">성공</span><span className="font-medium text-emerald-600">{data.failure_rates.llm.success_count}</span></div>
                  <div className="flex justify-between"><span className="text-sm text-slate-500">실패율</span><span className="font-medium text-red-600">{(data.failure_rates.llm.failure_rate * 100).toFixed(2)}%</span></div>
                </div>
              </div>
            </section>

            {/* At Risk Students */}
            <section>
              <h2 className="text-lg font-semibold text-slate-800 mb-3">이탈 위험 학생 ({data.at_risk_students.length}명)</h2>
              {data.at_risk_students.length === 0 ? (
                <div className="bg-emerald-50 text-emerald-700 rounded-xl p-4 text-sm">이탈 위험 학생이 없습니다.</div>
              ) : (
                <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-red-50 border-b">
                      <tr>
                        <th className="px-4 py-2 text-left text-xs text-red-700">이름</th>
                        <th className="px-4 py-2 text-left text-xs text-red-700">이메일</th>
                        <th className="px-4 py-2 text-left text-xs text-red-700">학과</th>
                        <th className="px-4 py-2 text-right text-xs text-red-700">미접속 일수</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.at_risk_students.slice(0, 20).map((s, i) => (
                        <tr key={i} className="border-b border-slate-100">
                          <td className="px-4 py-2 font-medium">{s.name}</td>
                          <td className="px-4 py-2 text-slate-500">{s.email}</td>
                          <td className="px-4 py-2 text-xs">{DEPT_LABEL[s.department] || '-'}</td>
                          <td className="px-4 py-2 text-right text-red-600 font-medium">{s.inactive_days}일</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
