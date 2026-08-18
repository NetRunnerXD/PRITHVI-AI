"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DashboardSnapshot, NowcastPack, SatKalmanPack } from "@/types/dashboard";
import { NowcastSat } from "@/components/NowcastSat";
import { COPY, type Locale } from "@/i18n/copy";
import { fetchNowcastLive } from "@/lib/api";
import { gapFromHours } from "@/lib/nowcastGap";
import { rain } from "@/lib/units";
import { useApp } from "@/lib/store";

type LivePack = {
  as_of?: string;
  knots?: { t: string; mm: number; engine?: string; p_wet?: number; lead_h?: number }[];
  gap?: { dt_s?: number; series?: { t: string; mm: number; mm_h?: number; p_wet?: number }[]; note?: string };
  playhead?: Record<string, unknown>;
  clock?: { t_start?: string | null; t_stop?: string | null };
  pump?: { action?: string; p_interrupt_90m?: number; liters_at_risk?: number };
  access?: { enterable?: boolean; reasons?: string[] };
  ponding?: { mm_60?: number; factor?: number };
  kal?: { level?: string };
  tide?: { drain_blocked?: boolean };
  locked?: Record<string, unknown>;
  actions?: { id?: string; action?: string }[];
  provenance?: Record<string, string>;
  port?: { active?: boolean; signal?: string | null };
  monsoon?: { label?: string; regime?: string };
  cwc?: { name?: string; km?: number; river?: string };
  sat?: SatKalmanPack;
};

function hhmmss(d: Date) {
  return d.toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function parseIso(t?: string | null) {
  if (!t) return null;
  const d = new Date(t.includes("T") ? t : `${t}+05:30`);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** Hugli M2 prior — matches backend hugli_harmonics_v1 for Haldia. */
function tideHaldia(now: Date) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).formatToParts(now);
  const h = Number(parts.find((p) => p.type === "hour")?.value || 0);
  const m = Number(parts.find((p) => p.type === "minute")?.value || 0);
  const s = Number(parts.find((p) => p.type === "second")?.value || 0);
  const hour = h + m / 60 + s / 3600;
  const phase = 1.1;
  const m2 = 2 * Math.PI * (hour / 12.42 + phase / (2 * Math.PI));
  const s2 = 2 * Math.PI * (hour / 12.0 + phase / (2 * Math.PI) + 0.08);
  const k1 = 2 * Math.PI * (hour / 23.93 + 0.2);
  return 2.55 + 1.55 * Math.sin(m2) + 0.58 * Math.sin(s2) + 0.16 * Math.sin(k1);
}

export function NowcastLive({ dash, locale }: { dash: DashboardSnapshot; locale: Locale }) {
  const t = COPY[locale];
  const units = useApp((s) => s.settings.units);
  const reduce = useApp((s) => s.settings.reduceMotion);
  const loc = dash.location;
  const [live, setLive] = useState<LivePack | null>(null);
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    let dead = false;
    async function load() {
      const data = await fetchNowcastLive(loc);
      if (dead || !data) return;
      const knots = (data.knots as LivePack["knots"]) || (data.hours as LivePack["knots"]);
      setLive({
        ...(data as LivePack),
        knots,
        gap: (data.gap as LivePack["gap"]) || undefined,
      });
    }
    void load();
    const id = window.setInterval(() => void load(), 90_000);
    return () => {
      dead = true;
      window.clearInterval(id);
    };
  }, [loc.id, loc.lat, loc.lon, loc.place_name]);

  useEffect(() => {
    if (reduce) return;
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, [reduce]);

  const nc: NowcastPack | undefined = dash.science?.nowcast;
  const gap = live?.gap?.series || nc?.gap?.series || gapFromHours(live?.knots || nc?.hours);
  const tideM = tideHaldia(now);
  const onset = parseIso(live?.clock?.t_start || nc?.clock?.t_start);
  const secs = onset ? Math.round((onset.getTime() - now.getTime()) / 1000) : null;
  const factor = Number(live?.ponding?.factor ?? nc?.ponding?.factor ?? 0.2);
  let pond = 0;
  let rate = 0;
  for (const row of gap) {
    const dt = parseIso(row.t);
    if (!dt || dt > now) break;
    pond += Number(row.mm || 0) * factor;
    rate = Number(row.mm_h || 0);
  }

  const chart = useMemo(() => {
    return gap.slice(0, 180).map((row) => {
      const dt = parseIso(row.t);
      return {
        t: dt ? dt.toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit" }) : row.t,
        ms: dt?.getTime() || 0,
        mmh: Number(row.mm_h || 0),
        p: Number(row.p_wet || 0),
      };
    });
  }, [gap]);

  const nowMs = now.getTime();
  const minuteBar = gap.slice(0, 120);
  const pump = live?.pump || nc?.pump;
  const access = live?.access || nc?.access;
  const kal = live?.kal || nc?.kal;
  const drain = live?.tide?.drain_blocked ?? nc?.tide?.drain_blocked;
  const prov = live?.provenance || dash.science?.provenance;

  return (
    <div className="space-y-3">
      <section className="neo p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.tabNowcast}</h2>
          <p className="font-mono text-sm font-bold text-neo-accent">{hhmmss(now)}</p>
        </div>
        <p className="mt-1 text-xs text-neo-muted">{t.liveClockHint}</p>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <Chip k={t.secondsToOnset} v={fmtCountdown(secs, t)} />
          <Chip k={t.tideHaldia} v={`${tideM.toFixed(2)} m`} sub={t.tideProxy} />
          <Chip k={t.ponding} v={rain(pond, units)} />
          <Chip k={t.gapRate} v={`${rate.toFixed(2)} mm/h`} sub={t.notAForecast} />
        </div>
        <div className="mt-3 grid gap-2 sm:grid-cols-3">
          <Chip
            k={t.pumpSet}
            v={(pump?.action || "—").toUpperCase()}
            sub={`${t.pInterrupt} ${pump?.p_interrupt_90m ?? "—"}`}
            hot={pump?.action === "hold"}
          />
          <Chip k={t.fieldAccess} v={access?.enterable === false ? t.closedField : t.enterable} hot={access?.enterable === false} />
          <Chip
            k={t.kalWatch}
            v={kal?.level === "watch" || drain ? t.watchThis : t.allClear}
            hot={kal?.level === "watch" || Boolean(drain)}
          />
        </div>
      </section>

      <NowcastSat loc={loc} locale={locale} seed={(live?.sat || nc?.sat) as SatKalmanPack | undefined} />

      <section className="neo p-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.liveSweep}</p>
        <p className="mt-1 text-[11px] text-neo-muted">{t.liveSweepHint}</p>
        <div className="mt-3 h-56">
          {chart.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" />
                <XAxis dataKey="t" tick={{ fontSize: 10, fill: "var(--muted)" }} interval={14} />
                <YAxis tick={{ fontSize: 10, fill: "var(--muted)" }} width={36} />
                <Tooltip
                  contentStyle={{ background: "var(--card)", border: "1px solid var(--line)", borderRadius: 12, fontSize: 12 }}
                />
                <Area type="monotone" dataKey="mmh" stroke="var(--rain)" fill="var(--rain)" fillOpacity={0.25} name="mm/h" />
                <ReferenceLine
                  x={nearestTick(chart, nowMs)}
                  stroke="var(--accent)"
                  strokeWidth={2}
                  label={{ value: t.now, fill: "var(--accent)", fontSize: 10 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-neo-muted">{t.loading}</p>
          )}
        </div>
      </section>

      <section className="neo overflow-x-auto p-3">
        <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.minuteBar}</p>
        <div className="flex min-w-max gap-0.5">
          {minuteBar.map((row, i) => {
            const dt = parseIso(row.t);
            const past = dt ? dt <= now : false;
            const wet = Number(row.p_wet || 0);
            const mm = Number(row.mm || 0);
            const bg = mm >= 0.4 || wet >= 0.55 ? "var(--rain)" : wet >= 0.3 ? "var(--accent)" : "var(--line)";
            return (
              <div key={`${row.t}-${i}`} className="w-1.5 shrink-0" title={`${row.t} ${mm.toFixed(2)} mm`}>
                <div className="h-8 rounded-sm" style={{ background: bg, opacity: past ? 1 : 0.45 }} />
              </div>
            );
          })}
        </div>
        <p className="mt-2 text-[10px] text-neo-muted">{t.minuteBarHint}</p>
      </section>

      <section className="neo p-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.pondTank}</p>
        <div className="mt-3 h-16 overflow-hidden rounded-2xl bg-neo-bg">
          <div
            className="h-full rounded-2xl"
            style={{ width: `${Math.min(100, pond * 18)}%`, background: "var(--rain)", transition: reduce ? "none" : "width 0.8s linear" }}
          />
        </div>
        <p className="mt-2 font-mono text-sm">{rain(pond, units)}</p>
      </section>

      <section className="neo grid gap-2 p-4 text-sm md:grid-cols-2">
        <p>
          <span className="text-neo-muted">{t.monsoonClock}: </span>
          {(live?.monsoon || dash.science?.monsoon)?.label || "—"}
        </p>
        <p>
          <span className="text-neo-muted">{t.nearestRiver}: </span>
          {live?.cwc?.name || dash.science?.cwc?.name || "—"}
          {live?.cwc?.km != null ? ` · ${live.cwc.km} km` : ""}
        </p>
        <p>
          <span className="text-neo-muted">{t.portSignal}: </span>
          {live?.port?.active ? live.port.signal || t.watchThis : t.allClear}
        </p>
        <p className="text-xs text-neo-muted md:col-span-2">{live?.gap?.note || t.liveClockHint}</p>
      </section>

      {prov ? (
        <section className="neo p-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.provenance}</p>
          <ul className="mt-2 space-y-1 text-xs text-neo-muted">
            {Object.entries(prov).map(([k, v]) => (
              <li key={k}>
                <span className="font-semibold text-neo-text">{k}</span> — {v}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

function Chip({ k, v, sub, hot }: { k: string; v: string; sub?: string; hot?: boolean }) {
  return (
    <div className={`neo-in rounded-2xl px-3 py-2 ${hot ? "ring-1 ring-neo-danger" : ""}`}>
      <p className="text-[10px] uppercase tracking-widest text-neo-muted">{k}</p>
      <p className="mt-1 text-sm font-bold">{v}</p>
      {sub ? <p className="text-[11px] text-neo-muted">{sub}</p> : null}
    </div>
  );
}

function fmtCountdown(secs: number | null, t: Record<string, string>) {
  if (secs == null) return "—";
  if (secs < 0) return t.onsetPassed;
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  if (h) return `${h}h ${m}m ${s}s`;
  return `${m}m ${s}s`;
}

function nearestTick(chart: { t: string; ms: number }[], nowMs: number) {
  if (!chart.length) return "";
  let best = chart[0];
  for (const row of chart) {
    if (Math.abs(row.ms - nowMs) < Math.abs(best.ms - nowMs)) best = row;
  }
  return best.t;
}
