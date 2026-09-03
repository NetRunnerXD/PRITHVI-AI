"use client";

import { useEffect, useState } from "react";
import { COPY } from "@/i18n/copy";
import { useApp } from "@/lib/store";
import { ChatDock } from "./ChatDock";
import { IconCross } from "./Icons";

function AnimatedEarthGlobe({ isOpen }: { isOpen: boolean }) {
  return (
    <div className="relative w-14 h-14 sm:w-16 sm:h-16 flex items-center justify-center select-none">
      {/* Outer Atmospheric Cyan/Emerald Aura Glow */}
      <div className="absolute inset-0 rounded-full bg-cyan-400/25 blur-md animate-pulse" />

      {/* Orbital Satellite Track with Rotating Satellite Beacon */}
      {!isOpen && (
        <div className="absolute -inset-1.5 anim-orbit-spin pointer-events-none">
          <div className="relative w-full h-full">
            {/* Satellite Beacon */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 flex items-center justify-center">
              <span className="h-2.5 w-2.5 rounded-full bg-cyan-300 shadow-[0_0_8px_#38bdf8] animate-ping absolute" />
              <span className="h-2 w-2 rounded-full bg-white shadow-[0_0_6px_#38bdf8] relative" />
            </div>
          </div>
        </div>
      )}

      {/* Main Spherical Globe Body */}
      <div
        className={`relative w-12 h-12 sm:w-14 sm:h-14 rounded-full overflow-hidden shadow-2xl transition-all duration-300 border border-cyan-300/50 ${
          isOpen ? "rotate-90 scale-95 bg-slate-900" : "anim-earth-globe"
        }`}
        style={{
          background: "radial-gradient(circle at 35% 30%, #38bdf8 0%, #0284c7 40%, #1e3a8a 75%, #09152b 100%)",
        }}
      >
        {isOpen ? (
          <div className="absolute inset-0 flex items-center justify-center text-white bg-slate-950/80">
            <IconCross className="w-6 h-6 sm:w-7 sm:h-7 text-cyan-200" />
          </div>
        ) : (
          <>
            {/* Rotating Continents Layer */}
            <div className="absolute inset-0 w-[200%] h-full flex anim-earth-spin opacity-95">
              <svg viewBox="0 0 200 100" className="w-full h-full fill-emerald-500/90 drop-shadow-[0_1px_2px_rgba(0,0,0,0.4)]" preserveAspectRatio="none">
                {/* Landmass shapes (Panel 1) */}
                <path d="M15,25 Q25,15 38,22 Q48,32 40,48 Q30,55 20,45 Z" fill="#10b981" />
                <path d="M48,18 Q62,12 72,25 Q78,42 65,52 Q52,58 46,38 Z" fill="#059669" />
                <path d="M58,45 Q68,40 75,55 Q72,75 58,82 Q50,70 54,58 Z" fill="#10b981" />
                <path d="M22,58 Q34,52 38,68 Q35,88 24,85 Q18,75 22,58 Z" fill="#34d399" />
                <path d="M78,60 Q88,55 92,70 Q88,85 78,80 Z" fill="#10b981" />
                
                {/* Landmass shapes (Panel 2 seamless loop) */}
                <path d="M115,25 Q125,15 138,22 Q148,32 140,48 Q130,55 120,45 Z" fill="#10b981" />
                <path d="M148,18 Q162,12 172,25 Q178,42 165,52 Q152,58 146,38 Z" fill="#059669" />
                <path d="M158,45 Q168,40 175,55 Q172,75 158,82 Q150,70 154,58 Z" fill="#10b981" />
                <path d="M122,58 Q134,52 138,68 Q135,88 124,85 Q118,75 122,58 Z" fill="#34d399" />
                <path d="M178,60 Q188,55 192,70 Q188,85 178,80 Z" fill="#10b981" />
              </svg>
            </div>

            {/* Rotating Swirling Clouds Layer */}
            <div className="absolute inset-0 w-[200%] h-full flex anim-cloud-spin pointer-events-none opacity-60">
              <svg viewBox="0 0 200 100" className="w-full h-full fill-white" preserveAspectRatio="none">
                <path d="M10,20 Q30,12 55,22 Q75,15 90,26 Q60,30 35,26 Z" />
                <path d="M25,48 Q50,38 75,46 Q95,40 100,52 Q70,55 45,52 Z" />
                <path d="M5,72 Q35,65 65,75 Q85,68 95,80 Q65,82 35,78 Z" />
                
                {/* Seamless loop clouds */}
                <path d="M110,20 Q130,12 155,22 Q175,15 190,26 Q160,30 135,26 Z" />
                <path d="M125,48 Q150,38 175,46 Q195,40 200,52 Q170,55 145,52 Z" />
                <path d="M105,72 Q135,65 165,75 Q185,68 195,80 Q165,82 135,78 Z" />
              </svg>
            </div>

            {/* 3D Spherical Specular Lighting & Terminator Shadow Overlay */}
            <div
              className="absolute inset-0 pointer-events-none rounded-full"
              style={{
                background:
                  "radial-gradient(circle at 30% 25%, rgba(255, 255, 255, 0.5) 0%, rgba(255, 255, 255, 0.12) 35%, transparent 60%), radial-gradient(circle at 75% 80%, rgba(0, 0, 0, 0.65) 0%, transparent 70%)",
                boxShadow: "inset 2px 2px 5px rgba(255,255,255,0.5), inset -3px -3px 7px rgba(0,0,0,0.6)",
              }}
            />

            {/* AI Core Specular Sparkle */}
            <div className="absolute top-2 right-2 w-1.5 h-1.5 rounded-full bg-white shadow-[0_0_6px_#fff] animate-ping opacity-75 pointer-events-none" />
          </>
        )}
      </div>
    </div>
  );
}

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

      {/* Floating Action Bar: 'ASK ME' Pill & Animated Earth Globe FAB */}
      <div className="flex items-center gap-2.5">
        {!floatChatOpen && (
          <button
            type="button"
            onClick={() => setFloatChatOpen(true)}
            className="anim-float-badge pointer-events-auto flex items-center gap-2 rounded-full bg-[var(--card)]/95 border border-[var(--line)] shadow-xl shadow-blue-950/25 px-4 py-2 text-xs font-black tracking-widest uppercase text-blue-600 dark:text-blue-400 backdrop-blur-xl hover:scale-105 active:scale-95 transition-all group cursor-pointer"
            title="Ask WeatherGPT"
          >
            <span className="flex h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse shrink-0" />
            <span className="font-black text-xs sm:text-[13px] tracking-wider group-hover:text-blue-500 transition-colors">
              {t.askMe || "ASK ME"}
            </span>
          </button>
        )}

        {/* Floating Animated Earth Trigger Button */}
        <button
          type="button"
          className={`pointer-events-auto relative p-1 rounded-full hover:scale-110 active:scale-95 transition-all duration-200 cursor-pointer focus:outline-none focus:ring-2 focus:ring-cyan-400/50 ${
            bounce ? "assistant-bob" : ""
          }`}
          onClick={() => setFloatChatOpen(!floatChatOpen)}
          title={floatChatOpen ? "Close WeatherGPT assistant" : "Ask WeatherGPT (PRITHVI-AI)"}
          aria-label={floatChatOpen ? "Close WeatherGPT assistant" : "Ask WeatherGPT"}
        >
          {!floatChatOpen && (
            <span className="absolute top-1 right-1 z-10 flex h-3.5 w-3.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-emerald-500 border-2 border-[var(--card)]" />
            </span>
          )}

          <AnimatedEarthGlobe isOpen={floatChatOpen} />
        </button>
      </div>
    </div>
  );
}

