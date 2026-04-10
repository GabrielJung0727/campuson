import Link from 'next/link';

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-6 py-24">
      <div className="mx-auto max-w-2xl text-center">
        <p className="mb-2 text-sm font-semibold uppercase tracking-wider text-brand-600">
          경복대학교 · 보건계열
        </p>
        <h1 className="mb-6 text-5xl font-bold tracking-tight text-slate-900">
          CampusON
        </h1>
        <p className="mb-8 text-lg leading-relaxed text-slate-600">
          진단 테스트와 RAG 기반 지식베이스를 활용한
          <br />
          <span className="font-semibold text-slate-900">
            국가고시 대비 AI 학습튜터링 플랫폼
          </span>
        </p>

        <div className="mb-12 grid grid-cols-3 gap-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="text-2xl">🩺</div>
            <div className="mt-2 text-sm font-medium">간호학과</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="text-2xl">🦴</div>
            <div className="mt-2 text-sm font-medium">물리치료학과</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="text-2xl">🦷</div>
            <div className="mt-2 text-sm font-medium">치위생과</div>
          </div>
        </div>

        <div className="mb-6 flex gap-3 justify-center">
          <Link
            href="/login"
            className="rounded-lg bg-brand-600 px-8 py-3 text-sm font-semibold text-white hover:bg-brand-700"
          >
            로그인
          </Link>
          <Link
            href="/register"
            className="rounded-lg border border-brand-600 px-8 py-3 text-sm font-semibold text-brand-600 hover:bg-brand-50"
          >
            회원가입
          </Link>
        </div>

        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-left">
          <p className="text-xs font-semibold uppercase tracking-wider text-emerald-700">
            Day 13 — Week 2 거의 완료!
          </p>
          <p className="mt-1 text-sm text-emerald-900">
            RAG 기반 QA/해설 + 추천 엔진 + 하이브리드 검색 + 프론트엔드 8개 페이지
            (로그인/가입/대시보드/진단/문제풀이/AI채팅/오답노트/리포트/관리자) 완료.
          </p>
        </div>
      </div>
    </main>
  );
}
