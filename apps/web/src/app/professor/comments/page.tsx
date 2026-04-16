'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

interface ClassItem { id: string; class_name: string }
interface StudentItem {
  id: string;
  name: string;
  email: string;
  student_no: string | null;
}
interface CommentItem {
  id: string;
  professor_id: string;
  student_id: string;
  target_type: string;
  target_id: string | null;
  content: string;
  is_private: boolean;
  created_at: string;
}

const TARGET_LABELS: Record<string, string> = {
  learning_history: '학습 이력',
  assignment_submission: '과제 제출',
  practicum_session: '실습 세션',
  general: '일반',
};

export default function ProfessorCommentsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [selectedClassId, setSelectedClassId] = useState('');
  const [students, setStudents] = useState<StudentItem[]>([]);
  const [selectedStudentId, setSelectedStudentId] = useState('');
  const [comments, setComments] = useState<CommentItem[]>([]);
  const [form, setForm] = useState({ content: '', target_type: 'general', is_private: false });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && (!user || !['PROFESSOR', 'ADMIN', 'DEVELOPER'].includes(user.role))) {
      router.push('/dashboard');
    }
  }, [user, loading, router]);

  useEffect(() => {
    api.getMyClasses().then((d: any) => setClasses(d || [])).catch(() => {});
  }, []);

  useEffect(() => {
    if (selectedClassId) {
      api.getClassDetail(selectedClassId)
        .then((d: any) => setStudents(d.students || []))
        .catch(() => {});
    }
  }, [selectedClassId]);

  useEffect(() => {
    if (selectedStudentId) {
      api.getStudentComments(selectedStudentId, true)
        .then((d: any) => setComments(d || []))
        .catch(() => {});
    }
  }, [selectedStudentId]);

  const handleSubmit = async () => {
    if (!form.content.trim() || !selectedStudentId) return;
    setBusy(true);
    try {
      await api.createComment({
        student_id: selectedStudentId,
        target_type: form.target_type,
        content: form.content,
        is_private: form.is_private,
      });
      setForm({ content: '', target_type: 'general', is_private: false });
      const d: any = await api.getStudentComments(selectedStudentId, true);
      setComments(d || []);
    } finally {
      setBusy(false);
    }
  };

  if (loading || !user) return null;

  return (
    <main className="mx-auto max-w-4xl p-6">
      <div className="mb-6">
        <Link href="/dashboard" className="text-sm text-blue-600 hover:underline">&larr; 대시보드</Link>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">학생 피드백 코멘트</h1>
        <p className="text-sm text-gray-500">학생별 개인 피드백 · 비공개 메모</p>
      </div>

      {/* Selectors */}
      <div className="mb-6 grid gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">클래스 선택</label>
          <select
            className="w-full rounded-lg border px-3 py-2 text-sm"
            value={selectedClassId}
            onChange={(e) => { setSelectedClassId(e.target.value); setSelectedStudentId(''); setComments([]); }}
          >
            <option value="">-- 선택 --</option>
            {classes.map((c) => (
              <option key={c.id} value={c.id}>{c.class_name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">학생 선택</label>
          <select
            className="w-full rounded-lg border px-3 py-2 text-sm"
            value={selectedStudentId}
            onChange={(e) => setSelectedStudentId(e.target.value)}
            disabled={!selectedClassId}
          >
            <option value="">-- 선택 --</option>
            {students.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} {s.student_no && `(${s.student_no})`}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Comment Form */}
      {selectedStudentId && (
        <div className="mb-6 rounded-xl border bg-white p-5 shadow-sm">
          <h3 className="mb-3 font-semibold text-gray-800">새 코멘트 작성</h3>
          <textarea
            className="w-full rounded-lg border px-3 py-2 text-sm"
            rows={3}
            placeholder="피드백 내용을 입력하세요..."
            value={form.content}
            onChange={(e) => setForm({ ...form, content: e.target.value })}
          />
          <div className="mt-3 flex items-center gap-4">
            <select
              className="rounded-lg border px-3 py-2 text-sm"
              value={form.target_type}
              onChange={(e) => setForm({ ...form, target_type: e.target.value })}
            >
              {Object.entries(TARGET_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            <label className="flex items-center gap-2 text-sm text-gray-600">
              <input
                type="checkbox"
                checked={form.is_private}
                onChange={(e) => setForm({ ...form, is_private: e.target.checked })}
              />
              비공개 (학생 미공개)
            </label>
            <div className="flex-1" />
            <button
              onClick={handleSubmit}
              disabled={busy || !form.content.trim()}
              className="rounded-lg bg-indigo-600 px-5 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {busy ? '저장 중...' : '코멘트 저장'}
            </button>
          </div>
        </div>
      )}

      {/* Comment List */}
      {selectedStudentId && (
        <div>
          <h3 className="mb-3 font-semibold text-gray-800">코멘트 이력 ({comments.length}건)</h3>
          {comments.length === 0 && (
            <p className="py-8 text-center text-gray-400">아직 코멘트가 없습니다.</p>
          )}
          <div className="space-y-3">
            {comments.map((c) => (
              <div
                key={c.id}
                className={`rounded-xl border p-4 shadow-sm ${
                  c.is_private ? 'border-yellow-200 bg-yellow-50' : 'bg-white'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                      {TARGET_LABELS[c.target_type] || c.target_type}
                    </span>
                    {c.is_private && (
                      <span className="rounded bg-yellow-200 px-2 py-0.5 text-xs text-yellow-800">비공개</span>
                    )}
                  </div>
                  <span className="text-xs text-gray-400">
                    {new Date(c.created_at).toLocaleDateString('ko-KR')}
                  </span>
                </div>
                <p className="mt-2 text-sm text-gray-800 whitespace-pre-wrap">{c.content}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </main>
  );
}
