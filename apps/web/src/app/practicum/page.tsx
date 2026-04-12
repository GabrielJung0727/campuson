'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

interface Scenario { id: string; name: string; category: string; category_label: string; department: string; department_label: string; total_points: number; checklist_items: unknown[] }
interface Session { id: string; scenario_id: string; scenario_name: string; scenario_category_label: string; status: string; total_score: number | null; grade: string | null; grade_label: string | null; total_points: number; created_at: string }

const GRADE_COLOR: Record<string, string> = {
  EXCELLENT: 'bg-emerald-100 text-emerald-700',
  GOOD: 'bg-blue-100 text-blue-700',
  NEEDS_IMPROVEMENT: 'bg-amber-100 text-amber-700',
  FAIL: 'bg-red-100 text-red-700',
};

const STATUS_LABEL: Record<string, { label: string; color: string }> = {
  DRAFT: { label: '진행 중', color: 'bg-slate-100 text-slate-600' },
  SUBMITTED: { label: '제출 완료', color: 'bg-amber-100 text-amber-700' },
  REVIEWED: { label: '리뷰 완료', color: 'bg-emerald-100 text-emerald-700' },
};

export default function PracticumPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  useEffect(() => {
    if (user) {
      api.getPracticumScenarios().then((d: unknown) => setScenarios(d as Scenario[])).catch(() => {});
      api.getPracticumSessions().then((d: unknown) => setSessions(d as Session[])).catch(() => {});
    }
  }, [user]);

  const [joinCode, setJoinCode] = useState('');
  const [joining, setJoining] = useState(false);

  async function handleStart(scenarioId: string, mode: 'self' | 'video') {
    try {
      const res = mode === 'video'
        ? await api.createVideoSession(scenarioId) as { id: string }
        : await api.createPracticumSession(scenarioId) as { id: string };
      router.push(`/practicum/session/${res.id}`);
    } catch (err) {
      alert(err instanceof Error ? err.message : '세션 생성 실패');
    }
  }

  async function handleJoin() {
    if (joinCode.length < 4) return;
    setJoining(true);
    try {
      const res = await api.joinLiveSession(joinCode) as { id: string };
      router.push(`/practicum/session/${res.id}`);
    } catch (err) {
      alert(err instanceof Error ? err.message : '참여 실패');
    } finally {
      setJoining(false);
    }
  }

  if (loading || !user) return <div className="p-8 text-center">로딩 중...</div>;

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">실습 평가</h1>
          <p className="text-sm text-slate-500">AI 기반 실습 수행 체크리스트 평가</p>
        </div>
        <Link href="/dashboard" className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-100">
          &larr; 대시보드
        </Link>
      </div>

      {/* 실시간 세션 참여 */}
      <section className="mb-8">
        <div className="rounded-xl border border-purple-200 bg-purple-50 p-5">
          <h2 className="mb-2 text-sm font-bold text-purple-800">교수 실시간 세션 참여</h2>
          <p className="mb-3 text-xs text-purple-600">교수님이 공유한 4자리 참여 코드를 입력하세요.</p>
          <div className="flex gap-2">
            <input
              type="text"
              value={joinCode}
              onChange={(e) => setJoinCode(e.target.value.replace(/\D/g, '').slice(0, 4))}
              placeholder="참여 코드 (4자리)"
              maxLength={4}
              className="w-32 rounded-lg border border-purple-300 bg-white px-3 py-2 text-center font-mono text-lg tracking-widest focus:border-purple-500 focus:outline-none"
            />
            <button
              onClick={handleJoin}
              disabled={joining || joinCode.length < 4}
              className="rounded-lg bg-purple-600 px-5 py-2 text-sm font-semibold text-white hover:bg-purple-700 disabled:opacity-40"
            >
              {joining ? '참여 중...' : '참여'}
            </button>
          </div>
        </div>
      </section>

      {/* 시나리오 목록 */}
      <section className="mb-10">
        <h2 className="mb-4 text-lg font-semibold">실습 시나리오</h2>
        {scenarios.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-400">
            등록된 시나리오가 없습니다.
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {scenarios.map((s) => (
              <div key={s.id} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm hover:shadow-md transition">
                <div className="mb-2 flex items-center gap-2">
                  <span className="rounded-full bg-brand-50 px-2.5 py-0.5 text-[11px] font-semibold text-brand-700">
                    {s.category_label}
                  </span>
                  <span className="text-[11px] text-slate-400">{s.department_label}</span>
                </div>
                <h3 className="font-semibold text-slate-900">{s.name}</h3>
                <p className="mt-1 text-xs text-slate-500">
                  {(s.checklist_items as unknown[]).length}개 항목 &middot; {s.total_points}점 만점
                </p>
                <div className="mt-3 space-y-2">
                  <button
                    onClick={async () => {
                      try {
                        const res = await api.createPracticumSession(s.id) as { id: string };
                        router.push(`/practicum/live/${res.id}`);
                      } catch (err) { alert(err instanceof Error ? err.message : '실패'); }
                    }}
                    className="w-full rounded-lg bg-teal-600 py-2 text-sm font-semibold text-white hover:bg-teal-700 transition"
                  >
                    실시간 AI 분석
                  </button>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleStart(s.id, 'self')}
                      className="flex-1 rounded-lg border border-slate-300 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 transition"
                    >
                      자체 평가
                    </button>
                    <button
                      onClick={() => handleStart(s.id, 'video')}
                      className="flex-1 rounded-lg border border-slate-300 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 transition"
                    >
                      영상 평가
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* 내 세션 이력 */}
      <section>
        <h2 className="mb-4 text-lg font-semibold">내 실습 기록</h2>
        {sessions.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-400">
            아직 실습 기록이 없습니다.
          </div>
        ) : (
          <div className="space-y-3">
            {sessions.map((s) => {
              const st = STATUS_LABEL[s.status] || STATUS_LABEL.DRAFT;
              return (
                <Link
                  key={s.id}
                  href={`/practicum/session/${s.id}`}
                  className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4 shadow-sm hover:shadow-md transition"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-slate-900">{s.scenario_name || s.scenario_category_label}</span>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${st.color}`}>{st.label}</span>
                    </div>
                    <div className="mt-1 text-xs text-slate-400">
                      {new Date(s.created_at).toLocaleDateString('ko-KR')}
                    </div>
                  </div>
                  <div className="text-right">
                    {s.total_score !== null && (
                      <div className="text-lg font-bold text-slate-900">{s.total_score}<span className="text-sm text-slate-400">/{s.total_points}</span></div>
                    )}
                    {s.grade && (
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${GRADE_COLOR[s.grade] || ''}`}>
                        {s.grade_label}
                      </span>
                    )}
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </section>
    </main>
  );
}
