'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api, apiFetch } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';

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

const DEPT_META: Record<string, { label: string; color: string; accent: string; icon: string }> = {
  NURSING: { label: '간호학과', color: 'from-cyan-500/20 to-cyan-900/10', accent: 'text-cyan-400', icon: '💉' },
  PHYSICAL_THERAPY: { label: '물리치료학과', color: 'from-emerald-500/20 to-emerald-900/10', accent: 'text-emerald-400', icon: '🦴' },
  DENTAL_HYGIENE: { label: '치위생과', color: 'from-violet-500/20 to-violet-900/10', accent: 'text-violet-400', icon: '🦷' },
};

const ROLE_BADGE: Record<string, string> = {
  STUDENT: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  PROFESSOR: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
  ADMIN: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  DEVELOPER: 'bg-rose-500/20 text-rose-300 border-rose-500/30',
};

const STATUS_BADGE: Record<string, string> = {
  ACTIVE: 'bg-emerald-500/20 text-emerald-300',
  PENDING: 'bg-yellow-500/20 text-yellow-300',
  SUSPENDED: 'bg-red-500/20 text-red-300',
};

export default function DevDashboardPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<'overview' | 'users' | 'settings' | 'llm'>('overview');
  const [health, setHealth] = useState<HealthCheck | null>(null);
  const [stats, setStats] = useState<DevStats | null>(null);
  const [settings, setSettings] = useState<Record<string, unknown> | null>(null);
  const [users, setUsers] = useState<UserItem[]>([]);
  const [deptFilter, setDeptFilter] = useState<string>('ALL');
  const [roleFilter, setRoleFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [now, setNow] = useState(new Date());

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

  // Live clock
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const filteredUsers = useMemo(() => {
    return users.filter((u) => {
      if (deptFilter !== 'ALL' && u.department !== deptFilter) return false;
      if (roleFilter !== 'ALL' && u.role !== roleFilter) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        return u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q) || (u.student_no || '').includes(q);
      }
      return true;
    });
  }, [users, deptFilter, roleFilter, searchQuery]);

  // Department aggregation
  const deptAgg = useMemo(() => {
    const result: Record<string, { total: number; students: number; professors: number; admins: number }> = {};
    for (const dept of Object.keys(DEPT_META)) {
      result[dept] = { total: 0, students: 0, professors: 0, admins: 0 };
    }
    for (const u of users) {
      if (!result[u.department]) continue;
      result[u.department].total++;
      if (u.role === 'STUDENT') result[u.department].students++;
      else if (u.role === 'PROFESSOR') result[u.department].professors++;
      else result[u.department].admins++;
    }
    return result;
  }, [users]);

  async function handleRoleChange(userId: string, field: string, value: string) {
    try {
      const body: Record<string, unknown> = { [field]: value === '' ? null : (field === 'grade' ? Number(value) : value) };
      await api.updateUserRole(userId, body);
      const updated = await apiFetch<UserItem[]>('/users');
      setUsers(updated);
    } catch (err) {
      console.error('Role update failed:', err);
      alert(`변경 실패: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  if (loading || !user) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-950">
        <div className="text-slate-400 font-mono text-sm animate-pulse">INITIALIZING...</div>
      </div>
    );
  }

  const tabs = [
    { key: 'overview' as const, label: 'SYSTEM', icon: '>' },
    { key: 'users' as const, label: `USERS [${users.length}]`, icon: '>' },
    { key: 'settings' as const, label: 'CONFIG', icon: '>' },
    { key: 'llm' as const, label: 'AI/RAG', icon: '>' },
  ];

  const totalRecords = stats ? Object.values(stats.table_counts).reduce((a, b) => a + b, 0) : 0;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200">
      {/* Top Bar */}
      <header className="sticky top-0 z-50 border-b border-slate-800/80 bg-slate-950/95 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-rose-500 to-orange-500 text-sm font-black text-white">
              C
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm font-bold tracking-wider text-slate-100">CAMPUSON</span>
                <span className="rounded bg-rose-500/20 px-1.5 py-0.5 font-mono text-[10px] font-bold text-rose-400 border border-rose-500/30">
                  DEV
                </span>
              </div>
              <div className="font-mono text-[10px] text-slate-500">
                {now.toLocaleDateString('ko-KR')} {now.toLocaleTimeString('ko-KR')}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-2 text-xs text-slate-500 font-mono">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
              {user.name}
            </div>
            <button
              onClick={() => router.push('/dashboard')}
              className="rounded-md border border-slate-700 bg-slate-800/50 px-3 py-1.5 font-mono text-xs text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition"
            >
              EXIT
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-4 py-6">
        {/* Tab Navigation */}
        <nav className="mb-6 flex gap-1 rounded-lg border border-slate-800 bg-slate-900/50 p-1">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex-1 rounded-md px-3 py-2.5 font-mono text-xs font-medium tracking-wide transition ${
                tab === t.key
                  ? 'bg-slate-800 text-slate-100 shadow-lg shadow-slate-900/50'
                  : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/30'
              }`}
            >
              <span className={tab === t.key ? 'text-rose-400' : 'text-slate-600'}>{t.icon}</span> {t.label}
            </button>
          ))}
        </nav>

        {/* ===== OVERVIEW TAB ===== */}
        {tab === 'overview' && (
          <div className="space-y-6">
            {/* Health Status Row */}
            {health && (
              <div className="grid gap-3 grid-cols-2 md:grid-cols-5">
                {([
                  { name: 'DATABASE', val: health.db, detail: 'PostgreSQL 16' },
                  { name: 'CACHE', val: health.redis, detail: 'Redis 7' },
                  { name: 'LLM', val: 'ok', detail: `${health.llm.provider} / ${health.llm.model}` },
                  { name: 'EMBED', val: 'ok', detail: `${health.embedding.provider} (${health.embedding.dimensions}d)` },
                  { name: 'SMTP', val: health.smtp.enabled ? 'ok' : 'off', detail: health.smtp.host || 'disabled' },
                ] as const).map((s) => {
                  const isOk = s.val === 'ok';
                  const isOff = s.val === 'off';
                  return (
                    <div key={s.name} className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <span className={`h-2 w-2 rounded-full ${isOk ? 'bg-emerald-400 shadow-lg shadow-emerald-400/50' : isOff ? 'bg-slate-600' : 'bg-red-400 shadow-lg shadow-red-400/50'}`} />
                        <span className="font-mono text-[11px] font-bold tracking-widest text-slate-400">{s.name}</span>
                      </div>
                      <div className={`font-mono text-xs ${isOk ? 'text-emerald-400' : isOff ? 'text-slate-500' : 'text-red-400'}`}>
                        {isOk ? 'ONLINE' : isOff ? 'DISABLED' : 'ERROR'}
                      </div>
                      <div className="mt-1 truncate font-mono text-[10px] text-slate-600">{s.detail}</div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Department Cards — ALL 3 departments */}
            <div>
              <h2 className="mb-3 font-mono text-xs font-bold tracking-widest text-slate-500">DEPARTMENTS</h2>
              <div className="grid gap-4 md:grid-cols-3">
                {Object.entries(DEPT_META).map(([key, meta]) => {
                  const agg = deptAgg[key] || { total: 0, students: 0, professors: 0, admins: 0 };
                  return (
                    <div key={key} className={`rounded-xl border border-slate-800 bg-gradient-to-br ${meta.color} p-5`}>
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-2">
                          <span className="text-2xl">{meta.icon}</span>
                          <div>
                            <div className={`font-bold ${meta.accent}`}>{meta.label}</div>
                            <div className="font-mono text-[10px] text-slate-500">{key}</div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-2xl font-black text-slate-200">{agg.total}</div>
                          <div className="font-mono text-[10px] text-slate-500">USERS</div>
                        </div>
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        {([
                          { label: '학생', count: agg.students, color: 'text-blue-400' },
                          { label: '교수', count: agg.professors, color: 'text-purple-400' },
                          { label: '관리', count: agg.admins, color: 'text-amber-400' },
                        ]).map((r) => (
                          <div key={r.label} className="rounded-lg bg-slate-900/40 px-2 py-2 text-center">
                            <div className={`text-lg font-bold ${r.color}`}>{r.count}</div>
                            <div className="text-[10px] text-slate-500">{r.label}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Table Records */}
            {stats && (
              <div>
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="font-mono text-xs font-bold tracking-widest text-slate-500">DATA STORAGE</h2>
                  <span className="font-mono text-xs text-slate-600">{totalRecords.toLocaleString()} total records</span>
                </div>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
                  {Object.entries(stats.table_counts)
                    .sort(([, a], [, b]) => b - a)
                    .map(([table, count]) => (
                      <div key={table} className="group rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-center hover:border-slate-700 hover:bg-slate-900/80 transition">
                        <div className="text-xl font-black text-slate-200 group-hover:text-white">{count.toLocaleString()}</div>
                        <div className="mt-1 truncate font-mono text-[10px] text-slate-500 group-hover:text-slate-400">{table}</div>
                        {/* mini bar */}
                        <div className="mt-2 h-1 w-full rounded-full bg-slate-800 overflow-hidden">
                          <div
                            className="h-full rounded-full bg-gradient-to-r from-rose-500 to-orange-500"
                            style={{ width: `${Math.max(2, (count / Math.max(...Object.values(stats.table_counts), 1)) * 100)}%` }}
                          />
                        </div>
                      </div>
                    ))}
                </div>
              </div>
            )}

            {/* Role Distribution across all departments */}
            {stats && stats.department_stats.length > 0 && (
              <div>
                <h2 className="mb-3 font-mono text-xs font-bold tracking-widest text-slate-500">ROLE MATRIX</h2>
                <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/40">
                  <table className="w-full font-mono text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-500">
                        <th className="px-4 py-3 text-left tracking-wider">DEPT</th>
                        <th className="px-4 py-3 text-left tracking-wider">ROLE</th>
                        <th className="px-4 py-3 text-right tracking-wider">COUNT</th>
                        <th className="px-4 py-3 text-left tracking-wider w-48">VISUAL</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stats.department_stats.map((d, i) => {
                        const maxCount = Math.max(...stats.department_stats.map((s) => s.count), 1);
                        const meta = DEPT_META[d.department];
                        return (
                          <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition">
                            <td className={`px-4 py-2.5 ${meta?.accent || 'text-slate-300'}`}>
                              {meta?.icon} {meta?.label || d.department}
                            </td>
                            <td className="px-4 py-2.5">
                              <span className={`inline-block rounded border px-2 py-0.5 text-[10px] ${ROLE_BADGE[d.role] || 'text-slate-400'}`}>
                                {d.role}
                              </span>
                            </td>
                            <td className="px-4 py-2.5 text-right font-bold text-slate-200">{d.count}</td>
                            <td className="px-4 py-2.5">
                              <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                                <div
                                  className="h-full rounded-full bg-gradient-to-r from-blue-500 to-cyan-400 transition-all duration-500"
                                  style={{ width: `${(d.count / maxCount) * 100}%` }}
                                />
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ===== USERS TAB ===== */}
        {tab === 'users' && (
          <div className="space-y-4">
            {/* Filters */}
            <div className="flex flex-wrap gap-3 rounded-xl border border-slate-800 bg-slate-900/50 p-4">
              <div className="flex-1 min-w-[200px]">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search name, email, student_no..."
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 font-mono text-xs text-slate-200 placeholder-slate-600 focus:border-rose-500/50 focus:outline-none focus:ring-1 focus:ring-rose-500/30"
                />
              </div>
              <select
                value={deptFilter}
                onChange={(e) => setDeptFilter(e.target.value)}
                className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 font-mono text-xs text-slate-300 focus:border-rose-500/50 focus:outline-none"
              >
                <option value="ALL">ALL DEPTS</option>
                {Object.entries(DEPT_META).map(([key, meta]) => (
                  <option key={key} value={key}>{meta.label}</option>
                ))}
              </select>
              <select
                value={roleFilter}
                onChange={(e) => setRoleFilter(e.target.value)}
                className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 font-mono text-xs text-slate-300 focus:border-rose-500/50 focus:outline-none"
              >
                <option value="ALL">ALL ROLES</option>
                {ROLE_OPTIONS.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
              <div className="flex items-center gap-2 font-mono text-[11px] text-slate-500">
                {filteredUsers.length}/{users.length} records
              </div>
            </div>

            {/* Users Table */}
            <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/40">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-500 font-mono text-[10px] tracking-widest">
                    <th className="px-3 py-3 text-left">NAME</th>
                    <th className="px-3 py-3 text-left">EMAIL</th>
                    <th className="px-3 py-3 text-left">DEPT</th>
                    <th className="px-3 py-3 text-left">ROLE</th>
                    <th className="px-3 py-3 text-left">SUB-ROLE</th>
                    <th className="px-3 py-3 text-left">GRADE</th>
                    <th className="px-3 py-3 text-left">STATUS</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredUsers.map((u) => {
                    const meta = DEPT_META[u.department];
                    return (
                      <tr key={u.id} className="border-b border-slate-800/40 hover:bg-slate-800/40 transition">
                        <td className="px-3 py-2.5 font-medium text-slate-200">{u.name}</td>
                        <td className="px-3 py-2.5 font-mono text-slate-500">{u.email}</td>
                        <td className="px-3 py-2.5">
                          <span className={meta?.accent || 'text-slate-400'}>
                            {meta?.icon} {meta?.label || u.department}
                          </span>
                        </td>
                        <td className="px-3 py-2.5">
                          <select
                            value={u.role}
                            onChange={(e) => handleRoleChange(u.id, 'role', e.target.value)}
                            className="rounded border border-slate-700 bg-slate-800 px-2 py-1 font-mono text-[11px] text-slate-300 focus:outline-none focus:border-rose-500/50"
                          >
                            {ROLE_OPTIONS.map((r) => <option key={r} value={r}>{r}</option>)}
                          </select>
                        </td>
                        <td className="px-3 py-2.5">
                          {u.role === 'PROFESSOR' && (
                            <select
                              value={u.professor_role || ''}
                              onChange={(e) => handleRoleChange(u.id, 'professor_role', e.target.value)}
                              className="rounded border border-slate-700 bg-slate-800 px-2 py-1 font-mono text-[11px] text-slate-300 focus:outline-none"
                            >
                              <option value="">-</option>
                              {PROF_ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                            </select>
                          )}
                          {u.role === 'ADMIN' && (
                            <select
                              value={u.admin_role || ''}
                              onChange={(e) => handleRoleChange(u.id, 'admin_role', e.target.value)}
                              className="rounded border border-slate-700 bg-slate-800 px-2 py-1 font-mono text-[11px] text-slate-300 focus:outline-none"
                            >
                              <option value="">-</option>
                              {ADMIN_ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                            </select>
                          )}
                          {u.role !== 'PROFESSOR' && u.role !== 'ADMIN' && (
                            <span className="text-slate-600">-</span>
                          )}
                        </td>
                        <td className="px-3 py-2.5">
                          {u.role === 'STUDENT' ? (
                            <select
                              value={u.grade || ''}
                              onChange={(e) => handleRoleChange(u.id, 'grade', e.target.value)}
                              className="rounded border border-slate-700 bg-slate-800 px-2 py-1 font-mono text-[11px] text-slate-300 focus:outline-none"
                            >
                              <option value="">-</option>
                              {[1, 2, 3, 4].map((g) => <option key={g} value={g}>{g}</option>)}
                            </select>
                          ) : (
                            <span className="text-slate-600">-</span>
                          )}
                        </td>
                        <td className="px-3 py-2.5">
                          <span className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-bold ${STATUS_BADGE[u.status] || 'text-slate-400'}`}>
                            {u.status}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                  {filteredUsers.length === 0 && (
                    <tr>
                      <td colSpan={7} className="px-3 py-8 text-center font-mono text-slate-600">
                        NO MATCHING RECORDS
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ===== SETTINGS TAB ===== */}
        {tab === 'settings' && settings && (
          <div className="space-y-4">
            <div className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-900/50 px-4 py-3">
              <span className="h-2 w-2 rounded-full bg-amber-400" />
              <span className="font-mono text-xs text-slate-400">READ-ONLY &mdash; .env or system settings center</span>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 divide-y divide-slate-800/60">
              {Object.entries(settings).map(([key, val]) => {
                const isSecret = String(key).toLowerCase().includes('key') || String(key).toLowerCase().includes('password');
                const isEnabled = String(val) === 'true' || String(val) === 'True';
                const isDisabled = String(val) === 'false' || String(val) === 'False';
                return (
                  <div key={key} className="flex items-center justify-between px-4 py-3 hover:bg-slate-800/20 transition">
                    <span className="font-mono text-xs text-slate-400">{key}</span>
                    <span className={`font-mono text-xs font-medium ${
                      isSecret ? 'text-rose-400/60' : isEnabled ? 'text-emerald-400' : isDisabled ? 'text-slate-500' : 'text-slate-200'
                    }`}>
                      {String(val)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ===== LLM/RAG TAB ===== */}
        {tab === 'llm' && health && (
          <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-3">
              {/* LLM Card */}
              <div className="rounded-xl border border-slate-800 bg-gradient-to-br from-blue-500/10 to-slate-900/50 p-6">
                <div className="flex items-center gap-2 mb-4">
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-lg shadow-emerald-400/50 animate-pulse" />
                  <span className="font-mono text-[10px] font-bold tracking-widest text-slate-400">LANGUAGE MODEL</span>
                </div>
                <div className="space-y-3">
                  <div>
                    <div className="font-mono text-[10px] text-slate-500">PROVIDER</div>
                    <div className="font-mono text-sm font-bold text-blue-400">{health.llm.provider}</div>
                  </div>
                  <div>
                    <div className="font-mono text-[10px] text-slate-500">MODEL</div>
                    <div className="font-mono text-sm font-bold text-slate-200">{health.llm.model}</div>
                  </div>
                  <div className="mt-4 rounded-lg bg-slate-800/50 px-3 py-2">
                    <div className="font-mono text-[10px] text-emerald-400">STATUS: OPERATIONAL</div>
                  </div>
                </div>
              </div>

              {/* Embedding Card */}
              <div className="rounded-xl border border-slate-800 bg-gradient-to-br from-violet-500/10 to-slate-900/50 p-6">
                <div className="flex items-center gap-2 mb-4">
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-lg shadow-emerald-400/50 animate-pulse" />
                  <span className="font-mono text-[10px] font-bold tracking-widest text-slate-400">EMBEDDING</span>
                </div>
                <div className="space-y-3">
                  <div>
                    <div className="font-mono text-[10px] text-slate-500">PROVIDER</div>
                    <div className="font-mono text-sm font-bold text-violet-400">{health.embedding.provider}</div>
                  </div>
                  <div>
                    <div className="font-mono text-[10px] text-slate-500">MODEL</div>
                    <div className="font-mono text-sm font-bold text-slate-200">{health.embedding.model}</div>
                  </div>
                  <div>
                    <div className="font-mono text-[10px] text-slate-500">DIMENSIONS</div>
                    <div className="font-mono text-sm font-bold text-slate-200">{health.embedding.dimensions}</div>
                  </div>
                </div>
              </div>

              {/* SMTP Card */}
              <div className="rounded-xl border border-slate-800 bg-gradient-to-br from-amber-500/10 to-slate-900/50 p-6">
                <div className="flex items-center gap-2 mb-4">
                  <span className={`h-2.5 w-2.5 rounded-full ${health.smtp.enabled ? 'bg-emerald-400 shadow-lg shadow-emerald-400/50 animate-pulse' : 'bg-slate-600'}`} />
                  <span className="font-mono text-[10px] font-bold tracking-widest text-slate-400">SMTP EMAIL</span>
                </div>
                <div className="space-y-3">
                  <div>
                    <div className="font-mono text-[10px] text-slate-500">ENABLED</div>
                    <div className={`font-mono text-sm font-bold ${health.smtp.enabled ? 'text-emerald-400' : 'text-red-400'}`}>
                      {health.smtp.enabled ? 'YES' : 'NO'}
                    </div>
                  </div>
                  <div>
                    <div className="font-mono text-[10px] text-slate-500">HOST</div>
                    <div className="font-mono text-sm font-bold text-slate-200">{health.smtp.host || '-'}</div>
                  </div>
                  <div className="mt-4 rounded-lg bg-slate-800/50 px-3 py-2">
                    <div className={`font-mono text-[10px] ${health.smtp.enabled ? 'text-emerald-400' : 'text-amber-400'}`}>
                      STATUS: {health.smtp.enabled ? 'OPERATIONAL' : 'DISABLED'}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* RAG Pipeline info */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
              <h3 className="mb-4 font-mono text-xs font-bold tracking-widest text-slate-400">RAG PIPELINE</h3>
              <div className="flex items-center gap-2 flex-wrap font-mono text-xs">
                {[
                  { label: 'PDF Upload', color: 'border-blue-500/50 text-blue-400' },
                  { label: 'Chunking', color: 'border-violet-500/50 text-violet-400' },
                  { label: 'Embedding', color: 'border-purple-500/50 text-purple-400' },
                  { label: 'pgvector', color: 'border-cyan-500/50 text-cyan-400' },
                  { label: 'Hybrid Search', color: 'border-emerald-500/50 text-emerald-400' },
                  { label: 'RRF Fusion', color: 'border-amber-500/50 text-amber-400' },
                  { label: 'LLM Generate', color: 'border-rose-500/50 text-rose-400' },
                ].map((step, i) => (
                  <div key={step.label} className="flex items-center gap-2">
                    <span className={`rounded-lg border bg-slate-800/60 px-3 py-1.5 ${step.color}`}>
                      {step.label}
                    </span>
                    {i < 6 && <span className="text-slate-600">&rarr;</span>}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
