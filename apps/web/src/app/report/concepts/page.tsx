'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

interface TagWeakness {
  tag: string;
  attempts: number;
  correct: number;
  accuracy: number;
  weakness_level: string;
}

interface ConceptNode {
  id: string;
  name: string;
  level: number;
  description: string | null;
  blueprint_area: string | null;
  children: ConceptNode[];
}

interface DiagnosticReport {
  overall: { total_attempts: number; accuracy: number; avg_time_sec: number };
  trend: { recent_14d_accuracy: number; older_accuracy: number; direction: string };
  error_distribution: Record<string, number>;
  error_interpretation: string;
  subject_analysis: Array<{
    subject: string; attempts: number; accuracy: number; avg_time_sec: number;
  }>;
  study_frequency: { active_days_last_30: number; avg_problems_per_day: number };
  improvement_curve: Array<{ attempt: number; accuracy: number; count: number }>;
  grade: { score: number; grade: string; label: string };
}

const WEAKNESS_COLORS: Record<string, string> = {
  '심각': 'bg-red-100 text-red-700 border-red-200',
  '취약': 'bg-yellow-100 text-yellow-700 border-yellow-200',
  '보통': 'bg-green-100 text-green-700 border-green-200',
};

const ERROR_LABEL: Record<string, string> = {
  CONCEPT_GAP: '개념 부족',
  CONFUSION: '헷갈림',
  CARELESS: '실수',
  APPLICATION_GAP: '응용 부족',
  UNKNOWN: '미분류',
};

const TREND_ICON: Record<string, string> = {
  '향상': '↑',
  '하락': '↓',
  '유지': '→',
};

export default function ConceptAnalysisPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<'weakness' | 'tree' | 'report'>('weakness');
  const [tagWeakness, setTagWeakness] = useState<TagWeakness[]>([]);
  const [conceptTree, setConceptTree] = useState<ConceptNode[]>([]);
  const [report, setReport] = useState<DiagnosticReport | null>(null);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
    if (!loading && user && user.role !== 'STUDENT') router.push('/dashboard');
  }, [user, loading, router]);

  useEffect(() => {
    if (user) {
      api.getConceptWeakness().then(setTagWeakness).catch(console.error);
      api.getConceptTree().then(setConceptTree).catch(console.error);
      api.getDiagnosticReport().then(setReport).catch(console.error);
    }
  }, [user]);

  if (loading || !user) return null;

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-6xl">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">개념별 학습 분석</h1>
        <p className="text-gray-600 mb-6">개념 태그 기반 취약도 분석과 종합 진단 리포트를 확인하세요.</p>

        <div className="flex gap-2 mb-6">
          {(['weakness', 'tree', 'report'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                tab === t ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-100'
              }`}
            >
              {t === 'weakness' ? '개념별 취약도' : t === 'tree' ? '개념 체계' : '종합 진단'}
            </button>
          ))}
        </div>

        {/* Tag Weakness */}
        {tab === 'weakness' && (
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="text-lg font-semibold mb-4">개념 태그별 취약도</h2>
            {tagWeakness.length === 0 ? (
              <p className="text-gray-500">학습 데이터가 부족합니다.</p>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {tagWeakness.map((tw) => (
                  <div
                    key={tw.tag}
                    className={`p-4 rounded-lg border ${WEAKNESS_COLORS[tw.weakness_level] || 'bg-gray-50'}`}
                  >
                    <div className="font-medium mb-1">{tw.tag}</div>
                    <div className="text-sm">
                      정답률 {(tw.accuracy * 100).toFixed(1)}% ({tw.correct}/{tw.attempts})
                    </div>
                    <div className="text-xs mt-1 opacity-75">{tw.weakness_level}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Concept Tree */}
        {tab === 'tree' && (
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="text-lg font-semibold mb-4">개념 체계 (과목 → 단원 → 개념)</h2>
            {conceptTree.length === 0 ? (
              <p className="text-gray-500">개념 트리가 구성되지 않았습니다.</p>
            ) : (
              <div className="space-y-4">
                {conceptTree.map((root) => (
                  <div key={root.id} className="border rounded-lg p-4">
                    <h3 className="font-semibold text-blue-700">{root.name}</h3>
                    {root.description && <p className="text-sm text-gray-500">{root.description}</p>}
                    {root.children.length > 0 && (
                      <div className="ml-4 mt-2 space-y-2">
                        {root.children.map((unit) => (
                          <div key={unit.id} className="border-l-2 border-blue-200 pl-3">
                            <div className="font-medium text-gray-800">{unit.name}</div>
                            {unit.children.length > 0 && (
                              <div className="ml-3 mt-1 flex flex-wrap gap-1">
                                {unit.children.map((concept) => (
                                  <span
                                    key={concept.id}
                                    className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs"
                                  >
                                    {concept.name}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Diagnostic Report */}
        {tab === 'report' && report && (
          <div className="space-y-6">
            {/* Grade Card */}
            <div className="bg-white rounded-xl shadow-sm border p-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold">종합 학습 등급</h2>
                  <p className="text-gray-500 text-sm">최근 학습 데이터 기반 종합 평가</p>
                </div>
                <div className="text-center">
                  <div className={`text-4xl font-bold ${
                    report.grade.grade === 'A' ? 'text-green-600' :
                    report.grade.grade === 'B' ? 'text-blue-600' :
                    report.grade.grade === 'C' ? 'text-yellow-600' :
                    'text-red-600'
                  }`}>
                    {report.grade.grade}
                  </div>
                  <div className="text-sm text-gray-500">{report.grade.label} ({report.grade.score}점)</div>
                </div>
              </div>
            </div>

            {/* Stats Grid */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="bg-white rounded-xl border p-4">
                <div className="text-sm text-gray-500">전체 정답률</div>
                <div className="text-2xl font-bold">{(report.overall.accuracy * 100).toFixed(1)}%</div>
                <div className="text-xs text-gray-400">{report.overall.total_attempts}문항</div>
              </div>
              <div className="bg-white rounded-xl border p-4">
                <div className="text-sm text-gray-500">최근 2주 추이</div>
                <div className="text-2xl font-bold">
                  {TREND_ICON[report.trend.direction]} {(report.trend.recent_14d_accuracy * 100).toFixed(1)}%
                </div>
                <div className={`text-xs ${
                  report.trend.direction === '향상' ? 'text-green-600' :
                  report.trend.direction === '하락' ? 'text-red-600' : 'text-gray-400'
                }`}>{report.trend.direction}</div>
              </div>
              <div className="bg-white rounded-xl border p-4">
                <div className="text-sm text-gray-500">학습 일수 (30일)</div>
                <div className="text-2xl font-bold">{report.study_frequency.active_days_last_30}일</div>
                <div className="text-xs text-gray-400">일평균 {report.study_frequency.avg_problems_per_day}문항</div>
              </div>
              <div className="bg-white rounded-xl border p-4">
                <div className="text-sm text-gray-500">평균 풀이 시간</div>
                <div className="text-2xl font-bold">{report.overall.avg_time_sec}초</div>
              </div>
            </div>

            {/* Error Interpretation */}
            <div className="bg-white rounded-xl shadow-sm border p-6">
              <h3 className="font-semibold mb-3">오답 패턴 분석</h3>
              <p className="text-gray-700 mb-4">{report.error_interpretation}</p>
              <div className="flex flex-wrap gap-3">
                {Object.entries(report.error_distribution).map(([type, cnt]) => (
                  <div key={type} className="px-3 py-2 bg-gray-50 rounded-lg text-sm">
                    <span className="font-medium">{ERROR_LABEL[type] || type}</span>
                    <span className="text-gray-500 ml-2">{cnt}건</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Subject Analysis */}
            <div className="bg-white rounded-xl shadow-sm border p-6">
              <h3 className="font-semibold mb-3">과목별 분석</h3>
              <div className="space-y-2">
                {report.subject_analysis.map((s) => (
                  <div key={s.subject} className="flex items-center justify-between p-2 rounded hover:bg-gray-50">
                    <span className="font-medium">{s.subject}</span>
                    <div className="flex items-center gap-4 text-sm">
                      <div className="w-32 h-2 bg-gray-200 rounded-full">
                        <div
                          className={`h-2 rounded-full ${
                            s.accuracy >= 0.7 ? 'bg-green-500' :
                            s.accuracy >= 0.5 ? 'bg-yellow-500' : 'bg-red-500'
                          }`}
                          style={{ width: `${s.accuracy * 100}%` }}
                        />
                      </div>
                      <span>{(s.accuracy * 100).toFixed(1)}%</span>
                      <span className="text-gray-400">{s.attempts}문항</span>
                      <span className="text-gray-400">{s.avg_time_sec}초</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Improvement Curve */}
            {report.improvement_curve.length > 1 && (
              <div className="bg-white rounded-xl shadow-sm border p-6">
                <h3 className="font-semibold mb-3">반복 풀이 개선 곡선</h3>
                <div className="flex items-end gap-2 h-32">
                  {report.improvement_curve.map((point) => (
                    <div key={point.attempt} className="flex flex-col items-center flex-1">
                      <div className="text-xs text-gray-500 mb-1">
                        {(point.accuracy * 100).toFixed(0)}%
                      </div>
                      <div
                        className="w-full bg-blue-400 rounded-t"
                        style={{ height: `${point.accuracy * 100}%` }}
                      />
                      <div className="text-xs text-gray-400 mt-1">{point.attempt}회차</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        {tab === 'report' && !report && (
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <p className="text-gray-500">진단 리포트를 생성하는 중...</p>
          </div>
        )}
      </div>
    </div>
  );
}
