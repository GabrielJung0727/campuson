'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

const DEPT_LABEL: Record<string, string> = {
  NURSING: '간호학과',
  PHYSICAL_THERAPY: '물리치료학과',
  DENTAL_HYGIENE: '치위생과',
};

const ROLE_LABEL: Record<string, string> = {
  STUDENT: '학생',
  PROFESSOR: '교수',
  ADMIN: '관리자',
  DEVELOPER: '개발자',
};

export default function AccountPage() {
  const { user, loading, logout, logoutAll } = useAuth();
  const router = useRouter();
  const [logoutAllLoading, setLogoutAllLoading] = useState(false);

  async function handleLogoutAll() {
    if (!confirm('모든 기기에서 로그아웃하시겠습니까? 다른 브라우저/기기에서도 즉시 로그아웃됩니다.')) return;
    setLogoutAllLoading(true);
    try {
      await logoutAll();
    } finally {
      setLogoutAllLoading(false);
    }
  }

  // Password change
  const [pwForm, setPwForm] = useState({ current: '', next: '', confirm: '' });
  const [pwLoading, setPwLoading] = useState(false);
  const [pwMsg, setPwMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null);

  // Notification prefs (local)
  const [prefs, setPrefs] = useState({
    email_announcement: true,
    email_assignment: true,
    email_report: false,
  });
  const [prefsSaved, setPrefsSaved] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  // Load prefs from localStorage
  useEffect(() => {
    if (user) {
      const stored = localStorage.getItem(`prefs_${user.id}`);
      if (stored) {
        try { setPrefs(JSON.parse(stored)); } catch { /* ignore */ }
      }
    }
  }, [user]);

  async function handlePasswordChange() {
    setPwMsg(null);
    if (pwForm.next !== pwForm.confirm) {
      setPwMsg({ type: 'err', text: '새 비밀번호가 일치하지 않습니다.' });
      return;
    }
    if (pwForm.next.length < 8) {
      setPwMsg({ type: 'err', text: '비밀번호는 최소 8자 이상이어야 합니다.' });
      return;
    }
    setPwLoading(true);
    try {
      await api.changePassword({ current_password: pwForm.current, new_password: pwForm.next });
      setPwMsg({ type: 'ok', text: '비밀번호가 변경되었습니다.' });
      setPwForm({ current: '', next: '', confirm: '' });
    } catch (err) {
      setPwMsg({ type: 'err', text: err instanceof Error ? err.message : '변경 실패' });
    } finally {
      setPwLoading(false);
    }
  }

  function savePrefs(updated: typeof prefs) {
    setPrefs(updated);
    if (user) localStorage.setItem(`prefs_${user.id}`, JSON.stringify(updated));
    setPrefsSaved(true);
    setTimeout(() => setPrefsSaved(false), 2000);
  }

  if (loading || !user) return <div className="p-8 text-center">로딩 중...</div>;

  return (
    <main className="mx-auto max-w-2xl px-4 py-8">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">계정 설정</h1>
          <p className="text-sm text-slate-500">프로필 정보, 비밀번호 변경, 알림 설정</p>
        </div>
        <Link
          href="/dashboard"
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 transition"
        >
          &larr; 대시보드
        </Link>
      </div>

      {/* ===== Profile Info ===== */}
      <section className="mb-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-bold text-slate-900">프로필 정보</h2>
        <div className="space-y-4">
          <div className="flex items-center gap-4">
            {/* Avatar */}
            <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-brand-100 text-2xl font-bold text-brand-700">
              {user.name.charAt(0)}
            </div>
            <div>
              <div className="text-lg font-semibold text-slate-900">{user.name}</div>
              <div className="text-sm text-slate-500">{user.email}</div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 rounded-xl bg-slate-50 p-4">
            <div>
              <div className="text-xs font-medium text-slate-400">학과</div>
              <div className="mt-0.5 text-sm font-semibold text-slate-700">
                {DEPT_LABEL[user.department] || user.department}
              </div>
            </div>
            <div>
              <div className="text-xs font-medium text-slate-400">역할</div>
              <div className="mt-0.5 text-sm font-semibold text-slate-700">
                {ROLE_LABEL[user.role] || user.role}
              </div>
            </div>
            {user.student_no && (
              <div>
                <div className="text-xs font-medium text-slate-400">학번</div>
                <div className="mt-0.5 text-sm font-semibold text-slate-700">{user.student_no}</div>
              </div>
            )}
            <div>
              <div className="text-xs font-medium text-slate-400">상태</div>
              <div className="mt-0.5 flex items-center gap-1.5 text-sm font-semibold text-emerald-600">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                {user.status === 'ACTIVE' ? '활성' : user.status}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ===== Password Change ===== */}
      <section className="mb-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-bold text-slate-900">비밀번호 변경</h2>
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500">현재 비밀번호</label>
            <input
              type="password"
              value={pwForm.current}
              onChange={(e) => setPwForm((f) => ({ ...f, current: e.target.value }))}
              className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              placeholder="현재 비밀번호 입력"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500">새 비밀번호</label>
            <input
              type="password"
              value={pwForm.next}
              onChange={(e) => setPwForm((f) => ({ ...f, next: e.target.value }))}
              className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              placeholder="8자 이상"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500">새 비밀번호 확인</label>
            <input
              type="password"
              value={pwForm.confirm}
              onChange={(e) => setPwForm((f) => ({ ...f, confirm: e.target.value }))}
              className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              placeholder="다시 입력"
            />
          </div>

          {pwMsg && (
            <div className={`rounded-lg px-3 py-2 text-sm ${
              pwMsg.type === 'ok' ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'
            }`}>
              {pwMsg.text}
            </div>
          )}

          <button
            onClick={handlePasswordChange}
            disabled={pwLoading || !pwForm.current || !pwForm.next || !pwForm.confirm}
            className="rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {pwLoading ? '변경 중...' : '비밀번호 변경'}
          </button>
        </div>
      </section>

      {/* ===== Notification Prefs ===== */}
      <section className="mb-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-bold text-slate-900">알림 설정</h2>
          {prefsSaved && (
            <span className="text-xs font-medium text-emerald-600">저장됨</span>
          )}
        </div>
        <div className="space-y-4">
          {([
            { key: 'email_announcement' as const, label: '공지사항 이메일', desc: '새로운 공지가 등록되면 이메일로 알려드립니다.' },
            { key: 'email_assignment' as const, label: '과제 알림 이메일', desc: '새 과제가 배정되거나 마감이 임박하면 알려드립니다.' },
            { key: 'email_report' as const, label: '주간 학습 리포트', desc: '매주 학습 현황 요약을 이메일로 받아봅니다.' },
          ]).map((item) => (
            <div key={item.key} className="flex items-start justify-between gap-4">
              <div>
                <div className="text-sm font-semibold text-slate-700">{item.label}</div>
                <div className="text-xs text-slate-400">{item.desc}</div>
              </div>
              <button
                onClick={() => savePrefs({ ...prefs, [item.key]: !prefs[item.key] })}
                className={`relative mt-0.5 h-6 w-11 shrink-0 rounded-full transition ${
                  prefs[item.key] ? 'bg-brand-600' : 'bg-slate-300'
                }`}
              >
                <span
                  className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
                    prefs[item.key] ? 'translate-x-5' : 'translate-x-0.5'
                  }`}
                />
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* ===== Danger Zone ===== */}
      <section className="rounded-2xl border border-red-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-bold text-red-600">계정</h2>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold text-slate-700">로그아웃</div>
              <div className="text-xs text-slate-400">현재 세션을 종료합니다.</div>
            </div>
            <button
              onClick={logout}
              className="rounded-lg border border-red-300 px-4 py-2 text-sm font-medium text-red-600 transition hover:bg-red-50"
            >
              로그아웃
            </button>
          </div>

          <div className="flex items-center justify-between border-t border-slate-100 pt-4">
            <div>
              <div className="text-sm font-semibold text-slate-700">모든 기기에서 로그아웃</div>
              <div className="text-xs text-slate-400">
                다른 브라우저/기기에서도 즉시 로그아웃됩니다. 계정 보안이 의심될 때 사용하세요.
              </div>
            </div>
            <button
              onClick={handleLogoutAll}
              disabled={logoutAllLoading}
              className="shrink-0 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-red-700 disabled:opacity-50"
            >
              {logoutAllLoading ? '처리 중...' : '전체 로그아웃'}
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}
