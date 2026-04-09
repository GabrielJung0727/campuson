export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-6 py-24">
      <div className="mx-auto max-w-2xl text-center">
        <p className="mb-2 text-sm font-semibold uppercase tracking-wider text-brand-600">
          경복대학교 · 보건계열
        </p>
        <h1 className="mb-6 text-5xl font-bold tracking-tight text-slate-900">
          🎓 CampusON
        </h1>
        <p className="mb-8 text-lg leading-relaxed text-slate-600">
          진단 테스트와 RAG 기반 지식베이스를 활용한
          <br />
          <span className="font-semibold text-slate-900">국가고시 대비 AI 학습튜터링 플랫폼</span>
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

        <div className="rounded-xl border border-sky-200 bg-sky-50 p-4 text-left">
          <p className="text-xs font-semibold uppercase tracking-wider text-sky-700">
            ✅ Day 3 — Question Bank
          </p>
          <p className="mt-1 text-sm text-sky-900">
            QuestionBank 테이블 + CRUD/필터/태그 검색 + CSV 일괄 업로드 완료.
            샘플 200문항 시드(간호 80, 물치 60, 치위생 60). Day 4부터 진단 테스트가 추가됩니다.
          </p>
        </div>
      </div>
    </main>
  );
}
