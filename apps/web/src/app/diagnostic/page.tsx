'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

interface DiagQuestion {
  id: string;
  question_text: string;
  choices: string[];
  subject: string;
  difficulty: string;
}

export default function DiagnosticPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [phase, setPhase] = useState<'intro' | 'test' | 'result'>('intro');
  const [testId, setTestId] = useState('');
  const [questions, setQuestions] = useState<DiagQuestion[]>([]);
  const [current, setCurrent] = useState(0);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState('');
  const [startTime, setStartTime] = useState(0);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  async function handleStart() {
    setError('');
    try {
      const data = (await api.startDiagnostic()) as {
        test_id: string;
        questions: DiagQuestion[];
      };
      setTestId(data.test_id);
      setQuestions(data.questions);
      setPhase('test');
      setStartTime(Date.now());
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '진단 테스트를 시작할 수 없습니다.');
    }
  }

  function selectChoice(qId: string, choiceIdx: number) {
    setAnswers((prev) => ({ ...prev, [qId]: choiceIdx }));
  }

  async function handleSubmit() {
    setSubmitting(true);
    setError('');
    try {
      const elapsed = Math.floor((Date.now() - startTime) / 1000);
      const perQ = Math.floor(elapsed / questions.length);
      const answerList = questions.map((q) => ({
        question_id: q.id,
        selected_choice: answers[q.id] ?? 0,
        time_spent_sec: perQ,
      }));
      const data = (await api.submitDiagnostic(testId, answerList)) as Record<string, unknown>;
      setResult(data);
      setPhase('result');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '제출에 실패했습니다.');
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <div className="p-8 text-center">로딩 중...</div>;

  // === Intro ===
  if (phase === 'intro') {
    return (
      <main className="mx-auto max-w-2xl px-4 py-12 text-center">
        <h1 className="mb-4 text-3xl font-bold">진단 테스트</h1>
        <p className="mb-6 text-slate-600">
          학과별 30문항으로 현재 학습 수준을 진단합니다.
          <br />
          결과를 바탕으로 AI가 맞춤형 학습을 제공합니다.
        </p>
        {error && <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>}
        <button
          onClick={handleStart}
          className="rounded-lg bg-brand-600 px-8 py-3 text-lg font-semibold text-white hover:bg-brand-700"
        >
          진단 시작
        </button>
        <p className="mt-4 text-xs text-slate-400">1회만 응시 가능합니다.</p>
      </main>
    );
  }

  // === Test ===
  if (phase === 'test') {
    const q = questions[current];
    const progress = Math.round(((current + 1) / questions.length) * 100);
    const answered = Object.keys(answers).length;

    return (
      <main className="mx-auto max-w-3xl px-4 py-8">
        {/* Progress */}
        <div className="mb-6">
          <div className="mb-2 flex items-center justify-between text-sm text-slate-500">
            <span>
              {current + 1} / {questions.length}
            </span>
            <span>{answered}개 응답 완료</span>
          </div>
          <div className="h-2 w-full rounded-full bg-slate-200">
            <div
              className="h-2 rounded-full bg-brand-500 transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* Question */}
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-1 text-xs text-slate-400">
            {q.subject} | {q.difficulty}
          </div>
          <h2 className="mb-4 text-lg font-medium leading-relaxed">{q.question_text}</h2>

          <div className="space-y-2">
            {q.choices.map((choice, idx) => (
              <button
                key={idx}
                onClick={() => selectChoice(q.id, idx)}
                className={`w-full rounded-lg border p-3 text-left text-sm transition ${
                  answers[q.id] === idx
                    ? 'border-brand-500 bg-brand-50 font-semibold text-brand-700'
                    : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                }`}
              >
                <span className="mr-2 font-mono text-slate-400">{idx + 1}.</span>
                {choice}
              </button>
            ))}
          </div>
        </div>

        {/* Navigation */}
        <div className="mt-6 flex justify-between">
          <button
            disabled={current === 0}
            onClick={() => setCurrent((c) => c - 1)}
            className="rounded-lg border border-slate-300 px-6 py-2 text-sm disabled:opacity-30"
          >
            이전
          </button>

          {current < questions.length - 1 ? (
            <button
              onClick={() => setCurrent((c) => c + 1)}
              className="rounded-lg bg-brand-600 px-6 py-2 text-sm font-semibold text-white hover:bg-brand-700"
            >
              다음
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={submitting || answered < questions.length}
              className="rounded-lg bg-emerald-600 px-6 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              {submitting ? '제출 중...' : `제출 (${answered}/${questions.length})`}
            </button>
          )}
        </div>

        {error && (
          <div className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>
        )}
      </main>
    );
  }

  // === Result ===
  return (
    <main className="mx-auto max-w-2xl px-4 py-12">
      <div className="text-center">
        <h1 className="mb-4 text-3xl font-bold">진단 완료!</h1>
        <div className="mb-6 inline-block rounded-full bg-emerald-100 px-6 py-3 text-2xl font-bold text-emerald-700">
          {Math.round(((result?.total_score as number) || 0) * 100)}점
        </div>
        <p className="mb-2 text-lg text-slate-600">
          수준:{' '}
          <span className="font-semibold">
            {result?.level === 'ADVANCED' ? '상급' : result?.level === 'INTERMEDIATE' ? '중급' : '초급'}
          </span>
        </p>
      </div>

      {/* 과목별 점수 */}
      {result?.section_scores && (
        <div className="mt-8 rounded-xl border border-slate-200 bg-white p-6">
          <h3 className="mb-4 font-semibold">과목별 정답률</h3>
          <div className="space-y-3">
            {Object.entries(result.section_scores as Record<string, number>).map(
              ([subject, score]) => (
                <div key={subject}>
                  <div className="mb-1 flex justify-between text-sm">
                    <span>{subject}</span>
                    <span className="font-mono">{Math.round(score * 100)}%</span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-slate-200">
                    <div
                      className={`h-2 rounded-full transition-all ${
                        score >= 0.7 ? 'bg-emerald-500' : score >= 0.5 ? 'bg-amber-500' : 'bg-red-500'
                      }`}
                      style={{ width: `${Math.round(score * 100)}%` }}
                    />
                  </div>
                </div>
              ),
            )}
          </div>
        </div>
      )}

      <div className="mt-8 text-center">
        <button
          onClick={() => router.push('/dashboard')}
          className="rounded-lg bg-brand-600 px-8 py-3 font-semibold text-white hover:bg-brand-700"
        >
          대시보드로 이동
        </button>
      </div>
    </main>
  );
}
