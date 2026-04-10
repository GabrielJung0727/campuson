'use client';

import { api } from '@/lib/api';
import { useEffect, useState } from 'react';

interface Ann {
  id: string;
  title: string;
  content: string;
  announcement_type: string;
  target_audience: string;
}

export function AnnouncementBanner() {
  const [urgent, setUrgent] = useState<Ann | null>(null);

  useEffect(() => {
    api.getAnnouncements()
      .then((data: unknown) => {
        const list = data as Ann[];
        const u = list.find((a) => a.announcement_type === 'URGENT' || a.announcement_type === 'MAINTENANCE');
        setUrgent(u || null);
      })
      .catch(() => {});
  }, []);

  if (!urgent) return null;

  const isMaintenance = urgent.announcement_type === 'MAINTENANCE';
  return (
    <div
      className={`px-4 py-2 text-center text-sm font-medium ${
        isMaintenance
          ? 'bg-amber-500 text-white'
          : 'bg-red-600 text-white'
      }`}
    >
      {isMaintenance ? '🔧' : '🚨'} {urgent.title}
      {urgent.content && (
        <span className="ml-2 font-normal opacity-90">— {urgent.content.slice(0, 100)}</span>
      )}
    </div>
  );
}

export function AnnouncementFooter() {
  const [announcements, setAnnouncements] = useState<Ann[]>([]);
  const [current, setCurrent] = useState(0);

  useEffect(() => {
    api.getAnnouncements()
      .then((data: unknown) => {
        const list = (data as Ann[]).filter((a) => a.announcement_type === 'GENERAL');
        setAnnouncements(list);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (announcements.length <= 1) return;
    const timer = setInterval(() => {
      setCurrent((c) => (c + 1) % announcements.length);
    }, 5000);
    return () => clearInterval(timer);
  }, [announcements.length]);

  if (announcements.length === 0) return null;

  const ann = announcements[current];
  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 border-t border-slate-200 bg-white px-4 py-2">
      <div className="mx-auto flex max-w-4xl items-center justify-between text-xs text-slate-600">
        <span>
          📢 <strong>{ann.title}</strong>
          <span className="ml-2 text-slate-400">{ann.content.slice(0, 80)}</span>
        </span>
        {announcements.length > 1 && (
          <span className="text-slate-400">{current + 1}/{announcements.length}</span>
        )}
      </div>
    </div>
  );
}
