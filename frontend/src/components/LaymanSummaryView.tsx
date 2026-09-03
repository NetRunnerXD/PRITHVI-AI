"use client";

import React from "react";
import type { LaymanSummary, MetricTone } from "@/lib/laymanSummaries";

const TONE_BADGE: Record<MetricTone, { bg: string; text: string; dot: string; border: string }> = {
  ok: {
    bg: "bg-emerald-500/10 dark:bg-emerald-400/15",
    text: "text-emerald-700 dark:text-emerald-300 font-bold",
    dot: "bg-emerald-500",
    border: "border-emerald-500/25",
  },
  watch: {
    bg: "bg-amber-500/10 dark:bg-amber-400/15",
    text: "text-amber-700 dark:text-amber-300 font-bold",
    dot: "bg-amber-500",
    border: "border-amber-500/25",
  },
  alert: {
    bg: "bg-rose-500/12 dark:bg-rose-500/20",
    text: "text-rose-700 dark:text-rose-300 font-bold",
    dot: "bg-rose-500 animate-pulse",
    border: "border-rose-500/30",
  },
  info: {
    bg: "bg-sky-500/10 dark:bg-sky-400/15",
    text: "text-sky-700 dark:text-sky-300 font-bold",
    dot: "bg-sky-500",
    border: "border-sky-500/25",
  },
};

/**
 * Inner body component designed to fit seamlessly within the existing card's
 * body container (`min-h-[160px] flex flex-col justify-between`) without altering
 * the card's outer shape, padding, borders, or layout size.
 */
export function LaymanSummaryBody({
  summary,
  isWide = false,
}: {
  summary: LaymanSummary;
  isWide?: boolean;
}) {
  const badgeStyle = TONE_BADGE[summary.badge.tone] || TONE_BADGE.ok;

  return (
    <div className="fade-in-scale flex flex-col justify-between min-h-[175px] select-none py-0.5 space-y-2 min-w-0 max-w-full overflow-hidden">
      {/* 1. Direct Factual Headline & Status Badge */}
      <div className="flex shrink-0 items-start justify-between gap-2 min-w-0 h-9">
        <p className="text-xs sm:text-[13px] font-bold text-neo-text leading-snug line-clamp-2 min-w-0 flex-1 break-words">
          {summary.headline}
        </p>
        <span
          className={`shrink-0 text-[9px] font-extrabold uppercase px-2 py-0.5 rounded-md border inline-flex items-center gap-1 ${badgeStyle.bg} ${badgeStyle.text} ${badgeStyle.border}`}
        >
          <span className={`h-1.5 w-1.5 rounded-full ${badgeStyle.dot}`} />
          <span>{summary.badge.label}</span>
        </span>
      </div>

      {/* 2. Key Overview Metrics Grid */}
      <div className={`grid gap-1.5 min-w-0 ${isWide ? "grid-cols-2 sm:grid-cols-4" : "grid-cols-2"}`}>
        {summary.metrics.map((m, idx) => {
          const tone = TONE_BADGE[m.tone] || TONE_BADGE.ok;
          return (
            <div
              key={idx}
              className="neo-in p-2 rounded-xl flex flex-col justify-between text-left min-w-0 overflow-hidden bg-[color-mix(in_srgb,var(--card)_75%,var(--bg))] border border-[color-mix(in_srgb,var(--line)_50%,transparent)] shadow-2xs"
            >
              <span className="text-[8.5px] uppercase tracking-wider text-neo-muted font-bold block truncate min-w-0">
                {m.label}
              </span>
              <span className={`font-mono text-xs sm:text-[13px] font-black mt-0.5 block truncate min-w-0 ${tone.text}`}>
                {m.value}
              </span>
            </div>
          );
        })}
      </div>

      {/* 3. Concise Overview Highlights as Insight Callout Strips */}
      <div className="space-y-1 min-w-0">
        {summary.points.slice(0, 2).map((p, idx) => (
          <div
            key={idx}
            className="bg-[color-mix(in_srgb,var(--bg)_60%,transparent)] border border-[color-mix(in_srgb,var(--line)_40%,transparent)] px-2.5 py-1.5 rounded-lg flex items-start gap-2 min-w-0 overflow-hidden"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-neo-accent mt-1 shrink-0" />
            <span className="text-[10.5px] sm:text-[11px] font-medium leading-snug text-neo-text/90 line-clamp-2 min-w-0 flex-1 break-words">
              {p}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Backward-compatible full-card wrapper, preserving identical card dimensions.
 */
export function LaymanSummaryView({
  summary,
  className = "",
  onBack,
  isWide = false,
}: {
  summary: LaymanSummary;
  className?: string;
  onBack?: () => void;
  isWide?: boolean;
}) {
  return (
    <div
      onClick={onBack}
      className={`relative w-full h-full flex flex-col justify-between select-none p-4 cursor-pointer ${className}`}
    >
      <LaymanSummaryBody summary={summary} isWide={isWide} />
    </div>
  );
}
