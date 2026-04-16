'use client';

import { useAuth } from '@/contexts/AuthContext';
import { AnnouncementBanner, AnnouncementFooter } from '@/components/AnnouncementBar';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

interface AssignmentItem { id: string; title: string; due_date: string | null; status: string }
interface AnnItem { title: string; content: string; announcement_type: string }

export default function DashboardPage() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const [hasDiagnostic, setHasDiagnostic] = useState<boolean | null>(null);
  const [assignments, setAssignments] = useState<AssignmentItem[]>([]);
  const [announcements, setAnnouncements] = useState<AnnItem[]>([]);
  const [percentile, setPercentile] = useState<number | null>(null);
  const [unreadNotifs, setUnreadNotifs] = useState(0);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  useEffect(() => {
    if (user) {
      api.getUnreadCount()
        .then((d: any) => setUnreadNotifs(d.unread_count || 0))
        .catch(() => {});
      api.getMyDiagnostic()
        .then((data: unknown) => { setHasDiagnostic(!!(data as { completed_at: string | null }).completed_at); })
        .catch(() => setHasDiagnostic(false));
      api.getAssignments()
        .then((data: unknown) => setAssignments((data as AssignmentItem[]).slice(0, 3)))
        .catch(() => {});
      api.getAnnouncements()
        .then((data: unknown) => setAnnouncements((data as AnnItem[]).filter(a => a.announcement_type === 'GENERAL').slice(0, 3)))
        .catch(() => {});
      api.getMyPercentile()
        .then((data: unknown) => setPercentile((data as { overall_percentile: number }).overall_percentile))
        .catch(() => {});
    }
  }, [user]);

  if (loading || !user) return <div className="p-8 text-center">로딩 중...</div>;

  const DEPT_LABEL: Record<string, string> = {
    NURSING: '간호학과',
    PHYSICAL_THERAPY: '물리치료학과',
    DENTAL_HYGIENE: '치위생과',
  };

  // Keep the old reference but we already define it above in the return, let me just use inline
  const _DEPT_LABEL: Record<string, string> = {
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
        <div className="flex items-center gap-2">
          <Link
            href="/notifications"
            className="relative rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 transition"
          >
            🔔
            {unreadNotifs > 0 && (
              <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
                {unreadNotifs > 9 ? '9+' : unreadNotifs}
              </span>
            )}
          </Link>
          <Link
            href="/account"
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 transition"
          >
            <svg className="inline-block h-4 w-4 mr-1 -mt-0.5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" /><path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" /></svg>
            설정
          </Link>
          <button
            onClick={logout}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-slate-100"
          >
            로그아웃
          </button>
        </div>
      </div>

      {/* v0.3: 상단 배너 */}
      <AnnouncementBanner />

      {/* v0.3: 백분위 + 과제 + 공지 카드 */}
      {user.role === 'STUDENT' && (
        <div className="mb-6 grid gap-4 md:grid-cols-3">
          {percentile !== null && (
            <div className="rounded-xl border border-brand-200 bg-brand-50 p-4">
              <div className="text-xs text-brand-600">학과 내 나의 순위</div>
              <div className="text-2xl font-bold text-brand-700">상위 {100 - percentile}%</div>
            </div>
          )}
          {assignments.length > 0 && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
              <div className="text-xs text-amber-600">진행 중 과제</div>
              {assignments.map((a) => (
                <div key={a.id} className="mt-1 text-sm font-medium text-amber-800">{a.title}</div>
              ))}
            </div>
          )}
          {announcements.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="text-xs text-slate-500">공지사항</div>
              {announcements.map((a, i) => (
                <div key={i} className="mt-1 text-sm text-slate-700">📢 {a.title}</div>
              ))}
            </div>
          )}
        </div>
      )}

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

        <Link
          href="/practicum"
          className="rounded-xl border border-teal-200 bg-teal-50 p-6 shadow-sm transition hover:shadow-md"
        >
          <div className="text-2xl">🩺</div>
          <h3 className="mt-2 font-semibold text-teal-800">실습 평가</h3>
          <p className="mt-1 text-xs text-teal-600">AI 실습 체크리스트 평가</p>
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

        {user.role === 'PROFESSOR' && (
          <>
            <Link href="/professor/classes" className="rounded-xl border border-purple-200 bg-purple-50 p-6 shadow-sm transition hover:shadow-md">
              <div className="text-2xl">📚</div>
              <h3 className="mt-2 font-semibold text-purple-800">클래스 관리</h3>
              <p className="mt-1 text-xs text-purple-600">학생 관리 · 통계</p>
            </Link>
            <Link href="/professor/assignments" className="rounded-xl border border-purple-200 bg-purple-50 p-6 shadow-sm transition hover:shadow-md">
              <div className="text-2xl">📋</div>
              <h3 className="mt-2 font-semibold text-purple-800">과제</h3>
              <p className="mt-1 text-xs text-purple-600">출제 · 채점</p>
            </Link>
            <Link href="/professor/analytics" className="rounded-xl border border-purple-200 bg-purple-50 p-6 shadow-sm transition hover:shadow-md">
              <div className="text-2xl">📊</div>
              <h3 className="mt-2 font-semibold text-purple-800">분석</h3>
              <p className="mt-1 text-xs text-purple-600">빅데이터 대시보드</p>
            </Link>
            <Link href="/professor/practicum" className="rounded-xl border border-teal-200 bg-teal-50 p-6 shadow-sm transition hover:shadow-md">
              <div className="text-2xl">🩺</div>
              <h3 className="mt-2 font-semibold text-teal-800">실습 평가 관리</h3>
              <p className="mt-1 text-xs text-teal-600">시나리오 · 리뷰</p>
            </Link>
          </>
        )}

        {user.role === 'ADMIN' && (
          <>
            <Link href="/admin" className="rounded-xl border border-purple-200 bg-purple-50 p-6 shadow-sm transition hover:shadow-md">
              <div className="text-2xl">⚙️</div>
              <h3 className="mt-2 font-semibold text-purple-800">관리자</h3>
              <p className="mt-1 text-xs text-purple-600">시스템 운영</p>
            </Link>
            <Link href="/admin/ops" className="rounded-xl border border-indigo-200 bg-indigo-50 p-6 shadow-sm transition hover:shadow-md">
              <div className="text-2xl">📈</div>
              <h3 className="mt-2 font-semibold text-indigo-800">운영 대시보드</h3>
              <p className="mt-1 text-xs text-indigo-600">메트릭 · 비용 · 장애</p>
            </Link>
          </>
        )}

        {user.role === 'DEVELOPER' && (
          <>
            <Link href="/dev" className="rounded-xl border border-red-200 bg-red-50 p-6 shadow-sm transition hover:shadow-md">
              <div className="text-2xl">🛠</div>
              <h3 className="mt-2 font-semibold text-red-800">개발자 센터</h3>
              <p className="mt-1 text-xs text-red-600">설정 · 모니터링 · LLM</p>
            </Link>
            <Link href="/admin/ops" className="rounded-xl border border-indigo-200 bg-indigo-50 p-6 shadow-sm transition hover:shadow-md">
              <div className="text-2xl">📈</div>
              <h3 className="mt-2 font-semibold text-indigo-800">운영 대시보드</h3>
              <p className="mt-1 text-xs text-indigo-600">메트릭 · 비용 · 장애</p>
            </Link>
          </>
        )}
      </div>
    </main>
  );
}
