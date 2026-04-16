'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

interface OSCEExam {
  id: string;
  name: string;
  department: string;
  total_stations: number;
  time_per_station_sec: number;
  is_active: boolean;
  created_at: string;
}

interface Station {
  id: string;
  station_order: number;
  station_name: string;
  scenario_id: string;
  time_limit_sec: number | null;
  weight: number;
  instructions: string | null;
}

interface ExamDetail {
  id: string;
  name: string;
  description: string | null;
  department: string;
  total_stations: number;
  time_per_station_sec: number;
  transition_time_sec: number;
  is_active: boolean;
  stations: Station[];
}

interface RubricItem {
  id: string;
  name: string;
  description: string | null;
  department: string;
  criteria: any[];
  total_score: number;
  created_at: string;
}

export default function OSCEManagementPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<'exams' | 'rubrics' | 'detail'>('exams');
  const [exams, setExams] = useState<OSCEExam[]>([]);
  const [rubrics, setRubrics] = useState<RubricItem[]>([]);
  const [detail, setDetail] = useState<ExamDetail | null>(null);

  useEffect(() => {
    if (!loading && (!user || !['PROFESSOR', 'ADMIN', 'DEVELOPER'].includes(user.role))) {
      router.push('/dashboard');
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (user?.department) {
      api.getOsceExams(user.department).then((d: any) => setExams(d)).catch(() => {});
      api.getRubrics(user.department).then((d: any) => setRubrics(d)).catch(() => {});
    }
  }, [user]);

  const viewDetail = async (id: string) => {
    try {
      const d: any = await api.getOsceExam(id);
      setDetail(d);
      setTab('detail');
    } catch { /* ignore */ }
  };

  if (loading || !user) return null;

  const tabs = [
    { key: 'exams' as const, label: 'OSCE 시험' },
    { key: 'rubrics' as const, label: '루브릭' },
  ];

  return (
    <main className="mx-auto max-w-5xl p-6">
      <div className="mb-6">
        <Link href="/dashboard" className="text-sm text-blue-600 hover:underline">&larr; 대시보드</Link>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">OSCE 시험 관리</h1>
        <p className="text-sm text-gray-500">다중 스테이션 실습 시험 · 루브릭 평가</p>
      </div>

      <div className="mb-4 flex gap-2">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`rounded-lg px-4 py-2 text-sm font-medium ${
              tab === t.key ? 'bg-teal-100 text-teal-800' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* OSCE Exams List */}
      {tab === 'exams' && (
        <div className="space-y-3">
          {exams.length === 0 && (
            <p className="py-12 text-center text-gray-400">등록된 OSCE 시험이 없습니다.</p>
          )}
          {exams.map((e) => (
            <div
              key={e.id}
              onClick={() => viewDetail(e.id)}
              className="cursor-pointer rounded-xl border bg-white p-5 shadow-sm transition hover:shadow-md"
            >
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-semibold text-gray-900">{e.name}</h3>
                  <p className="mt-1 text-xs text-gray-500">
                    {e.total_stations}개 스테이션 · 스테이션당 {Math.floor(e.time_per_station_sec / 60)}분
                  </p>
                </div>
                <span className={`rounded-full px-3 py-1 text-xs font-medium ${
                  e.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-200 text-gray-500'
                }`}>
                  {e.is_active ? '활성' : '비활성'}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Rubrics */}
      {tab === 'rubrics' && (
        <div className="space-y-3">
          {rubrics.length === 0 && (
            <p className="py-12 text-center text-gray-400">등록된 루브릭이 없습니다.</p>
          )}
          {rubrics.map((r) => (
            <div key={r.id} className="rounded-xl border bg-white p-5 shadow-sm">
              <h3 className="font-semibold text-gray-900">{r.name}</h3>
              {r.description && <p className="mt-1 text-sm text-gray-500">{r.description}</p>}
              <div className="mt-3 flex gap-4 text-xs text-gray-500">
                <span>총점: {r.total_score}점</span>
                <span>평가 기준: {r.criteria.length}개</span>
              </div>
              {r.criteria.length > 0 && (
                <div className="mt-3 space-y-1">
                  {r.criteria.slice(0, 5).map((c: any, i: number) => (
                    <div key={i} className="flex items-center justify-between rounded bg-gray-50 px-3 py-1.5 text-xs">
                      <span className="text-gray-700">{c.name || c.label || `기준 ${i + 1}`}</span>
                      <span className="text-gray-500">{c.max_score || c.weight || '-'}점</span>
                    </div>
                  ))}
                  {r.criteria.length > 5 && (
                    <p className="text-center text-xs text-gray-400">+ {r.criteria.length - 5}개 더...</p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Exam Detail */}
      {tab === 'detail' && detail && (
        <div className="rounded-xl border bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">{detail.name}</h2>
              {detail.description && <p className="mt-1 text-sm text-gray-500">{detail.description}</p>}
            </div>
            <button
              onClick={() => setTab('exams')}
              className="rounded-lg bg-gray-100 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-200"
            >
              목록으로
            </button>
          </div>

          <div className="mb-4 grid grid-cols-3 gap-4">
            <div className="rounded-lg bg-teal-50 p-3 text-center">
              <p className="text-2xl font-bold text-teal-700">{detail.total_stations}</p>
              <p className="text-xs text-teal-600">스테이션</p>
            </div>
            <div className="rounded-lg bg-blue-50 p-3 text-center">
              <p className="text-2xl font-bold text-blue-700">{Math.floor(detail.time_per_station_sec / 60)}분</p>
              <p className="text-xs text-blue-600">스테이션당 시간</p>
            </div>
            <div className="rounded-lg bg-purple-50 p-3 text-center">
              <p className="text-2xl font-bold text-purple-700">{detail.transition_time_sec}초</p>
              <p className="text-xs text-purple-600">전환 시간</p>
            </div>
          </div>

          <h3 className="mb-2 font-medium text-gray-700">스테이션 목록</h3>
          <div className="space-y-2">
            {detail.stations.map((s) => (
              <div key={s.id} className="flex items-center gap-3 rounded-lg bg-gray-50 p-3">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-teal-100 text-sm font-bold text-teal-700">
                  {s.station_order}
                </span>
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-800">{s.station_name}</p>
                  {s.instructions && <p className="text-xs text-gray-500">{s.instructions}</p>}
                </div>
                <div className="text-right text-xs text-gray-500">
                  {s.time_limit_sec && <p>{Math.floor(s.time_limit_sec / 60)}분</p>}
                  <p>가중치: {s.weight}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </main>
  );
}
