"use client";

import { useEffect, useState } from "react";
import { COPY } from "@/i18n/copy";
import { useApp } from "@/lib/store";
import { ChatDock } from "./ChatDock";
import { IconAdvisor, IconCross, IconSparkle } from "./Icons";

export function ChatFloat() {
  const { locale, floatChatOpen, setFloatChatOpen } = useApp();
  const t = COPY[locale];
  const [bounce, setBounce] = useState(true);

  useEffect(() => {
    const id = window.setTimeout(() => setBounce(false), 4200);
    return () => window.clearTimeout(id);
  }, []);

  return (
    <div className="pointer-events-none fixed bottom-20 right-4 z-[1200] flex flex-col items-end gap-3 lg:bottom-6 lg:right-6">
      {floatChatOpen && (
        <div className="pointer-events-auto w-[min(100vw-1.5rem,27rem)] overflow-hidden rounded-3xl border border-[var(--line)] shadow-2xl shadow-blue-950/30 backdrop-blur-xl bg-[var(--card)] anim-chat-pop">
          <ChatDock compact onClose={() => setFloatChatOpen(false)} />
        </div>
      )}

      {/* Floating Action Bar: 'ASK ME' Pill & Larger Morphing FAB */}
      <div className="flex items-center gap-2.5">
        {!floatChatOpen && (
          <button
            type="button"
            onClick={() => setFloatChatOpen(true)}
            className="anim-float-badge pointer-events-auto flex items-center gap-2 rounded-full bg-[var(--card)]/95 border border-[var(--line)] shadow-xl shadow-blue-950/25 px-4 py-2 text-xs font-black tracking-widest uppercase text-blue-600 dark:text-blue-400 backdrop-blur-xl hover:scale-105 active:scale-95 transition-all group cursor-pointer"
            title="Ask PRITHVI-AI"
          >
            <span className="flex h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse shrink-0" />
            <span className="font-black text-xs sm:text-[13px] tracking-wider group-hover:text-blue-500 transition-colors">
              ASK ME
            </span>
          </button>
        )}

        {/* Larger Floating Action Trigger Button */}
        <button
          type="button"
          className={`pointer-events-auto relative flex h-15 w-15 sm:h-16 sm:w-16 items-center justify-center rounded-2xl sm:rounded-3xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-violet-600 text-white shadow-xl shadow-indigo-500/35 hover:shadow-indigo-500/55 hover:scale-105 active:scale-95 transition-all duration-200 border-2 border-white/30 ${
            bounce ? "assistant-bob" : ""
          }`}
          onClick={() => setFloatChatOpen(!floatChatOpen)}
          title={floatChatOpen ? "Close assistant" : "Ask PRITHVI-AI"}
          aria-label={floatChatOpen ? "Close assistant" : "Ask PRITHVI-AI"}
        >
          {!floatChatOpen && (
            <span className="absolute -top-1 -right-1 flex h-4 w-4">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-4 w-4 bg-emerald-500 border-2 border-[var(--card)]" />
            </span>
          )}

          <div className={`transition-transform duration-300 ${floatChatOpen ? "rotate-90 scale-90" : "rotate-0 scale-100"}`}>
            {floatChatOpen ? <IconCross className="h-6 w-6" /> : <IconSparkle className="h-7 w-7 sm:h-8 sm:w-8" />}
          </div>
        </button>
      </div>
    </div>
  );
}

