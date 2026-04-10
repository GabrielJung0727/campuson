'use client';

import { useAuth } from '@/contexts/AuthContext';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

export default function DashboardPage() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const [hasDiagnostic, setHasDiagnostic] = useState<boolean | null>(null);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  useEffect(() => {
    if (user) {
      api
        .getMyDiagnostic()
        .then((data: unknown) => {
          const d = data as { completed_at: string | null };
          setHasDiagnostic(!!d.completed_at);
        })
        .catch(() => setHasDiagnostic(false));
    }
  }, [user]);

  if (loading || !user) return <div className="p-8 text-center">로딩 중...</div>;

  const DEPT_LABEL: Record<string, string> = {
    NURSING: '간호학과',
    PHYSICAL_THERAPY: '물리치료학과',
    DENTAL_HYGIENE: '치위생과',
  };

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">CampusON</h1>
          <p className="text-sm text-slate-500">
            {user.name} ({DEPT_LABEL[user.department] || user.department})
          </p>
        </div>
        <button
          onClick={logout}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-slate-100"
        >
          로그아웃
        </button>
      </div>

      {/* 진단 테스트 안내 */}
      {hasDiagnostic === false && (
        <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-6">
          <h2 className="text-lg font-semibold text-amber-800">진단 테스트를 먼저 응시하세요</h2>
          <p className="mt-1 text-sm text-amber-700">
            AI가 학습 수준을 분석하고 맞춤형 학습을 제공하기 위해 최초 1회 진단 테스트가 필요합니다.
          </p>
          <Link
            href="/diagnostic"
            className="mt-4 inline-block rounded-lg bg-amber-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-amber-700"
          >
            진단 테스트 시작하기
          </Link>
        </div>
      )}

      {/* 메뉴 그리드 */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        <Link
          href="/quiz"
          className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition hover:shadow-md"
        >
          <div className="text-2xl">📝</div>
          <h3 className="mt-2 font-semibold">문제 풀이</h3>
          <p className="mt-1 text-xs text-slate-500">국시 문제 풀고 AI 해설 받기</p>
        </Link>

        <Link
          href="/chat"
          className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition hover:shadow-md"
        >
          <div className="text-2xl">💬</div>
          <h3 className="mt-2 font-semibold">AI 튜터</h3>
          <p className="mt-1 text-xs text-slate-500">자유롭게 질문하기</p>
        </Link>

        <Link
          href="/wrong-answers"
          className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition hover:shadow-md"
        >
          <div className="text-2xl">❌</div>
          <h3 className="mt-2 font-semibold">오답노트</h3>
          <p className="mt-1 text-xs text-slate-500">틀린 문제 복습하기</p>
        </Link>

        <Link
          href="/report"
          className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition hover:shadow-md"
        >
          <div className="text-2xl">📊</div>
          <h3 className="mt-2 font-semibold">학습 리포트</h3>
          <p className="mt-1 text-xs text-slate-500">성과 분석</p>
        </Link>

        {hasDiagnostic === false && (
          <Link
            href="/diagnostic"
            className="rounded-xl border border-amber-200 bg-amber-50 p-6 shadow-sm transition hover:shadow-md"
          >
            <div className="text-2xl">🧪</div>
            <h3 className="mt-2 font-semibold text-amber-800">진단 테스트</h3>
            <p className="mt-1 text-xs text-amber-600">AI 분석을 위한 필수 단계</p>
          </Link>
        )}

        {(user.role === 'PROFESSOR' || user.role === 'ADMIN') && (
          <Link
            href="/admin"
            className="rounded-xl border border-purple-200 bg-purple-50 p-6 shadow-sm transition hover:shadow-md"
          >
            <div className="text-2xl">⚙️</div>
            <h3 className="mt-2 font-semibold text-purple-800">관리</h3>
            <p className="mt-1 text-xs text-purple-600">
              {user.role === 'PROFESSOR' ? '학과 학생 관리' : '시스템 운영'}
            </p>
          </Link>
        )}
      </div>
    </main>
  );
}
