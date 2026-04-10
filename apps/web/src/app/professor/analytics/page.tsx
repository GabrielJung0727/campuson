'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api, apiFetch } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

interface DeptOverview {
  overall_accuracy: number;
  total_attempts: number;
  total_correct: number;
  total_wrong: number;
  subject_breakdown: Array<{
    subject: string;
    total_attempts: number;
    correct_count: number;
    accuracy: number;
    wrong_count: number;
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

const ERROR_COLOR: Record<string, string> = {
  CONCEPT_GAP: 'bg-red-500',
  CONFUSION: 'bg-amber-500',
  CARELESS: 'bg-blue-500',
  APPLICATION_GAP: 'bg-purple-500',
  UNCLASSIFIED: 'bg-slate-400',
};

export default function ProfessorAnalyticsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [stats, setStats] = useState<DeptOverview | null>(null);

  useEffect(() => {
    if (!loading && (!user || !['PROFESSOR', 'ADMIN', 'DEVELOPER'].includes(user.role)))
      router.push('/dashboard');
  }, [user, loading, router]);

  useEffect(() => {
    if (user) {
      // 학과 전체 통계 (학습 이력 기반)
      apiFetch(`/history/stats?period=monthly&days=365`)
        .then((d: unknown) => setStats(d as DeptOverview))
        .catch(() => {});
    }
  }, [user]);

  if (loading || !user) return <div className="p-8 text-center">Loading...</div>;

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">학과 분석 대시보드</h1>
          <p className="text-sm text-slate-500">빅데이터 시각화</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => router.push('/professor/classes')} className="rounded-lg border border-slate-300 px-4 py-2 text-sm">
            📚 클래스
          </button>
          <button onClick={() => router.push('/dashboard')} className="text-sm text-slate-500">
            ← 대시보드
          </button>
        </div>
      </div>

      {!stats ? (
        <div className="rounded-xl border bg-white p-12 text-center text-slate-400">
          학습 데이터가 아직 부족합니다.
        </div>
      ) : (
        <>
          {/* Summary */}
          <div className="mb-6 grid grid-cols-4 gap-4">
            <div className="rounded-xl border bg-white p-4 text-center">
              <div className="text-2xl font-bold text-brand-600">
                {Math.round(stats.overall_accuracy * 100)}%
              </div>
              <div className="text-xs text-slate-500">전체 정답률</div>
            </div>
            <div className="rounded-xl border bg-white p-4 text-center">
              <div className="text-2xl font-bold">{stats.total_attempts}</div>
              <div className="text-xs text-slate-500">총 풀이</div>
            </div>
            <div className="rounded-xl border bg-white p-4 text-center">
              <div className="text-2xl font-bold text-emerald-600">{stats.total_correct}</div>
              <div className="text-xs text-slate-500">정답</div>
            </div>
            <div className="rounded-xl border bg-white p-4 text-center">
              <div className="text-2xl font-bold text-red-600">{stats.total_wrong}</div>
              <div className="text-xs text-slate-500">오답</div>
            </div>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            {/* 과목별 정답률 */}
            <div className="rounded-xl border bg-white p-6">
              <h3 className="mb-4 font-semibold">과목별 정답률</h3>
              <div className="space-y-3">
                {stats.subject_breakdown
                  .sort((a, b) => a.accuracy - b.accuracy)
                  .map((s) => (
                    <div key={s.subject}>
                      <div className="mb-1 flex justify-between text-sm">
                        <span>{s.subject}</span>
                        <span className="font-mono">
                          {Math.round(s.accuracy * 100)}%
                          <span className="ml-1 text-xs text-slate-400">({s.total_attempts}회)</span>
                        </span>
                      </div>
                      <div className="h-3 w-full rounded-full bg-slate-100">
                        <div
                          className={`h-3 rounded-full ${
                            s.accuracy >= 0.7 ? 'bg-emerald-500' : s.accuracy >= 0.5 ? 'bg-amber-500' : 'bg-red-500'
                          }`}
                          style={{ width: `${Math.round(s.accuracy * 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
              </div>
              {stats.subject_breakdown.length > 0 && (
                <div className="mt-4 rounded-lg bg-red-50 p-3 text-xs text-red-700">
                  ⚠️ 가장 어려운 과목:{' '}
                  <strong>
                    {stats.subject_breakdown.sort((a, b) => a.accuracy - b.accuracy)[0]?.subject}
                  </strong>{' '}
                  ({Math.round(stats.subject_breakdown.sort((a, b) => a.accuracy - b.accuracy)[0]?.accuracy * 100)}%)
                </div>
              )}
            </div>

            {/* 오답 유형 분포 */}
            <div className="rounded-xl border bg-white p-6">
              <h3 className="mb-4 font-semibold">오답 유형 분포</h3>
              {Object.keys(stats.error_type_distribution).length === 0 ? (
                <p className="text-sm text-slate-400">오답 데이터가 없습니다.</p>
              ) : (
                <>
                  {/* Horizontal stacked bar */}
                  <div className="mb-4 flex h-8 overflow-hidden rounded-full">
                    {(() => {
                      const total = Object.values(stats.error_type_distribution).reduce((a, b) => a + b, 0);
                      return Object.entries(stats.error_type_distribution).map(([type, count]) => (
                        <div
                          key={type}
                          className={`${ERROR_COLOR[type] || 'bg-slate-400'} transition-all`}
                          style={{ width: `${(count / total) * 100}%` }}
                          title={`${ERROR_LABEL[type] || type}: ${count}건 (${Math.round((count / total) * 100)}%)`}
                        />
                      ));
                    })()}
                  </div>
                  {/* Legend */}
                  <div className="grid grid-cols-2 gap-2">
                    {Object.entries(stats.error_type_distribution).map(([type, count]) => {
                      const total = Object.values(stats.error_type_distribution).reduce((a, b) => a + b, 0);
                      return (
                        <div key={type} className="flex items-center gap-2 text-sm">
                          <div className={`h-3 w-3 rounded-full ${ERROR_COLOR[type] || 'bg-slate-400'}`} />
                          <span>{ERROR_LABEL[type] || type}</span>
                          <span className="ml-auto font-mono text-xs text-slate-500">
                            {count}건 ({Math.round((count / total) * 100)}%)
                          </span>
                        </div>
                      );
                    })}
                  </div>
                  {/* Insight */}
                  {(() => {
                    const entries = Object.entries(stats.error_type_distribution);
                    const top = entries.sort((a, b) => b[1] - a[1])[0];
                    if (!top) return null;
                    return (
                      <div className="mt-4 rounded-lg bg-amber-50 p-3 text-xs text-amber-700">
                        💡 가장 많은 오답 유형: <strong>{ERROR_LABEL[top[0]] || top[0]}</strong> —
                        {top[0] === 'CONCEPT_GAP' && ' 기초 개념 복습 자료를 강화하세요.'}
                        {top[0] === 'CONFUSION' && ' 유사 개념 비교 자료를 제공하세요.'}
                        {top[0] === 'CARELESS' && ' 문제를 꼼꼼히 읽는 습관을 교육하세요.'}
                        {top[0] === 'APPLICATION_GAP' && ' 임상 사례 문제를 추가로 연습시키세요.'}
                      </div>
                    );
                  })()}
                </>
              )}
            </div>
          </div>
        </>
      )}
    </main>
  );
}
