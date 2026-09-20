"use client";

import { useEffect, useRef, useState } from "react";
import { COPY, type Locale } from "@/i18n/copy";
import { streamChat } from "@/lib/api";
import {
  SCHEDULED_LANGS,
  defaultSpeechLang,
  loadSpeechStatus,
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
  const [showEn, setShowEn] = useState(false);
  const [answerFor, setAnswerFor] = useState("");
  const [speechLang, setSpeechLang] = useState(() => defaultSpeechLang(locale));
  const [listening, setListening] = useState(false);
  const [speakingId, setSpeakingId] = useState<string | null>(null);
  const [speechErr, setSpeechErr] = useState("");
  const [notice, setNotice] = useState("");
  const stopListen = useRef<(() => void) | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const [support, setSupport] = useState(() => speechSupported());

  useEffect(() => {
    void loadSpeechStatus().then(() => setSupport(speechSupported()));
  }, []);

  useEffect(() => {
    setSpeechLang(defaultSpeechLang(locale));
  }, [locale]);

  useEffect(() => {
    if (!pendingAsk) return;
    setText(pendingAsk);
    setPendingAsk(null);
  }, [pendingAsk, setPendingAsk]);

  useEffect(() => {
    setAnswerFor("");
  }, [location?.id, location?.lat, location?.lon]);

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

  async function run(message: string, opts?: { regenerate?: boolean }) {
    if (!message || streaming || !location) return;
    const history = opts?.regenerate
      ? chat.filter((m) => m.role === "user" || m.id !== chat[chat.length - 1]?.id)
      : [...chat];
    if (!opts?.regenerate) {
      addChat({
        id: `u-${Date.now()}`,
        role: "user",
        content: message,
        locale,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false }),
      });
    }
    setStreaming(true);
    setNotice("");
    try {
      const final = await streamChat(
        message,
        location,
        locale,
        history,
        (ev) => {
          if (ev.type === "notice" && typeof ev.message === "string") {
            setNotice(ev.message);
          }
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
        compact ? "auto" : outputLocale,
        opts?.regenerate,
        conversationId,
        settings.llmProvider,
        settings.showEvidence
      );
      if (final) {
        if (opts?.regenerate) replaceLastAssistant(final);
        else addChat(final);
        if (final.ui?.length) applyUi(final.ui);
      } else {
        const empty: ChatMsg = {
          id: `e-${Date.now()}`,
          role: "assistant",
          content: "No reply came back. Try again — if the advisor model is offline, answers still use live station data after a short wait.",
        };
        if (opts?.regenerate) replaceLastAssistant(empty);
        else addChat(empty);
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
        if (err && err !== "aborted" && err !== "no-speech") {
          if (err === "not-allowed") {
            setSpeechErr("Microphone permission denied. Please allow microphone access in your browser settings.");
          } else if (err === "audio-capture") {
            setSpeechErr("No microphone detected or audio capture failed.");
          } else if (err === "network") {
            setSpeechErr("Speech recognition service network error.");
          } else if (err === "unsupported") {
            setSpeechErr("Speech recognition is not supported in this browser (Chrome / Edge / Safari recommended).");
          } else {
            setSpeechErr(`Speech recognition error: ${err}`);
          }
        }
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
    {
      label: t.chatStarterRainLabel || "Rain Forecast",
      query: t.chatStarterRainQuery || "When will rainfall occur today in my area?",
    },
    {
      label: t.chatStarterHazardsLabel || "Severe Hazards",
      query: t.chatStarterHazardsQuery || "Are there any active thunderstorm, extreme heat, or severe weather alerts?",
    },
    {
      label: t.chatStarterGeneralLabel || "Day Outlook & Outdoor",
      query: t.chatStarterGeneralQuery || "What is today's weather outlook and conditions for travel and outdoor activities?",
    },
    {
      label: t.chatStarterAqiLabel || (locale === "hi" ? "पवन एवं वायु गुणवत्ता" : locale === "bn" ? "বাতাস ও বায়ুর মান" : "Air quality for health"),
      query: t.chatStarterAqiQuery || (locale === "hi"
        ? "क्या हवा बच्चों के लिए खराब है और हमें क्या करना चाहिए?"
        : locale === "bn"
        ? "বাচ্চাদের জন্য বাতাস কি খারাপ, এবং আমাদের কী করা উচিত?"
        : "Is the air bad for my kids right now, and what should we do?"),
    },
  ];

  return (
    <section
      className={`flex flex-col overflow-hidden ${
        compact
          ? "h-[min(34rem,72dvh)] min-h-[340px] bg-transparent"
          : "h-full min-h-[calc(100dvh-5.5rem)] lg:h-[min(720px,calc(100vh-11rem))] lg:min-h-[420px] rounded-2xl border border-[var(--line)] shadow-xl bg-[var(--card)]"
      }`}
    >
      {/* Clean Minimalist Header with Perfectly Aligned Logo */}
      <header className="flex shrink-0 items-center justify-between gap-3 border-b border-white/10 dark:border-white/10 bg-[color-mix(in_srgb,var(--card)_60%,transparent)] backdrop-blur-2xl px-3.5 py-2.5 sm:px-4 sm:py-3">
        <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
          <div className="relative flex h-9 w-9 sm:h-10 sm:w-10 shrink-0 items-center justify-center rounded-full overflow-hidden bg-transparent border-2 border-white/30 shadow-md">
            <img src="/logo.png" alt="PRITHVI-AI" width={40} height={40} className="h-full w-full object-cover rounded-full" />
            <span className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full bg-emerald-500 border-2 border-[var(--card)] animate-pulse" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm sm:text-[15px] font-black tracking-tight bg-gradient-to-r from-blue-500 via-sky-400 to-indigo-500 bg-clip-text text-transparent leading-none">
                PRITHVI-AI
              </span>
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 border border-emerald-500/30 px-1.5 py-0.5 text-[8.5px] font-extrabold text-emerald-600 dark:text-emerald-400 uppercase tracking-widest shadow-xs">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-ping" />
                Live
              </span>
            </div>
            <p className="text-[10.5px] sm:text-[11px] text-neo-muted truncate font-semibold mt-1 flex items-center gap-1 leading-none" data-testid="chat-locus">
              <span className="text-neo-accent font-bold">📍</span>
              {location?.label ? `${t.answeringFor} ${answerFor && answerFor !== location.label ? answerFor : location.label}` : t.assistant}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {/* Clear thread */}
          <button
            type="button"
            className="rounded-xl p-1.5 text-neo-muted hover:bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] hover:text-neo-text border border-transparent hover:border-[var(--line)] transition-all duration-200 disabled:opacity-30 cursor-pointer"
            onClick={() => {
              clearChat();
              setAnswerFor("");
            }}
            disabled={streaming || !chat.length}
            title={t.clear}
            aria-label={t.clear}
          >
            <IconRefresh className="h-4 w-4 transition-transform hover:rotate-180 duration-500" />
          </button>

          {/* Close button in compact mode */}
          {compact && onClose && (
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl p-1.5 text-neo-muted hover:bg-rose-500/15 hover:text-rose-500 border border-transparent hover:border-rose-500/30 transition-all duration-200 cursor-pointer"
              title="Close chat window"
              aria-label="Close chat window"
            >
              <IconCross className="h-4 w-4" />
            </button>
          )}
        </div>
      </header>

      {/* Message Thread Area */}
      <div
        ref={scroller}
        className="modal-scrollbar min-h-0 flex-1 space-y-3 overflow-y-auto p-4"
        data-testid="chat-thread"
      >
        {chat.length === 0 ? (
          <div className="py-5 text-center space-y-4">
            <div className="relative inline-flex items-center justify-center">
              <div className="absolute inset-0 rounded-3xl bg-gradient-to-tr from-blue-500/25 to-indigo-500/25 blur-xl animate-pulse" />
              <div className="relative inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-tr from-blue-600/20 via-sky-500/20 to-indigo-600/20 text-neo-accent border border-neo-accent/30 shadow-lg shadow-blue-500/15">
                <IconAdvisor className="h-6 w-6" />
              </div>
            </div>
            <div className="px-2">
              <p className="text-sm font-extrabold text-neo-text tracking-tight">
                {t.chatAssistTitle || "How can I assist you with the weather?"}
              </p>
              <p className="text-[11px] text-neo-muted mt-1 leading-relaxed max-w-sm mx-auto">
                {t.chatAssistSub || "Ask about hyper-local rainfall, IMD alerts, air quality, wind trends, or 7-day outlooks."}
              </p>
            </div>

            {/* Quick Starters Cards */}
            <div className="flex flex-col gap-2 text-left pt-1">
              {quickStarters.map((qs, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => run(qs.query)}
                  className="w-full text-left rounded-2xl border border-[color-mix(in_srgb,var(--line)_70%,transparent)] bg-[color-mix(in_srgb,var(--bg)_60%,var(--card))] hover:bg-[color-mix(in_srgb,var(--card)_40%,var(--accent))] hover:border-neo-accent/40 p-3 text-xs font-medium text-neo-text transition-all duration-200 flex items-center justify-between group shadow-xs hover:shadow-md hover:-translate-y-0.5 cursor-pointer"
                >
                  <div className="flex items-center gap-2.5 min-w-0 pr-2">
                    <span className="flex h-2 w-2 rounded-full bg-neo-accent shrink-0 group-hover:scale-125 transition-transform" />
                    <span className="text-[11px] font-bold truncate text-neo-text">{qs.label}</span>
                  </div>
                  <span className="text-[11px] text-neo-accent font-black tracking-wider flex items-center gap-1 opacity-70 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all shrink-0">
                    Ask <span>→</span>
                  </span>
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {chat.map((m) => {
          const isUser = m.role === "user";
          return (
            <div key={m.id} className="flex flex-col space-y-1">
              <div className={`flex items-start gap-2 ${isUser ? "justify-end" : "justify-start"}`}>
                {/* Assistant Pulse Avatar Icon */}
                {!isUser && (
                  <div className="mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-sky-500/15 border border-sky-400/40 text-sky-500 shadow-xs">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5">
                      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                    </svg>
                  </div>
                )}

                <div
                  className={`max-w-[86%] rounded-3xl p-4 text-xs transition-all shadow-md ${
                    isUser
                      ? "rounded-tr-xs bg-[#0b6399] text-white font-medium shadow-blue-900/20"
                      : "rounded-tl-xs bg-white dark:bg-[#121e33] border border-slate-200/80 dark:border-sky-500/20 text-slate-800 dark:text-slate-100 shadow-[0_4px_20px_-4px_rgba(0,0,0,0.1),0_0_15px_rgba(2,132,199,0.06)]"
                  }`}
                  data-testid={isUser ? "chat-user" : "chat-assistant"}
                >
                  {isUser ? (
                    <p className="whitespace-pre-wrap leading-relaxed text-[13px]">{m.content}</p>
                  ) : (
                    <>
                      {settings.showEvidence && m.blocks && m.blocks.length ? (
                        <ChatBlocks blocks={m.blocks} prose={m.content} />
                      ) : (
                        <ChatBlocks prose={m.content} />
                      )}

                      {/* Assistant suggestions */}
                      {m.insight?.bands?.length ? (
                        <div className="mt-2.5 flex flex-wrap gap-1.5" data-testid="chat-insight-bands">
                          {m.insight.bands.slice(0, 6).map((b, i) => (
                            <span
                              key={`${b.key || "b"}-${i}`}
                              className="rounded-lg border border-[var(--line)] bg-[var(--card)] px-2 py-0.5 text-[9px] font-bold text-neo-muted shadow-2xs"
                              title={b.meaning || ""}
                            >
                              {(b.category || b.band || b.key) as string}
                            </span>
                          ))}
                        </div>
                      ) : null}

                      {m.suggestions && m.suggestions.length ? (
                        <div className="mt-2.5 flex flex-wrap gap-1.5">
                          {m.suggestions.map((s: ChatSuggestion) => {
                            const label = (() => {
                              const raw = s.label || "";
                              const currentLoc = (locale || m.locale || "en") as Locale;
                              if (currentLoc === "en") return raw;
                              
                              // Open alerts
                              if (s.id === "open-alerts" || /open alerts/i.test(raw)) {
                                const place = raw.replace(/^open alerts for\s+/i, "").trim();
                                if (currentLoc === "hi") return place && place !== raw ? `${place} के लिए अलर्ट खोलें` : "अलर्ट खोलें";
                                if (currentLoc === "bn") return place && place !== raw ? `${place}-এর জন্য সতর্কতা দেখুন` : "সতর্কতা দেখুন";
                              }
                              // Focus map
                              if (s.id === "focus-map" || /focus (?:the )?map/i.test(raw)) {
                                const place = raw.replace(/^focus (?:the )?map on\s+/i, "").trim();
                                if (currentLoc === "hi") return place && place !== raw ? `मानचित्र को ${place} पर केंद्रित करें` : "मानचित्र पर केंद्रित करें";
                                if (currentLoc === "bn") return place && place !== raw ? `মানচিত্র ${place}-এ ফোকাস করুন` : "মানচিত্রে ফোকাস করুন";
                              }
                              // Open forecast
                              if (s.id === "open-forecast" || /forecast/i.test(raw)) {
                                const place = raw.replace(/^(?:open the 7-day forecast for|show this date window on forecast for)\s+/i, "").trim();
                                if (currentLoc === "hi") return place && place !== raw ? `${place} का 7-दिवसीय पूर्वानुमान` : "7-दिवसीय पूर्वानुमान";
                                if (currentLoc === "bn") return place && place !== raw ? `${place}-এর ৭ দিনের পূর্বাভাস` : "৭ দিনের পূর্বাভাস";
                              }
                              // Open nowcast
                              if (s.id === "open-nowcast" || /nowcast/i.test(raw)) {
                                const place = raw.replace(/^open the 0–6 hour nowcast for\s+/i, "").trim();
                                if (currentLoc === "hi") return place && place !== raw ? `${place} का नाउकास्ट (0-6 घंटे)` : "0-6 घंटे नाउकास्ट";
                                if (currentLoc === "bn") return place && place !== raw ? `${place}-এর নাওকাস্ট (০-৬ ঘণ্টা)` : "০-৬ ঘণ্টা নাওকাস্ট";
                              }
                              // Open risks
                              if (s.id === "open-risks" || /risk/i.test(raw)) {
                                const place = raw.replace(/^open risk cards for\s+/i, "").trim();
                                if (currentLoc === "hi") return place && place !== raw ? `${place} के जोखिम कार्ड` : "जोखिम कार्ड खोलें";
                                if (currentLoc === "bn") return place && place !== raw ? `${place}-এর ঝুঁকি কার্ড` : "ঝুঁকি কার্ড দেখুন";
                              }
                              // Open market
                              if (s.id === "open-market" || /mandi/i.test(raw)) {
                                const place = raw.replace(/^open mandi prices for\s+/i, "").trim();
                                if (currentLoc === "hi") return place && place !== raw ? `${place} के मंडी भाव` : "मंडी भाव खोलें";
                                if (currentLoc === "bn") return place && place !== raw ? `${place}-এর মান্ডি দর` : "মান্ডি দর দেখুন";
                              }
                              return raw;
                            })();

                            return (
                              <button
                                key={s.id}
                                type="button"
                                className="chip text-[9px] font-bold text-sky-500 dark:text-sky-300 border border-sky-500/30 bg-sky-500/10 hover:bg-sky-500/20 hover:border-sky-400 hover:scale-[1.03] rounded-lg px-2.5 py-1 transition-all shadow-xs cursor-pointer"
                                onClick={() => applySuggestion(s)}
                              >
                                {label}
                              </button>
                            );
                          })}
                        </div>
                      ) : null}

                      {/* Card Footer: Listen & Copy actions */}
                      <div className="mt-3 flex items-center justify-end border-t border-slate-100 dark:border-sky-500/20 pt-2 text-[10px] text-neo-muted">
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => {
                              if (navigator.clipboard) navigator.clipboard.writeText(m.content);
                            }}
                            className="p-1 hover:text-neo-accent transition-colors"
                            title="Copy response"
                          >
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5">
                              <rect width="14" height="14" x="8" y="8" rx="2" ry="2" />
                              <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
                            </svg>
                          </button>
                          <button
                            type="button"
                            className={`flex items-center gap-1 font-bold rounded-full px-2 py-0.5 transition-colors cursor-pointer ${
                              speakingId === m.id
                                ? "bg-rose-500/20 text-rose-400"
                                : "hover:text-neo-accent"
                            }`}
                            onClick={() => toggleSpeak(m.id, m.content, m.content_en || undefined, m.locale)}
                            title={speakingId === m.id ? t.stopSpeak : t.speakReply}
                            aria-label={speakingId === m.id ? t.stopSpeak : t.speakReply}
                            data-testid={`chat-tts-${m.id}`}
                          >
                            {speakingId === m.id ? (
                              <IconVolumeOff className="h-3.5 w-3.5 text-rose-400" />
                            ) : (
                              <IconVolume className="h-3.5 w-3.5" />
                            )}
                          </button>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>

              {/* Timestamp tick under bubble */}
              {isUser && (
                <div className="flex items-center justify-end gap-1 pr-1 text-[9.5px] font-mono font-semibold text-slate-400">
                  <span>
                    {m.timestamp ||
                      (m.id.startsWith("u-") && !isNaN(Number(m.id.slice(2)))
                        ? new Date(Number(m.id.slice(2))).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false })
                        : "")}{" "}
                    IST
                  </span>
                  <span>✓</span>
                </div>
              )}
            </div>
          );
        })}

        {streaming ? (
          <div className="flex items-center gap-2 p-3 text-xs text-sky-500 dark:text-sky-400 bg-white/90 dark:bg-slate-900/80 rounded-2xl w-fit border border-sky-400/40 shadow-md backdrop-blur-xl" data-testid="chat-streaming">
            <span className="h-2 w-2 rounded-full bg-sky-500 animate-bounce" style={{ animationDelay: "0ms" }} />
            <span className="h-2 w-2 rounded-full bg-sky-500 animate-bounce" style={{ animationDelay: "150ms" }} />
            <span className="h-2 w-2 rounded-full bg-sky-400 animate-bounce" style={{ animationDelay: "300ms" }} />
            <span className="text-[10px] font-extrabold ml-1 tracking-wide text-sky-600 dark:text-sky-300">
              {notice || "Synthesizing live weather answer..."}
            </span>
          </div>
        ) : null}
      </div>

      {/* Modern Capsule Input Bar matching the design screenshot */}
      <div className="shrink-0 bg-transparent p-3 sm:p-4">
        {/* Active Dictation Notice */}
        {listening && (
          <div className="mb-2 flex items-center justify-between gap-2 px-3.5 py-2 rounded-2xl bg-rose-500/20 border border-rose-500/50 text-rose-300 text-xs font-semibold animate-pulse shadow-md">
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-rose-400 animate-ping" />
              <span>{t.listeningIn || "Listening in"} {SCHEDULED_LANGS.find((l) => l.id === speechLang)?.name || "Auto"}... {t.speakClearly || "Speak clearly"}</span>
            </div>
            <button
              type="button"
              onClick={toggleListen}
              className="text-[10px] font-black uppercase underline hover:opacity-80 cursor-pointer text-rose-200"
            >
              {t.done || "Done"}
            </button>
          </div>
        )}

        {speechErr && (
          <p className="mb-2 text-[10px] font-bold text-rose-400 bg-rose-500/15 p-2 rounded-xl border border-rose-500/30">
            {speechErr}
          </p>
        )}

        <form
          className="flex items-center gap-2 rounded-full bg-white dark:bg-[#101b2f] border border-slate-200/90 dark:border-sky-500/25 px-2 py-1.5 shadow-lg shadow-sky-950/5"
          onSubmit={(e) => {
            e.preventDefault();
            const msg = text.trim();
            setText("");
            run(msg);
          }}
        >
          {/* Microphone Icon */}
          <button
            type="button"
            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-all duration-200 cursor-pointer ${
              listening
                ? "bg-rose-600 text-white anim-mic-recording shadow-md scale-105"
                : "text-slate-500 hover:text-sky-600 dark:text-slate-400 dark:hover:text-sky-300"
            }`}
            onClick={toggleListen}
            disabled={!location || streaming}
            title={listening ? "Listening... click to stop" : "Voice dictation"}
            aria-label={listening ? t.listening : t.listen}
            data-testid="chat-mic"
          >
            <IconMic className="h-5 w-5" />
          </button>

          {/* Text Input */}
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="min-w-0 flex-1 bg-transparent px-2 py-1 text-xs sm:text-sm text-slate-800 dark:text-slate-100 placeholder:text-slate-400 outline-none"
            placeholder={
              location
                ? listening
                  ? "Listening to voice input..."
                  : locale === "hi"
                  ? "PRITHVI-AI से अगला प्रश्न पूछें..."
                  : locale === "bn"
                  ? "PRITHVI-AI কে পরবর্তী প্রশ্ন জিজ্ঞাসা করুন..."
                  : "Ask PRITHVI-AI a follow-up..."
                : t.loading
            }
            disabled={!location || streaming}
            data-testid="chat-input"
          />

          {/* Location Pin action shortcut */}
          <button
            type="button"
            onClick={() => {
              if (location) {
                run(`Give a detailed weather summary for ${location.place_name || location.district || location.label}`);
              }
            }}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-slate-400 hover:text-sky-600 dark:hover:text-sky-300 transition-colors"
            title="Ask for current pinned location"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
              <circle cx="12" cy="12" r="3" />
              <path d="M12 2a8 8 0 0 0-8 8c0 5.25 8 12 8 12s8-6.75 8-12a8 8 0 0 0-8-8z" />
            </svg>
          </button>

          {/* Send Up-Arrow Button in circular pill */}
          <button
            type="submit"
            disabled={streaming || !location || !text.trim()}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-200 dark:bg-slate-700/60 text-slate-500 dark:text-slate-300 disabled:opacity-40 enabled:bg-sky-600 enabled:text-white transition-all shadow-xs cursor-pointer hover:scale-105 active:scale-95"
            title={t.send}
            aria-label={t.send}
            data-testid="chat-send"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
          </button>
        </form>
      </div>
    </section>
  );
}

