'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

interface CalendarEvent {
  id: string;
  title: string;
  description: string | null;
  event_type: string;
  start_at: string;
  end_at: string | null;
  all_day: boolean;
  color: string | null;
  reminder_minutes: number | null;
  is_completed: boolean;
  reference_type: string | null;
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  assignment_due: '과제 마감',
  exam: '시험',
  practicum: '실습',
  diagnostic: '진단 테스트',
  review: '복습',
  custom: '개인 일정',
};

const EVENT_TYPE_COLORS: Record<string, string> = {
  assignment_due: 'bg-amber-100 text-amber-800 border-amber-200',
  exam: 'bg-red-100 text-red-800 border-red-200',
  practicum: 'bg-teal-100 text-teal-800 border-teal-200',
  diagnostic: 'bg-purple-100 text-purple-800 border-purple-200',
  review: 'bg-blue-100 text-blue-800 border-blue-200',
  custom: 'bg-gray-100 text-gray-800 border-gray-200',
};

export default function CalendarPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [filter, setFilter] = useState<string>('');
  const [syncing, setSyncing] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ title: '', event_type: 'custom', start_at: '', description: '' });

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  const loadEvents = () => {
    const params = filter ? `event_type=${filter}` : '';
    api.getCalendarEvents(params || undefined).then((d: any) => setEvents(d)).catch(() => {});
  };

  useEffect(() => { if (user) loadEvents(); }, [user, filter]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      const r: any = await api.syncAssignmentDeadlines();
      alert(`${r.synced}개 과제 일정이 동기화되었습니다.`);
      loadEvents();
    } finally {
      setSyncing(false);
    }
  };

  const handleCreate = async () => {
    if (!form.title || !form.start_at) return;
    try {
      await api.createCalendarEvent({
        ...form,
        start_at: new Date(form.start_at).toISOString(),
      });
      setShowCreate(false);
      setForm({ title: '', event_type: 'custom', start_at: '', description: '' });
      loadEvents();
    } catch { /* ignore */ }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.deleteCalendarEvent(id);
      loadEvents();
    } catch { /* ignore */ }
  };

  const toggleComplete = async (ev: CalendarEvent) => {
    try {
      await api.updateCalendarEvent(ev.id, { is_completed: !ev.is_completed });
      loadEvents();
    } catch { /* ignore */ }
  };

  if (loading || !user) return null;

  // Group events by date
  const grouped: Record<string, CalendarEvent[]> = {};
  events.forEach((ev) => {
    const date = ev.start_at.split('T')[0];
    if (!grouped[date]) grouped[date] = [];
    grouped[date].push(ev);
  });
  const sortedDates = Object.keys(grouped).sort();

  return (
    <main className="mx-auto max-w-3xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <Link href="/dashboard" className="text-sm text-blue-600 hover:underline">&larr; 대시보드</Link>
          <h1 className="mt-1 text-2xl font-bold text-gray-900">학습 캘린더</h1>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleSync}
            disabled={syncing}
            className="rounded-lg bg-amber-100 px-3 py-2 text-sm font-medium text-amber-800 hover:bg-amber-200 disabled:opacity-50"
          >
            {syncing ? '동기화 중...' : '과제 동기화'}
          </button>
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            + 일정 추가
          </button>
        </div>
      </div>

      {/* Filter */}
      <div className="mb-4 flex flex-wrap gap-2">
        <button
          onClick={() => setFilter('')}
          className={`rounded-full px-3 py-1 text-xs font-medium ${
            !filter ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'
          }`}
        >
          전체
        </button>
        {Object.entries(EVENT_TYPE_LABELS).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              filter === key ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Create Form */}
      {showCreate && (
        <div className="mb-4 rounded-xl border bg-white p-5 shadow-sm">
          <h3 className="mb-3 font-semibold text-gray-800">새 일정</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <input
              className="rounded-lg border px-3 py-2 text-sm"
              placeholder="제목 *"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
            <select
              className="rounded-lg border px-3 py-2 text-sm"
              value={form.event_type}
              onChange={(e) => setForm({ ...form, event_type: e.target.value })}
            >
              {Object.entries(EVENT_TYPE_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            <input
              type="datetime-local"
              className="rounded-lg border px-3 py-2 text-sm"
              value={form.start_at}
              onChange={(e) => setForm({ ...form, start_at: e.target.value })}
            />
            <input
              className="rounded-lg border px-3 py-2 text-sm"
              placeholder="설명 (선택)"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </div>
          <button
            onClick={handleCreate}
            className="mt-3 rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            일정 생성
          </button>
        </div>
      )}

      {/* Timeline */}
      {sortedDates.length === 0 && (
        <p className="py-16 text-center text-gray-400">표시할 일정이 없습니다.</p>
      )}
      {sortedDates.map((date) => (
        <div key={date} className="mb-6">
          <h3 className="mb-2 text-sm font-semibold text-gray-500">
            {new Date(date + 'T00:00:00').toLocaleDateString('ko-KR', {
              year: 'numeric', month: 'long', day: 'numeric', weekday: 'short',
            })}
          </h3>
          <div className="space-y-2">
            {grouped[date].map((ev) => (
              <div
                key={ev.id}
                className={`flex items-center gap-3 rounded-xl border p-4 transition ${
                  ev.is_completed ? 'opacity-50' : ''
                } ${EVENT_TYPE_COLORS[ev.event_type] || EVENT_TYPE_COLORS.custom}`}
                style={ev.color ? { borderLeftColor: ev.color, borderLeftWidth: 4 } : undefined}
              >
                <button
                  onClick={() => toggleComplete(ev)}
                  className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border ${
                    ev.is_completed ? 'bg-green-500 text-white' : 'bg-white'
                  }`}
                >
                  {ev.is_completed && '✓'}
                </button>
                <div className="flex-1">
                  <p className={`text-sm font-medium ${ev.is_completed ? 'line-through' : ''}`}>
                    {ev.title}
                  </p>
                  <p className="text-xs opacity-70">
                    {new Date(ev.start_at).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}
                    {ev.end_at && ` ~ ${new Date(ev.end_at).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}`}
                    {' · '}{EVENT_TYPE_LABELS[ev.event_type] || ev.event_type}
                  </p>
                </div>
                {!ev.reference_type && (
                  <button
                    onClick={() => handleDelete(ev.id)}
                    className="text-xs text-red-400 hover:text-red-600"
                  >
                    삭제
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </main>
  );
}
