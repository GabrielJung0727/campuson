import Link from 'next/link';

const DEPARTMENTS = [
  {
    name: '간호학과',
    eng: 'Nursing',
    desc: '간호사 국가시험 대비 핵심 이론과 실기를 AI가 분석하여 맞춤형 학습을 제공합니다.',
    color: 'bg-cyan-500',
    light: 'bg-cyan-50',
    text: 'text-cyan-600',
    icon: (
      <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12Z" />
      </svg>
    ),
  },
  {
    name: '치위생과',
    eng: 'Dental Hygiene',
    desc: '치과위생사 국가시험 출제 경향을 분석하고 취약 영역을 집중 보강합니다.',
    color: 'bg-violet-500',
    light: 'bg-violet-50',
    text: 'text-violet-600',
    icon: (
      <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 0 0-2.455 2.456Z" />
      </svg>
    ),
  },
  {
    name: '물리치료학과',
    eng: 'Physical Therapy',
    desc: '물리치료사 국가시험의 해부학, 운동치료학 등 전 과목을 체계적으로 학습합니다.',
    color: 'bg-emerald-500',
    light: 'bg-emerald-50',
    text: 'text-emerald-600',
    icon: (
      <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" />
      </svg>
    ),
  },
];

const FEATURES = [
  {
    title: '진단 테스트',
    desc: 'AI가 현재 학습 수준을 정밀 분석하여 개인별 학습 프로필을 생성합니다.',
    icon: (
      <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 0 0 2.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 0 0-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75 2.25 2.25 0 0 0-.1-.664m-5.8 0A2.251 2.251 0 0 1 13.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25Z" />
      </svg>
    ),
  },
  {
    title: 'AI 튜터',
    desc: '모르는 문제를 질문하면 RAG 기반 지식검색으로 정확한 해설을 제공합니다.',
    icon: (
      <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z" />
      </svg>
    ),
  },
  {
    title: '맞춤형 추천',
    desc: '오답 패턴과 학습 이력을 분석하여 취약 영역 중심으로 문제를 추천합니다.',
    icon: (
      <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 0 0 6 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0 1 18 16.5h-2.25m-7.5 0h7.5m-7.5 0-1 3m8.5-3 1 3m0 0 .5 1.5m-.5-1.5h-9.5m0 0-.5 1.5m.75-9 3-3 2.148 2.148A12.061 12.061 0 0 1 16.5 7.605" />
      </svg>
    ),
  },
  {
    title: '학습 분석',
    desc: '전체 응시자 대비 백분위, 과목별 정답률, 학습 추이를 한눈에 확인합니다.',
    icon: (
      <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
      </svg>
    ),
  },
];

const STATS = [
  { value: '3', label: '보건 학과', suffix: '개' },
  { value: '1,000', label: '국시 기출문제', suffix: '+' },
  { value: 'AI', label: '실시간 튜터링', suffix: '' },
  { value: '24/7', label: '언제 어디서든', suffix: '' },
];

export default function Home() {
  return (
    <div className="min-h-screen">
      {/* ===== HERO ===== */}
      <section className="relative overflow-hidden bg-slate-950">
        {/* Background effects */}
        <div className="dot-pattern absolute inset-0" />
        <div className="hero-glow absolute -top-40 left-1/2 -translate-x-1/2 bg-sky-500" />
        <div className="hero-glow absolute top-1/2 -left-20 bg-violet-600" style={{ width: 400, height: 400 }} />
        <div className="hero-glow absolute top-1/3 -right-20 bg-cyan-500" style={{ width: 350, height: 350 }} />

        {/* Nav */}
        <nav className="relative z-10 mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/10 backdrop-blur-sm border border-white/10">
              <span className="text-sm font-black text-white">C</span>
            </div>
            <span className="text-lg font-bold text-white tracking-tight">
              Campus<span className="text-sky-400">ON</span>
            </span>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/login"
              className="rounded-lg px-5 py-2 text-sm font-medium text-slate-300 transition hover:text-white"
            >
              로그인
            </Link>
            <Link
              href="/register"
              className="rounded-lg bg-white px-5 py-2 text-sm font-semibold text-slate-900 transition hover:bg-slate-100"
            >
              시작하기
            </Link>
          </div>
        </nav>

        {/* Hero content */}
        <div className="relative z-10 mx-auto max-w-4xl px-6 pb-28 pt-20 text-center">
          <div className="animate-fade-in-up">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 backdrop-blur-sm">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-xs font-medium text-slate-300 tracking-wide">경복대학교 보건계열 전용</span>
            </div>
          </div>

          <h1 className="animate-fade-in-up delay-100 text-5xl font-extrabold leading-tight tracking-tight text-white sm:text-6xl lg:text-7xl">
            국가고시,{' '}
            <span className="bg-gradient-to-r from-sky-400 via-cyan-300 to-emerald-400 bg-clip-text text-transparent">
              AI와 함께
            </span>{' '}
            준비하세요
          </h1>

          <p className="animate-fade-in-up delay-200 mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-slate-400">
            진단 테스트로 현재 수준을 파악하고, RAG 기반 AI 튜터가
            <br className="hidden sm:block" />
            취약 영역을 집중 보강하여 합격까지 함께합니다.
          </p>

          <div className="animate-fade-in-up delay-300 mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
            <Link
              href="/register"
              className="group relative inline-flex items-center gap-2 rounded-xl bg-white px-8 py-3.5 text-sm font-bold text-slate-900 shadow-lg shadow-white/10 transition hover:shadow-white/20 hover:scale-[1.02]"
            >
              무료로 시작하기
              <svg className="h-4 w-4 transition group-hover:translate-x-0.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
              </svg>
            </Link>
            <Link
              href="/login"
              className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/5 px-8 py-3.5 text-sm font-semibold text-white backdrop-blur-sm transition hover:bg-white/10"
            >
              기존 계정 로그인
            </Link>
          </div>
        </div>

        {/* Bottom fade */}
        <div className="absolute bottom-0 left-0 right-0 h-24 bg-gradient-to-t from-white to-transparent" />
      </section>

      {/* ===== DEPARTMENTS ===== */}
      <section className="bg-white py-24">
        <div className="mx-auto max-w-6xl px-6">
          <div className="text-center">
            <p className="text-sm font-semibold uppercase tracking-widest text-brand-600">Departments</p>
            <h2 className="mt-2 text-3xl font-bold tracking-tight text-slate-900">
              3개 보건계열 학과 지원
            </h2>
            <p className="mt-3 text-base text-slate-500">
              각 학과 국가시험에 최적화된 AI 학습 커리큘럼을 제공합니다
            </p>
          </div>

          <div className="mt-14 grid gap-6 md:grid-cols-3">
            {DEPARTMENTS.map((dept) => (
              <div
                key={dept.eng}
                className="group relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition-all hover:shadow-lg hover:-translate-y-1"
              >
                {/* Top color bar */}
                <div className={`absolute top-0 left-0 right-0 h-1 ${dept.color}`} />

                <div className={`inline-flex items-center justify-center rounded-xl ${dept.light} p-3 ${dept.text}`}>
                  {dept.icon}
                </div>
                <h3 className="mt-4 text-lg font-bold text-slate-900">{dept.name}</h3>
                <p className="mt-0.5 text-xs font-medium uppercase tracking-wider text-slate-400">{dept.eng}</p>
                <p className="mt-3 text-sm leading-relaxed text-slate-500">{dept.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ===== FEATURES ===== */}
      <section className="bg-slate-50 py-24">
        <div className="mx-auto max-w-6xl px-6">
          <div className="text-center">
            <p className="text-sm font-semibold uppercase tracking-widest text-brand-600">Features</p>
            <h2 className="mt-2 text-3xl font-bold tracking-tight text-slate-900">
              AI 기반 스마트 학습
            </h2>
            <p className="mt-3 text-base text-slate-500">
              단순 문제풀이를 넘어, 진짜 학습이 되는 시스템
            </p>
          </div>

          <div className="mt-14 grid gap-6 sm:grid-cols-2">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="group rounded-2xl border border-slate-200 bg-white p-6 transition-all hover:border-brand-200 hover:shadow-md"
              >
                <div className="inline-flex items-center justify-center rounded-xl bg-brand-50 p-3 text-brand-600 group-hover:bg-brand-600 group-hover:text-white transition-colors">
                  {f.icon}
                </div>
                <h3 className="mt-4 text-base font-bold text-slate-900">{f.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-500">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ===== STATS ===== */}
      <section className="bg-slate-950 py-20">
        <div className="mx-auto max-w-6xl px-6">
          <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
            {STATS.map((s) => (
              <div key={s.label} className="text-center">
                <div className="text-4xl font-extrabold text-white sm:text-5xl">
                  {s.value}
                  {s.suffix && <span className="text-sky-400">{s.suffix}</span>}
                </div>
                <p className="mt-2 text-sm text-slate-400">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ===== CTA ===== */}
      <section className="bg-white py-24">
        <div className="mx-auto max-w-3xl px-6 text-center">
          <h2 className="text-3xl font-bold tracking-tight text-slate-900">
            합격을 향한 첫걸음,<br />
            지금 시작하세요
          </h2>
          <p className="mt-4 text-base text-slate-500">
            회원가입 후 진단 테스트를 응시하면 AI가 맞춤형 학습을 제안합니다.
          </p>
          <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
            <Link
              href="/register"
              className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-8 py-3.5 text-sm font-bold text-white shadow-lg shadow-brand-600/20 transition hover:bg-brand-700 hover:shadow-brand-700/30"
            >
              무료 회원가입
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
              </svg>
            </Link>
          </div>
        </div>
      </section>

      {/* ===== FOOTER ===== */}
      <footer className="border-t border-slate-200 bg-white py-8">
        <div className="mx-auto max-w-6xl px-6">
          <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-900">
                <span className="text-xs font-black text-white">C</span>
              </div>
              <span className="text-sm font-bold text-slate-900">
                Campus<span className="text-brand-600">ON</span>
              </span>
            </div>
            <p className="text-xs text-slate-400">
              경복대학교 보건계열 AI 학습튜터링 플랫폼 &copy; 2026
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
