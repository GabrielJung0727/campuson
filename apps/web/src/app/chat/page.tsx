'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { FormEvent, useEffect, useRef, useState } from 'react';

interface ContentWarning {
  pattern_name: string;
  matched_text: string;
  severity: 'info' | 'warning' | 'critical';
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  citations?: Array<{ number: number; document_title: string; snippet: string; source?: string }>;
  metadata?: { latency_ms: number; provider: string; rag_used: boolean };
  confidence?: string;
  content_warnings?: ContentWarning[];
  disclaimer?: string;
}

export default function ChatPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function handleSend(e: FormEvent) {
    e.preventDefault();
    if (!input.trim() || sending) return;

    const userMsg: Message = { role: 'user', content: input.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setSending(true);

    try {
      const data = (await api.aiQA(userMsg.content)) as {
        output_text: string;
        citations: Array<{ number: number; document_title: string; snippet: string; source?: string }>;
        metadata: { latency_ms: number; provider: string };
        rag_used: boolean;
        confidence: string;
        content_warnings: ContentWarning[];
        disclaimer: string;
      };
      const assistantMsg: Message = {
        role: 'assistant',
        content: data.output_text,
        citations: data.citations,
        metadata: {
          latency_ms: data.metadata.latency_ms,
          provider: data.metadata.provider,
          rag_used: data.rag_used,
        },
        confidence: data.confidence,
        content_warnings: data.content_warnings,
        disclaimer: data.disclaimer,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `오류가 발생했습니다: ${err instanceof Error ? err.message : '알 수 없는 오류'}` },
      ]);
    } finally {
      setSending(false);
    }
  }

  if (loading) return <div className="p-8 text-center">로딩 중...</div>;

  return (
    <main className="mx-auto flex h-screen max-w-3xl flex-col px-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 py-4">
        <div>
          <h1 className="text-lg font-bold">AI 튜터</h1>
          <p className="text-xs text-slate-500">국가고시 대비 질의응답</p>
        </div>
        <button
          onClick={() => router.push('/dashboard')}
          className="text-sm text-slate-500 hover:text-slate-700"
        >
          ← 대시보드
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto py-4">
        {messages.length === 0 && (
          <div className="mt-20 text-center text-sm text-slate-400">
            <p className="mb-4 text-4xl">💬</p>
            <p>궁금한 것을 자유롭게 물어보세요.</p>
            <p className="mt-1 text-xs">예: "심방세동의 간호 중재를 알려주세요"</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`mb-4 ${msg.role === 'user' ? 'text-right' : 'text-left'}`}
          >
            <div
              className={`inline-block max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-brand-600 text-white'
                  : 'border border-slate-200 bg-white text-slate-800'
              }`}
            >
              <div className="whitespace-pre-wrap">{msg.content}</div>

              {/* Content Warnings (v0.5) */}
              {msg.content_warnings && msg.content_warnings.length > 0 && (
                <div className="mt-2 space-y-1">
                  {msg.content_warnings.filter(w => w.severity !== 'info').map((w, wi) => (
                    <div
                      key={wi}
                      className={`rounded px-2 py-1 text-xs ${
                        w.severity === 'critical'
                          ? 'bg-red-100 text-red-700'
                          : 'bg-amber-100 text-amber-700'
                      }`}
                    >
                      {w.severity === 'critical' ? '🚨' : '⚠️'} 주의: 이 내용은 실제 임상에서 지도교수의 확인이 필요합니다
                    </div>
                  ))}
                </div>
              )}

              {/* Citations with snippets (v0.5 enhanced) */}
              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-3 border-t border-slate-200 pt-2">
                  <p className="mb-1 text-xs font-semibold text-slate-500">참고 자료</p>
                  {msg.citations.map((c) => (
                    <div key={c.number} className="mb-1.5 rounded bg-slate-50 p-1.5 text-xs text-slate-600">
                      <span className="font-semibold">[{c.number}]</span> {c.document_title}
                      {c.source && <span className="ml-1 text-slate-400">({c.source})</span>}
                      {c.snippet && (
                        <p className="mt-0.5 text-[10px] text-slate-400 line-clamp-2">{c.snippet}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Confidence Badge (v0.5) */}
              {msg.confidence && (
                <div className="mt-2 flex items-center gap-2">
                  <span
                    className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                      msg.confidence === 'HIGH'
                        ? 'bg-emerald-100 text-emerald-700'
                        : msg.confidence === 'MEDIUM'
                          ? 'bg-blue-100 text-blue-700'
                          : msg.confidence === 'LOW'
                            ? 'bg-amber-100 text-amber-700'
                            : 'bg-slate-100 text-slate-500'
                    }`}
                  >
                    {msg.confidence === 'HIGH'
                      ? '✅ 교재 근거 있음'
                      : msg.confidence === 'MEDIUM'
                        ? '📖 부분 근거'
                        : msg.confidence === 'LOW'
                          ? '⚠️ 검토 필요'
                          : '❓ 미검증'}
                  </span>
                </div>
              )}

              {/* Disclaimer (v0.5) */}
              {msg.disclaimer && (
                <div className="mt-2 border-t border-slate-100 pt-1.5 text-[10px] text-slate-400">
                  {msg.disclaimer}
                </div>
              )}

              {/* Metadata */}
              {msg.metadata && (
                <div className="mt-1 text-[10px] text-slate-400">
                  {msg.metadata.latency_ms}ms |{' '}
                  {msg.metadata.rag_used ? 'RAG 사용' : 'RAG 미사용'}
                </div>
              )}
            </div>
          </div>
        ))}

        {sending && (
          <div className="mb-4 text-left">
            <div className="inline-block rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-400">
              답변 생성 중...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSend} className="border-t border-slate-200 py-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="질문을 입력하세요..."
            className="flex-1 rounded-xl border border-slate-300 px-4 py-3 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            disabled={sending}
          />
          <button
            type="submit"
            disabled={!input.trim() || sending}
            className="rounded-xl bg-brand-600 px-6 py-3 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
          >
            전송
          </button>
        </div>
      </form>
    </main>
  );
}
