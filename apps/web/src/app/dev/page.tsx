'use client';

import { useAuth } from '@/contexts/AuthContext';
import { AnnouncementFooter } from '@/components/AnnouncementBar';
import { api, apiFetch } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

interface HealthCheck {
  db: string;
  redis: string;
  llm: { provider: string; model: string };
  embedding: { provider: string; model: string; dimensions: number };
  smtp: { enabled: boolean; host: string };
}

interface DevStats {
  table_counts: Record<string, number>;
  department_stats: Array<{ department: string; role: string; count: number }>;
}

interface UserItem {
  id: string;
  email: string;
  name: string;
  department: string;
  role: string;
  status: string;
  student_no: string | null;
  professor_role: string | null;
  admin_role: string | null;
  nationality: string | null;
  grade: number | null;
}

const ROLE_OPTIONS = ['STUDENT', 'PROFESSOR', 'ADMIN', 'DEVELOPER'];
const PROF_ROLES = ['FULL_TIME', 'ADJUNCT', 'DEPT_HEAD'];
const ADMIN_ROLES = ['ACADEMIC_AFFAIRS', 'STUDENT_AFFAIRS', 'GENERAL_ADMIN', 'PLANNING', 'IT_CENTER', 'ADMISSIONS', 'SUPER_ADMIN'];

export default function DevDashboardPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<'overview' | 'users' | 'settings' | 'llm'>('overview');
  const [health, setHealth] = useState<HealthCheck | null>(null);
  const [stats, setStats] = useState<DevStats | null>(null);
  const [settings, setSettings] = useState<Record<string, unknown> | null>(null);
  const [users, setUsers] = useState<UserItem[]>([]);

  useEffect(() => {
    if (!loading && (!user || user.role !== 'DEVELOPER')) router.push('/dashboard');
  }, [user, loading, router]);

  useEffect(() => {
    if (user?.role === 'DEVELOPER') {
      api.devHealthCheck().then((d: unknown) => setHealth(d as HealthCheck)).catch(() => {});
      api.devStats().then((d: unknown) => setStats(d as DevStats)).catch(() => {});
      api.devSettings().then((d: unknown) => setSettings(d as Record<string, unknown>)).catch(() => {});
      apiFetch<UserItem[]>('/users').then(setUsers).catch(() => {});
    }
  }, [user]);

  async function handleRoleChange(userId: string, field: string, value: string) {
    try {
      await api.updateUserRole(userId, { [field]: value || null });
      const updated = await apiFetch<UserItem[]>('/users');
      setUsers(updated);
    } catch { /* ignore */ }
  }

  if (loading || !user) return <div className="p-8 text-center">Loading...</div>;

  const tabs = [
    { key: 'overview', label: '시스템 현황' },
    { key: 'users', label: `사용자 (${users.length})` },
    { key: 'settings', label: '설정' },
    { key: 'llm', label: 'LLM/RAG' },
  ] as const;

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">🛠 개발자 센터</h1>
          <p className="text-sm text-slate-500">코드 수정 없이 시스템 관리</p>
        </div>
        <button onClick={() => router.push('/dashboard')} className="text-sm text-slate-500">← 대시보드</button>
      </div>

      {/* 탭 */}
      <div className="mb-6 flex gap-1 rounded-lg bg-slate-100 p-1">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition ${
              tab === t.key ? 'bg-white shadow-sm text-slate-900' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* === 시스템 현황 === */}
      {tab === 'overview' && (
        <div className="space-y-6">
          {/* Health */}
          {health && (
            <div className="grid gap-4 md:grid-cols-5">
              {Object.entries({
                DB: health.db,
                Redis: health.redis,
                LLM: `${health.llm.provider} (${health.llm.model})`,
                Embedding: `${health.embedding.provider} (${health.embedding.dimensions}d)`,
                SMTP: health.smtp.enabled ? `ON (${health.smtp.host})` : 'OFF',
              }).map(([name, val]) => (
                <div key={name} className="rounded-xl border bg-white p-4 text-center">
                  <div className={`text-xs font-bold ${String(val).includes('ok') || String(val).includes('ON') ? 'text-emerald-600' : 'text-slate-500'}`}>
                    {String(val).includes('ok') ? '✅' : String(val).includes('error') ? '❌' : '⚙️'} {name}
                  </div>
                  <div className="mt-1 truncate text-xs text-slate-600">{String(val)}</div>
                </div>
              ))}
            </div>
          )}

          {/* Table counts */}
          {stats && (
            <div className="rounded-xl border bg-white p-6">
              <h3 className="mb-4 font-semibold">테이블별 레코드 수</h3>
              <div className="grid grid-cols-3 gap-3 md:grid-cols-4">
                {Object.entries(stats.table_counts).map(([table, count]) => (
                  <div key={table} className="rounded-lg bg-slate-50 p-3 text-center">
                    <div className="text-lg font-bold text-brand-600">{count}</div>
                    <div className="truncate text-xs text-slate-500">{table}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Department stats */}
          {stats && (
            <div className="rounded-xl border bg-white p-6">
              <h3 className="mb-4 font-semibold">학과별 · 역할별 사용자</h3>
              <div className="space-y-1 text-sm">
                {stats.department_stats.map((d, i) => (
                  <div key={i} className="flex justify-between rounded px-2 py-1 hover:bg-slate-50">
                    <span>{d.department} / {d.role}</span>
                    <span className="font-mono font-bold">{d.count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* === 사용자 관리 === */}
      {tab === 'users' && (
        <div className="rounded-xl border bg-white overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-slate-50 text-left text-xs text-slate-500">
                <th className="px-3 py-2">이름</th>
                <th className="px-3 py-2">이메일</th>
                <th className="px-3 py-2">학과</th>
                <th className="px-3 py-2">역할</th>
                <th className="px-3 py-2">세부역할</th>
                <th className="px-3 py-2">학년</th>
                <th className="px-3 py-2">상태</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-3 py-2 font-medium">{u.name}</td>
                  <td className="px-3 py-2 text-xs text-slate-500">{u.email}</td>
                  <td className="px-3 py-2 text-xs">{u.department}</td>
                  <td className="px-3 py-2">
                    <select
                      value={u.role}
                      onChange={(e) => handleRoleChange(u.id, 'role', e.target.value)}
                      className="rounded border border-slate-300 px-1 py-0.5 text-xs"
                    >
                      {ROLE_OPTIONS.map((r) => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </td>
                  <td className="px-3 py-2">
                    {u.role === 'PROFESSOR' && (
                      <select
                        value={u.professor_role || ''}
                        onChange={(e) => handleRoleChange(u.id, 'professor_role', e.target.value)}
                        className="rounded border border-slate-300 px-1 py-0.5 text-xs"
                      >
                        <option value="">-</option>
                        {PROF_ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                      </select>
                    )}
                    {u.role === 'ADMIN' && (
                      <select
                        value={u.admin_role || ''}
                        onChange={(e) => handleRoleChange(u.id, 'admin_role', e.target.value)}
                        className="rounded border border-slate-300 px-1 py-0.5 text-xs"
                      >
                        <option value="">-</option>
                        {ADMIN_ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                      </select>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {u.role === 'STUDENT' && (
                      <select
                        value={u.grade || ''}
                        onChange={(e) => handleRoleChange(u.id, 'grade', e.target.value)}
                        className="rounded border border-slate-300 px-1 py-0.5 text-xs"
                      >
                        <option value="">-</option>
                        {[1, 2, 3, 4].map((g) => <option key={g} value={g}>{g}학년</option>)}
                      </select>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <span className={`rounded px-2 py-0.5 text-xs ${u.status === 'ACTIVE' ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-600'}`}>
                      {u.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* === 설정 === */}
      {tab === 'settings' && settings && (
        <div className="rounded-xl border bg-white p-6">
          <h3 className="mb-4 font-semibold">현재 시스템 설정 (읽기 전용, .env 또는 시스템 설정 센터에서 변경)</h3>
          <div className="space-y-2">
            {Object.entries(settings).map(([key, val]) => (
              <div key={key} className="flex items-center justify-between rounded px-3 py-2 text-sm hover:bg-slate-50">
                <span className="font-mono text-xs text-slate-600">{key}</span>
                <span className="font-mono text-xs text-slate-900">{String(val)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* === LLM/RAG === */}
      {tab === 'llm' && health && (
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border bg-white p-6">
              <h3 className="mb-3 font-semibold">LLM 상태</h3>
              <div className="space-y-2 text-sm">
                <div>Provider: <strong>{health.llm.provider}</strong></div>
                <div>Model: <strong>{health.llm.model}</strong></div>
                <div>Status: <span className="text-emerald-600">Active</span></div>
              </div>
            </div>
            <div className="rounded-xl border bg-white p-6">
              <h3 className="mb-3 font-semibold">Embedding 상태</h3>
              <div className="space-y-2 text-sm">
                <div>Provider: <strong>{health.embedding.provider}</strong></div>
                <div>Model: <strong>{health.embedding.model}</strong></div>
                <div>Dimensions: <strong>{health.embedding.dimensions}</strong></div>
              </div>
            </div>
          </div>
          <div className="rounded-xl border bg-white p-6">
            <h3 className="mb-3 font-semibold">SMTP 이메일</h3>
            <div className="text-sm">
              <div>Enabled: <strong className={health.smtp.enabled ? 'text-emerald-600' : 'text-red-600'}>{health.smtp.enabled ? 'ON' : 'OFF'}</strong></div>
              <div>Host: <strong>{health.smtp.host}</strong></div>
            </div>
          </div>
        </div>
      )}

      {/* Footer 공지 */}
      <div className="mt-8">
        <AnnouncementFooter />
      </div>
    </main>
  );
}

