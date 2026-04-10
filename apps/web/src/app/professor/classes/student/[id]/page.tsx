'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import { useParams, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

export default function StudentDetailPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const params = useParams();
  const studentId = params.id as string;
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    if (!loading && (!user || !['PROFESSOR', 'ADMIN', 'DEVELOPER'].includes(user.role)))
      router.push('/dashboard');
  }, [user, loading, router]);

  useEffect(() => {
    if (user && studentId) {
      api.getStudentDetail(studentId).then((d: unknown) => setDetail(d as Record<string, unknown>)).catch(() => {});
    }
  }, [user, studentId]);

  if (loading || !detail) return <div className="p-8 text-center">Loading...</div>;

  const student = detail.student as Record<string, string>;
  const diagnostic = detail.diagnostic as Record<string, unknown> | undefined;
  const aiProfile = detail.ai_profile as Record<string, unknown> | undefined;
  const percentile = detail.percentile as {
    overall_percentile: number;
    overall_accuracy: number;
    total_students: number;
    subject_percentiles: Record<string, { percentile: number; accuracy: number }>;
  } | undefined;

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{student.name} 학생</h1>
          <p className="text-sm text-slate-500">{student.email} | {student.student_no || '-'}</p>
        </div>
        <button onClick={() => router.back()} className="text-sm text-slate-500">← 뒤로</button>
      </div>

      {/* 백분위 */}
      {percentile && percentile.total_students > 0 && (
        <div className="mb-6 rounded-xl border border-brand-200 bg-brand-50 p-6">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-slate-500">학과 내 순위</div>
              <div className="text-4xl font-bold text-brand-700">상위 {100 - percentile.overall_percentile}%</div>
              <div className="text-xs text-slate-400">
                {percentile.total_students}명 중 정답률 {Math.round(percentile.overall_accuracy * 100)}%
              </div>
            </div>
            <div className="text-5xl opacity-20">🏅</div>
          </div>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {/* 진단 결과 */}
        {diagnostic && (
          <div className="rounded-xl border border-slate-200 bg-white p-6">
            <h3 className="mb-3 font-semibold">진단 테스트</h3>
            <div className="mb-2 text-3xl font-bold text-emerald-600">
              {Math.round(((diagnostic.total_score as number) || 0) * 100)}점
            </div>
            <div className="text-sm text-slate-500">
              수준: <span className="font-semibold">{diagnostic.level as string}</span>
            </div>
            {diagnostic.section_scores && (
              <div className="mt-3 space-y-1.5">
                {Object.entries(diagnostic.section_scores as Record<string, number>).map(([subj, score]) => (
                  <div key={subj} className="text-xs">
                    <div className="flex justify-between">
                      <span>{subj}</span>
                      <span className="font-mono">{Math.round(score * 100)}%</span>
                    </div>
                    <div className="h-1.5 w-full rounded bg-slate-100">
                      <div
                        className={`h-1.5 rounded ${score >= 0.7 ? 'bg-emerald-500' : score >= 0.5 ? 'bg-amber-500' : 'bg-red-500'}`}
                        style={{ width: `${Math.round(score * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* AI 프로파일 */}
        {aiProfile && (
          <div className="rounded-xl border border-purple-200 bg-purple-50 p-6">
            <h3 className="mb-3 font-semibold text-purple-800">AI 프로파일</h3>
            <div className="space-y-2 text-sm">
              <div><span className="text-purple-600">수준:</span> <strong>{aiProfile.level as string}</strong></div>
              <div><span className="text-purple-600">설명 선호:</span> {aiProfile.explanation_pref as string}</div>
              <div>
                <span className="text-purple-600">취약 영역:</span>
                <div className="mt-1 flex flex-wrap gap-1">
                  {((aiProfile.weak_priority as Array<{ subject: string }>) || []).slice(0, 3).map((w, i) => (
                    <span key={i} className="rounded bg-purple-100 px-2 py-0.5 text-xs text-purple-700">
                      {w.subject}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 과목별 백분위 */}
      {percentile && Object.keys(percentile.subject_percentiles).length > 0 && (
        <div className="mt-4 rounded-xl border border-slate-200 bg-white p-6">
          <h3 className="mb-3 font-semibold">과목별 순위</h3>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
            {Object.entries(percentile.subject_percentiles).map(([subj, data]) => (
              <div key={subj} className="rounded-lg bg-slate-50 p-3 text-center">
                <div className="text-xs text-slate-500">{subj}</div>
                <div className="text-lg font-bold text-brand-600">상위 {100 - data.percentile}%</div>
                <div className="text-xs text-slate-400">{Math.round(data.accuracy * 100)}%</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {!diagnostic && !aiProfile && (
        <div className="mt-4 rounded-xl border bg-white p-8 text-center text-slate-400">
          이 학생은 아직 진단 테스트를 응시하지 않았습니다.
        </div>
      )}
    </main>
  );
}
