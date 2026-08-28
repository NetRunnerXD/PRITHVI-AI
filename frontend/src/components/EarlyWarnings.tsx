"use client";

import { useMemo, useState } from "react";
import type { EarlyWarning, LiveWatch } from "@/types/dashboard";
import { COPY, type Locale } from "@/i18n/copy";

const tone: Record<string, string> = {
  extreme: "text-neo-danger",
  warning: "text-neo-warn",
  alert: "text-neo-accent",
  watch: "text-neo-accent2",
};

function hazardLabel(hazard: string | undefined, t: Record<string, string>) {
  const map: Record<string, string> = {
    weather: t.sky,
    flood: t.floodWatch,
    air: t.aqi,
    marine: t.marine,
    seismic: t.seismic,
    tsunami: t.tsunami,
  };
  return map[hazard || "weather"] || hazard || t.sky;
}

const FEEDS: { key: string; label: string }[] = [
  { key: "imd-cap", label: "IMD CAP" },
  { key: "data.gov.in-aqi", label: "CPCB" },
  { key: "openaq-hist", label: "OpenAQ hist" },
  { key: "incois-tsunami", label: "INCOIS ITEWS" },
  { key: "usgs-seismic", label: "USGS seismic" },
  { key: "open-meteo", label: "Open-Meteo wx" },
  { key: "open-meteo-flood", label: "OM flood" },
  { key: "open-meteo-marine", label: "OM marine" },
  { key: "open-meteo-air", label: "OM air" },
];

function chipTone(st?: string) {
  if (st === "ok") return "text-neo-accent2";
  if (st === "empty") return "text-neo-muted";
  if (st === "unauthorized" || st === "missing_key") return "text-neo-warn";
  if (st === "error") return "text-neo-danger";
  return "text-neo-muted";
}

function marineLabel(live: LiveWatch | undefined, t: Record<string, string>) {
  const m = live?.marine;
  if (!m) return "—";
  const wave =
    m.wave_height_m != null ? `${Number(m.wave_height_m).toFixed(1)} m ${m.wave_compass || ""}`.trim() : "";
  if (wave && m.nearest_coast) {
    const km = m.coast_km != null ? ` · ${Math.round(Number(m.coast_km))} km` : "";
    return `${wave} · ${m.nearest_coast}${km}`;
  }
  if (wave) return wave;
  if (m.nearest_coast) {
    const km = m.coast_km != null ? ` · ${Math.round(Number(m.coast_km))} km` : "";
    return `${t.nearestCoast}: ${m.nearest_coast}${km}`;
  }
  return t.seaUnavailable;
}

function stackedRain(text: string) {
  const low = text.toLowerCase();
  return (
    /heavy\s+to\s+very\s+heavy/.test(low) ||
    /extremely heavy rainfall at/.test(low) ||
    /heavy to very heavy with/.test(low)
  );
}

function bulletinLine(w: EarlyWarning) {
  const body = (w.body || "").trim();
  if (!body || stackedRain(body) || stackedRain(w.title || "")) return "";
  const first = body.split(/(?<=[.!?])\s+/)[0] || body;
  if (stackedRain(first)) return "";
  return first.length > 180 ? `${first.slice(0, 177)}…` : first;
}

function issuedLabel(iso?: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function EarlyWarnings({
  items,
  locale,
  live,
  status,
}: {
  items: EarlyWarning[];
  locale: Locale;
  live?: LiveWatch;
  status?: Record<string, string>;
}) {
  const t = COPY[locale];
  const hot = items.some((w) => w.severity === "extreme" || w.severity === "warning");
  const [open, setOpen] = useState(hot);
  const nearest = live?.quakes?.[0];
  const tsunami = live?.tsunami?.[0];
  const worst = useMemo(() => {
    const order = ["extreme", "warning", "alert", "watch"];
    return items.slice().sort((a, b) => order.indexOf(a.severity) - order.indexOf(b.severity))[0];
  }, [items]);

  return (
    <section className="neo px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <button
          type="button"
          className="min-w-0 flex-1 text-left"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
        >
          <div className="flex flex-wrap items-center gap-2">
            <span className="live-dot" aria-hidden />
            <h2 className="text-xs font-bold uppercase tracking-[0.16em] text-neo-accent">{t.warnings}</h2>
            <span className="chip">
              {items.length} {t.activeAlerts}
              {worst ? ` · ${worst.severity}` : ""}
            </span>
            <span className="text-[11px] text-neo-muted">{open ? t.collapse : t.expand}</span>
          </div>
          {!open ? (
            <p className="mt-1 line-clamp-2 text-[11px] leading-snug text-neo-muted">
              {worst ? worst.title : t.noWarnings}
            </p>
          ) : null}
        </button>
        {open ? (
          <div className="flex flex-wrap gap-1.5">
            {FEEDS.map((f) => (
              <span key={f.key} className={`chip ${chipTone(status?.[f.key])}`}>
                {f.label}
                {status?.[f.key] ? ` · ${status[f.key]}` : ""}
              </span>
            ))}
          </div>
        ) : null}
      </div>

      {open ? (
        <>
          {items.length === 0 ? (
            <p className="mt-3 text-sm text-neo-muted">{t.noWarnings}</p>
          ) : (
            <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {items.map((w) => {
                const line = bulletinLine(w);
                const when = issuedLabel(w.issued_at);
                return (
                  <article key={w.id} className="neo-in px-3 py-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className={`text-[10px] uppercase tracking-widest ${tone[w.severity] || ""}`}>{w.severity}</p>
                      <span className="chip">{hazardLabel(w.hazard, t)}</span>
                    </div>
                    <p className="mt-2 text-sm font-semibold leading-snug">{w.title}</p>
                    {line ? <p className="mt-1 text-xs leading-snug text-neo-muted">{line}</p> : null}
                    <p className="mt-2 text-[10px] uppercase tracking-wide text-neo-muted">
                      {w.source}
                      {when ? ` · ${when}` : ""}
                    </p>
                  </article>
                );
              })}
            </div>
          )}

          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            <Quiet
              k={t.floodWatch}
              v={`${live?.flood?.trend || "—"} · ${live?.flood?.score_pct ?? "—"}%`}
              src="Open-Meteo GloFAS"
            />
            <Quiet
              k={t.aqi}
              v={
                live?.air?.cpcb?.value != null
                  ? `${live.air.cpcb.value} ${live.air.cpcb.category || ""}`.trim()
                  : "—"
              }
              src="CPCB / data.gov.in realtime"
            />
            <Quiet k={t.marine} v={marineLabel(live, t)} src={String(live?.marine?.source || "nearest-coast marine")} />
            <Quiet
              k={nearest ? t.nearestQuake : t.tsunami}
              v={
                nearest
                  ? `M${nearest.mag ?? "—"} · ${nearest.distance_km != null ? `${Math.round(nearest.distance_km)} km` : "—"}`
                  : tsunami?.title || t.noItews
              }
              src={nearest ? "USGS FDSN" : "INCOIS ITEWS"}
            />
          </div>
        </>
      ) : null}
    </section>
  );
}

function Quiet({ k, v, src }: { k: string; v: string; src: string }) {
  return (
    <div className="neo-in px-3 py-2">
      <p className="text-[10px] uppercase tracking-widest text-neo-muted">{k}</p>
      <p className="mt-0.5 text-sm font-semibold leading-snug">{v}</p>
      <p className="mt-1 text-[10px] text-neo-muted">{src}</p>
    </div>
  );
}
