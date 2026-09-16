'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { analyticsApi } from '@/lib/api-client';
import type { AIChatResponse } from '@/types';
import { Bot, Loader2, Send, Sparkles, User } from 'lucide-react';

type ChatRole = 'user' | 'assistant';

interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  meta?: string;
}

export function ClinicAIChat() {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content:
        'Merhaba, klinik AI analiz asistaniyim. Randevu, yedek liste, envanter, hekim ve hasta tedavi dagilimlari hakkinda soru sorabilirsiniz.',
      meta: 'Hazir',
    },
  ]);

  const disabled = loading || input.trim().length < 3;

  const examplePrompts = useMemo(
    () => [
      'Son 30 gunde iptal/no-show oranini yorumla ve aksiyon oner.',
      'Hangi malzemelerde stok riski var, satin alma onceligi cikart.',
      'Hekim bazli tedavi dagilimini analiz et ve kapasite oner.',
      'Yedek listeyi hangi bransta daha agresif kullanmaliyiz?',
    ],
    [],
  );

  useEffect(() => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, loading]);

  const ask = async (messageText: string) => {
    const clean = messageText.trim();
    if (clean.length < 3 || loading) return;

    setLoading(true);
    setMessages((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, role: 'user', content: clean },
    ]);
    setInput('');

    try {
      const res = await analyticsApi.aiChat(clean);
      const data = res.data as AIChatResponse;
      const meta = data.fallback_used ? `${data.model} (analitik fallback)` : data.model;
      setMessages((prev) => [
        ...prev,
        {
          id: `a-${Date.now()}`,
          role: 'assistant',
          content: data.answer,
          meta,
        },
      ]);
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'AI analiz yaniti alinamadi. Lutfen tekrar deneyin.';
      setMessages((prev) => [
        ...prev,
        { id: `e-${Date.now()}`, role: 'assistant', content: detail, meta: 'Hata' },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="relative border-b border-slate-100 bg-gradient-to-r from-slate-900 via-slate-800 to-blue-900 px-5 py-4 text-white">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.18),transparent_40%)]" />
        <div className="relative flex items-center justify-between gap-3">
          <div>
            <div className="mb-1 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-2.5 py-1 text-[11px] font-medium">
              <Sparkles className="h-3.5 w-3.5" />
              AI Decision Support
            </div>
            <h3 className="text-sm font-semibold tracking-wide">Klinik AI Analiz Chat</h3>
          </div>
          <span className="rounded-full border border-emerald-300/50 bg-emerald-400/20 px-2.5 py-1 text-[11px] font-medium text-emerald-100">
            owner / superadmin
          </span>
        </div>
      </div>

      <div className="grid gap-0 lg:grid-cols-[1fr_260px]">
        <div className="min-h-[22rem] border-b border-slate-100 bg-gradient-to-b from-slate-50/70 to-white lg:border-b-0 lg:border-r">
          <div ref={scrollRef} className="max-h-[26rem] space-y-3 overflow-y-auto p-4 sm:p-5">
            {messages.map((m) => (
              <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[90%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed shadow-sm sm:max-w-[82%] ${
                    m.role === 'user'
                      ? 'bg-gradient-to-br from-blue-600 to-blue-700 text-white'
                      : 'border border-slate-200 bg-white text-slate-700'
                  }`}
                >
                  <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-medium opacity-80">
                    {m.role === 'user' ? <User className="h-3 w-3" /> : <Bot className="h-3 w-3" />}
                    {m.role === 'user' ? 'Siz' : 'AI Asistan'}
                    {m.meta ? ` | ${m.meta}` : ''}
                  </div>
                  {m.content}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="rounded-2xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-600 shadow-sm">
                  <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-medium text-slate-500">
                    <Bot className="h-3 w-3" />
                    AI Asistan | dusunuyor
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-400" />
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-400 [animation-delay:120ms]" />
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-400 [animation-delay:240ms]" />
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        <aside className="border-b border-slate-100 bg-slate-50/80 p-4 lg:border-b-0">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Hizli Sorular</p>
          <div className="space-y-2.5">
            {examplePrompts.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => ask(p)}
                disabled={loading}
                className="w-full rounded-xl border border-slate-200 bg-white p-2.5 text-left text-xs text-slate-700 transition hover:border-blue-300 hover:bg-blue-50/50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {p}
              </button>
            ))}
          </div>
        </aside>
      </div>

      <div className="border-t border-slate-100 bg-white p-3 sm:p-4">
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                ask(input);
              }
            }}
            rows={2}
            placeholder="Ornek: Son 30 gunde no-show oranini dusurmek icin 3 net aksiyon oner"
            className="w-full resize-none border-0 bg-transparent px-2 py-1.5 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none"
          />
          <div className="mt-1 flex items-center justify-between px-1 pb-1">
            <span className="text-[11px] text-slate-400">Enter gonderir, Shift+Enter yeni satir</span>
            <button
              type="button"
              onClick={() => ask(input)}
              disabled={disabled}
              className="inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm transition hover:from-blue-700 hover:to-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              Gonder
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
