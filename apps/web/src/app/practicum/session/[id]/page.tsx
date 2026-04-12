'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

interface ChecklistItem { id: string; label: string; points: number; is_critical: boolean }
interface ChecklistResult { item_id: string; status: string; points_earned: number }
interface SessionData {
  id: string; mode: string; status: string; total_score: number | null; grade: string | null; grade_label: string | null;
  total_points: number; scenario_name: string; scenario_category_label: string; scenario_department: string;
  checklist_items: ChecklistItem[]; checklist_results: ChecklistResult[] | null;
  ai_feedback: { good: string[]; needs_improvement: string[]; suggestions: string[] } | null;
  professor_comment: string | null; video_description: string | null; join_code: string | null; created_at: string;
}

type ItemStatus = 'success' | 'partial' | 'fail' | 'danger';

const STATUS_BTN: Record<ItemStatus, { label: string; color: string; active: string }> = {
  success: { label: '성공', color: 'border-emerald-300 text-emerald-600', active: 'bg-emerald-500 text-white border-emerald-500' },
  partial: { label: '부분', color: 'border-amber-300 text-amber-600', active: 'bg-amber-500 text-white border-amber-500' },
  fail: { label: '실패', color: 'border-red-300 text-red-600', active: 'bg-red-500 text-white border-red-500' },
  danger: { label: '위험', color: 'border-rose-400 text-rose-700', active: 'bg-rose-700 text-white border-rose-700' },
};

const GRADE_STYLE: Record<string, string> = {
  EXCELLENT: 'from-emerald-500 to-teal-500',
  GOOD: 'from-blue-500 to-cyan-500',
  NEEDS_IMPROVEMENT: 'from-amber-500 to-orange-500',
  FAIL: 'from-red-500 to-rose-500',
};

export default function PracticumSessionPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const { id: sessionId } = useParams<{ id: string }>();

  const [session, setSession] = useState<SessionData | null>(null);
  const [results, setResults] = useState<Record<string, { status: ItemStatus; points: number }>>({});
  const [submitting, setSubmitting] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [videoDesc, setVideoDesc] = useState('');
  const [aiEvaluating, setAiEvaluating] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  useEffect(() => {
    if (user && sessionId) {
      api.getPracticumSession(sessionId).then((d: unknown) => {
        const s = d as SessionData;
        setSession(s);
        if (s.checklist_results) {
          const map: Record<string, { status: ItemStatus; points: number }> = {};
          for (const r of s.checklist_results) map[r.item_id] = { status: r.status as ItemStatus, points: r.points_earned };
          setResults(map);
        }
      }).catch(() => router.push('/practicum'));
    }
  }, [user, sessionId, router]);

  // LIVE 모드 폴링: 교수 체크 결과 실시간 반영
  useEffect(() => {
    if (!session || session.mode !== 'LIVE' || session.status !== 'DRAFT') return;
    const interval = setInterval(async () => {
      try {
        const d = await api.getPracticumSession(sessionId) as SessionData;
        setSession(d);
        if (d.checklist_results) {
          const map: Record<string, { status: ItemStatus; points: number }> = {};
          for (const r of d.checklist_results) map[r.item_id] = { status: r.status as ItemStatus, points: r.points_earned };
          setResults(map);
        }
      } catch { /* ignore */ }
    }, 3000);
    return () => clearInterval(interval);
  }, [session?.mode, session?.status, sessionId]);

  async function handleAiEvaluate() {
    if (videoDesc.length < 10) { alert('실습 수행 내용을 10자 이상 설명해주세요.'); return; }
    setAiEvaluating(true);
    try {
      const res = await api.aiEvaluateSession(sessionId, { video_description: videoDesc }) as SessionData;
      setSession(res);
      if (res.checklist_results) {
        const map: Record<string, { status: ItemStatus; points: number }> = {};
        for (const r of res.checklist_results) map[r.item_id] = { status: r.status as ItemStatus, points: r.points_earned };
        setResults(map);
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : 'AI 평가 실패');
    } finally {
      setAiEvaluating(false);
    }
  }

  function setItemStatus(itemId: string, status: ItemStatus, maxPoints: number) {
    const pts = status === 'success' ? maxPoints : status === 'partial' ? Math.round(maxPoints * 0.5) : 0;
    setResults((prev) => ({ ...prev, [itemId]: { status, points: pts } }));
  }

  async function handleSubmit() {
    if (!session) return;
    const missing = session.checklist_items.filter((item) => !results[item.id]);
    if (missing.length > 0) { alert(`${missing.length}개 항목을 평가해주세요.`); return; }

    setSubmitting(true);
    try {
      const checklist_results = Object.entries(results).map(([item_id, r]) => ({
        item_id, status: r.status, points_earned: r.points,
      }));
      const res = await api.submitPracticumSession(sessionId, { checklist_results }) as SessionData;
      setSession(res);
    } catch (err) {
      alert(err instanceof Error ? err.message : '제출 실패');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleGenerateFeedback() {
    setGenerating(true);
    try {
      const res = await api.generatePracticumFeedback(sessionId) as SessionData;
      setSession(res);
    } catch (err) {
      alert(err instanceof Error ? err.message : '피드백 생성 실패');
    } finally {
      setGenerating(false);
    }
  }

  if (loading || !user || !session) return <div className="p-8 text-center">로딩 중...</div>;

  const isDraft = session.status === 'DRAFT';
  const totalChecked = Object.keys(results).length;
  const totalItems = session.checklist_items.length;

  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="rounded-full bg-brand-50 px-2.5 py-0.5 text-[11px] font-semibold text-brand-700">
              {session.scenario_category_label}
            </span>
          </div>
          <h1 className="text-2xl font-bold">{session.scenario_name}</h1>
        </div>
        <Link href="/practicum" className="text-sm text-slate-500 hover:text-slate-700">&larr; 목록</Link>
      </div>

      {/* Score Card (submitted) */}
      {!isDraft && session.total_score !== null && (
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

      {/* Mode Badge */}
      <div className="mb-4 flex items-center gap-2">
        <span className={`rounded-full px-3 py-1 text-xs font-bold ${
          session.mode === 'LIVE' ? 'bg-purple-100 text-purple-700' :
          session.mode === 'VIDEO' ? 'bg-teal-100 text-teal-700' :
          'bg-slate-100 text-slate-600'
        }`}>
          {session.mode === 'LIVE' ? '실시간 세션' : session.mode === 'VIDEO' ? '영상 평가' : '자체 평가'}
        </span>
        {session.mode === 'LIVE' && session.status === 'DRAFT' && (
          <span className="flex items-center gap-1 text-xs text-purple-500">
            <span className="h-1.5 w-1.5 rounded-full bg-purple-400 animate-pulse" />
            교수님이 실시간으로 평가 중...
          </span>
        )}
      </div>

      {/* VIDEO 모드: 영상 설명 입력 + AI 평가 */}
      {session.mode === 'VIDEO' && isDraft && (
        <section className="mb-6 rounded-xl border border-teal-200 bg-teal-50 p-5">
          <h2 className="mb-2 text-sm font-bold text-teal-800">실습 영상 설명</h2>
          <p className="mb-3 text-xs text-teal-600">
            촬영한 실습 영상의 수행 내용을 자세히 설명해주세요. AI가 체크리스트 항목별로 자동 평가합니다.
          </p>
          <textarea
            value={videoDesc}
            onChange={(e) => setVideoDesc(e.target.value)}
            rows={6}
            placeholder="예: 먼저 손위생 6단계를 수행했습니다. 손바닥을 마주 비비고, 손등을 문질렀습니다. 이후 장갑을 착용하고..."
            className="w-full rounded-lg border border-teal-300 bg-white px-3 py-2.5 text-sm focus:border-teal-500 focus:outline-none resize-none"
          />
          <div className="mt-3 flex items-center justify-between">
            <span className="text-xs text-teal-500">{videoDesc.length}자</span>
            <button
              onClick={handleAiEvaluate}
              disabled={aiEvaluating || videoDesc.length < 10}
              className="rounded-lg bg-teal-600 px-6 py-2.5 text-sm font-bold text-white hover:bg-teal-700 disabled:opacity-40 transition"
            >
              {aiEvaluating ? 'AI 평가 중...' : 'AI 자동 평가 실행'}
            </button>
          </div>
        </section>
      )}

      {/* Checklist */}
      <section className="mb-6">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">체크리스트</h2>
          {isDraft && <span className="text-xs text-slate-400">{totalChecked}/{totalItems} 완료</span>}
        </div>
        <div className="space-y-2">
          {session.checklist_items.map((item) => {
            const r = results[item.id];
            return (
              <div key={item.id} className={`rounded-xl border p-4 transition ${item.is_critical ? 'border-red-200 bg-red-50/30' : 'border-slate-200 bg-white'}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-900">{item.label}</span>
                      {item.is_critical && (
                        <span className="rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-bold text-red-600">필수</span>
                      )}
                    </div>
                    <div className="mt-0.5 text-xs text-slate-400">{item.points}점</div>
                  </div>
                  <div className="flex gap-1">
                    {isDraft && session.mode === 'SELF' ? (
                      (['success', 'partial', 'fail', 'danger'] as ItemStatus[]).map((st) => {
                        const btn = STATUS_BTN[st];
                        const isActive = r?.status === st;
                        return (
                          <button
                            key={st}
                            onClick={() => setItemStatus(item.id, st, item.points)}
                            className={`rounded-lg border px-2.5 py-1 text-[11px] font-medium transition ${isActive ? btn.active : btn.color} ${!isActive ? 'bg-white hover:opacity-80' : ''}`}
                          >
                            {btn.label}
                          </button>
                        );
                      })
                    ) : (
                      r && (
                        <span className={`rounded-lg px-3 py-1 text-[11px] font-bold ${STATUS_BTN[r.status]?.active || 'bg-slate-200'}`}>
                          {STATUS_BTN[r.status]?.label} ({r.points}점)
                        </span>
                      )
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Submit Button (SELF mode only) */}
      {isDraft && session.mode === 'SELF' && (
        <button
          onClick={handleSubmit}
          disabled={submitting || totalChecked < totalItems}
          className="mb-6 w-full rounded-xl bg-brand-600 py-3 text-sm font-bold text-white transition hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {submitting ? '제출 중...' : `평가 제출 (${totalChecked}/${totalItems})`}
        </button>
      )}

      {/* AI Feedback */}
      {!isDraft && (
        <section className="mb-6">
          {!session.ai_feedback ? (
            <button
              onClick={handleGenerateFeedback}
              disabled={generating}
              className="w-full rounded-xl border-2 border-dashed border-brand-300 bg-brand-50 py-4 text-sm font-semibold text-brand-700 transition hover:bg-brand-100 disabled:opacity-50"
            >
              {generating ? 'AI 피드백 생성 중...' : 'AI 피드백 받기'}
            </button>
          ) : (
            <div className="space-y-3">
              <h2 className="text-lg font-semibold">AI 피드백</h2>
              {/* Good */}
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                <h3 className="mb-2 text-sm font-bold text-emerald-700">잘한 점</h3>
                <ul className="space-y-1">
                  {session.ai_feedback.good.map((t, i) => (
                    <li key={i} className="text-sm text-emerald-800">+ {t}</li>
                  ))}
                </ul>
              </div>
              {/* Needs Improvement */}
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                <h3 className="mb-2 text-sm font-bold text-amber-700">부족한 점</h3>
                <ul className="space-y-1">
                  {session.ai_feedback.needs_improvement.map((t, i) => (
                    <li key={i} className="text-sm text-amber-800">- {t}</li>
                  ))}
                </ul>
              </div>
              {/* Suggestions */}
              <div className="rounded-xl border border-blue-200 bg-blue-50 p-4">
                <h3 className="mb-2 text-sm font-bold text-blue-700">개선 방법</h3>
                <ul className="space-y-1">
                  {session.ai_feedback.suggestions.map((t, i) => (
                    <li key={i} className="text-sm text-blue-800">&rarr; {t}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </section>
      )}

      {/* Professor Comment */}
      {session.professor_comment && (
        <section className="mb-6 rounded-xl border border-purple-200 bg-purple-50 p-4">
          <h3 className="mb-2 text-sm font-bold text-purple-700">교수 코멘트</h3>
          <p className="text-sm text-purple-800 whitespace-pre-wrap">{session.professor_comment}</p>
        </section>
      )}
    </main>
  );
}
