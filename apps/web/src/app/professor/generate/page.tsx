'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { FormEvent, useEffect, useState } from 'react';

interface GeneratedQ {
  question_text: string;
  choices: string[];
  correct_answer: number;
  explanation: string;
}

const DIFFICULTIES = ['EASY', 'MEDIUM', 'HARD'];

export default function GenerateQuestionsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [subject, setSubject] = useState('');
  const [unit, setUnit] = useState('');
  const [difficulty, setDifficulty] = useState('MEDIUM');
  const [count, setCount] = useState(5);
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<GeneratedQ[] | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!loading && (!user || !['PROFESSOR', 'ADMIN', 'DEVELOPER'].includes(user.role)))
      router.push('/dashboard');
  }, [user, loading, router]);

  async function handleGenerate(e: FormEvent) {
    e.preventDefault();
    setGenerating(true);
    setError('');
    setResult(null);
    try {
      const data = (await api.generateQuestions({
        department: user?.department || 'NURSING',
        subject,
        unit: unit || undefined,
        difficulty,
        count,
      })) as { questions: GeneratedQ[]; provider: string; model: string };
      setResult(data.questions);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'AI 문제 생성에 실패했습니다.');
    } finally {
      setGenerating(false);
    }
  }

  if (loading) return <div className="p-8 text-center">Loading...</div>;

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">AI 문제 생성</h1>
          <p className="text-sm text-slate-500">RAG 지식베이스를 참조하여 국시 문제를 자동 생성</p>
        </div>
        <button onClick={() => router.push('/professor/assignments')} className="text-sm text-slate-500">← 과제 관리</button>
      </div>

      {/* 설정 폼 */}
      <form onSubmit={handleGenerate} className="mb-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium">과목 *</label>
            <input
              type="text"
              required
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="예: 성인간호학"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">단원 (선택)</label>
            <input
              type="text"
              value={unit}
              onChange={(e) => setUnit(e.target.value)}
              placeholder="예: 심혈관계"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">난이도</label>
            <select
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
              {DIFFICULTIES.map((d) => (
                <option key={d} value={d}>{d === 'EASY' ? '쉬움' : d === 'MEDIUM' ? '보통' : '어려움'}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">문항 수 (1~50)</label>
            <input
              type="number"
              min={1}
              max={50}
              value={count}
              onChange={(e) => setCount(+e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
        </div>
        {error && <div className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>}
        <button
          type="submit"
          disabled={generating}
          className="mt-4 w-full rounded-lg bg-purple-600 py-3 text-sm font-semibold text-white hover:bg-purple-700 disabled:opacity-50"
        >
          {generating ? '🤖 AI가 문제를 생성하는 중...' : `🤖 ${count}문항 생성하기`}
        </button>
      </form>

      {/* 결과 */}
      {result && (
        <div>
          <h2 className="mb-4 text-lg font-semibold">생성된 문제 ({result.length}건)</h2>
          <p className="mb-4 text-xs text-amber-600">
            ⚠️ AI 생성 문제입니다. 반드시 검수 후 문제은행에 등록하세요.
            Swagger UI에서 POST /questions로 등록할 수 있습니다.
          </p>
          <div className="space-y-4">
            {result.map((q, i) => (
              <div key={i} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-1 text-xs text-slate-400">문제 {i + 1}</div>
                <h3 className="mb-3 font-medium">{q.question_text}</h3>
                <div className="mb-3 space-y-1">
                  {(q.choices || []).map((choice, ci) => (
                    <div
                      key={ci}
                      className={`rounded-lg border p-2 text-sm ${
                        ci === q.correct_answer
                          ? 'border-emerald-400 bg-emerald-50 font-semibold text-emerald-700'
                          : 'border-slate-200'
                      }`}
                    >
                      {ci + 1}. {choice}
                      {ci === q.correct_answer && ' ✓'}
                    </div>
                  ))}
                </div>
                {q.explanation && (
                  <div className="rounded-lg bg-blue-50 p-3 text-xs text-blue-800">
                    <strong>해설:</strong> {q.explanation}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </main>
  );
}
