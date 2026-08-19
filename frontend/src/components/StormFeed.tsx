"use client";

import { useEffect, useMemo, useState } from "react";
import { COPY, type Locale } from "@/i18n/copy";
import type { StormIncident, StormMapPack } from "@/lib/api";

function fmtRemain(ms: number) {
  if (ms <= 0) return "0s";
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h) return `${h}h ${m}m`;
  if (m) return `${m}m ${sec}s`;
  return `${sec}s`;
}

function ts(inc: StormIncident, iso: string | undefined, ms?: number) {
  if (typeof ms === "number" && Number.isFinite(ms)) return ms;
  if (!iso) return NaN;
  return Date.parse(iso);
}

function windowBits(inc: StormIncident, now: number) {
  const start = ts(inc, inc.started_at, inc.started_ms);
  const close = ts(inc, inc.closes_at, inc.closes_ms);
  if (Number.isNaN(start) || Number.isNaN(close)) {
    if (inc.phase === "predicted") return { phase: "opens", label: inc.lead_min != null ? `opens ${inc.lead_min}m` : "predicted" };
    return { phase: "live", label: inc.remain_min != null ? `closes ${Math.round(inc.remain_min)}m` : "live" };
  }
  if (now < start) return { phase: "opens", label: `opens ${fmtRemain(start - now)}` };
  if (now < close) return { phase: "closes", label: `closes ${fmtRemain(close - now)}` };
  return { phase: "ended", label: "ended" };
}

const KIND_LABEL: Record<string, string> = {
  lightning: "Lightning",
  cloudburst: "Cloudburst",
  downburst: "Downburst",
  storm: "Storm",
  cloud: "Cold cloud",
};

export function StormFeed({
  storm,
  locale,
  selectedId,
  onSelect,
}: {
  storm: StormMapPack | null;
  locale: Locale;
  selectedId?: string | null;
  onSelect: (inc: StormIncident) => void;
}) {
  const t = COPY[locale];
  const [now, setNow] = useState(() => Date.now());
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const rows = useMemo(() => {
    let list = storm?.incidents || [];
    if (!list.length && storm?.cells?.length) {
      const asOf = storm.as_of_ms || Date.parse(storm.as_of || "") || Date.now();
      list = storm.cells.map((c, i) => {
        const life = Math.round(25 + ((c.p_lightning || 0) * 40) + Math.min(30, (c.area_km2 || 80) / 20));
        return {
          id: c.id || `cell-${i}`,
          kind: c.kind || "storm",
          lat: c.lat,
          lon: c.lon,
          place: c.place || `${c.lat.toFixed(2)}, ${c.lon.toFixed(2)}`,
          started_at: new Date(asOf - 10 * 60_000).toISOString(),
          closes_at: new Date(asOf + life * 60_000).toISOString(),
          started_ms: asOf - 10 * 60_000,
          closes_ms: asOf + life * 60_000,
          rain_ir_mm_h: c.rain_ir_mm_h,
          min_tb_k: c.min_tb_k,
          p_lightning: c.p_lightning,
          p_cloudburst: c.p_cloudburst,
          phase: "live" as const,
        };
      });
    }
    if (filter === "past") return list.filter((i) => i.phase === "past");
    if (filter === "predicted") return list.filter((i) => i.phase === "predicted" || (i.lead_min || 0) > 0);
    if (filter === "live") return list.filter((i) => (i.phase || "live") === "live");
    const open = list.filter((inc) => {
      if (inc.phase === "past") return filter === "all" || inc.kind === filter;
      const close = ts(inc, inc.closes_at, inc.closes_ms);
      if (Number.isNaN(close)) return inc.phase !== "ended";
      return close + 15_000 >= now;
    });
    if (filter === "all") return open;
    return open.filter((i) => i.kind === filter);
  }, [storm, filter, now]);

  const kinds = ["all", "past", "predicted", "live", "lightning", "storm", "cloudburst"];
  const ltn = storm?.sensors?.lightning_status;

  return (
    <section className="neo p-3" aria-labelledby="storm-feed-title">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="storm-feed-title" className="text-[11px] font-bold uppercase tracking-wide text-neo-muted">
          {t.stormFeed || "Live incidents"}
        </h2>
        <p className="text-[11px] text-neo-muted" aria-live="polite">
          {storm?.counts?.all ?? rows.length} {t.activeAlerts || "active"}
          {storm?.counts?.predicted ? ` · ${storm.counts.predicted} ${t.stormPredicted || "predicted"}` : ""}
        </p>
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5" role="group" aria-label={t.stormHighlights || "Kind"}>
        {kinds.map((k) => (
          <button
            key={k}
            type="button"
            className={`neo-btn text-xs ${filter === k ? "neo-btn-on" : ""}`}
            aria-pressed={filter === k}
            onClick={() => setFilter(k)}
          >
            {k === "all"
              ? t.stormAll || "All"
              : k === "predicted"
                ? t.stormPredicted || "Predicted"
                : k === "past"
                  ? t.stormPast || "Past"
                  : k === "live"
                    ? t.stormLive || "Live"
                    : KIND_LABEL[k] || k}
          </button>
        ))}
      </div>
      {ltn && ltn !== "ok" && ltn !== "cv+open-meteo" ? (
        <p className="mt-2 text-xs text-neo-warn" role="status">
          {ltn === "rate_limited"
            ? t.stormLightningQuota || "Lightning feed hit today’s quota. IR cells still update."
            : `Lightning: ${ltn}`}
        </p>
      ) : null}
      {rows.length === 0 ? (
        <p className="mt-3 text-sm text-neo-muted">{t.noWarnings || "No active incidents in this view."}</p>
      ) : (
        <ul className="mt-3 max-h-72 space-y-1 overflow-y-auto" role="listbox" aria-label={t.stormFeed || "Live incidents"}>
          {rows.map((inc) => {
            const win = windowBits(inc, now);
            const selected = inc.id === selectedId;
            const predicted = inc.phase === "predicted" || (inc.lead_min || 0) > 0;
            return (
              <li key={inc.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={selected}
                  className={`w-full rounded-xl px-2 py-2 text-left text-sm ${selected ? "ring-1 ring-neo-accent bg-neo-bg" : "hover:bg-neo-bg"}`}
                  onClick={() => onSelect(inc)}
                >
                  <span className="flex items-baseline justify-between gap-2">
                    <span className="font-semibold">
                      {KIND_LABEL[inc.kind] || inc.kind}
                      {inc.phase === "past" ? (
                        <span className="ml-1 text-[10px] font-bold uppercase tracking-wide text-neo-muted">{t.stormPast || "past"}</span>
                      ) : null}
                      {predicted ? (
                        <span className="ml-1 text-[10px] font-bold uppercase tracking-wide text-neo-accent">
                          {t.stormPredicted || "predicted"}
                          {inc.lead_min ? ` +${inc.lead_min}m` : ""}
                          {inc.confidence != null ? ` · ${(inc.confidence * 100).toFixed(0)}%` : ""}
                        </span>
                      ) : null}
                    </span>
                    <span className={`font-mono text-[11px] ${win.phase === "closes" || win.phase === "opens" ? "text-neo-accent" : "text-neo-muted"}`}>
                      {win.label}
                    </span>
                  </span>
                  <span className="mt-0.5 block text-xs text-neo-muted">{inc.place}</span>
                  {inc.rain_ir_mm_h != null ? (
                    <span className="mt-0.5 block font-mono text-[11px]">{inc.rain_ir_mm_h} mm/h</span>
                  ) : null}
                  {inc.confidence != null ? (
                    <span className="mt-0.5 block font-mono text-[11px]">
                      {t.stormConfidence || "Confidence"} {(inc.confidence * 100).toFixed(0)}% ({inc.confidence_band || "—"})
                    </span>
                  ) : null}
                  {inc.p_lightning != null || inc.p_cloudburst != null ? (
                    <span className="mt-0.5 block font-mono text-[11px] text-neo-muted">
                      {inc.p_lightning != null ? `P(ltn) ${(inc.p_lightning * 100).toFixed(0)}%` : ""}
                      {inc.p_lightning != null && inc.p_cloudburst != null ? " · " : ""}
                      {inc.p_cloudburst != null ? `P(burst) ${(inc.p_cloudburst * 100).toFixed(0)}%` : ""}
                    </span>
                  ) : null}
                  {inc.verify && inc.verify.agrees != null ? (
                    <span className={`mt-0.5 block text-[11px] ${inc.verify.agrees ? "text-neo-accent" : "text-neo-warn"}`}>
                      {inc.verify.agrees ? "matches live weather" : "differs from live weather"}
                      {inc.verify.note ? ` · ${inc.verify.note}` : ""}
                    </span>
                  ) : null}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
