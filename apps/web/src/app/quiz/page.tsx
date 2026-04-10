'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api, ApiError } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

interface Question {
  id: string;
  question_text: string;
  choices: string[];
  subject: string;
  unit: string | null;
  difficulty: string;
  tags: string[];
}

interface AnswerResult {
  is_correct: boolean;
  correct_answer: number;
  error_type: string | null;
  explanation: string | null;
  attempt_no: number;
  history_id: string;
}

export default function QuizPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [questions, setQuestions] = useState<Question[]>([]);
  const [current, setCurrent] = useState(0);
  const [answered, setAnswered] = useState<AnswerResult | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [solving, setSolving] = useState(false);
  const [startTime, setStartTime] = useState(Date.now());
  const [aiExplain, setAiExplain] = useState('');
  const [loadingExplain, setLoadingExplain] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  // 추천 문제 세트 가져오기
  useEffect(() => {
    if (user) {
      api
        .getRecommendedSet(10)
        .then((data: unknown) => {
          const d = data as { questions: Question[] };
          setQuestions(d.questions);
        })
        .catch((err: unknown) => {
          // 추천이 안 되면 일반 문제 목록
          api
            .searchQuestions('page_size=10')
            .then((data: unknown) => {
              const d = data as { items: Question[] };
              setQuestions(d.items.map((q: Record<string, unknown>) => ({
                id: q.id as string,
                question_text: q.question_text as string,
                choices: q.choices as string[],
                subject: q.subject as string,
                unit: q.unit as string | null,
                difficulty: q.difficulty as string,
                tags: q.tags as string[],
              })));
            })
            .catch(() => {});
        });
    }
  }, [user]);

  const q = questions[current];

  async function handleSubmit() {
    if (selected === null || !q) return;
    setSolving(true);
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    try {
      const data = (await api.submitAnswer({
        question_id: q.id,
        selected_choice: selected,
        solving_time_sec: elapsed,
      })) as AnswerResult;
      setAnswered(data);
    } catch {
      /* ignore */
    } finally {
      setSolving(false);
    }
  }

  async function handleExplain() {
    if (!answered || !q) return;
    setLoadingExplain(true);
    try {
      const data = (await api.aiExplain(q.id, answered.history_id)) as {
        output_text: string;
      };
      setAiExplain(data.output_text);
    } catch {
      setAiExplain('AI 해설을 불러올 수 없습니다.');
    } finally {
      setLoadingExplain(false);
    }
  }

  function handleNext() {
    setAnswered(null);
    setSelected(null);
    setAiExplain('');
    setStartTime(Date.now());
    setCurrent((c) => Math.min(c + 1, questions.length - 1));
  }

  if (loading) return <div className="p-8 text-center">로딩 중...</div>;
  if (!questions.length) return <div className="p-8 text-center">문제를 불러오는 중...</div>;
  if (!q) return <div className="p-8 text-center">문제가 없습니다.</div>;

  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <button onClick={() => router.push('/dashboard')} className="text-sm text-slate-500 hover:text-slate-700">
          ← 대시보드
        </button>
        <span className="text-sm text-slate-500">
          {current + 1} / {questions.length}
        </span>
      </div>

      {/* Question */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-1 text-xs text-slate-400">
          {q.subject} {q.unit ? `> ${q.unit}` : ''} | {q.difficulty}
        </div>
        <h2 className="mb-4 text-lg font-medium leading-relaxed">{q.question_text}</h2>

        <div className="space-y-2">
          {q.choices.map((choice, idx) => {
            let style = 'border-slate-200 hover:border-slate-300 hover:bg-slate-50';
            if (answered) {
              if (idx === answered.correct_answer) style = 'border-emerald-500 bg-emerald-50 font-semibold text-emerald-700';
              else if (idx === selected && !answered.is_correct) style = 'border-red-500 bg-red-50 text-red-700';
              else style = 'border-slate-200 opacity-60';
            } else if (selected === idx) {
              style = 'border-brand-500 bg-brand-50 font-semibold text-brand-700';
            }

            return (
              <button
                key={idx}
                onClick={() => !answered && setSelected(idx)}
                disabled={!!answered}
                className={`w-full rounded-lg border p-3 text-left text-sm transition ${style}`}
              >
                <span className="mr-2 font-mono text-slate-400">{idx + 1}.</span>
                {choice}
              </button>
            );
          })}
        </div>
      </div>

      {/* Submit / Result */}
      {!answered ? (
        <div className="mt-4 text-right">
          <button
            onClick={handleSubmit}
            disabled={selected === null || solving}
            className="rounded-lg bg-brand-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {solving ? '채점 중...' : '제출'}
          </button>
        </div>
      ) : (
        <div className="mt-4 space-y-4">
          {/* Result badge */}
          <div
            className={`rounded-lg p-4 ${answered.is_correct ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'}`}
          >
            <span className="text-lg font-bold">{answered.is_correct ? '정답!' : '오답'}</span>
            {answered.error_type && (
              <span className="ml-2 text-sm opacity-75">({answered.error_type})</span>
            )}
            {answered.explanation && (
              <p className="mt-2 text-sm">{answered.explanation}</p>
            )}
          </div>

          {/* AI Explain */}
          {!aiExplain ? (
            <button
              onClick={handleExplain}
              disabled={loadingExplain}
              className="rounded-lg border border-purple-300 px-4 py-2 text-sm text-purple-700 hover:bg-purple-50"
            >
              {loadingExplain ? 'AI 해설 생성 중...' : 'AI 해설 보기'}
            </button>
          ) : (
            <div className="rounded-lg border border-purple-200 bg-purple-50 p-4">
              <h4 className="mb-2 text-sm font-semibold text-purple-800">AI 해설</h4>
              <div className="prose prose-sm max-w-none text-purple-900 whitespace-pre-wrap">
                {aiExplain}
              </div>
            </div>
          )}

          {/* Next */}
          <div className="text-right">
            <button
              onClick={handleNext}
              className="rounded-lg bg-brand-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-brand-700"
            >
              {current < questions.length - 1 ? '다음 문제' : '완료'}
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
