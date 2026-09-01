"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { COPY } from "@/i18n/copy";
import { presetsFor } from "@/i18n/presets";
import { streamChat } from "@/lib/api";
import {
  SCHEDULED_LANGS,
  defaultSpeechLang,
  speakText,
  speechSupported,
  startDictation,
  stopSpeaking,
} from "@/lib/speech";
import { useApp } from "@/lib/store";
import type { ChatMsg, ChatSuggestion, DashboardSnapshot } from "@/types/dashboard";
import { ChatBlocks } from "./ChatBlocks";
import {
  IconAdvisor,
  IconCross,
  IconMic,
  IconRefresh,
  IconSend,
  IconSparkle,
  IconVolume,
  IconVolumeOff,
} from "./Icons";

export function ChatDock({
  compact = false,
  onClose,
}: {
  compact?: boolean;
  onClose?: () => void;
}) {
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
  const [speechLang, setSpeechLang] = useState(() => defaultSpeechLang(locale));
  const [listening, setListening] = useState(false);
  const [speakingId, setSpeakingId] = useState<string | null>(null);
  const [speechErr, setSpeechErr] = useState("");
  const stopListen = useRef<(() => void) | null>(null);
  const presets = presetsFor(locale);
  const scroller = useRef<HTMLDivElement>(null);
  const support = useMemo(() => speechSupported(), []);

  useEffect(() => {
    setPreset("");
  }, [locale]);

  useEffect(() => {
    setSpeechLang(defaultSpeechLang(locale));
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

  useEffect(() => {
    return () => {
      stopListen.current?.();
      stopSpeaking();
    };
  }, []);

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

  function toggleListen() {
    if (listening) {
      stopListen.current?.();
      stopListen.current = null;
      setListening(false);
      return;
    }
    if (!support.stt) {
      setSpeechErr(t.speechNeedHttps);
      return;
    }
    setSpeechErr("");
    setListening(true);
    stopListen.current = startDictation(
      speechLang,
      (piece, isFinal) => {
        setText(piece);
        if (isFinal) setText(piece.trim());
      },
      (err) => {
        setListening(false);
        stopListen.current = null;
        if (err && err !== "aborted" && err !== "no-speech") setSpeechErr(err);
      }
    );
  }

  function toggleSpeak(id: string, content: string, contentEn?: string, msgLocale?: string) {
    if (speakingId === id) {
      stopSpeaking();
      setSpeakingId(null);
      return;
    }
    if (!support.tts) {
      setSpeechErr(t.speechNeedHttps);
      return;
    }
    setSpeakingId(id);
    const hint = msgLocale && msgLocale !== "auto" ? msgLocale : speechLang;
    speakText(content, hint, () => setSpeakingId((cur) => (cur === id ? null : cur)), contentEn);
  }

  const quickStarters = [
    { label: "🌦️ Rain Forecast", query: "When will rainfall occur today in my area?" },
    { label: "⚡ Active Hazards", query: "Are there any extreme thunderstorm or flood warnings?" },
    { label: "🌾 Farming Advisory", query: "What are the recommended crop and irrigation actions for today?" },
  ];

  return (
    <section
      className={`flex flex-col overflow-hidden bg-[var(--card)] ${
        compact
          ? "h-[min(30rem,68dvh)] min-h-[300px]"
          : "h-[min(70dvh,calc(100dvh-8rem))] min-h-[280px] lg:h-[min(720px,calc(100vh-11rem))] lg:min-h-[420px] rounded-2xl border border-[var(--line)] shadow-lg"
      }`}
    >
      {/* Header with Copilot identity, language switcher, and controls */}
      <header className="flex shrink-0 items-center justify-between gap-2 border-b border-[var(--line)] bg-[color-mix(in_srgb,var(--card)_95%,var(--line))] px-3.5 py-2.5">
        <div className="flex items-center gap-2 min-w-0">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 text-white shadow-sm">
            <IconSparkle className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-black text-neo-text tracking-tight">PRITHVI-AI</span>
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
            </div>
            <p className="text-[10px] text-neo-muted truncate font-medium" data-testid="chat-locus">
              {answerFor || location?.label ? `${t.answeringFor} ${answerFor || location?.label}` : t.assistant}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          {/* Language selector chips */}
          <div className="flex items-center rounded-lg bg-[var(--bg)] p-0.5 border border-[var(--line)]">
            {(["en", "hi", "bn"] as const).map((l) => (
              <button
                key={l}
                type="button"
                className={`rounded-md px-1.5 py-0.5 text-[9px] font-black uppercase transition-all ${
                  outputLocale === l ? "bg-neo-accent text-white shadow-xs" : "text-neo-muted hover:text-neo-text"
                }`}
                onClick={() => setOutputLocale(l)}
                data-testid={`locale-${l}`}
              >
                {l}
              </button>
            ))}
          </div>

          {/* Clear thread */}
          <button
            type="button"
            className="rounded-lg p-1 text-neo-muted hover:bg-[var(--bg)] hover:text-neo-text transition-all disabled:opacity-40"
            onClick={() => {
              clearChat();
              setAnswerFor("");
            }}
            disabled={streaming || !chat.length}
            title={t.clear}
            aria-label={t.clear}
          >
            <IconRefresh className="h-3.5 w-3.5" />
          </button>

          {/* Close button in compact mode */}
          {compact && onClose && (
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1 text-neo-muted hover:bg-rose-500/10 hover:text-rose-600 transition-all ml-0.5"
              title="Close chat window"
              aria-label="Close chat window"
            >
              <IconCross className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </header>

      {/* Message Thread */}
      <div
        ref={scroller}
        className="modal-scrollbar min-h-0 flex-1 space-y-2.5 overflow-y-auto p-3.5"
        data-testid="chat-thread"
      >
        {chat.length === 0 ? (
          <div className="py-4 text-center space-y-3">
            <div className="inline-flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-tr from-blue-500/15 to-indigo-500/15 text-neo-accent border border-neo-accent/20">
              <IconAdvisor className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs font-bold text-neo-text">How can I assist you with the weather?</p>
              <p className="text-[10px] text-neo-muted mt-0.5">
                Ask about hyper-local rainfall, IMD warnings, mandi logistics, or crop advice.
              </p>
            </div>
            {/* Quick Starters */}
            <div className="flex flex-col gap-1.5 text-left pt-1">
              {quickStarters.map((qs, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => run(qs.query)}
                  className="w-full text-left rounded-xl border border-[var(--line)] bg-[var(--bg)] hover:bg-[color-mix(in_srgb,var(--card)_60%,var(--accent))] hover:border-neo-accent/30 p-2 text-xs font-medium text-neo-text transition-all flex items-center justify-between group"
                >
                  <span className="text-[11px]">{qs.label}</span>
                  <span className="text-[10px] text-neo-accent opacity-0 group-hover:opacity-100 transition-opacity font-bold">
                    Ask →
                  </span>
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {chat.map((m) => (
          <div
            key={m.id}
            className={`max-w-[88%] rounded-2xl p-2.5 text-xs transition-all ${
              m.role === "user"
                ? "ml-auto bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-sm font-medium"
                : "bg-[var(--bg)] border border-[var(--line)] text-neo-text shadow-xs"
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
              <p className="whitespace-pre-wrap leading-relaxed">{m.content}</p>
            )}

            {/* Assistant suggestions */}
            {m.role === "assistant" && m.suggestions && m.suggestions.length ? (
              <div className="mt-2 flex flex-wrap gap-1">
                {m.suggestions.map((s: ChatSuggestion) => (
                  <button
                    key={s.id}
                    type="button"
                    className="chip text-[9px] font-bold text-neo-accent border border-[var(--line)] bg-[var(--card)] hover:border-neo-accent rounded-md px-1.5 py-0.5 transition-all"
                    onClick={() => applySuggestion(s)}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            ) : null}

            {/* Read out loud audio button */}
            {m.role === "assistant" && m.content ? (
              <div className="mt-2 flex items-center justify-between border-t border-[color-mix(in_srgb,var(--line)_50%,transparent)] pt-1.5 text-[9px] text-neo-muted">
                <button
                  type="button"
                  className="hover:text-neo-accent flex items-center gap-1 font-semibold transition-colors"
                  onClick={() => toggleSpeak(m.id, m.content, m.content_en || undefined, m.locale)}
                  title={speakingId === m.id ? t.stopSpeak : t.speakReply}
                  aria-label={speakingId === m.id ? t.stopSpeak : t.speakReply}
                  data-testid={`chat-tts-${m.id}`}
                >
                  {speakingId === m.id ? (
                    <>
                      <IconVolumeOff className="h-3 w-3 text-rose-500 animate-pulse" />
                      <span className="text-rose-500 font-bold">Stop Audio</span>
                    </>
                  ) : (
                    <>
                      <IconVolume className="h-3 w-3" />
                      <span>Listen</span>
                    </>
                  )}
                </button>
              </div>
            ) : null}
          </div>
        ))}

        {streaming ? (
          <div className="flex items-center gap-1.5 p-2 text-xs text-neo-accent bg-[var(--bg)] rounded-xl w-fit border border-[var(--line)]" data-testid="chat-streaming">
            <span className="h-1.5 w-1.5 rounded-full bg-neo-accent animate-bounce" style={{ animationDelay: "0ms" }} />
            <span className="h-1.5 w-1.5 rounded-full bg-neo-accent animate-bounce" style={{ animationDelay: "150ms" }} />
            <span className="h-1.5 w-1.5 rounded-full bg-neo-accent animate-bounce" style={{ animationDelay: "300ms" }} />
            <span className="text-[10px] font-bold ml-1">Analyzing meteorological radar...</span>
          </div>
        ) : null}
      </div>

      {/* Input Bar with Embedded Microphone and Send Controls */}
      <div className="shrink-0 border-t border-[var(--line)] bg-[color-mix(in_srgb,var(--card)_95%,var(--line))] p-3">
        {/* Active Dictation Notice */}
        {listening && (
          <div className="mb-2 flex items-center justify-between gap-2 px-3 py-1.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-400 text-xs font-semibold animate-pulse">
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-rose-500 animate-ping" />
              <span>Listening in {SCHEDULED_LANGS.find((l) => l.id === speechLang)?.name || "Auto"}... Speak clearly</span>
            </div>
            <button
              type="button"
              onClick={toggleListen}
              className="text-[10px] font-black uppercase underline hover:opacity-80"
            >
              Done
            </button>
          </div>
        )}

        {speechErr && (
          <p className="mb-2 text-[10px] font-bold text-rose-500 bg-rose-500/10 p-1.5 rounded-lg border border-rose-500/20">
            {speechErr}
          </p>
        )}

        <form
          className="flex items-center gap-1.5"
          onSubmit={(e) => {
            e.preventDefault();
            const msg = text.trim();
            setText("");
            run(msg);
          }}
        >
          {/* Microphone button right next to the text bar */}
          <button
            type="button"
            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border transition-all ${
              listening
                ? "bg-rose-600 text-white border-rose-500 anim-mic-recording shadow-md"
                : "bg-[var(--bg)] text-neo-muted hover:text-neo-accent border-[var(--line)] hover:border-neo-accent shadow-xs"
            }`}
            onClick={toggleListen}
            disabled={!location || streaming}
            title={listening ? "Listening... click to stop" : "Voice dictation (Click to speak)"}
            aria-label={listening ? t.listening : t.listen}
            data-testid="chat-mic"
          >
            <IconMic className={`h-4 w-4 ${listening ? "animate-pulse" : ""}`} />
          </button>

          {/* Text Input */}
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="min-w-0 flex-1 rounded-xl bg-[var(--bg)] border border-[var(--line)] focus:border-neo-accent focus:ring-2 focus:ring-neo-accent/20 px-3 py-2 text-xs text-neo-text placeholder:text-neo-muted outline-none transition-all"
            placeholder={
              location
                ? listening
                  ? "Listening to voice input..."
                  : t.message || "Ask PRITHVI-AI..."
                : t.loading
            }
            disabled={!location || streaming}
            data-testid="chat-input"
          />

          {/* Send Button */}
          <button
            type="submit"
            disabled={streaming || !location || !text.trim()}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-neo-accent text-white hover:brightness-110 shadow-sm transition-all disabled:opacity-40 disabled:hover:brightness-100"
            title={t.send}
            aria-label={t.send}
            data-testid="chat-send"
          >
            <IconSend className="h-4 w-4" />
          </button>
        </form>
      </div>
    </section>
  );
}

