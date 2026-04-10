'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { FormEvent, useEffect, useState } from 'react';

interface ClassItem {
  id: string;
  class_name: string;
  department: string;
  year: number;
  semester: number;
  student_count: number;
}

const DEPT_LABEL: Record<string, string> = {
  NURSING: '간호학과',
  PHYSICAL_THERAPY: '물리치료학과',
  DENTAL_HYGIENE: '치위생과',
};

export default function ProfessorClassesPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ class_name: '', year: 2026, semester: 1 });
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!loading && (!user || !['PROFESSOR', 'ADMIN', 'DEVELOPER'].includes(user.role)))
      router.push('/dashboard');
  }, [user, loading, router]);

  useEffect(() => {
    if (user) {
      api.getMyClasses().then((d: unknown) => setClasses(d as ClassItem[])).catch(() => {});
    }
  }, [user]);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setCreating(true);
    try {
      await api.createClass({
        ...form,
        department: user?.department || 'NURSING',
      });
      const updated = (await api.getMyClasses()) as ClassItem[];
      setClasses(updated);
      setShowCreate(false);
      setForm({ class_name: '', year: 2026, semester: 1 });
    } catch {
      /* ignore */
    } finally {
      setCreating(false);
    }
  }

  if (loading || !user) return <div className="p-8 text-center">Loading...</div>;

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">
            내 클래스
            {(user as Record<string, unknown>).professor_role === 'DEPT_HEAD' && (
              <span className="ml-2 rounded-full bg-amber-100 px-3 py-1 text-xs font-bold text-amber-700">학과장</span>
            )}
          </h1>
          <p className="text-sm text-slate-500">
            {user.name} 교수님의 반 관리
            {(user as Record<string, unknown>).professor_role === 'DEPT_HEAD' && ' (학과 전체 클래스 조회 가능)'}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
          >
            + 클래스 생성
          </button>
          <button onClick={() => router.push('/professor/analytics')} className="rounded-lg border border-slate-300 px-4 py-2 text-sm">
            📊 분석
          </button>
          <button onClick={() => router.push('/dashboard')} className="text-sm text-slate-500">
            ← 대시보드
          </button>
        </div>
      </div>

      {/* 클래스 생성 폼 */}
      {showCreate && (
        <form onSubmit={handleCreate} className="mb-6 rounded-xl border border-brand-200 bg-brand-50 p-4">
          <div className="flex gap-3">
            <input
              type="text"
              required
              placeholder="클래스 이름 (예: 간호학과 24학번 1반)"
              value={form.class_name}
              onChange={(e) => setForm((f) => ({ ...f, class_name: e.target.value }))}
              className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
            <input
              type="number"
              value={form.year}
              onChange={(e) => setForm((f) => ({ ...f, year: +e.target.value }))}
              className="w-20 rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
            <select
              value={form.semester}
              onChange={(e) => setForm((f) => ({ ...f, semester: +e.target.value }))}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
              <option value={1}>1학기</option>
              <option value={2}>2학기</option>
            </select>
            <button
              type="submit"
              disabled={creating}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              생성
            </button>
          </div>
        </form>
      )}

      {/* 클래스 목록 */}
      {classes.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center text-slate-400">
          아직 클래스가 없습니다. "클래스 생성"을 눌러 시작하세요.
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {classes.map((cls) => (
            <div
              key={cls.id}
              onClick={() => router.push(`/professor/classes/${cls.id}`)}
              className="cursor-pointer rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition hover:shadow-md"
            >
              <h3 className="text-lg font-semibold">{cls.class_name}</h3>
              <div className="mt-2 flex gap-2 text-xs text-slate-500">
                <span className="rounded bg-slate-100 px-2 py-0.5">
                  {DEPT_LABEL[cls.department] || cls.department}
                </span>
                <span className="rounded bg-slate-100 px-2 py-0.5">
                  {cls.year}년 {cls.semester}학기
                </span>
              </div>
              <div className="mt-3 text-2xl font-bold text-brand-600">
                {cls.student_count}
                <span className="ml-1 text-sm font-normal text-slate-500">명</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
