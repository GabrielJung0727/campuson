'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

interface Stats {
  period: string;
  overall_accuracy: number;
  total_attempts: number;
  total_correct: number;
  total_wrong: number;
  subject_breakdown: Array<{
    subject: string;
    total_attempts: number;
    correct_count: number;
    accuracy: number;
  }>;
  buckets: Array<{
    period_start: string;
    total_attempts: number;
    accuracy: number;
  }>;
  error_type_distribution: Record<string, number>;
}

const ERROR_LABEL: Record<string, string> = {
  CONCEPT_GAP: '개념 부족',
  CONFUSION: '헷갈림',
  CARELESS: '실수',
  APPLICATION_GAP: '응용 부족',
  UNCLASSIFIED: '미분류',
};

export default function ReportPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [stats, setStats] = useState<Stats | null>(null);
  const [period, setPeriod] = useState<'daily' | 'weekly' | 'monthly'>('weekly');
  const [profile, setProfile] = useState<Record<string, unknown> | null>(null);
  const [percentile, setPercentile] = useState<{
    overall_percentile: number;
    overall_accuracy: number;
    total_students: number;
    subject_percentiles: Record<string, { percentile: number; accuracy: number; total: number }>;
  } | null>(null);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  useEffect(() => {
    if (user) {
      api.getMyStats(`period=${period}&days=90`).then((d: unknown) => setStats(d as Stats)).catch(() => {});
      api.getMyProfile().then((d: unknown) => setProfile(d as Record<string, unknown>)).catch(() => {});
      api.getMyPercentile().then((d: unknown) => setPercentile(d as typeof percentile)).catch(() => {});
    }
  }, [user, period]);

  if (loading || !user) return <div className="p-8 text-center">Loading...</div>;

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">학습 리포트</h1>
        <button onClick={() => router.push('/dashboard')} className="text-sm text-slate-500">
          ← 대시보드
        </button>
      </div>

      {/* AI Profile */}
      {profile && (
        <div className="mb-6 rounded-xl border border-purple-200 bg-purple-50 p-6">
          <h2 className="mb-2 font-semibold text-purple-800">AI 학습 프로파일</h2>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <div className="text-xs text-purple-600">학습 수준</div>
              <div className="text-lg font-bold text-purple-900">{profile.level as string}</div>
            </div>
            <div>
              <div className="text-xs text-purple-600">설명 선호</div>
              <div className="font-semibold">{profile.explanation_pref as string}</div>
            </div>
            <div>
              <div className="text-xs text-purple-600">취약 영역</div>
              <div className="font-semibold">
                {(profile.weak_priority as Array<{ subject: string }>)?.slice(0, 2).map((w) => w.subject).join(', ') || '없음'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* v0.2: 백분위 카드 */}
      {percentile && percentile.total_students > 0 && (
        <div className="mb-6 rounded-xl border border-brand-200 bg-gradient-to-r from-brand-50 to-white p-6">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-slate-500">학과 내 나의 순위</div>
              <div className="mt-1 text-4xl font-bold text-brand-700">
                상위 {100 - percentile.overall_percentile}%
              </div>
              <div className="mt-1 text-xs text-slate-400">
                {percentile.total_students}명 중 정답률 {Math.round(percentile.overall_accuracy * 100)}%
              </div>
            </div>
            <div className="text-6xl opacity-20">🏆</div>
          </div>
          {/* 과목별 백분위 */}
          {Object.keys(percentile.subject_percentiles).length > 0 && (
            <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-3">
              {Object.entries(percentile.subject_percentiles).map(([subj, data]) => (
                <div key={subj} className="rounded-lg bg-white p-2 text-center text-xs shadow-sm">
                  <div className="font-medium text-slate-700">{subj}</div>
                  <div className="text-lg font-bold text-brand-600">상위 {100 - data.percentile}%</div>
                  <div className="text-slate-400">{Math.round(data.accuracy * 100)}% ({data.total}명)</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Summary Cards */}
      {stats && (
        <>
          <div className="mb-6 grid grid-cols-4 gap-4">
            <div className="rounded-xl border border-slate-200 bg-white p-4 text-center">
              <div className="text-2xl font-bold text-brand-600">
                {Math.round(stats.overall_accuracy * 100)}%
              </div>
              <div className="text-xs text-slate-500">전체 정답률</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 text-center">
              <div className="text-2xl font-bold">{stats.total_attempts}</div>
              <div className="text-xs text-slate-500">총 시도</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 text-center">
              <div className="text-2xl font-bold text-emerald-600">{stats.total_correct}</div>
              <div className="text-xs text-slate-500">정답</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 text-center">
              <div className="text-2xl font-bold text-red-600">{stats.total_wrong}</div>
              <div className="text-xs text-slate-500">오답</div>
            </div>
          </div>

          {/* Period selector */}
          <div className="mb-4 flex gap-2">
            {(['daily', 'weekly', 'monthly'] as const).map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`rounded-lg px-4 py-2 text-sm ${
                  period === p ? 'bg-brand-600 font-semibold text-white' : 'bg-slate-100 text-slate-600'
                }`}
              >
                {p === 'daily' ? '일간' : p === 'weekly' ? '주간' : '월간'}
              </button>
            ))}
          </div>

          {/* Time series (text-based for now) */}
          {stats.buckets.length > 0 && (
            <div className="mb-6 rounded-xl border border-slate-200 bg-white p-6">
              <h3 className="mb-4 font-semibold">시계열 추이</h3>
              <div className="space-y-2">
                {stats.buckets.slice(-10).map((b) => (
                  <div key={b.period_start} className="flex items-center gap-3 text-sm">
                    <span className="w-24 font-mono text-xs text-slate-500">{b.period_start}</span>
                    <div className="flex-1">
                      <div className="h-3 w-full rounded-full bg-slate-100">
                        <div
                          className="h-3 rounded-full bg-brand-500"
                          style={{ width: `${Math.round(b.accuracy * 100)}%` }}
                        />
                      </div>
                    </div>
                    <span className="w-12 text-right font-mono">{Math.round(b.accuracy * 100)}%</span>
                    <span className="w-12 text-right text-xs text-slate-400">{b.total_attempts}회</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Subject breakdown */}
          <div className="mb-6 rounded-xl border border-slate-200 bg-white p-6">
            <h3 className="mb-4 font-semibold">과목별 정답률</h3>
            <div className="space-y-3">
              {stats.subject_breakdown.map((s) => (
                <div key={s.subject}>
                  <div className="mb-1 flex justify-between text-sm">
                    <span>{s.subject}</span>
                    <span className="font-mono">{Math.round(s.accuracy * 100)}% ({s.total_attempts}회)</span>
                  </div>
                  <div className="h-2.5 w-full rounded-full bg-slate-100">
                    <div
                      className={`h-2.5 rounded-full ${
                        s.accuracy >= 0.7 ? 'bg-emerald-500' : s.accuracy >= 0.5 ? 'bg-amber-500' : 'bg-red-500'
                      }`}
                      style={{ width: `${Math.round(s.accuracy * 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Error distribution */}
          {Object.keys(stats.error_type_distribution).length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-6">
              <h3 className="mb-4 font-semibold">오답 유형 분포</h3>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                {Object.entries(stats.error_type_distribution).map(([type, count]) => (
                  <div key={type} className="rounded-lg bg-red-50 p-3 text-center">
                    <div className="text-lg font-bold text-red-700">{count}</div>
                    <div className="text-xs text-red-600">{ERROR_LABEL[type] || type}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {!stats && <p className="text-center text-slate-400">학습 이력이 없습니다. 문제를 풀어보세요!</p>}
    </main>
  );
}
