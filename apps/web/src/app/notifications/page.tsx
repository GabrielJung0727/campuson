'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';

interface Notification {
  id: string;
  category: string;
  title: string;
  message: string;
  link: string | null;
  is_read: boolean;
  created_at: string;
}

const CATEGORY_ICON: Record<string, string> = {
  ASSIGNMENT_DUE: '📝',
  DIAGNOSTIC_REMINDER: '🧪',
  PROFESSOR_FEEDBACK: '💬',
  WEAK_AREA_REVIEW: '📚',
  PRACTICUM_SCHEDULE: '🏥',
  ANNOUNCEMENT: '📢',
  KB_UPDATE: '📖',
  SYSTEM: '⚙️',
};

const CATEGORY_LABEL: Record<string, string> = {
  ASSIGNMENT_DUE: '과제',
  DIAGNOSTIC_REMINDER: '진단 테스트',
  PROFESSOR_FEEDBACK: '피드백',
  WEAK_AREA_REVIEW: '복습 추천',
  PRACTICUM_SCHEDULE: '실습 일정',
  ANNOUNCEMENT: '공지사항',
  KB_UPDATE: '자료 업데이트',
  SYSTEM: '시스템',
};

export default function NotificationsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [filter, setFilter] = useState<'all' | 'unread'>('all');
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const params = filter === 'unread' ? '?unread_only=true' : '';
      const data: any = await api.getNotifications(params);
      setNotifications(data.items || []);
      setUnreadCount(data.unread_count || 0);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!user) { router.push('/login'); return; }
    load();
  }, [user, filter]);

  const handleRead = async (id: string, link: string | null) => {
    await api.markNotificationRead(id).catch(() => {});
    setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
    setUnreadCount(prev => Math.max(0, prev - 1));
    if (link) router.push(link);
  };

  const handleReadAll = async () => {
    await api.markAllNotificationsRead().catch(() => {});
    setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
    setUnreadCount(0);
  };

  const handleDelete = async (id: string) => {
    await api.deleteNotification(id).catch(() => {});
    setNotifications(prev => prev.filter(n => n.id !== id));
  };

  const timeAgo = (dateStr: string) => {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return '방금';
    if (mins < 60) return `${mins}분 전`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}시간 전`;
    const days = Math.floor(hours / 24);
    return `${days}일 전`;
  };

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">알림</h1>
            {unreadCount > 0 && (
              <p className="text-sm text-brand-600 mt-1">읽지 않은 알림 {unreadCount}개</p>
            )}
          </div>
          <div className="flex gap-2">
            {unreadCount > 0 && (
              <button
                onClick={handleReadAll}
                className="text-sm text-brand-600 hover:underline"
              >모두 읽음</button>
            )}
            <button onClick={() => router.push('/dashboard')} className="text-sm text-slate-500 hover:underline">&larr; 돌아가기</button>
          </div>
        </div>

        {/* Filter */}
        <div className="flex gap-2 mb-4">
          {(['all', 'unread'] as const).map(f => (
            <button
              key={f}
              onClick={() => { setFilter(f); setLoading(true); }}
              className={`px-3 py-1 rounded-full text-sm ${
                filter === f
                  ? 'bg-brand-600 text-white'
                  : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
              }`}
            >{f === 'all' ? '전체' : '읽지 않음'}</button>
          ))}
        </div>

        {/* List */}
        {loading ? (
          <div className="text-center text-slate-400 py-8">로딩 중...</div>
        ) : notifications.length === 0 ? (
          <div className="text-center text-slate-400 py-12 bg-white rounded-xl border border-slate-200">
            {filter === 'unread' ? '읽지 않은 알림이 없습니다.' : '알림이 없습니다.'}
          </div>
        ) : (
          <div className="space-y-2">
            {notifications.map(n => (
              <div
                key={n.id}
                className={`bg-white rounded-xl border p-4 transition cursor-pointer hover:shadow-sm ${
                  n.is_read ? 'border-slate-200' : 'border-brand-300 bg-brand-50/30'
                }`}
                onClick={() => handleRead(n.id, n.link)}
              >
                <div className="flex items-start gap-3">
                  <span className="text-xl mt-0.5">{CATEGORY_ICON[n.category] || '📌'}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-semibold ${n.is_read ? 'text-slate-700' : 'text-slate-900'}`}>
                        {n.title}
                      </span>
                      {!n.is_read && <span className="w-2 h-2 rounded-full bg-brand-500 flex-shrink-0" />}
                    </div>
                    <p className="text-sm text-slate-500 mt-0.5 line-clamp-2">{n.message}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs text-slate-400">{timeAgo(n.created_at)}</span>
                      <span className="text-xs px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                        {CATEGORY_LABEL[n.category] || n.category}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDelete(n.id); }}
                    className="text-slate-300 hover:text-red-400 text-sm p-1"
                  >&times;</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
