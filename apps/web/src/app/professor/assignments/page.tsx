'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

interface AssignmentItem {
  id: string;
  title: string;
  status: string;
  total_questions: number;
  due_date: string | null;
  submission_count: number;
  created_at: string;
}

const STATUS_LABEL: Record<string, { text: string; color: string }> = {
  DRAFT: { text: '초안', color: 'bg-slate-100 text-slate-600' },
  PUBLISHED: { text: '진행중', color: 'bg-emerald-100 text-emerald-700' },
  CLOSED: { text: '마감', color: 'bg-red-100 text-red-600' },
};

export default function AssignmentsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [assignments, setAssignments] = useState<AssignmentItem[]>([]);

  useEffect(() => {
    if (!loading && (!user || !['PROFESSOR', 'ADMIN', 'DEVELOPER'].includes(user.role)))
      router.push('/dashboard');
  }, [user, loading, router]);

  useEffect(() => {
    if (user) api.getAssignments().then((d: unknown) => setAssignments(d as AssignmentItem[])).catch(() => {});
  }, [user]);

  if (loading) return <div className="p-8 text-center">Loading...</div>;

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">과제 관리</h1>
        <div className="flex gap-2">
          <button onClick={() => router.push('/professor/generate')} className="rounded-lg bg-purple-600 px-4 py-2 text-sm font-semibold text-white hover:bg-purple-700">
            🤖 AI 문제 생성
          </button>
          <button onClick={() => router.push('/account')} className="text-sm text-slate-500">설정</button>
          <button onClick={() => router.push('/dashboard')} className="text-sm text-slate-500">&larr; 대시보드</button>
        </div>
      </div>

      {assignments.length === 0 ? (
        <div className="rounded-xl border bg-white p-12 text-center text-slate-400">
          아직 과제가 없습니다. Swagger UI에서 과제를 출제하세요.
        </div>
      ) : (
        <div className="space-y-3">
          {assignments.map((a) => {
            const st = STATUS_LABEL[a.status] || STATUS_LABEL.DRAFT;
            return (
              <div key={a.id} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-lg font-semibold">{a.title}</h3>
                    <div className="mt-1 flex gap-2 text-xs">
                      <span className={`rounded px-2 py-0.5 ${st.color}`}>{st.text}</span>
                      <span className="text-slate-400">{a.total_questions}문항</span>
                      {a.due_date && <span className="text-slate-400">마감: {new Date(a.due_date).toLocaleDateString()}</span>}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-bold text-brand-600">{a.submission_count}</div>
                    <div className="text-xs text-slate-500">제출</div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </main>
  );
}
