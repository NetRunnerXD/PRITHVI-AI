"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Location, SatHistoryPack } from "@/types/dashboard";
import { COPY, type Locale } from "@/i18n/copy";
import { fetchNowcastSat } from "@/lib/api";
import {
  buildHistoryChart,
  buildLiveChart,
  chartFromPredSeries,
  interpSeries,
  parseIso,
  rateAt,
  type SatFormula,
} from "@/lib/satKalman";
import { useApp } from "@/lib/store";

type SatPack = {
  source?: string;
  source_kind?: string;
  obs_knots?: { t: string; mm?: number; mm_h?: number }[];
  playhead_rate?: number;
  last_error_mm_h?: number | null;
  mae?: number | null;
  n_updates?: number;
  next_obs_eta_s?: number | null;
  note?: string;
  formula?: SatFormula;
  pred_series?: { t: string; mm_h?: number; mm?: number }[];
  innovations?: { t: string; y: number; obs: number; pred: number }[];
  history?: SatHistoryPack;
  engine?: string;
};

export function NowcastSat({ loc, locale, seed }: { loc: Location; locale: Locale; seed?: SatPack | null }) {
  const t = COPY[locale];
  const reduce = useApp((s) => s.settings.reduceMotion);
  const stride = 60;
  const [sat, setSat] = useState<SatPack | null>(seed || null);
  const [now, setNow] = useState(() => new Date());
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let dead = false;
    async function load() {
      const data = await fetchNowcastSat(loc, 60);
      if (dead) return;
      if (!data) {
        setErr("sat");
        return;
      }
      setErr(null);
      setSat((data.sat as SatPack) || data);
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

  const form = sat?.formula;
  const liveRate =
    interpSeries(sat?.pred_series, now) ?? (form ? rateAt(form, now) : null) ?? sat?.playhead_rate ?? null;
  const lastObs = parseIso(form?.last_obs_t);
  const nativeStep = sat?.source_kind === "satellite-qpe" ? 1800 : 3600;
  const etaLive =
    lastObs != null
      ? Math.max(0, Math.round((lastObs.getTime() + nativeStep * 1000 - now.getTime()) / 1000))
      : sat?.next_obs_eta_s ?? null;

  const serverChart = useMemo(
    () => chartFromPredSeries(sat?.pred_series, stride, sat?.obs_knots || []),
    [sat?.pred_series, stride, sat?.obs_knots]
  );
  const fallbackChart = useMemo(() => {
    if (serverChart.length || !form) return [];
    return buildLiveChart(form, now, stride, sat?.obs_knots || []);
  }, [serverChart.length, form, now, stride, sat?.obs_knots]);
  const chart = serverChart.length ? serverChart : fallbackChart;

  const notSat = (sat?.source_kind || "model-analysis") !== "satellite-qpe";
  const lastY = sat?.last_error_mm_h;
  const innovations = (sat?.innovations || []).slice(-8);
  const hist = sat?.history;
  const histChart = useMemo(() => buildHistoryChart(hist?.series || []), [hist?.series]);
  const offsetBars = useMemo(() => {
    return (hist?.scenes || []).map((sc) => {
      const dt = parseIso(sc.t);
      return {
        label: dt
          ? dt.toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit" })
          : sc.t,
        y: sc.y,
        obs: sc.obs,
        pred: sc.pred,
      };
    });
  }, [hist?.scenes]);

  return (
    <section className="neo p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.satEngine}</p>
        </div>
      </div>

      <p className={`mt-2 text-[11px] ${notSat ? "text-neo-muted" : "text-neo-accent"}`}>
        {t.satSource}: {sat?.source || "om-analysis"}
      </p>

      <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <Chip k={t.satLiveRate} v={liveRate == null ? "—" : `${liveRate.toFixed(2)} mm/h`} hot={Boolean(liveRate && liveRate >= 4)} />
        <Chip
          k={t.satLastError}
          v={lastY == null ? "—" : `${lastY > 0 ? "+" : ""}${Number(lastY).toFixed(2)} mm/h`}
          sub={`${t.satMae} ${sat?.mae ?? "—"}`}
        />
        <Chip k={t.satUpdates} v={sat?.n_updates == null ? "—" : String(sat.n_updates)} />
        <Chip k={t.satNextScene} v={fmtEta(etaLive, t)} />
      </div>

      <div className="mt-3 h-56">
        {chart.length ? (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" />
              <XAxis dataKey="t" tick={{ fontSize: 10, fill: "var(--muted)" }} interval={stride <= 1 ? 29 : 9} />
              <YAxis tick={{ fontSize: 10, fill: "var(--muted)" }} width={40} />
              <Tooltip
                contentStyle={{ background: "var(--card)", border: "1px solid var(--line)", borderRadius: 12, fontSize: 12 }}
              />
              <Line type="monotone" dataKey="mmh" stroke="var(--rain)" strokeWidth={2} dot={false} name="mm/h" connectNulls isAnimationActive={false} />
              <Scatter dataKey="obs" fill="var(--accent)" name="obs" />
              <ReferenceLine
                x={nearestTick(chart, now.getTime())}
                stroke="var(--accent)"
                strokeWidth={2}
                label={{ value: t.now, fill: "var(--accent)", fontSize: 10 }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-sm text-neo-muted">{err ? t.satUnavailable : t.loading}</p>
        )}
      </div>

      <div className="mt-5 border-t border-neo-line pt-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.satHistory}</p>
        {histChart.length ? (
          <>
            <div className="mt-3 h-56">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={histChart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" />
                  <XAxis dataKey="label" tick={{ fontSize: 10, fill: "var(--muted)" }} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 10, fill: "var(--muted)" }} width={40} />
                  <Tooltip
                    contentStyle={{ background: "var(--card)", border: "1px solid var(--line)", borderRadius: 12, fontSize: 12 }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Line type="monotone" dataKey="pred" stroke="var(--rain)" strokeWidth={2} dot={false} connectNulls={false} name={t.satPredLine} />
                  <Line type="stepAfter" dataKey="held" stroke="var(--muted)" strokeDasharray="5 4" strokeWidth={1.5} dot={false} name={t.satHeldLine} />
                  <Scatter dataKey="obs" fill="var(--accent)" name={t.satScenePts} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            {offsetBars.length ? (
              <div className="mt-3 h-36">
                <p className="mb-1 text-[10px] uppercase tracking-widest text-neo-muted">{t.satOffset}</p>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={offsetBars} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" />
                    <XAxis dataKey="label" tick={{ fontSize: 10, fill: "var(--muted)" }} interval={0} />
                    <YAxis tick={{ fontSize: 10, fill: "var(--muted)" }} width={40} />
                    <Tooltip
                      contentStyle={{ background: "var(--card)", border: "1px solid var(--line)", borderRadius: 12, fontSize: 12 }}
                    />
                    <ReferenceLine y={0} stroke="var(--line)" />
                    <Bar dataKey="y" name={t.satOffset} maxBarSize={28}>
                      {offsetBars.map((row, i) => (
                        <Cell key={`${row.label}-${i}`} fill={row.y >= 0 ? "var(--rain)" : "var(--danger)"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : null}
          </>
        ) : (
          <p className="mt-2 text-sm text-neo-muted">{t.satNoHistory}</p>
        )}
      </div>

      {innovations.length ? (
        <div className="mt-3 overflow-x-auto">
          <p className="mb-1 text-[10px] uppercase tracking-widest text-neo-muted">{t.satInnovation}</p>
          <table className="w-full text-left text-[11px]">
            <thead>
              <tr className="text-neo-muted">
                <th className="py-1 font-medium">t</th>
                <th className="py-1 font-medium">obs</th>
                <th className="py-1 font-medium">pred</th>
                <th className="py-1 font-medium">y</th>
              </tr>
            </thead>
            <tbody>
              {innovations.map((row) => (
                <tr key={row.t} className="border-t border-neo-line">
                  <td className="py-1 font-mono">
                    {parseIso(row.t)?.toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit" }) ||
                      row.t}
                  </td>
                  <td className="py-1 font-mono">{row.obs.toFixed(2)}</td>
                  <td className="py-1 font-mono">{row.pred.toFixed(2)}</td>
                  <td className={`py-1 font-mono ${Math.abs(row.y) >= 1 ? "text-neo-danger" : ""}`}>
                    {row.y > 0 ? "+" : ""}
                    {row.y.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}


    </section>
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

function fmtEta(secs: number | null | undefined, t: Record<string, string>) {
  if (secs == null) return "—";
  if (secs <= 0) return t.satSceneDue;
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
