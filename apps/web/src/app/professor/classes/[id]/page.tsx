'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import { useParams, useRouter } from 'next/navigation';
import { FormEvent, useEffect, useState } from 'react';

interface Student {
  id: string;
  name: string;
  email: string;
  student_no: string | null;
  department: string;
  status: string;
  joined_at: string;
}

interface ClassDetail {
  id: string;
  class_name: string;
  department: string;
  year: number;
  semester: number;
  students: Student[];
}

interface ClassStats {
  class_name: string;
  student_count: number;
  active_students: number;
  avg_accuracy: number;
  student_stats: Array<{
    user_id: string;
    total_attempts: number;
    correct_count: number;
    accuracy: number;
  }>;
}

export default function ClassDetailPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const params = useParams();
  const classId = params.id as string;

  const [detail, setDetail] = useState<ClassDetail | null>(null);
  const [stats, setStats] = useState<ClassStats | null>(null);
  const [addEmail, setAddEmail] = useState('');
  const [adding, setAdding] = useState(false);
  const [tab, setTab] = useState<'students' | 'stats'>('students');

  useEffect(() => {
    if (!loading && (!user || !['PROFESSOR', 'ADMIN', 'DEVELOPER'].includes(user.role)))
      router.push('/dashboard');
  }, [user, loading, router]);

  function refresh() {
    api.getClassDetail(classId).then((d: unknown) => setDetail(d as ClassDetail)).catch(() => {});
    api.getClassStats(classId).then((d: unknown) => setStats(d as ClassStats)).catch(() => {});
  }

  useEffect(() => {
    if (user && classId) refresh();
  }, [user, classId]);

  async function handleAddStudent(e: FormEvent) {
    e.preventDefault();
    setAdding(true);
    try {
      await api.addStudentToClass(classId, { email: addEmail });
      setAddEmail('');
      refresh();
    } catch {
      alert('학생을 찾을 수 없거나 이미 추가되어 있습니다.');
    } finally {
      setAdding(false);
    }
  }

  async function handleRemove(studentId: string) {
    if (!confirm('이 학생을 클래스에서 제거하시겠습니까?')) return;
    await api.removeStudentFromClass(classId, studentId);
    refresh();
  }

  if (loading || !detail) return <div className="p-8 text-center">Loading...</div>;

  // stats에서 학생별 정답률 매핑
  const accMap: Record<string, number> = {};
  stats?.student_stats.forEach((s) => { accMap[s.user_id] = s.accuracy; });

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{detail.class_name}</h1>
          <p className="text-sm text-slate-500">
            {detail.students.length}명 | 평균 정답률 {stats ? Math.round(stats.avg_accuracy * 100) : '-'}%
          </p>
        </div>
        <button onClick={() => router.push('/professor/classes')} className="text-sm text-slate-500">
          ← 클래스 목록
        </button>
      </div>

      {/* 학생 추가 */}
      <form onSubmit={handleAddStudent} className="mb-6 flex gap-2">
        <input
          type="email"
          placeholder="학생 이메일로 추가..."
          value={addEmail}
          onChange={(e) => setAddEmail(e.target.value)}
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
          required
        />
        <button
          type="submit"
          disabled={adding}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          추가
        </button>
      </form>

      {/* 탭 */}
      <div className="mb-4 flex gap-2 border-b border-slate-200 pb-2">
        {(['students', 'stats'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm ${
              tab === t ? 'border-b-2 border-brand-600 font-semibold text-brand-600' : 'text-slate-500'
            }`}
          >
            {t === 'students' ? `학생 (${detail.students.length})` : '통계'}
          </button>
        ))}
      </div>

      {/* 학생 목록 */}
      {tab === 'students' && (
        <div className="space-y-2">
          {detail.students.length === 0 ? (
            <div className="rounded-xl border bg-white p-8 text-center text-slate-400">
              아직 학생이 없습니다. 위에서 이메일로 추가하세요.
            </div>
          ) : (
            detail.students.map((s) => (
              <div
                key={s.id}
                className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4 hover:bg-slate-50"
              >
                <div
                  className="flex-1 cursor-pointer"
                  onClick={() => router.push(`/professor/classes/student/${s.id}`)}
                >
                  <div className="font-medium">{s.name}</div>
                  <div className="text-xs text-slate-500">
                    {s.email} | {s.student_no || '-'}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {accMap[s.id] !== undefined && (
                    <span className={`rounded-full px-3 py-1 text-xs font-bold ${
                      accMap[s.id] >= 0.7 ? 'bg-emerald-100 text-emerald-700' :
                      accMap[s.id] >= 0.5 ? 'bg-amber-100 text-amber-700' :
                      'bg-red-100 text-red-700'
                    }`}>
                      {Math.round(accMap[s.id] * 100)}%
                    </span>
                  )}
                  <button
                    onClick={() => handleRemove(s.id)}
                    className="text-xs text-red-500 hover:underline"
                  >
                    제거
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* 통계 */}
      {tab === 'stats' && stats && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <div className="rounded-xl border bg-white p-4 text-center">
              <div className="text-2xl font-bold">{stats.student_count}</div>
              <div className="text-xs text-slate-500">전체 학생</div>
            </div>
            <div className="rounded-xl border bg-white p-4 text-center">
              <div className="text-2xl font-bold text-brand-600">{stats.active_students}</div>
              <div className="text-xs text-slate-500">학습 활동 중</div>
            </div>
            <div className="rounded-xl border bg-white p-4 text-center">
              <div className="text-2xl font-bold text-emerald-600">{Math.round(stats.avg_accuracy * 100)}%</div>
              <div className="text-xs text-slate-500">평균 정답률</div>
            </div>
          </div>

          {/* 학생별 정답률 바 차트 */}
          <div className="rounded-xl border bg-white p-6">
            <h3 className="mb-4 font-semibold">학생별 정답률</h3>
            <div className="space-y-2">
              {stats.student_stats
                .sort((a, b) => b.accuracy - a.accuracy)
                .map((s) => {
                  const student = detail.students.find((st) => st.id === s.user_id);
                  return (
                    <div key={s.user_id} className="flex items-center gap-3 text-sm">
                      <span className="w-24 truncate">{student?.name || '?'}</span>
                      <div className="flex-1">
                        <div className="h-4 w-full rounded bg-slate-100">
                          <div
                            className={`h-4 rounded ${
                              s.accuracy >= 0.7 ? 'bg-emerald-500' : s.accuracy >= 0.5 ? 'bg-amber-500' : 'bg-red-500'
                            }`}
                            style={{ width: `${Math.round(s.accuracy * 100)}%` }}
                          />
                        </div>
                      </div>
                      <span className="w-12 text-right font-mono">{Math.round(s.accuracy * 100)}%</span>
                      <span className="w-16 text-right text-xs text-slate-400">{s.total_attempts}회</span>
                    </div>
                  );
                })}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
