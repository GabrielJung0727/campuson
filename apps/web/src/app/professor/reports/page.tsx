'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

interface ClassInfo {
  id: string;
  class_name: string;
  department: string;
  year: number;
  semester: number;
  student_count: number;
  active_students: number;
  active_rate: number;
  total_attempts: number;
  avg_accuracy: number;
  avg_time_sec: number;
}

interface StudentAchievement {
  user_id: string;
  name: string;
  student_no: string;
  total_attempts: number;
  accuracy: number;
  avg_time_sec: number;
  active_days: number;
  last_activity: string | null;
  recent_14d: { attempts: number; accuracy: number };
}

interface ObjectiveItem {
  learning_objective: string;
  subject: string;
  attempts: number;
  accuracy: number;
  student_count: number;
  status: string;
}

interface AtRiskData {
  class_name: string;
  total_at_risk: number;
  low_accuracy: Array<{
    user_id: string; name: string; student_no: string;
    attempts: number; accuracy: number; risk_type: string;
  }>;
  inactive: Array<{
    user_id: string; name: string; student_no: string;
    last_activity: string | null; risk_type: string;
  }>;
  declining: Array<{
    user_id: string; name: string; student_no: string;
    recent_accuracy: number; older_accuracy: number; delta: number; risk_type: string;
  }>;
}

export default function ProfessorReportsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<'compare' | 'students' | 'objectives' | 'risk'>('compare');
  const [classes, setClasses] = useState<ClassInfo[]>([]);
  const [selectedClassId, setSelectedClassId] = useState<string>('');
  const [students, setStudents] = useState<StudentAchievement[]>([]);
  const [objectives, setObjectives] = useState<ObjectiveItem[]>([]);
  const [atRisk, setAtRisk] = useState<AtRiskData | null>(null);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
    if (!loading && user && !['PROFESSOR', 'ADMIN', 'DEVELOPER'].includes(user.role)) {
      router.push('/dashboard');
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (user) {
      api.compareClasses().then((data: ClassInfo[]) => {
        setClasses(data);
        if (data.length > 0) setSelectedClassId(data[0].id);
      }).catch(console.error);
    }
  }, [user]);

  useEffect(() => {
    if (!selectedClassId) return;
    if (tab === 'students') {
      api.getClassStudents(selectedClassId).then(setStudents).catch(console.error);
    } else if (tab === 'objectives') {
      api.getClassObjectives(selectedClassId).then(setObjectives).catch(console.error);
    } else if (tab === 'risk') {
      api.getAtRiskStudents(selectedClassId).then(setAtRisk).catch(console.error);
    }
  }, [selectedClassId, tab]);

  if (loading || !user) return null;

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-7xl">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">학습 분석 리포트</h1>
        <p className="text-gray-600 mb-6">분반별 학생 성취도, 학습목표 달성률, 취약 학생을 한눈에 확인하세요.</p>

        {/* Class Selector */}
        {classes.length > 0 && tab !== 'compare' && (
          <div className="mb-4">
            <select
              value={selectedClassId}
              onChange={(e) => setSelectedClassId(e.target.value)}
              className="rounded-lg border px-4 py-2 text-sm"
            >
              {classes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.class_name} ({c.year}년 {c.semester}학기)
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-2 mb-6">
          {(['compare', 'students', 'objectives', 'risk'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                tab === t ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-100'
              }`}
            >
              {t === 'compare' ? '분반 비교' :
               t === 'students' ? '학생 성취도' :
               t === 'objectives' ? '학습목표 달성' : '취약 학생'}
            </button>
          ))}
        </div>

        {/* Compare Tab */}
        {tab === 'compare' && (
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="text-lg font-semibold mb-4">분반 비교 분석</h2>
            {classes.length === 0 ? (
              <p className="text-gray-500">등록된 분반이 없습니다.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-gray-500">
                      <th className="pb-2">분반</th>
                      <th className="pb-2">학생수</th>
                      <th className="pb-2">활동율</th>
                      <th className="pb-2">풀이수</th>
                      <th className="pb-2">평균 정답률</th>
                      <th className="pb-2">평균 풀이시간</th>
                    </tr>
                  </thead>
                  <tbody>
                    {classes.map((c) => (
                      <tr key={c.id} className="border-b hover:bg-gray-50">
                        <td className="py-3 font-medium">{c.class_name}</td>
                        <td className="py-3">{c.student_count}명</td>
                        <td className="py-3">
                          <span className={`px-2 py-0.5 rounded text-xs ${
                            c.active_rate >= 0.7 ? 'bg-green-100 text-green-700' :
                            c.active_rate >= 0.4 ? 'bg-yellow-100 text-yellow-700' :
                            'bg-red-100 text-red-700'
                          }`}>
                            {(c.active_rate * 100).toFixed(0)}%
                          </span>
                        </td>
                        <td className="py-3">{c.total_attempts}</td>
                        <td className="py-3">
                          <div className="flex items-center gap-2">
                            <div className="w-20 h-2 bg-gray-200 rounded-full">
                              <div
                                className={`h-2 rounded-full ${
                                  c.avg_accuracy >= 0.7 ? 'bg-green-500' :
                                  c.avg_accuracy >= 0.5 ? 'bg-yellow-500' : 'bg-red-500'
                                }`}
                                style={{ width: `${c.avg_accuracy * 100}%` }}
                              />
                            </div>
                            <span>{(c.avg_accuracy * 100).toFixed(1)}%</span>
                          </div>
                        </td>
                        <td className="py-3">{c.avg_time_sec}초</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Students Tab */}
        {tab === 'students' && (
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="text-lg font-semibold mb-4">학생별 성취도</h2>
            {students.length === 0 ? (
              <p className="text-gray-500">학생 데이터가 없습니다.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-gray-500">
                      <th className="pb-2">학번</th>
                      <th className="pb-2">이름</th>
                      <th className="pb-2">풀이수</th>
                      <th className="pb-2">정답률</th>
                      <th className="pb-2">최근2주</th>
                      <th className="pb-2">활동일</th>
                      <th className="pb-2">최근 활동</th>
                    </tr>
                  </thead>
                  <tbody>
                    {students.map((s) => (
                      <tr
                        key={s.user_id}
                        className="border-b hover:bg-gray-50 cursor-pointer"
                        onClick={() => router.push(`/professor/classes/${selectedClassId}`)}
                      >
                        <td className="py-2">{s.student_no}</td>
                        <td className="py-2 font-medium">{s.name}</td>
                        <td className="py-2">{s.total_attempts}</td>
                        <td className="py-2">
                          <span className={`px-2 py-0.5 rounded text-xs ${
                            s.accuracy >= 0.7 ? 'bg-green-100 text-green-700' :
                            s.accuracy >= 0.5 ? 'bg-yellow-100 text-yellow-700' :
                            'bg-red-100 text-red-700'
                          }`}>
                            {(s.accuracy * 100).toFixed(1)}%
                          </span>
                        </td>
                        <td className="py-2">
                          {s.recent_14d.attempts > 0
                            ? `${(s.recent_14d.accuracy * 100).toFixed(1)}%`
                            : '-'}
                        </td>
                        <td className="py-2">{s.active_days}일</td>
                        <td className="py-2 text-gray-500">
                          {s.last_activity
                            ? new Date(s.last_activity).toLocaleDateString('ko-KR')
                            : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Objectives Tab */}
        {tab === 'objectives' && (
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="text-lg font-semibold mb-4">학습목표별 성취도</h2>
            {objectives.length === 0 ? (
              <p className="text-gray-500">학습목표 데이터가 없습니다.</p>
            ) : (
              <div className="space-y-3">
                {objectives.map((obj, i) => (
                  <div key={i} className="p-4 rounded-lg border hover:bg-gray-50">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="font-medium text-gray-900">{obj.learning_objective}</div>
                        <div className="text-sm text-gray-500">{obj.subject} | {obj.student_count}명 응시</div>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="text-right">
                          <div className="text-sm font-medium">
                            {(obj.accuracy * 100).toFixed(1)}%
                          </div>
                          <div className="text-xs text-gray-400">{obj.attempts}회</div>
                        </div>
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          obj.status === '달성' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                        }`}>
                          {obj.status}
                        </span>
                      </div>
                    </div>
                    <div className="mt-2 w-full h-2 bg-gray-200 rounded-full">
                      <div
                        className={`h-2 rounded-full ${
                          obj.accuracy >= 0.7 ? 'bg-green-500' : 'bg-red-400'
                        }`}
                        style={{ width: `${obj.accuracy * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* At-Risk Tab */}
        {tab === 'risk' && atRisk && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl shadow-sm border p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">취약 학생 탐지</h2>
                <span className="px-3 py-1 bg-red-100 text-red-700 rounded-full text-sm font-medium">
                  {atRisk.total_at_risk}명 감지
                </span>
              </div>

              {/* Low Accuracy */}
              {atRisk.low_accuracy.length > 0 && (
                <div className="mb-6">
                  <h3 className="font-medium text-red-600 mb-2">학습 부진 (정답률 40% 미만)</h3>
                  <div className="space-y-2">
                    {atRisk.low_accuracy.map((s) => (
                      <div key={s.user_id} className="flex items-center justify-between p-3 bg-red-50 rounded-lg">
                        <div>
                          <span className="font-medium">{s.name}</span>
                          <span className="text-sm text-gray-500 ml-2">{s.student_no}</span>
                        </div>
                        <div className="text-sm">
                          정답률 <span className="font-medium text-red-600">
                            {(s.accuracy * 100).toFixed(1)}%
                          </span> ({s.attempts}문항)
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Inactive */}
              {atRisk.inactive.length > 0 && (
                <div className="mb-6">
                  <h3 className="font-medium text-orange-600 mb-2">이탈 위험 (7일 이상 미활동)</h3>
                  <div className="space-y-2">
                    {atRisk.inactive.map((s) => (
                      <div key={s.user_id} className="flex items-center justify-between p-3 bg-orange-50 rounded-lg">
                        <div>
                          <span className="font-medium">{s.name}</span>
                          <span className="text-sm text-gray-500 ml-2">{s.student_no}</span>
                        </div>
                        <div className="text-sm text-orange-600">
                          {s.last_activity
                            ? `마지막 활동: ${new Date(s.last_activity).toLocaleDateString('ko-KR')}`
                            : '활동 기록 없음'}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Declining */}
              {atRisk.declining.length > 0 && (
                <div>
                  <h3 className="font-medium text-yellow-600 mb-2">하락 추세 (정답률 10%p+ 하락)</h3>
                  <div className="space-y-2">
                    {atRisk.declining.map((s) => (
                      <div key={s.user_id} className="flex items-center justify-between p-3 bg-yellow-50 rounded-lg">
                        <div>
                          <span className="font-medium">{s.name}</span>
                          <span className="text-sm text-gray-500 ml-2">{s.student_no}</span>
                        </div>
                        <div className="text-sm">
                          {(s.older_accuracy * 100).toFixed(1)}% →{' '}
                          <span className="text-yellow-700 font-medium">
                            {(s.recent_accuracy * 100).toFixed(1)}%
                          </span>
                          <span className="text-red-500 ml-1">({(s.delta * 100).toFixed(1)}%p)</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {atRisk.total_at_risk === 0 && (
                <p className="text-green-600">모든 학생이 정상 범위 내에 있습니다.</p>
              )}
            </div>
          </div>
        )}
        {tab === 'risk' && !atRisk && (
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <p className="text-gray-500">데이터를 불러오는 중...</p>
          </div>
        )}
      </div>
    </div>
  );
}
