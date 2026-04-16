'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

interface ReviewQueueItem {
  question_id: string;
  department: string;
  subject: string;
  unit: string | null;
  difficulty: string;
  question_text: string;
  review_status: string;
  created_at: string;
  reviewer_comment: string | null;
}

interface ComparisonData {
  question_id: string;
  ai_explanation: string | null;
  professor_explanation: string | null;
  review_status: string;
  latest_review: {
    id: string;
    status: string;
    comment: string | null;
    ai_explanation: string | null;
    professor_explanation: string | null;
    reviewed_at: string | null;
  } | null;
}

export default function ProfessorReviewsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [queue, setQueue] = useState<ReviewQueueItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loadingQueue, setLoadingQueue] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [comparison, setComparison] = useState<ComparisonData | null>(null);
  const [reviewComment, setReviewComment] = useState('');
  const [profExplanation, setProfExplanation] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!loading && (!user || (user.role !== 'PROFESSOR' && user.role !== 'ADMIN' && user.role !== 'DEVELOPER'))) {
      router.push('/login');
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (user) loadQueue();
  }, [user]);

  async function loadQueue() {
    setLoadingQueue(true);
    try {
      const data = (await api.getReviewQueue()) as { items: ReviewQueueItem[]; total: number };
      setQueue(data.items);
      setTotal(data.total);
    } catch {
      /* ignore */
    } finally {
      setLoadingQueue(false);
    }
  }

  async function handleSelect(questionId: string) {
    setSelectedId(questionId);
    setReviewComment('');
    setProfExplanation('');
    try {
      const data = (await api.compareExplanations(questionId)) as ComparisonData;
      setComparison(data);
      if (data.professor_explanation) setProfExplanation(data.professor_explanation);
    } catch {
      setComparison(null);
    }
  }

  async function handleSubmitReview(status: 'APPROVED' | 'REJECTED' | 'REVISION_REQUESTED') {
    if (!selectedId) return;
    setSubmitting(true);
    try {
      await api.submitReview(selectedId, {
        status,
        comment: reviewComment || null,
        professor_explanation: profExplanation || null,
      });
      // Refresh
      await loadQueue();
      setSelectedId(null);
      setComparison(null);
    } catch {
      /* ignore */
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <div className="p-8 text-center">로딩 중...</div>;

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">문항 검수</h1>
          <p className="text-sm text-slate-500">AI 생성 문항을 검수하고 승인/반려합니다 ({total}건 대기)</p>
        </div>
        <button onClick={() => router.push('/dashboard')} className="text-sm text-slate-500 hover:text-slate-700">
          ← 대시보드
        </button>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Queue List */}
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-slate-700">검수 대기 목록</h2>
          {loadingQueue && <p className="text-sm text-slate-400">불러오는 중...</p>}
          {queue.length === 0 && !loadingQueue && (
            <p className="text-sm text-slate-400">검수 대기 문항이 없습니다.</p>
          )}
          {queue.map((item) => (
            <button
              key={item.question_id}
              onClick={() => handleSelect(item.question_id)}
              className={`w-full rounded-lg border p-3 text-left transition ${
                selectedId === item.question_id
                  ? 'border-brand-500 bg-brand-50'
                  : 'border-slate-200 hover:border-slate-300'
              }`}
            >
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                  item.review_status === 'PENDING_REVIEW' ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'
                }`}>
                  {item.review_status === 'PENDING_REVIEW' ? '검수 대기' : '수정 요청'}
                </span>
                <span>{item.subject}</span>
                {item.unit && <span>{'>'} {item.unit}</span>}
                <span className="ml-auto">{item.difficulty}</span>
              </div>
              <p className="mt-1 text-sm text-slate-800 line-clamp-2">{item.question_text}</p>
            </button>
          ))}
        </div>

        {/* Review Panel */}
        <div>
          {!selectedId ? (
            <div className="flex h-64 items-center justify-center rounded-lg border border-dashed border-slate-300">
              <p className="text-sm text-slate-400">왼쪽에서 문항을 선택하세요</p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* AI vs Professor Comparison */}
              {comparison && (
                <div className="space-y-3">
                  <div className="rounded-lg border border-purple-200 bg-purple-50 p-3">
                    <h3 className="mb-1 text-xs font-semibold text-purple-700">AI 생성 해설</h3>
                    <p className="text-sm text-purple-900 whitespace-pre-wrap">
                      {comparison.ai_explanation || '(AI 해설 없음)'}
                    </p>
                  </div>

                  <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
                    <h3 className="mb-1 text-xs font-semibold text-emerald-700">교수 공식 해설</h3>
                    <textarea
                      value={profExplanation}
                      onChange={(e) => setProfExplanation(e.target.value)}
                      placeholder="교수 공식 해설을 작성하세요 (AI 해설을 수정하거나 새로 작성)"
                      className="w-full rounded border border-emerald-200 bg-white p-2 text-sm"
                      rows={4}
                    />
                  </div>
                </div>
              )}

              {/* Comment */}
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">검수 코멘트</label>
                <textarea
                  value={reviewComment}
                  onChange={(e) => setReviewComment(e.target.value)}
                  placeholder="승인/반려 사유를 작성하세요"
                  className="w-full rounded-lg border border-slate-200 p-2 text-sm"
                  rows={2}
                />
              </div>

              {/* Actions */}
              <div className="flex gap-2">
                <button
                  onClick={() => handleSubmitReview('APPROVED')}
                  disabled={submitting}
                  className="flex-1 rounded-lg bg-emerald-600 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
                >
                  승인
                </button>
                <button
                  onClick={() => handleSubmitReview('REVISION_REQUESTED')}
                  disabled={submitting}
                  className="flex-1 rounded-lg bg-amber-500 py-2 text-sm font-semibold text-white hover:bg-amber-600 disabled:opacity-50"
                >
                  수정 요청
                </button>
                <button
                  onClick={() => handleSubmitReview('REJECTED')}
                  disabled={submitting}
                  className="flex-1 rounded-lg bg-red-500 py-2 text-sm font-semibold text-white hover:bg-red-600 disabled:opacity-50"
                >
                  반려
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
