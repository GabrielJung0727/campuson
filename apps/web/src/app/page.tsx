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

        <div className="rounded-xl border border-purple-200 bg-purple-50 p-4 text-left">
          <p className="text-xs font-semibold uppercase tracking-wider text-purple-700">
            ✅ Day 8 — Vector DB & Embeddings
          </p>
          <p className="mt-1 text-sm text-purple-900">
            pgvector 기반 KBDocument/KBChunk 스키마 + HNSW 인덱스 + OpenAI/Mock 임베딩 Gateway +
            문단 기반 오버랩 청킹 전략 + KB 적재 파이프라인 완료. Day 9부터 실제 지식베이스 적재 시작.
          </p>
        </div>
      </div>
    </main>
  );
}
