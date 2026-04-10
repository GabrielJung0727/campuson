'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api, apiFetch } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

interface UserItem {
  id: string;
  email: string;
  name: string;
  department: string;
  role: string;
  status: string;
  student_no: string | null;
  created_at: string;
}

const DEPT_LABEL: Record<string, string> = {
  NURSING: '간호학과',
  PHYSICAL_THERAPY: '물리치료학과',
  DENTAL_HYGIENE: '치위생과',
};

const ROLE_LABEL: Record<string, string> = {
  STUDENT: '학생',
  PROFESSOR: '교수',
  ADMIN: '관리자',
  DEVELOPER: '개발자',
};

export default function AdminPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [users, setUsers] = useState<UserItem[]>([]);
  const [tab, setTab] = useState<'users' | 'stats'>('users');

  useEffect(() => {
    if (!loading && !user) router.push('/login');
    if (!loading && user && !['PROFESSOR', 'ADMIN', 'DEVELOPER'].includes(user.role)) {
      router.push('/dashboard');
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (user && ['PROFESSOR', 'ADMIN', 'DEVELOPER'].includes(user.role)) {
      apiFetch<UserItem[]>('/users')
        .then(setUsers)
        .catch(() => {});
    }
  }, [user]);

  if (loading || !user) return <div className="p-8 text-center">Loading...</div>;

  const isProfessor = user.role === 'PROFESSOR';
  const filteredUsers = isProfessor
    ? users.filter((u) => u.department === user.department)
    : users;

  const studentCount = filteredUsers.filter((u) => u.role === 'STUDENT').length;

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">
            {isProfessor ? '학과 대시보드' : '관리자 대시보드'}
          </h1>
          <p className="text-sm text-slate-500">
            {isProfessor
              ? `${DEPT_LABEL[user.department]} 학생 관리`
              : '전체 시스템 운영'}
          </p>
        </div>
        <button onClick={() => router.push('/dashboard')} className="text-sm text-slate-500">
          ← 대시보드
        </button>
      </div>

      {/* Summary */}
      <div className="mb-6 grid grid-cols-3 gap-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-center">
          <div className="text-2xl font-bold text-brand-600">{studentCount}</div>
          <div className="text-xs text-slate-500">학생 수</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-center">
          <div className="text-2xl font-bold">{filteredUsers.length}</div>
          <div className="text-xs text-slate-500">전체 사용자</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-center">
          <div className="text-2xl font-bold text-emerald-600">
            {filteredUsers.filter((u) => u.status === 'ACTIVE').length}
          </div>
          <div className="text-xs text-slate-500">활성 계정</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="mb-4 flex gap-2 border-b border-slate-200 pb-2">
        {(['users', 'stats'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm ${
              tab === t ? 'border-b-2 border-brand-600 font-semibold text-brand-600' : 'text-slate-500'
            }`}
          >
            {t === 'users' ? '사용자 목록' : '통계'}
          </button>
        ))}
      </div>

      {/* User list */}
      {tab === 'users' && (
        <div className="rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs text-slate-500">
                <th className="px-4 py-3">이름</th>
                <th className="px-4 py-3">이메일</th>
                <th className="px-4 py-3">학과</th>
                <th className="px-4 py-3">역할</th>
                <th className="px-4 py-3">학번</th>
                <th className="px-4 py-3">상태</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map((u) => (
                <tr
                  key={u.id}
                  className="border-b border-slate-100 hover:bg-slate-50 cursor-pointer"
                  onClick={() => {
                    if (u.role === 'STUDENT') {
                      router.push(`/admin/student/${u.id}`);
                    }
                  }}
                >
                  <td className="px-4 py-3 font-medium">{u.name}</td>
                  <td className="px-4 py-3 text-slate-500">{u.email}</td>
                  <td className="px-4 py-3">{DEPT_LABEL[u.department] || u.department}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded px-2 py-0.5 text-xs ${
                        u.role === 'STUDENT'
                          ? 'bg-blue-50 text-blue-700'
                          : u.role === 'PROFESSOR'
                            ? 'bg-purple-50 text-purple-700'
                            : 'bg-amber-50 text-amber-700'
                      }`}
                    >
                      {ROLE_LABEL[u.role] || u.role}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">{u.student_no || '-'}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded px-2 py-0.5 text-xs ${
                        u.status === 'ACTIVE'
                          ? 'bg-emerald-50 text-emerald-700'
                          : 'bg-red-50 text-red-700'
                      }`}
                    >
                      {u.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filteredUsers.length === 0 && (
            <div className="p-8 text-center text-slate-400">사용자가 없습니다.</div>
          )}
        </div>
      )}

      {tab === 'stats' && (
        <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-400">
          학과별 통계 대시보드는 Day 14에서 시각화 차트와 함께 확장됩니다.
          <br />
          현재는 사용자 목록 → 학생 클릭 → 개별 학습 통계 조회가 가능합니다.
        </div>
      )}
    </main>
  );
}
