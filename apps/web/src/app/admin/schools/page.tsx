'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

interface SchoolItem {
  id: string;
  name: string;
  code: string;
  domain: string | null;
  logo_url: string | null;
  primary_color: string;
  is_active: boolean;
}

interface SchoolSettings {
  school_id: string;
  llm_provider: string;
  llm_model: string;
  daily_token_limit_student: number;
  daily_token_limit_professor: number;
  monthly_cost_limit_usd: number;
  sso_enabled: boolean;
  sso_provider: string | null;
  lms_enabled: boolean;
  lms_platform: string | null;
}

interface DepartmentItem {
  id: string;
  department: string;
  department_label: string;
  is_active: boolean;
  head_professor_id: string | null;
}

export default function SchoolAdminPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [schools, setSchools] = useState<SchoolItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [settings, setSettings] = useState<SchoolSettings | null>(null);
  const [departments, setDepartments] = useState<DepartmentItem[]>([]);
  const [tab, setTab] = useState<'list' | 'settings' | 'departments' | 'create'>('list');
  const [form, setForm] = useState({ name: '', code: '', domain: '' });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && (!user || !['ADMIN', 'DEVELOPER'].includes(user.role))) {
      router.push('/dashboard');
    }
  }, [user, loading, router]);

  useEffect(() => {
    api.getSchools().then((d: any) => setSchools(d)).catch(() => {});
  }, []);

  useEffect(() => {
    if (selectedId) {
      api.getSchoolSettings(selectedId).then((d: any) => setSettings(d)).catch(() => {});
      api.getSchoolDepartments(selectedId).then((d: any) => setDepartments(d)).catch(() => {});
    }
  }, [selectedId]);

  const handleCreate = async () => {
    if (!form.name || !form.code) return;
    setBusy(true);
    try {
      await api.createSchool(form);
      const list: any = await api.getSchools();
      setSchools(list);
      setTab('list');
      setForm({ name: '', code: '', domain: '' });
    } finally {
      setBusy(false);
    }
  };

  if (loading || !user) return null;

  return (
    <main className="mx-auto max-w-5xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <Link href="/dashboard" className="text-sm text-blue-600 hover:underline">&larr; 대시보드</Link>
          <h1 className="mt-1 text-2xl font-bold text-gray-900">학교 관리 (멀티테넌시)</h1>
        </div>
        <button
          onClick={() => setTab('create')}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          + 학교 추가
        </button>
      </div>

      {/* Tabs */}
      <div className="mb-4 flex gap-2">
        {(['list', 'settings', 'departments'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-lg px-4 py-2 text-sm font-medium ${
              tab === t ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {t === 'list' ? '학교 목록' : t === 'settings' ? '설정' : '학과 관리'}
          </button>
        ))}
      </div>

      {/* Create Form */}
      {tab === 'create' && (
        <div className="rounded-xl border bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold">새 학교 생성</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-gray-700">학교명 *</label>
              <input
                className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">코드 (slug) *</label>
              <input
                className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">도메인</label>
              <input
                className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
                value={form.domain}
                onChange={(e) => setForm({ ...form, domain: e.target.value })}
                placeholder="example.ac.kr"
              />
            </div>
          </div>
          <button
            onClick={handleCreate}
            disabled={busy}
            className="mt-4 rounded-lg bg-blue-600 px-6 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {busy ? '생성 중...' : '학교 생성'}
          </button>
        </div>
      )}

      {/* School List */}
      {tab === 'list' && (
        <div className="space-y-3">
          {schools.length === 0 && (
            <p className="py-12 text-center text-gray-400">등록된 학교가 없습니다.</p>
          )}
          {schools.map((s) => (
            <div
              key={s.id}
              onClick={() => { setSelectedId(s.id); setTab('settings'); }}
              className={`cursor-pointer rounded-xl border p-4 shadow-sm transition hover:shadow-md ${
                selectedId === s.id ? 'border-blue-400 bg-blue-50' : 'bg-white'
              }`}
            >
              <div className="flex items-center gap-3">
                <div
                  className="h-10 w-10 rounded-lg"
                  style={{ backgroundColor: s.primary_color }}
                />
                <div>
                  <h3 className="font-semibold text-gray-900">{s.name}</h3>
                  <p className="text-xs text-gray-500">
                    {s.code} {s.domain && `· ${s.domain}`}
                    {!s.is_active && ' · 비활성'}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Settings */}
      {tab === 'settings' && settings && (
        <div className="rounded-xl border bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold">학교 설정</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-lg bg-gray-50 p-4">
              <h4 className="text-sm font-medium text-gray-500">LLM 제공자</h4>
              <p className="mt-1 text-lg font-semibold">{settings.llm_provider || 'anthropic'}</p>
              <p className="text-xs text-gray-400">{settings.llm_model || 'claude-sonnet'}</p>
            </div>
            <div className="rounded-lg bg-gray-50 p-4">
              <h4 className="text-sm font-medium text-gray-500">일일 토큰 한도</h4>
              <p className="mt-1 text-sm">학생: {settings.daily_token_limit_student?.toLocaleString() || '-'}</p>
              <p className="text-xs text-gray-400">교수: {settings.daily_token_limit_professor?.toLocaleString() || '-'}</p>
            </div>
            <div className="rounded-lg bg-gray-50 p-4">
              <h4 className="text-sm font-medium text-gray-500">월 비용 한도</h4>
              <p className="mt-1 text-lg font-semibold">${settings.monthly_cost_limit_usd || '-'}</p>
            </div>
            <div className="rounded-lg bg-gray-50 p-4">
              <h4 className="text-sm font-medium text-gray-500">SSO</h4>
              <p className="mt-1 text-lg font-semibold">
                {settings.sso_enabled ? `활성 (${settings.sso_provider})` : '비활성'}
              </p>
            </div>
            <div className="rounded-lg bg-gray-50 p-4">
              <h4 className="text-sm font-medium text-gray-500">LMS 연동</h4>
              <p className="mt-1 text-lg font-semibold">
                {settings.lms_enabled ? `활성 (${settings.lms_platform})` : '비활성'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Departments */}
      {tab === 'departments' && (
        <div className="rounded-xl border bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold">학과 목록</h2>
          {departments.length === 0 && (
            <p className="py-8 text-center text-gray-400">등록된 학과가 없습니다.</p>
          )}
          <div className="space-y-2">
            {departments.map((d) => (
              <div key={d.id} className="flex items-center justify-between rounded-lg bg-gray-50 p-4">
                <div>
                  <span className="font-medium text-gray-900">{d.department_label}</span>
                  <span className="ml-2 text-xs text-gray-500">({d.department})</span>
                </div>
                <span className={`rounded-full px-2 py-0.5 text-xs ${
                  d.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-200 text-gray-500'
                }`}>
                  {d.is_active ? '활성' : '비활성'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </main>
  );
}
