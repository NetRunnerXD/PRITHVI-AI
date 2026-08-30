"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { COPY, type Locale } from "@/i18n/copy";
import { presetsFor } from "@/i18n/presets";
import { streamChat } from "@/lib/api";
import { useApp } from "@/lib/store";
import type { ChatMsg, ChatSuggestion, DashboardSnapshot } from "@/types/dashboard";
import { ChatBlocks } from "./ChatBlocks";

export function ChatDock({ compact = false }: { compact?: boolean }) {
  const {
    locale,
    outputLocale,
    setOutputLocale,
    location,
    chat,
    addChat,
    replaceLastAssistant,
    patchLastUser,
    clearChat,
    streaming,
    setStreaming,
    applySnapshot,
    applySuggestion,
    conversationId,
    pendingAsk,
    setPendingAsk,
    applyUi,
    settings,
  } = useApp();
  const t = COPY[locale];
  const [text, setText] = useState("");
  const [preset, setPreset] = useState("");
  const [showEn, setShowEn] = useState(false);
  const [answerFor, setAnswerFor] = useState("");
  const presets = presetsFor(locale);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setPreset("");
  }, [locale]);

  useEffect(() => {
    if (!pendingAsk) return;
    setText(pendingAsk);
    setPendingAsk(null);
  }, [pendingAsk, setPendingAsk]);

  useEffect(() => {
    const el = scroller.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [chat, streaming]);

  const lastUser = useMemo(() => [...chat].reverse().find((m) => m.role === "user"), [chat]);

  async function run(message: string, opts?: { regenerate?: boolean }) {
    if (!message || streaming || !location) return;
    const history = opts?.regenerate
      ? chat.filter((m) => m.role === "user" || m.id !== chat[chat.length - 1]?.id)
      : [...chat];
    if (!opts?.regenerate) {
      addChat({ id: `u-${Date.now()}`, role: "user", content: message, locale });
    }
    setStreaming(true);
    try {
      const final = await streamChat(
        message,
        location,
        locale,
        history,
        (ev) => {
          if (ev.type === "meta" && typeof ev.question_en === "string") {
            patchLastUser({ content_en: ev.question_en });
          }
          if (ev.type === "meta" && ev.location && typeof ev.location === "object") {
            const locn = ev.location as { label?: string };
            if (locn.label) setAnswerFor(locn.label);
          }
          if (ev.type === "widget_patch" && ev.path === "dashboard" && ev.value) {
            applySnapshot(ev.value as DashboardSnapshot);
          }
        },
        outputLocale,
        opts?.regenerate,
        conversationId,
        settings.llmProvider,
        settings.showEvidence
      );
      if (final) {
        if (opts?.regenerate) replaceLastAssistant(final);
        else addChat(final);
        if (final.ui?.length) applyUi(final.ui);
      }
    } catch (e) {
      const err: ChatMsg = { id: `e-${Date.now()}`, role: "assistant", content: `Chat failed: ${e}` };
      if (opts?.regenerate) replaceLastAssistant(err);
      else addChat(err);
    } finally {
      setStreaming(false);
    }
  }

  return (
    <section
      className={`neo flex flex-col overflow-hidden ${
        compact
          ? "h-[min(28rem,62dvh)] min-h-[240px]"
          : "h-[min(70dvh,calc(100dvh-8rem))] min-h-[280px] lg:h-[min(720px,calc(100vh-11rem))] lg:min-h-[420px]"
      }`}
    >
      <header className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-neo-line px-3 py-2">
        <div>
          <p className="text-sm font-bold">{t.chat}</p>
          {answerFor || location?.label ? (
            <p className="text-[10px] text-neo-muted" data-testid="chat-locus">
              {t.answeringFor} {answerFor || location?.label}
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-1">
          {(["en", "hi", "bn", "auto"] as const).map((l) => (
            <button
              key={l}
              type="button"
              className={`rounded-lg px-2 py-1 text-[10px] font-bold ${outputLocale === l ? "bg-neo-accent text-white" : "neo-btn"}`}
              onClick={() => setOutputLocale(l)}
              data-testid={`locale-${l}`}
            >
              {l === "auto" ? t.replyAuto : l.toUpperCase()}
            </button>
          ))}
          <button
            className="neo-btn text-xs"
            onClick={() => {
              clearChat();
              setAnswerFor("");
            }}
            disabled={streaming || !chat.length}
          >
            {t.clear}
          </button>
          <button className="neo-btn text-xs" disabled={streaming || !lastUser} onClick={() => lastUser && run(lastUser.content, { regenerate: true })}>
            {t.regenerate}
          </button>
        </div>
      </header>

      <div className="flex shrink-0 flex-wrap gap-1.5 border-b border-neo-line px-3 py-2">
        {presets.map((p) => (
          <button
            key={p.id}
            type="button"
            className={`chip ${preset === p.id ? "text-neo-accent" : ""}`}
            onClick={() => {
              setPreset(p.id);
              setText(p.text);
            }}
          >
            {p.label}
          </button>
        ))}
      </div>

      <div ref={scroller} className="min-h-0 flex-1 space-y-2 overflow-y-auto px-3 py-3" data-testid="chat-thread">
        {chat.length === 0 ? <p className="text-xs text-neo-muted">{t.pickPreset}</p> : null}
        {chat.map((m) => (
          <div
            key={m.id}
            className={`max-w-[92%] rounded-2xl px-3 py-2 text-sm ${
              m.role === "user" ? "ml-auto bg-neo-rain/15" : "bg-neo-bg"
            }`}
            data-testid={m.role === "assistant" ? "chat-assistant" : "chat-user"}
          >
            {m.role === "assistant" ? (
              m.blocks && m.blocks.length ? (
                <ChatBlocks blocks={m.blocks} prose={m.content} />
              ) : (
                <ChatBlocks prose={m.content} />
              )
            ) : (
              <p className="whitespace-pre-wrap">{m.content}</p>
            )}
            {m.role === "assistant" && m.suggestions && m.suggestions.length ? (
              <div className="mt-2 flex flex-wrap gap-1">
                {m.suggestions.map((s: ChatSuggestion) => (
                  <button
                    key={s.id}
                    type="button"
                    className="chip text-neo-accent"
                    onClick={() => applySuggestion(s)}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            ) : null}
            {m.role === "assistant" && m.content_en && showEn ? (
              <div className="mt-2 border-t border-neo-line pt-2 text-xs text-neo-muted">
                <ChatBlocks prose={m.content_en} />
              </div>
            ) : null}
          </div>
        ))}
        {streaming ? (
          <p className="text-xs text-neo-accent" data-testid="chat-streaming">
            …
          </p>
        ) : null}
      </div>

      <div className="shrink-0 border-t border-neo-line p-3">
        <label className="mb-2 flex items-center gap-2 text-[11px] text-neo-muted">
          <input type="checkbox" checked={showEn} onChange={(e) => setShowEn(e.target.checked)} />
          {t.showEn}
        </label>
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            const msg = text.trim();
            setText("");
            run(msg);
          }}
        >
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="neo-in min-w-0 flex-1 px-3 py-2 text-sm outline-none"
            placeholder={location ? t.message : t.loading}
            disabled={!location || streaming}
            data-testid="chat-input"
          />
          <button
            type="submit"
            disabled={streaming || !location}
            className="neo-btn shrink-0 disabled:opacity-50"
            data-testid="chat-send"
          >
            {t.send}
          </button>
        </form>
      </div>
    </section>
  );
}
