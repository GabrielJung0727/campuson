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

interface QuestionStatsData {
  total_attempts: number;
  correct_count: number;
  accuracy: number;
  choice_distribution: Record<string, number>;
}

interface ChoiceEvent {
  choice: number;
  ts: number;
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
  const [aiExplainMeta, setAiExplainMeta] = useState<{
    confidence?: string;
    citations?: Array<{ number: number; document_title: string; snippet: string; source?: string }>;
    disclaimer?: string;
    content_warnings?: Array<{ pattern_name: string; severity: string }>;
  } | null>(null);
  const [loadingExplain, setLoadingExplain] = useState(false);

  // v0.2: 트래킹 + 통계
  const [choiceEvents, setChoiceEvents] = useState<ChoiceEvent[]>([]);
  const [firstChoice, setFirstChoice] = useState<number>(-1);
  const [qStats, setQStats] = useState<QuestionStatsData | null>(null);
  const [percentile, setPercentile] = useState<number | null>(null);

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

  // v0.2: 선택지 클릭 트래킹
  function handleChoiceClick(idx: number) {
    if (answered) return;
    const ts = Date.now() - startTime;
    if (firstChoice === -1) setFirstChoice(idx);
    setChoiceEvents((prev) => [...prev, { choice: idx, ts }]);
    setSelected(idx);
  }

  async function handleSubmit() {
    if (selected === null || !q) return;
    setSolving(true);
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    try {
      const data = (await api.submitAnswer({
        question_id: q.id,
        selected_choice: selected,
        solving_time_sec: elapsed,
        // v0.2 트래킹
        time_to_first_click_ms: choiceEvents.length > 0 ? choiceEvents[0].ts : 0,
        first_choice: firstChoice,
        choice_changes: Math.max(0, choiceEvents.length - 1),
        choice_sequence: choiceEvents,
      })) as AnswerResult;
      setAnswered(data);

      // 통계 + 백분위 조회
      api.getQuestionStats(q.id).then((s: unknown) => setQStats(s as QuestionStatsData)).catch(() => {});
      api.getMyPercentile().then((p: unknown) => setPercentile((p as { overall_percentile: number }).overall_percentile)).catch(() => {});
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
        confidence?: string;
        citations?: Array<{ number: number; document_title: string; snippet: string; source?: string }>;
        disclaimer?: string;
        content_warnings?: Array<{ pattern_name: string; severity: string }>;
      };
      setAiExplain(data.output_text);
      setAiExplainMeta({
        confidence: data.confidence,
        citations: data.citations,
        disclaimer: data.disclaimer,
        content_warnings: data.content_warnings,
      });
    } catch {
      setAiExplain('AI 해설을 불러올 수 없습니다.');
    } finally {
      setLoadingExplain(false);
    }
  }

  function handleNext() {
    if (current >= questions.length - 1) {
      router.push('/dashboard');
      return;
    }
    setAnswered(null);
    setSelected(null);
    setAiExplain('');
    setAiExplainMeta(null);
    setStartTime(Date.now());
    setCurrent((c) => c + 1);
    // v0.2: 트래킹 리셋
    setChoiceEvents([]);
    setFirstChoice(-1);
    setQStats(null);
    setPercentile(null);
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
                onClick={() => handleChoiceClick(idx)}
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

          {/* v0.2: 문항 통계 + 백분위 */}
          {qStats && (
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="mb-3 flex items-center justify-between">
                <span className="text-sm font-semibold text-slate-700">
                  약 {qStats.total_attempts}명의 학생 중{' '}
                  <span className="text-emerald-600">{qStats.correct_count}명({Math.round(qStats.accuracy * 100)}%)</span>이 맞췄어요
                </span>
                {percentile !== null && (
                  <span className="rounded-full bg-brand-100 px-3 py-1 text-xs font-bold text-brand-700">
                    상위 {100 - percentile}%
                  </span>
                )}
              </div>
              {/* 선택지별 선택률 바 */}
              <div className="space-y-1.5">
                {q.choices.map((choice, idx) => {
                  const count = qStats.choice_distribution[String(idx)] || 0;
                  const pct = qStats.total_attempts > 0 ? Math.round((count / qStats.total_attempts) * 100) : 0;
                  const isCorrect = answered && idx === answered.correct_answer;
                  const isWrong = answered && idx === selected && !answered.is_correct;
                  return (
                    <div key={idx} className="flex items-center gap-2 text-xs">
                      <span className="w-6 text-right font-mono text-slate-400">{idx + 1}.</span>
                      <div className="flex-1">
                        <div className="relative h-5 w-full rounded bg-slate-100">
                          <div
                            className={`h-5 rounded transition-all ${
                              isCorrect ? 'bg-emerald-400' : isWrong ? 'bg-red-300' : 'bg-slate-300'
                            }`}
                            style={{ width: `${Math.max(pct, 2)}%` }}
                          />
                          <span className="absolute inset-0 flex items-center px-2 text-[10px]">
                            {choice.length > 30 ? choice.slice(0, 30) + '...' : choice}
                          </span>
                        </div>
                      </div>
                      <span className={`w-10 text-right font-mono ${isCorrect ? 'font-bold text-emerald-700' : ''}`}>
                        {pct}%
                      </span>
                    </div>
                  );
                })}
              </div>
              {/* 트래킹 피드백 */}
              {choiceEvents.length > 1 && (
                <p className="mt-2 text-xs text-amber-600">
                  💡 답을 {choiceEvents.length - 1}번 바꾸셨네요.
                  {firstChoice !== -1 && answered && firstChoice === answered.correct_answer && !answered.is_correct
                    ? ' 처음 선택이 정답이었어요! 다음엔 첫 직감을 믿어보세요.'
                    : ''}
                </p>
              )}
            </div>
          )}

          {/* AI Explain (v0.5 — 신뢰성 강화) */}
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
              <div className="mb-2 flex items-center gap-2">
                <h4 className="text-sm font-semibold text-purple-800">AI 해설</h4>
                {/* Confidence Badge */}
                {aiExplainMeta?.confidence && (
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                      aiExplainMeta.confidence === 'HIGH'
                        ? 'bg-emerald-100 text-emerald-700'
                        : aiExplainMeta.confidence === 'MEDIUM'
                          ? 'bg-blue-100 text-blue-700'
                          : aiExplainMeta.confidence === 'LOW'
                            ? 'bg-amber-100 text-amber-700'
                            : 'bg-slate-100 text-slate-500'
                    }`}
                  >
                    {aiExplainMeta.confidence === 'HIGH'
                      ? '✅ 교재 근거 있음'
                      : aiExplainMeta.confidence === 'MEDIUM'
                        ? '📖 부분 근거'
                        : aiExplainMeta.confidence === 'LOW'
                          ? '⚠️ 검토 필요'
                          : '❓ 미검증'}
                  </span>
                )}
              </div>

              {/* Content Warnings */}
              {aiExplainMeta?.content_warnings && aiExplainMeta.content_warnings.filter(w => w.severity !== 'info').length > 0 && (
                <div className="mb-2 rounded bg-amber-50 px-2 py-1 text-xs text-amber-700">
                  ⚠️ 이 해설에는 임상 관련 내용이 포함되어 있습니다. 실제 임상 적용 시 지도교수의 확인이 필요합니다.
                </div>
              )}

              <div className="prose prose-sm max-w-none text-purple-900 whitespace-pre-wrap">
                {aiExplain}
              </div>

              {/* Citations */}
              {aiExplainMeta?.citations && aiExplainMeta.citations.length > 0 && (
                <div className="mt-3 border-t border-purple-200 pt-2">
                  <p className="mb-1 text-xs font-semibold text-purple-600">참고 자료</p>
                  {aiExplainMeta.citations.map((c) => (
                    <div key={c.number} className="mb-1 rounded bg-purple-50/50 p-1 text-xs text-purple-700">
                      <span className="font-semibold">[{c.number}]</span> {c.document_title}
                      {c.source && <span className="ml-1 text-purple-400">({c.source})</span>}
                      {c.snippet && (
                        <p className="mt-0.5 text-[10px] text-purple-400 line-clamp-2">{c.snippet}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Disclaimer */}
              {aiExplainMeta?.disclaimer && (
                <div className="mt-2 border-t border-purple-200 pt-1.5 text-[10px] text-purple-400">
                  {aiExplainMeta.disclaimer}
                </div>
              )}
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
