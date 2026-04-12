'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

interface Scenario { id: string; name: string; category: string; category_label: string; department_label: string; total_points: number; checklist_items: unknown[] }
interface Session { id: string; student_name?: string; scenario_name: string; scenario_category_label: string; status: string; total_score: number | null; grade_label: string | null; total_points: number; created_at: string }

const DEPT_LABEL: Record<string, string> = { NURSING: '간호학과', PHYSICAL_THERAPY: '물리치료학과', DENTAL_HYGIENE: '치위생과' };
const CATEGORIES = [
  { dept: 'NURSING', items: ['HAND_HYGIENE', 'VITAL_SIGNS', 'INJECTION', 'ASEPTIC_TECHNIQUE', 'BLS'] },
  { dept: 'PHYSICAL_THERAPY', items: ['ROM_MEASUREMENT', 'GAIT_TRAINING', 'ELECTROTHERAPY', 'PATIENT_TRANSFER'] },
  { dept: 'DENTAL_HYGIENE', items: ['SCALING', 'ORAL_EXAM', 'INFECTION_CONTROL', 'TOOTH_POLISHING'] },
];
const CAT_LABEL: Record<string, string> = {
  HAND_HYGIENE: '손위생', VITAL_SIGNS: '활력징후', INJECTION: '주사 술기', ASEPTIC_TECHNIQUE: '무균술', BLS: '심폐소생술',
  ROM_MEASUREMENT: 'ROM 측정', GAIT_TRAINING: '보행 훈련', ELECTROTHERAPY: '전기치료', PATIENT_TRANSFER: '환자 이동',
  SCALING: '스케일링', ORAL_EXAM: '구강검진', INFECTION_CONTROL: '감염관리', TOOTH_POLISHING: '치면세마',
};

export default function ProfessorPracticumPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<'scenarios' | 'sessions'>('scenarios');
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);

  // Create form
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: '', description: '', department: 'NURSING', category: 'HAND_HYGIENE' });
  const [items, setItems] = useState<{ id: string; label: string; points: number; is_critical: boolean }[]>([]);
  const [creating, setCreating] = useState(false);

  // Live session
  const [liveCode, setLiveCode] = useState<string | null>(null);
  const [liveSessionId, setLiveSessionId] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && (!user || !['PROFESSOR', 'ADMIN', 'DEVELOPER'].includes(user.role))) router.push('/dashboard');
  }, [user, loading, router]);

  function refresh() {
    api.getPracticumScenarios().then((d: unknown) => setScenarios(d as Scenario[])).catch(() => {});
    api.getPracticumSessions().then((d: unknown) => setSessions(d as Session[])).catch(() => {});
  }

  useEffect(() => { if (user) refresh(); }, [user]);

  function addItem() {
    setItems((prev) => [...prev, { id: `item_${Date.now()}`, label: '', points: 10, is_critical: false }]);
  }

  function removeItem(id: string) {
    setItems((prev) => prev.filter((i) => i.id !== id));
  }

  async function handleCreate() {
    if (!form.name || items.length === 0) return;
    setCreating(true);
    try {
      const total = items.reduce((s, i) => s + i.points, 0);
      await api.createPracticumScenario({
        ...form,
        checklist_items: items,
        total_points: total,
      });
      setShowCreate(false);
      setForm({ name: '', description: '', department: 'NURSING', category: 'HAND_HYGIENE' });
      setItems([]);
      refresh();
    } catch (err) {
      alert(err instanceof Error ? err.message : '생성 실패');
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm('이 시나리오를 삭제하시겠습니까?')) return;
    await api.deletePracticumScenario(id).catch(() => {});
    refresh();
  }

  async function handleStartLive(scenarioId: string) {
    try {
      const res = await api.createLiveSession(scenarioId) as { id: string; join_code: string };
      setLiveCode(res.join_code);
      setLiveSessionId(res.id);
    } catch (err) {
      alert(err instanceof Error ? err.message : '세션 생성 실패');
    }
  }

  if (loading || !user) return <div className="p-8 text-center">로딩 중...</div>;

  const deptCats = CATEGORIES.find((c) => c.dept === form.department)?.items || [];

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">실습 평가 관리</h1>
          <p className="text-sm text-slate-500">시나리오 생성 · 학생 세션 리뷰</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowCreate(!showCreate)} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700">
            + 시나리오 생성
          </button>
          <button onClick={() => router.push('/dashboard')} className="text-sm text-slate-500">&larr; 대시보드</button>
        </div>
      </div>

      {/* Tabs */}
      <div className="mb-6 flex gap-1 rounded-lg border border-slate-200 bg-white p-1">
        {(['scenarios', 'sessions'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 rounded-md py-2 text-sm font-medium transition ${tab === t ? 'bg-brand-600 text-white' : 'text-slate-500 hover:text-slate-700'}`}
          >
            {t === 'scenarios' ? `시나리오 (${scenarios.length})` : `학생 세션 (${sessions.length})`}
          </button>
        ))}
      </div>

      {/* Create Form */}
      {showCreate && (
        <div className="mb-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="mb-4 text-lg font-semibold">새 시나리오</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="시나리오 이름" className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
            <select value={form.department} onChange={(e) => { setForm({ ...form, department: e.target.value, category: CATEGORIES.find((c) => c.dept === e.target.value)?.items[0] || '' }); }} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
              {Object.entries(DEPT_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
              {deptCats.map((c) => <option key={c} value={c}>{CAT_LABEL[c] || c}</option>)}
            </select>
            <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="설명 (선택)" className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          </div>
          {/* Checklist Builder */}
          <div className="mt-4">
            <div className="mb-2 flex items-center justify-between">
              <h4 className="text-sm font-semibold">체크리스트 항목</h4>
              <button onClick={addItem} className="text-xs text-brand-600 hover:underline">+ 항목 추가</button>
            </div>
            <div className="space-y-2">
              {items.map((item, i) => (
                <div key={item.id} className="flex items-center gap-2">
                  <span className="w-6 text-xs text-slate-400">{i + 1}</span>
                  <input value={item.label} onChange={(e) => { const copy = [...items]; copy[i] = { ...item, label: e.target.value }; setItems(copy); }} placeholder="항목 내용" className="flex-1 rounded border border-slate-300 px-2 py-1.5 text-sm" />
                  <input type="number" value={item.points} onChange={(e) => { const copy = [...items]; copy[i] = { ...item, points: Number(e.target.value) }; setItems(copy); }} className="w-16 rounded border border-slate-300 px-2 py-1.5 text-sm text-center" />
                  <label className="flex items-center gap-1 text-xs text-red-500">
                    <input type="checkbox" checked={item.is_critical} onChange={(e) => { const copy = [...items]; copy[i] = { ...item, is_critical: e.target.checked }; setItems(copy); }} />
                    필수
                  </label>
                  <button onClick={() => removeItem(item.id)} className="text-xs text-red-400 hover:text-red-600">X</button>
                </div>
              ))}
            </div>
            {items.length > 0 && (
              <div className="mt-2 text-right text-xs text-slate-500">
                총점: {items.reduce((s, i) => s + i.points, 0)}점
              </div>
            )}
          </div>
          <div className="mt-4 flex gap-2 justify-end">
            <button onClick={() => setShowCreate(false)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm">취소</button>
            <button onClick={handleCreate} disabled={creating || !form.name || items.length === 0} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">
              {creating ? '생성 중...' : '생성'}
            </button>
          </div>
        </div>
      )}

      {/* Live Session Code Banner */}
      {liveCode && (
        <div className="mb-6 rounded-xl border border-purple-300 bg-purple-50 p-6 text-center">
          <p className="text-sm text-purple-600 mb-2">실시간 세션이 생성되었습니다. 학생에게 아래 코드를 공유하세요.</p>
          <div className="text-5xl font-black tracking-[0.3em] text-purple-800 font-mono">{liveCode}</div>
          <div className="mt-4 flex gap-3 justify-center">
            <button
              onClick={() => { if (liveSessionId) router.push(`/professor/practicum/session/${liveSessionId}`); }}
              className="rounded-lg bg-purple-600 px-6 py-2 text-sm font-semibold text-white hover:bg-purple-700"
            >
              실시간 평가 시작
            </button>
            <button
              onClick={() => { setLiveCode(null); setLiveSessionId(null); }}
              className="rounded-lg border border-purple-300 px-4 py-2 text-sm text-purple-600"
            >
              닫기
            </button>
          </div>
        </div>
      )}

      {/* Scenarios Tab */}
      {tab === 'scenarios' && (
        <div className="space-y-3">
          {scenarios.length === 0 ? (
            <div className="rounded-xl border border-dashed p-8 text-center text-sm text-slate-400">시나리오가 없습니다.</div>
          ) : scenarios.map((s) => (
            <div key={s.id} className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-medium">{s.name}</span>
                  <span className="rounded-full bg-brand-50 px-2 py-0.5 text-[10px] text-brand-700">{s.category_label}</span>
                  <span className="text-[10px] text-slate-400">{s.department_label}</span>
                </div>
                <div className="mt-1 text-xs text-slate-400">{(s.checklist_items as unknown[]).length}개 항목 &middot; {s.total_points}점</div>
              </div>
              <div className="flex gap-2">
                <button onClick={() => handleStartLive(s.id)} className="rounded border border-purple-300 px-3 py-1 text-xs font-medium text-purple-600 hover:bg-purple-50">실시간 세션</button>
                <button onClick={() => handleDelete(s.id)} className="text-xs text-red-400 hover:text-red-600">삭제</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Sessions Tab */}
      {tab === 'sessions' && (
        <div className="space-y-3">
          {sessions.length === 0 ? (
            <div className="rounded-xl border border-dashed p-8 text-center text-sm text-slate-400">학생 세션이 없습니다.</div>
          ) : sessions.map((s) => (
            <Link key={s.id} href={`/professor/practicum/session/${s.id}`} className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4 shadow-sm hover:shadow-md transition">
              <div>
                <div className="font-medium">{s.scenario_name || s.scenario_category_label}</div>
                <div className="mt-1 text-xs text-slate-400">
                  {new Date(s.created_at).toLocaleDateString('ko-KR')}
                  <span className="ml-2">{s.status === 'DRAFT' ? '진행 중' : s.status === 'SUBMITTED' ? '제출됨' : '리뷰 완료'}</span>
                </div>
              </div>
              <div className="text-right">
                {s.total_score !== null && <div className="font-bold">{s.total_score}/{s.total_points}</div>}
                {s.grade_label && <div className="text-xs text-slate-500">{s.grade_label}</div>}
              </div>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
