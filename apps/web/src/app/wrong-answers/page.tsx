'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

interface WrongItem {
  question_id: string;
  subject: string;
  unit: string | null;
  difficulty: string;
  question_text_preview: string;
  last_error_type: string | null;
  wrong_count: number;
  total_attempts: number;
  is_resolved: boolean;
}

const ERROR_LABEL: Record<string, string> = {
  CONCEPT_GAP: '개념 부족',
  CONFUSION: '헷갈림',
  CARELESS: '실수',
  APPLICATION_GAP: '응용 부족',
};

export default function WrongAnswersPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [items, setItems] = useState<WrongItem[]>([]);
  const [total, setTotal] = useState(0);
  const [includeResolved, setIncludeResolved] = useState(false);
  const [fetching, setFetching] = useState(true);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  useEffect(() => {
    if (user) {
      setFetching(true);
      api
        .getWrongAnswers(`include_resolved=${includeResolved}&page_size=50`)
        .then((data: unknown) => {
          const d = data as { items: WrongItem[]; total: number };
          setItems(d.items);
          setTotal(d.total);
        })
        .catch(() => {})
        .finally(() => setFetching(false));
    }
  }, [user, includeResolved]);

  if (loading) return <div className="p-8 text-center">Loading...</div>;

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">오답노트</h1>
          <p className="text-sm text-slate-500">반복 오답 우선 정렬</p>
        </div>
        <button onClick={() => router.push('/dashboard')} className="text-sm text-slate-500">
          ← 대시보드
        </button>
      </div>

      <div className="mb-4 flex items-center gap-4">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={includeResolved}
            onChange={(e) => setIncludeResolved(e.target.checked)}
            className="rounded border-slate-300"
          />
          해결된 문제도 표시
        </label>
        <span className="text-sm text-slate-500">총 {total}건</span>
      </div>

      {fetching ? (
        <p className="text-center text-slate-400">불러오는 중...</p>
      ) : items.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center text-slate-400">
          오답이 없습니다. 문제를 풀어보세요!
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <div
              key={item.question_id}
              className={`rounded-xl border bg-white p-4 shadow-sm ${
                item.is_resolved ? 'border-emerald-200 opacity-60' : 'border-slate-200'
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="mb-1 flex gap-2 text-xs">
                    <span className="rounded bg-slate-100 px-2 py-0.5">{item.subject}</span>
                    {item.unit && (
                      <span className="rounded bg-slate-100 px-2 py-0.5">{item.unit}</span>
                    )}
                    <span className="rounded bg-slate-100 px-2 py-0.5">{item.difficulty}</span>
                  </div>
                  <p className="text-sm leading-relaxed">{item.question_text_preview}</p>
                </div>
                <div className="ml-4 text-right">
                  <div className="text-lg font-bold text-red-600">{item.wrong_count}회 오답</div>
                  <div className="text-xs text-slate-500">{item.total_attempts}회 시도</div>
                  {item.last_error_type && (
                    <div className="mt-1 inline-block rounded bg-red-50 px-2 py-0.5 text-xs text-red-600">
                      {ERROR_LABEL[item.last_error_type] || item.last_error_type}
                    </div>
                  )}
                  {item.is_resolved && (
                    <div className="mt-1 inline-block rounded bg-emerald-50 px-2 py-0.5 text-xs text-emerald-600">
                      해결됨
                    </div>
                  )}
                </div>
              </div>
              <div className="mt-3 text-right">
                <button
                  onClick={() => router.push(`/quiz?q=${item.question_id}`)}
                  className="rounded-lg border border-brand-300 px-3 py-1.5 text-xs text-brand-700 hover:bg-brand-50"
                >
                  다시 풀기
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
