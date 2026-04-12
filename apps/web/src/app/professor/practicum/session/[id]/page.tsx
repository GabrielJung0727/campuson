'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

interface ChecklistItem { id: string; label: string; points: number; is_critical: boolean }
interface SessionData {
  id: string; status: string; total_score: number | null; grade: string | null; grade_label: string | null;
  total_points: number; scenario_name: string; scenario_category_label: string;
  checklist_items: ChecklistItem[]; checklist_results: { item_id: string; status: string; points_earned: number }[] | null;
  ai_feedback: { good: string[]; needs_improvement: string[]; suggestions: string[] } | null;
  professor_comment: string | null; student_name: string; student_email: string; created_at: string;
}

const STATUS_LABEL: Record<string, string> = { success: '성공', partial: '부분', fail: '실패', danger: '위험' };
const STATUS_COLOR: Record<string, string> = { success: 'text-emerald-600', partial: 'text-amber-600', fail: 'text-red-600', danger: 'text-rose-700' };
const GRADE_STYLE: Record<string, string> = { EXCELLENT: 'from-emerald-500 to-teal-500', GOOD: 'from-blue-500 to-cyan-500', NEEDS_IMPROVEMENT: 'from-amber-500 to-orange-500', FAIL: 'from-red-500 to-rose-500' };
const GRADE_OPTIONS = [
  { value: '', label: '변경 안 함' },
  { value: 'EXCELLENT', label: '우수 (Excellent)' },
  { value: 'GOOD', label: '양호 (Good)' },
  { value: 'NEEDS_IMPROVEMENT', label: '보완 필요' },
  { value: 'FAIL', label: '불합격 (Fail)' },
];

export default function ProfessorSessionReviewPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const { id: sessionId } = useParams<{ id: string }>();
  const [session, setSession] = useState<SessionData | null>(null);
  const [comment, setComment] = useState('');
  const [gradeOverride, setGradeOverride] = useState('');
  const [reviewing, setReviewing] = useState(false);

  useEffect(() => {
    if (!loading && (!user || !['PROFESSOR', 'ADMIN', 'DEVELOPER'].includes(user.role))) router.push('/dashboard');
  }, [user, loading, router]);

  useEffect(() => {
    if (user && sessionId) {
      api.getPracticumSession(sessionId).then((d: unknown) => {
        const s = d as SessionData;
        setSession(s);
        if (s.professor_comment) setComment(s.professor_comment);
      }).catch(() => router.push('/professor/practicum'));
    }
  }, [user, sessionId, router]);

  async function handleReview() {
    setReviewing(true);
    try {
      const body: Record<string, unknown> = { professor_comment: comment };
      if (gradeOverride) body.grade_override = gradeOverride;
      const res = await api.reviewPracticumSession(sessionId, body) as SessionData;
      setSession(res);
    } catch (err) {
      alert(err instanceof Error ? err.message : '리뷰 실패');
    } finally {
      setReviewing(false);
    }
  }

  if (loading || !user || !session) return <div className="p-8 text-center">로딩 중...</div>;

  const resultMap = new Map((session.checklist_results || []).map((r) => [r.item_id, r]));

  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <span className="rounded-full bg-brand-50 px-2.5 py-0.5 text-[11px] font-semibold text-brand-700">
            {session.scenario_category_label}
          </span>
          <h1 className="mt-1 text-2xl font-bold">{session.scenario_name}</h1>
          <p className="text-sm text-slate-500">{session.student_name} ({session.student_email})</p>
        </div>
        <Link href="/professor/practicum" className="text-sm text-slate-500">&larr; 목록</Link>
      </div>

      {/* Score */}
      {session.total_score !== null && (
        <div className={`mb-6 rounded-2xl bg-gradient-to-r ${GRADE_STYLE[session.grade || 'FAIL']} p-6 text-white`}>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm opacity-80">총점</div>
              <div className="text-4xl font-extrabold">{session.total_score}<span className="text-lg opacity-70">/{session.total_points}</span></div>
            </div>
            <div className="text-right">
              <div className="text-sm opacity-80">등급</div>
              <div className="text-3xl font-extrabold">{session.grade_label}</div>
            </div>
          </div>
        </div>
      )}

      {/* Checklist Results */}
      <section className="mb-6">
        <h2 className="mb-3 text-lg font-semibold">체크리스트 결과</h2>
        <div className="space-y-2">
          {session.checklist_items.map((item) => {
            const r = resultMap.get(item.id);
            return (
              <div key={item.id} className={`flex items-center justify-between rounded-xl border p-3 ${item.is_critical ? 'border-red-200 bg-red-50/30' : 'border-slate-200 bg-white'}`}>
                <div className="flex items-center gap-2">
                  <span className="text-sm">{item.label}</span>
                  {item.is_critical && <span className="rounded bg-red-100 px-1 py-0.5 text-[9px] font-bold text-red-600">필수</span>}
                </div>
                {r ? (
                  <span className={`text-sm font-semibold ${STATUS_COLOR[r.status] || ''}`}>
                    {STATUS_LABEL[r.status]} ({r.points_earned}/{item.points})
                  </span>
                ) : (
                  <span className="text-xs text-slate-400">미평가</span>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* AI Feedback */}
      {session.ai_feedback && (
        <section className="mb-6 space-y-3">
          <h2 className="text-lg font-semibold">AI 피드백</h2>
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <h3 className="mb-2 text-sm font-bold text-emerald-700">잘한 점</h3>
            {session.ai_feedback.good.map((t, i) => <p key={i} className="text-sm text-emerald-800">+ {t}</p>)}
          </div>
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
            <h3 className="mb-2 text-sm font-bold text-amber-700">부족한 점</h3>
            {session.ai_feedback.needs_improvement.map((t, i) => <p key={i} className="text-sm text-amber-800">- {t}</p>)}
          </div>
          <div className="rounded-xl border border-blue-200 bg-blue-50 p-4">
            <h3 className="mb-2 text-sm font-bold text-blue-700">개선 방법</h3>
            {session.ai_feedback.suggestions.map((t, i) => <p key={i} className="text-sm text-blue-800">&rarr; {t}</p>)}
          </div>
        </section>
      )}

      {/* Review Form */}
      <section className="rounded-xl border border-purple-200 bg-purple-50 p-6">
        <h2 className="mb-4 text-lg font-semibold text-purple-800">교수 리뷰</h2>
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          rows={4}
          placeholder="학생에게 전달할 코멘트를 작성하세요..."
          className="w-full rounded-lg border border-purple-300 bg-white px-3 py-2.5 text-sm focus:border-purple-500 focus:outline-none resize-none"
        />
        <div className="mt-3 flex items-center gap-3">
          <select value={gradeOverride} onChange={(e) => setGradeOverride(e.target.value)} className="rounded-lg border border-purple-300 bg-white px-3 py-2 text-sm">
            {GRADE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <button
            onClick={handleReview}
            disabled={reviewing}
            className="rounded-lg bg-purple-600 px-6 py-2 text-sm font-semibold text-white hover:bg-purple-700 disabled:opacity-50"
          >
            {reviewing ? '저장 중...' : session.status === 'REVIEWED' ? '리뷰 수정' : '리뷰 완료'}
          </button>
        </div>
      </section>
    </main>
  );
}
