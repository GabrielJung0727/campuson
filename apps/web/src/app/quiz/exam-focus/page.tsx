'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

interface FocusQuestion {
  id: string;
  subject: string;
  unit: string;
  difficulty: string;
  national_exam_mapping: string | null;
}

interface FocusSet {
  questions: FocusQuestion[];
  total: number;
  allocation: Record<string, number>;
  weaknesses_targeted: string[];
}

interface BlueprintEntry {
  id: string;
  subject: string;
  area: string;
  weight_pct: number;
  question_count: number | null;
  competency: string | null;
}

interface WeaknessEntry {
  subject: string;
  area: string;
  accuracy: number;
  blueprint_weight: number;
  weakness_score: number;
  attempts: number;
}

const DIFF_COLORS: Record<string, string> = {
  EASY: 'bg-green-100 text-green-800',
  MEDIUM: 'bg-yellow-100 text-yellow-800',
  HARD: 'bg-red-100 text-red-800',
};

export default function ExamFocusPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [blueprint, setBlueprint] = useState<BlueprintEntry[]>([]);
  const [weaknesses, setWeaknesses] = useState<WeaknessEntry[]>([]);
  const [focusSet, setFocusSet] = useState<FocusSet | null>(null);
  const [setSize, setSetSize] = useState(30);
  const [tab, setTab] = useState<'blueprint' | 'weakness' | 'practice'>('blueprint');
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
    if (!loading && user && user.role !== 'STUDENT') router.push('/dashboard');
  }, [user, loading, router]);

  useEffect(() => {
    if (user) {
      api.getBlueprint().then(setBlueprint).catch(console.error);
      api.getBlueprintWeakness().then(setWeaknesses).catch(console.error);
    }
  }, [user]);

  const generateFocusSet = async () => {
    setGenerating(true);
    try {
      const data = await api.getBlueprintFocusSet(setSize) as FocusSet;
      setFocusSet(data);
      setTab('practice');
    } catch (err) {
      console.error(err);
    } finally {
      setGenerating(false);
    }
  };

  if (loading || !user) return null;

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-6xl">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          시험 직전 집중 모드
        </h1>
        <p className="text-gray-600 mb-6">
          국가고시 블루프린트 기반으로 출제 비중과 취약 영역을 반영한 집중 문제 세트를 생성합니다.
        </p>

        {/* Tabs */}
        <div className="flex gap-2 mb-6">
          {(['blueprint', 'weakness', 'practice'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                tab === t
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-100'
              }`}
            >
              {t === 'blueprint' ? '출제 블루프린트' : t === 'weakness' ? '약점 분석' : '집중 연습'}
            </button>
          ))}
        </div>

        {/* Blueprint Tab */}
        {tab === 'blueprint' && (
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="text-lg font-semibold mb-4">국가고시 출제 영역 비중</h2>
            {blueprint.length === 0 ? (
              <p className="text-gray-500">블루프린트 데이터가 없습니다. 관리자에게 시드 적재를 요청하세요.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-gray-500">
                      <th className="pb-2">과목</th>
                      <th className="pb-2">영역</th>
                      <th className="pb-2">비중</th>
                      <th className="pb-2">역량</th>
                    </tr>
                  </thead>
                  <tbody>
                    {blueprint.map((bp) => (
                      <tr key={bp.id} className="border-b hover:bg-gray-50">
                        <td className="py-2 font-medium">{bp.subject}</td>
                        <td className="py-2">{bp.area}</td>
                        <td className="py-2">
                          <div className="flex items-center gap-2">
                            <div className="w-20 h-2 bg-gray-200 rounded-full">
                              <div
                                className="h-2 bg-blue-500 rounded-full"
                                style={{ width: `${Math.min(100, bp.weight_pct * 100 * 5)}%` }}
                              />
                            </div>
                            <span>{(bp.weight_pct * 100).toFixed(1)}%</span>
                          </div>
                        </td>
                        <td className="py-2 text-gray-600">{bp.competency || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Weakness Tab */}
        {tab === 'weakness' && (
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="text-lg font-semibold mb-4">역량 단위 약점 분석</h2>
            {weaknesses.length === 0 ? (
              <p className="text-gray-500">충분한 학습 데이터가 없습니다. 문제를 더 풀어보세요.</p>
            ) : (
              <div className="space-y-3">
                {weaknesses.slice(0, 15).map((w, i) => (
                  <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-gray-50">
                    <div>
                      <span className="font-medium">{w.subject}</span>
                      <span className="text-gray-500 ml-2">{w.area}</span>
                    </div>
                    <div className="flex items-center gap-4 text-sm">
                      <span>정답률 {(w.accuracy * 100).toFixed(1)}%</span>
                      <span className="text-gray-400">|</span>
                      <span>비중 {(w.blueprint_weight * 100).toFixed(1)}%</span>
                      <span className="text-gray-400">|</span>
                      <span className={`px-2 py-0.5 rounded ${
                        w.weakness_score > 0.05 ? 'bg-red-100 text-red-700' :
                        w.weakness_score > 0.02 ? 'bg-yellow-100 text-yellow-700' :
                        'bg-green-100 text-green-700'
                      }`}>
                        위험도 {(w.weakness_score * 100).toFixed(2)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Practice Tab */}
        {tab === 'practice' && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl shadow-sm border p-6">
              <h2 className="text-lg font-semibold mb-4">집중 연습 세트 생성</h2>
              <div className="flex items-center gap-4">
                <label className="text-sm text-gray-600">문항 수:</label>
                <select
                  value={setSize}
                  onChange={(e) => setSetSize(Number(e.target.value))}
                  className="rounded-lg border px-3 py-2"
                >
                  {[10, 20, 30, 50].map((n) => (
                    <option key={n} value={n}>{n}문항</option>
                  ))}
                </select>
                <button
                  onClick={generateFocusSet}
                  disabled={generating}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {generating ? '생성 중...' : '문제 세트 생성'}
                </button>
              </div>
            </div>

            {focusSet && (
              <>
                <div className="bg-white rounded-xl shadow-sm border p-6">
                  <h3 className="font-semibold mb-3">과목별 배분</h3>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(focusSet.allocation).map(([subj, cnt]) => (
                      <span
                        key={subj}
                        className={`px-3 py-1 rounded-full text-sm ${
                          focusSet.weaknesses_targeted.includes(subj)
                            ? 'bg-red-100 text-red-700 font-medium'
                            : 'bg-gray-100 text-gray-700'
                        }`}
                      >
                        {subj}: {cnt}문항
                        {focusSet.weaknesses_targeted.includes(subj) && ' (약점 강화)'}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="bg-white rounded-xl shadow-sm border p-6">
                  <h3 className="font-semibold mb-3">문제 목록 ({focusSet.total}문항)</h3>
                  <div className="space-y-2">
                    {focusSet.questions.map((q, i) => (
                      <div
                        key={q.id}
                        onClick={() => router.push(`/quiz/${q.id}`)}
                        className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 cursor-pointer border"
                      >
                        <div className="flex items-center gap-3">
                          <span className="text-sm text-gray-400 w-6">{i + 1}</span>
                          <span className="font-medium">{q.subject}</span>
                          <span className="text-gray-500 text-sm">{q.unit}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          {q.national_exam_mapping && (
                            <span className="text-xs text-gray-400">{q.national_exam_mapping}</span>
                          )}
                          <span className={`px-2 py-0.5 rounded text-xs ${DIFF_COLORS[q.difficulty] || ''}`}>
                            {q.difficulty}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
