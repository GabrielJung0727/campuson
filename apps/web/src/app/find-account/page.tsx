'use client';

import { api, ApiError } from '@/lib/api';
import Link from 'next/link';
import { useState } from 'react';

type Tab = 'find-id' | 'reset-pw';
type ResetStep = 'request' | 'confirm' | 'done';

export default function FindAccountPage() {
  const [tab, setTab] = useState<Tab>('find-id');

  // Find ID
  const [findName, setFindName] = useState('');
  const [findStudentNo, setFindStudentNo] = useState('');
  const [findLoading, setFindLoading] = useState(false);
  const [foundEmail, setFoundEmail] = useState<string | null>(null);
  const [findError, setFindError] = useState('');

  // Reset PW
  const [resetEmail, setResetEmail] = useState('');
  const [resetStep, setResetStep] = useState<ResetStep>('request');
  const [resetToken, setResetToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newPasswordConfirm, setNewPasswordConfirm] = useState('');
  const [resetLoading, setResetLoading] = useState(false);
  const [resetMsg, setResetMsg] = useState('');
  const [resetError, setResetError] = useState('');

  async function handleFindEmail() {
    setFindError('');
    setFoundEmail(null);
    setFindLoading(true);
    try {
      const res = await api.findEmail({ name: findName, student_no: findStudentNo }) as { message: string };
      setFoundEmail(res.message);
    } catch (err) {
      setFindError(err instanceof ApiError ? err.detail : '조회에 실패했습니다.');
    } finally {
      setFindLoading(false);
    }
  }

  async function handleRequestReset() {
    setResetError('');
    setResetMsg('');
    setResetLoading(true);
    try {
      const res = await api.requestPasswordReset(resetEmail) as { message: string };
      setResetMsg(res.message);
      setResetStep('confirm');
    } catch (err) {
      setResetError(err instanceof ApiError ? err.detail : '요청에 실패했습니다.');
    } finally {
      setResetLoading(false);
    }
  }

  async function handleConfirmReset() {
    setResetError('');
    if (newPassword !== newPasswordConfirm) {
      setResetError('새 비밀번호가 일치하지 않습니다.');
      return;
    }
    if (newPassword.length < 8) {
      setResetError('비밀번호는 최소 8자 이상이어야 합니다.');
      return;
    }
    setResetLoading(true);
    try {
      await api.confirmPasswordReset({ token: resetToken, new_password: newPassword });
      setResetStep('done');
    } catch (err) {
      setResetError(err instanceof ApiError ? err.detail : '재설정에 실패했습니다.');
    } finally {
      setResetLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="mb-8 text-center">
          <Link href="/" className="text-2xl font-bold text-slate-900">
            Campus<span className="text-brand-600">ON</span>
          </Link>
          <p className="mt-2 text-sm text-slate-500">계정 찾기</p>
        </div>

        {/* Tab Switcher */}
        <div className="mb-6 flex rounded-xl border border-slate-200 bg-white p-1">
          <button
            onClick={() => { setTab('find-id'); setFindError(''); setFoundEmail(null); }}
            className={`flex-1 rounded-lg py-2.5 text-sm font-semibold transition ${
              tab === 'find-id'
                ? 'bg-brand-600 text-white shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            아이디 찾기
          </button>
          <button
            onClick={() => { setTab('reset-pw'); setResetError(''); setResetMsg(''); }}
            className={`flex-1 rounded-lg py-2.5 text-sm font-semibold transition ${
              tab === 'reset-pw'
                ? 'bg-brand-600 text-white shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            비밀번호 재설정
          </button>
        </div>

        {/* ===== FIND ID TAB ===== */}
        {tab === 'find-id' && (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="mb-1 text-lg font-bold text-slate-900">아이디(이메일) 찾기</h2>
            <p className="mb-5 text-xs text-slate-400">가입 시 등록한 이름과 학번으로 이메일을 찾습니다.</p>

            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-500">이름</label>
                <input
                  type="text"
                  value={findName}
                  onChange={(e) => setFindName(e.target.value)}
                  placeholder="홍길동"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-500">학번</label>
                <input
                  type="text"
                  value={findStudentNo}
                  onChange={(e) => setFindStudentNo(e.target.value)}
                  placeholder="2455025"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                />
              </div>

              {findError && (
                <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{findError}</div>
              )}

              {foundEmail && (
                <div className="rounded-lg bg-emerald-50 border border-emerald-200 px-4 py-3 text-center">
                  <p className="text-xs text-emerald-600 mb-1">등록된 이메일</p>
                  <p className="text-lg font-bold text-emerald-700">{foundEmail}</p>
                </div>
              )}

              <button
                onClick={handleFindEmail}
                disabled={findLoading || !findName || !findStudentNo}
                className="w-full rounded-lg bg-brand-600 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {findLoading ? '조회 중...' : '이메일 찾기'}
              </button>
            </div>
          </div>
        )}

        {/* ===== RESET PW TAB ===== */}
        {tab === 'reset-pw' && (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            {resetStep === 'request' && (
              <>
                <h2 className="mb-1 text-lg font-bold text-slate-900">비밀번호 재설정</h2>
                <p className="mb-5 text-xs text-slate-400">가입한 이메일 주소를 입력하면 재설정 토큰을 보내드립니다.</p>

                <div className="space-y-3">
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-500">이메일</label>
                    <input
                      type="email"
                      value={resetEmail}
                      onChange={(e) => setResetEmail(e.target.value)}
                      placeholder="email@kbu.ac.kr"
                      className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                    />
                  </div>

                  {resetError && (
                    <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{resetError}</div>
                  )}

                  <button
                    onClick={handleRequestReset}
                    disabled={resetLoading || !resetEmail}
                    className="w-full rounded-lg bg-brand-600 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {resetLoading ? '발송 중...' : '재설정 메일 발송'}
                  </button>
                </div>
              </>
            )}

            {resetStep === 'confirm' && (
              <>
                <h2 className="mb-1 text-lg font-bold text-slate-900">새 비밀번호 설정</h2>
                <p className="mb-5 text-xs text-slate-400">이메일로 수신한 토큰과 새 비밀번호를 입력하세요.</p>

                {resetMsg && (
                  <div className="mb-4 rounded-lg bg-blue-50 border border-blue-200 px-3 py-2 text-xs text-blue-700">
                    {resetMsg}
                  </div>
                )}

                <div className="space-y-3">
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-500">재설정 토큰</label>
                    <input
                      type="text"
                      value={resetToken}
                      onChange={(e) => setResetToken(e.target.value)}
                      placeholder="이메일에서 수신한 토큰 붙여넣기"
                      className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm font-mono focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-500">새 비밀번호</label>
                    <input
                      type="password"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder="8자 이상"
                      className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-500">비밀번호 확인</label>
                    <input
                      type="password"
                      value={newPasswordConfirm}
                      onChange={(e) => setNewPasswordConfirm(e.target.value)}
                      placeholder="다시 입력"
                      className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                    />
                  </div>

                  {resetError && (
                    <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{resetError}</div>
                  )}

                  <button
                    onClick={handleConfirmReset}
                    disabled={resetLoading || !resetToken || !newPassword || !newPasswordConfirm}
                    className="w-full rounded-lg bg-brand-600 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {resetLoading ? '처리 중...' : '비밀번호 변경'}
                  </button>

                  <button
                    onClick={() => { setResetStep('request'); setResetError(''); }}
                    className="w-full text-xs text-slate-400 hover:text-slate-600"
                  >
                    다시 이메일 입력하기
                  </button>
                </div>
              </>
            )}

            {resetStep === 'done' && (
              <div className="py-6 text-center">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100">
                  <svg className="h-7 w-7 text-emerald-600" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
                  </svg>
                </div>
                <h2 className="text-lg font-bold text-slate-900">비밀번호 변경 완료</h2>
                <p className="mt-1 text-sm text-slate-500">새 비밀번호로 로그인해주세요.</p>
                <Link
                  href="/login"
                  className="mt-6 inline-block rounded-lg bg-brand-600 px-8 py-2.5 text-sm font-semibold text-white hover:bg-brand-700"
                >
                  로그인하기
                </Link>
              </div>
            )}
          </div>
        )}

        {/* Bottom link */}
        <div className="mt-6 text-center text-sm text-slate-400">
          <Link href="/login" className="text-brand-600 hover:underline">
            로그인으로 돌아가기
          </Link>
        </div>
      </div>
    </main>
  );
}
