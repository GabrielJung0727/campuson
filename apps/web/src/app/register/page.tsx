'use client';

import { FormEvent, useRef, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { apiFetch, setTokens } from '@/lib/api';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

const DEPARTMENTS = [
  { value: 'NURSING', label: '간호학과' },
  { value: 'PHYSICAL_THERAPY', label: '물리치료학과' },
  { value: 'DENTAL_HYGIENE', label: '치위생과' },
];

type Phase = 'form' | 'verify';

export default function RegisterPage() {
  const router = useRouter();
  const { login } = useAuth();

  // --- Phase 1: 회원가입 폼 ---
  const [phase, setPhase] = useState<Phase>('form');
  const [form, setForm] = useState({
    email: '',
    password: '',
    name: '',
    department: 'NURSING',
    student_no: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // --- Phase 2: 인증코드 ---
  const [verifyEmail, setVerifyEmail] = useState('');
  const [code, setCode] = useState(['', '', '', '', '', '']);
  const [resending, setResending] = useState(false);
  const [resendMsg, setResendMsg] = useState('');
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  function update(key: string, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  // === Step 1: 회원가입 제출 ===
  async function handleRegister(e: FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const data = (await apiFetch('/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          ...form,
          role: 'STUDENT',
          student_no: form.student_no || null,
        }),
      })) as Record<string, unknown>;

      // SMTP 비활성 + 개발환경이면 바로 토큰 응답
      if (data.access_token) {
        setTokens(data.access_token as string, data.refresh_token as string);
        localStorage.setItem('user', JSON.stringify(data.user));
        router.push('/dashboard');
        return;
      }

      // 인증코드 발송됨 → Phase 2
      setVerifyEmail(form.email);
      setPhase('verify');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '회원가입에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }

  // === Step 2: 인증코드 입력 (6자리 개별 input) ===
  function handleCodeChange(index: number, value: string) {
    if (!/^\d*$/.test(value)) return; // 숫자만
    const next = [...code];
    next[index] = value.slice(-1); // 1자리만
    setCode(next);

    // 자동 포커스 이동
    if (value && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
  }

  function handleCodeKeyDown(index: number, e: React.KeyboardEvent) {
    if (e.key === 'Backspace' && !code[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  }

  function handleCodePaste(e: React.ClipboardEvent) {
    e.preventDefault();
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (pasted.length === 6) {
      setCode(pasted.split(''));
      inputRefs.current[5]?.focus();
    }
  }

  async function handleVerify(e: FormEvent) {
    e.preventDefault();
    const codeStr = code.join('');
    if (codeStr.length !== 6) {
      setError('6자리 인증코드를 모두 입력해주세요.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      const data = (await apiFetch('/auth/verify-email', {
        method: 'POST',
        body: JSON.stringify({ email: verifyEmail, code: codeStr }),
      })) as Record<string, unknown>;

      setTokens(data.access_token as string, data.refresh_token as string);
      localStorage.setItem('user', JSON.stringify(data.user));
      router.push('/dashboard');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '인증에 실패했습니다.');
      setCode(['', '', '', '', '', '']);
      inputRefs.current[0]?.focus();
    } finally {
      setLoading(false);
    }
  }

  async function handleResend() {
    setResending(true);
    setResendMsg('');
    setError('');
    try {
      const data = (await apiFetch('/auth/resend-verification', {
        method: 'POST',
        body: JSON.stringify({ email: verifyEmail }),
      })) as { message: string };
      setResendMsg(data.message);
      setCode(['', '', '', '', '', '']);
      inputRefs.current[0]?.focus();
    } catch {
      setResendMsg('재발송에 실패했습니다. 잠시 후 다시 시도해주세요.');
    } finally {
      setResending(false);
    }
  }

  // === Render: Phase 2 (인증코드 입력) ===
  if (phase === 'verify') {
    return (
      <main className="flex min-h-screen items-center justify-center px-4 py-12">
        <div className="w-full max-w-md">
          <div className="mb-8 text-center">
            <h1 className="text-3xl font-bold">CampusON</h1>
            <p className="mt-2 text-sm text-slate-500">이메일 인증</p>
          </div>

          <form
            onSubmit={handleVerify}
            className="space-y-6 rounded-xl border border-slate-200 bg-white p-8 shadow-sm"
          >
            {/* 안내 */}
            <div className="text-center">
              <div className="mb-3 inline-flex h-16 w-16 items-center justify-center rounded-full bg-brand-100">
                <span className="text-3xl">📧</span>
              </div>
              <h2 className="text-lg font-semibold">인증코드를 입력해주세요</h2>
              <p className="mt-2 text-sm text-slate-500">
                <span className="font-medium text-slate-700">{verifyEmail}</span>
                <br />
                으로 6자리 인증코드를 보냈습니다.
              </p>
            </div>

            {error && (
              <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>
            )}
            {resendMsg && (
              <div className="rounded-lg bg-blue-50 p-3 text-sm text-blue-700">{resendMsg}</div>
            )}

            {/* 6자리 코드 입력 */}
            <div className="flex justify-center gap-2" onPaste={handleCodePaste}>
              {code.map((digit, i) => (
                <input
                  key={i}
                  ref={(el) => { inputRefs.current[i] = el; }}
                  type="text"
                  inputMode="numeric"
                  maxLength={1}
                  value={digit}
                  onChange={(e) => handleCodeChange(i, e.target.value)}
                  onKeyDown={(e) => handleCodeKeyDown(i, e)}
                  className="h-14 w-12 rounded-xl border-2 border-slate-300 text-center text-2xl font-bold text-slate-900 transition focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
                  autoFocus={i === 0}
                />
              ))}
            </div>

            <button
              type="submit"
              disabled={loading || code.join('').length !== 6}
              className="w-full rounded-lg bg-brand-600 py-3 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {loading ? '인증 중...' : '인증 완료'}
            </button>

            {/* 재발송 */}
            <div className="text-center">
              <p className="mb-2 text-xs text-slate-400">
                코드가 오지 않았나요? (10분 이내 유효)
              </p>
              <button
                type="button"
                onClick={handleResend}
                disabled={resending}
                className="text-sm font-semibold text-brand-600 hover:underline disabled:opacity-50"
              >
                {resending ? '발송 중...' : '인증코드 재발송'}
              </button>
            </div>

            <p className="text-center text-xs text-slate-400">
              다른 이메일로 가입하시겠어요?{' '}
              <button
                type="button"
                onClick={() => {
                  setPhase('form');
                  setError('');
                  setCode(['', '', '', '', '', '']);
                }}
                className="font-semibold text-brand-600 hover:underline"
              >
                처음부터
              </button>
            </p>
          </form>
        </div>
      </main>
    );
  }

  // === Render: Phase 1 (회원가입 폼) ===
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold">CampusON</h1>
          <p className="mt-2 text-sm text-slate-500">학생 회원가입</p>
        </div>

        <form
          onSubmit={handleRegister}
          className="space-y-4 rounded-xl border border-slate-200 bg-white p-8 shadow-sm"
        >
          <h2 className="text-xl font-semibold">회원가입</h2>

          {error && (
            <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>
          )}

          <div>
            <label className="mb-1 block text-sm font-medium">이름</label>
            <input
              type="text"
              required
              value={form.name}
              onChange={(e) => update('name', e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              placeholder="홍길동"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium">이메일</label>
            <input
              type="email"
              required
              value={form.email}
              onChange={(e) => update('email', e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              placeholder="student@kbu.ac.kr"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium">비밀번호</label>
            <input
              type="password"
              required
              minLength={8}
              value={form.password}
              onChange={(e) => update('password', e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              placeholder="영문 + 숫자 8자 이상"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium">학과</label>
            <select
              value={form.department}
              onChange={(e) => update('department', e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
              {DEPARTMENTS.map((d) => (
                <option key={d.value} value={d.value}>
                  {d.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium">학번</label>
            <input
              type="text"
              required
              value={form.student_no}
              onChange={(e) => update('student_no', e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              placeholder="24001234"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-brand-600 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {loading ? '가입 중...' : '회원가입'}
          </button>

          <p className="text-center text-sm text-slate-500">
            이미 계정이 있으신가요?{' '}
            <Link href="/login" className="font-semibold text-brand-600 hover:underline">
              로그인
            </Link>
          </p>
        </form>
      </div>
    </main>
  );
}
