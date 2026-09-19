"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DashboardSnapshot } from "@/types/dashboard";
import { COPY, type Locale } from "@/i18n/copy";
import { useApp } from "@/lib/store";
import { localizeDigits, rain, rainUnit, speed, temp, tempUnit } from "@/lib/units";
import { LaymanSummaryBody } from "../LaymanSummaryView";
import { getRainLaymanSummary, getWindLaymanSummary } from "@/lib/laymanSummaries";
import { tWord } from "./i18n";
import { beaufortScale, hhmm, imdRainfallCategory, tip, weekday } from "./helpers";

export function Stat({ k, v }: { k: string; v: string }) {
  const displayNull = useApp((s) => s.settings.displayNullValues);
  if (!displayNull && (v == null || v === "—" || v === "" || v === "undefined" || v === "null")) {
    return null;
  }
  return (
    <div>
      <p className="text-[10px] uppercase tracking-widest text-neo-muted">{k}</p>
      <p className="font-mono text-lg font-semibold">{v}</p>
    </div>
  );
}


export function RainOdds({ k, pct, days }: { k: string; pct: number[]; days: string[] }) {
  if (!pct.length) {
    return <Stat k={k} v="—" />;
  }
  return (
    <div>
      <p className="text-[10px] uppercase tracking-widest text-neo-muted">{k}</p>
      <div className="mt-0.5 grid grid-cols-3 gap-1">
        {pct.map((p, i) => (
          <div key={days[i] || i} className="text-center">
            <p className="font-mono text-lg font-semibold">{p}%</p>
            <p className="text-[10px] uppercase tracking-widest text-neo-muted">{days[i] || `DAY${i + 1}`}</p>
          </div>
        ))}
      </div>
    </div>
  );
}


export function Spark({
  title,
  data,
  color,
  unit,
  kind = "area",
}: {
  title: string;
  data: { t: string; v: number }[];
  color: string;
  unit: string;
  kind?: "area" | "bar";
}) {
  return (
    <section className="neo p-3">
      <div className="mb-1 flex items-baseline justify-between">
        <h3 className="text-[11px] font-bold uppercase tracking-[0.14em] text-neo-accent">{title}</h3>
        <span className="text-[10px] text-neo-muted">{unit}</span>
      </div>
      <div className="h-32">
        {data.length === 0 ? (
          <p className="flex h-full items-center justify-center text-xs text-neo-muted">—</p>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            {kind === "bar" ? (
              <BarChart data={data}>
                <CartesianGrid stroke="var(--line)" vertical={false} />
                <XAxis dataKey="t" stroke="var(--muted)" fontSize={9} interval={3} />
                <YAxis stroke="var(--muted)" fontSize={9} width={28} />
                <Tooltip contentStyle={tip} />
                <Bar dataKey="v" fill={color} radius={[4, 4, 0, 0]} />
              </BarChart>
            ) : (
              <AreaChart data={data}>
                <CartesianGrid stroke="var(--line)" vertical={false} />
                <XAxis dataKey="t" stroke="var(--muted)" fontSize={9} interval={3} />
                <YAxis stroke="var(--muted)" fontSize={9} width={28} />
                <Tooltip contentStyle={tip} />
                <Area type="monotone" dataKey="v" stroke={color} fill={color} fillOpacity={0.18} strokeWidth={2} />
              </AreaChart>
            )}
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}


export function RainfallSection({
  dash,
  locale,
  units,
  onNavigateData,
  className,
  forceSummary,
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  units: "metric" | "imperial";
  onNavigateData?: (subTab: string) => void;
  className?: string;
  forceSummary?: boolean;
}) {
  const displayNull = useApp((s) => s.settings.displayNullValues);
  const t = COPY[locale];
  const [rainTab, setRainTab] = useState<"live" | "hourly" | "outlook">("live");

  const [localSummary, setLocalSummary] = useState<boolean | null>(null);
  useEffect(() => {
    setLocalSummary(null);
  }, [forceSummary]);
  const isSummary = localSummary !== null ? localSummary : Boolean(forceSummary);

  const cur = dash.descriptive.current;
  const series = dash.descriptive.series;
  const sky = dash.live?.sky || {};
  const predictive = dash.predictive;

  const precip1h = sky.precip_1h_mm ?? cur.precip_1h_mm ?? 0;
  const todayRainMm = predictive.outlook_days?.[0]?.precip_mm ?? series.precip_daily?.[0]?.value ?? 0;
  const precip3dMm = predictive.precip_next_3d_mm ?? 0;
  const precip7dMm = predictive.precip_7d_mm ?? ((predictive.outlook_days || []).reduce((acc, d) => acc + (d.precip_mm || 0), 0));

  const todayProb = predictive.outlook_days?.[0]?.precip_prob_pct ?? predictive.precip_probability_pct?.[0] ?? 0;
  const hourlySlots = predictive.hourly || [];

  const imdCat = imdRainfallCategory(todayRainMm);

  // 24-hour hyetograph data
  const hourlyRain24 = (hourlySlots.length > 0
    ? hourlySlots.slice(0, 24).map((h) => ({
      t: h.hour || hhmm(h.t),
      v: units === "imperial" ? (h.precip_mm ? Math.round((h.precip_mm / 25.4) * 100) / 100 : 0) : (h.precip_mm ?? 0),
      prob: h.precip_prob_pct ?? 0,
    }))
    : (series.precip_hourly || []).slice(0, 24).map((p) => ({
      t: hhmm(p.t),
      v: units === "imperial" ? Math.round((p.value / 25.4) * 100) / 100 : p.value,
      prob: todayProb,
    })));

  // Next 8 hours mini hyetograph
  const rain8h = hourlyRain24.slice(0, 8);

  const wetHoursCount = hourlyRain24.filter((h) => h.v > 0.05).length;
  const peakRainHour = hourlyRain24.reduce((max, h) => (h.v > max.v ? h : max), { t: "—", v: 0, prob: 0 });

  // 7-day outlook data
  const days7 = (predictive.outlook_days || []).slice(0, 7).map((d, i) => ({
    day: weekday(d.date),
    precip: units === "imperial" ? Math.round((d.precip_mm / 25.4) * 100) / 100 : d.precip_mm,
    prob: d.precip_prob_pct ?? (predictive.precip_probability_pct?.[i] ?? 0),
    balance: d.water_balance_mm,
  }));

  const waterBalance = predictive.water_balance_7d_mm ?? (predictive.outlook_days?.[0]?.water_balance_mm ?? 0);

  return (
    <section
      onClick={() => setLocalSummary(!isSummary)}
      className={`neo neo-section-rain p-4 cursor-pointer transition hover:border-[color-mix(in_srgb,var(--accent)_35%,var(--line))] ${className || "sm:col-span-6 lg:col-span-4 flex flex-col justify-start select-none"}`}
      title="Click card to switch between detailed data and overview"
    >
      {/* Header with Segmented Navigation */}
      <div className="flex shrink-0 items-center justify-between gap-2 flex-wrap mb-2">
        <div className="flex items-center gap-1.5">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400">
            <path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242" />
            <path d="M16 14v6M8 14v6M12 16v6" />
          </svg>
          <p className="text-[11px] font-black uppercase tracking-[0.18em] text-blue-700 dark:text-blue-400">
            {t.rainfall || "Rainfall"}
          </p>
        </div>
        {!isSummary && (
          <div className="inline-flex rounded-xl bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] p-0.5 border border-[var(--line)] shadow-inner">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setRainTab("live");
              }}
              className={`rounded-lg px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${rainTab === "live"
                  ? "bg-neo-accent text-white shadow-sm"
                  : "text-neo-muted hover:text-neo-text"
                }`}
            >
              Live
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setRainTab("hourly");
              }}
              className={`rounded-lg px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${rainTab === "hourly"
                  ? "bg-neo-accent text-white shadow-sm"
                  : "text-neo-muted hover:text-neo-text"
                }`}
              title="24-hour hyetograph"
            >
              24h
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setRainTab("outlook");
              }}
              className={`rounded-lg px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${rainTab === "outlook"
                  ? "bg-neo-accent text-white shadow-sm"
                  : "text-neo-muted hover:text-neo-text"
                }`}
              title="7-Day precipitation & water budget"
            >
              7-Day
            </button>
          </div>
        )}
      </div>

      <div className="w-full">
        {isSummary ? (
          <LaymanSummaryBody summary={getRainLaymanSummary(dash, locale, units)} />
        ) : (
          <>
            {/* Tab 1: Live / Accumulation Summary */}
            {rainTab === "live" && (
              <div key="rain-live" className="fade-in-scale space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="text-[9px] uppercase tracking-widest text-neo-muted font-bold">1h Rate / Today</p>
                    <div className="flex items-baseline gap-2 mt-0.5">
                      <span className="font-mono text-xl sm:text-2xl font-black text-neo-rain leading-none">
                        {rain(precip1h, units)}
                      </span>
                      <span className="text-[10px] font-mono font-semibold text-neo-muted">
                        ({rain(todayRainMm, units)} total)
                      </span>
                    </div>
                  </div>
                  <span
                    className={`chip text-[9px] font-bold uppercase px-2 py-0.5 whitespace-nowrap border ${imdCat.isAlert
                        ? "animate-pulse border-neo-danger text-neo-danger bg-[color-mix(in_srgb,var(--danger)_12%,transparent)]"
                        : "border-[color-mix(in_srgb,var(--line)_60%,transparent)]"
                      }`}
                    style={{ color: imdCat.color, backgroundColor: imdCat.bg }}
                  >
                    {imdCat.label}
                  </span>
                </div>

                <div className="grid grid-cols-4 gap-1 pt-1 border-t border-[color-mix(in_srgb,var(--line)_50%,transparent)]">
                  <div className="neo-in p-1 rounded-xl text-center">
                    <span className="text-[8px] uppercase tracking-wider text-neo-muted font-bold block">3-Day</span>
                    <span className="font-mono text-xs font-bold text-neo-rain mt-0.5 block truncate">
                      {rain(precip3dMm, units)}
                    </span>
                  </div>
                  <div className="neo-in p-1 rounded-xl text-center">
                    <span className="text-[8px] uppercase tracking-wider text-neo-muted font-bold block">7-Day</span>
                    <span className="font-mono text-xs font-bold text-neo-text mt-0.5 block truncate">
                      {rain(precip7dMm, units)}
                    </span>
                  </div>
                  <div className="neo-in p-1 rounded-xl text-center">
                    <span className="text-[8px] uppercase tracking-wider text-neo-muted font-bold block">Chance</span>
                    <span className="font-mono text-xs font-bold text-neo-accent mt-0.5 block truncate">
                      {todayProb}%
                    </span>
                  </div>
                  <div className="neo-in p-1 rounded-xl text-center">
                    <span className="text-[8px] uppercase tracking-wider text-neo-muted font-bold block">Balance</span>
                    <span className="font-mono text-xs font-bold text-neo-text mt-0.5 block truncate">
                      {waterBalance > 0 ? `+${waterBalance}` : `${waterBalance}`}
                    </span>
                  </div>
                </div>

                {rain8h.length > 0 && (
                  <div className="h-14 pt-1.5 border-t border-[color-mix(in_srgb,var(--line)_40%,transparent)]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={rain8h} margin={{ top: 2, right: 2, left: -20, bottom: 0 }}>
                        <XAxis dataKey="t" stroke="var(--muted)" fontSize={8} tickLine={false} />
                        <Tooltip contentStyle={tip} />
                        <Bar dataKey="v" fill="var(--rain)" radius={[3, 3, 0, 0]} opacity={0.9} name={`Rain (${rainUnit(units)})`} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            )}

            {/* Tab 2: 24h Hourly Hyetograph */}
            {rainTab === "hourly" && (
              <div key="rain-hourly" className="fade-in-scale space-y-1.5">
                <div className="flex items-center justify-between text-[10px]">
                  <span className="text-neo-muted font-semibold">24h Hyetograph</span>
                  <span className="font-mono font-bold text-neo-rain">
                    {peakRainHour.v > 0 ? `Peak: ${peakRainHour.v} ${rainUnit(units)} @ ${peakRainHour.t}` : "Dry 24h"}
                  </span>
                </div>
                <div className="h-24 sm:h-28">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={hourlyRain24}>
                      <CartesianGrid stroke="var(--line)" vertical={false} strokeDasharray="3 3" />
                      <XAxis dataKey="t" stroke="var(--muted)" fontSize={8} interval={3} />
                      <YAxis stroke="var(--muted)" fontSize={8} width={24} />
                      <Tooltip contentStyle={tip} />
                      <Bar
                        dataKey="v"
                        fill="var(--rain)"
                        radius={[3, 3, 0, 0]}
                        name={`Rain (${rainUnit(units)})`}
                        isAnimationActive={true}
                        animationDuration={300}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <div className="flex items-center justify-between text-[9px] text-neo-muted pt-1 border-t border-[color-mix(in_srgb,var(--line)_50%,transparent)]">
                  <span>{wetHoursCount} wet hour{wetHoursCount === 1 ? "" : "s"} forecast</span>
                  <span className="font-mono font-semibold text-neo-text">24h Sum: {rain(todayRainMm, units)}</span>
                </div>
              </div>
            )}

            {/* Tab 3: 7-Day Precipitation Outlook & Water Budget */}
            {rainTab === "outlook" && (
              <div key="rain-outlook" className="fade-in-scale space-y-1.5">
                <div className="flex items-center justify-between text-[10px] text-neo-muted font-semibold pb-1 border-b border-[color-mix(in_srgb,var(--line)_50%,transparent)]">
                  <span>7-Day Rain Outlook</span>
                  <span className="font-mono font-bold text-neo-rain">Total: {rain(precip7dMm, units)}</span>
                </div>
                <div className="space-y-1">
                  {days7.map((d) => (
                    <div key={d.day} className="neo-in px-2 py-0.5 rounded-lg flex items-center justify-between gap-2 text-[10px]">
                      <span className="font-medium text-neo-text w-8 shrink-0">{d.day}</span>
                      <div className="flex-1 h-1.5 rounded-full bg-[var(--line)] overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500 bg-neo-rain"
                          style={{ width: `${Math.min(100, Math.round((Number(d.precip) / (units === "imperial" ? 1.5 : 35)) * 100))}%` }}
                        />
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0 min-w-[4rem] justify-end">
                        <span className="font-mono font-bold text-neo-rain">{d.precip} {rainUnit(units)}</span>
                        <span className="text-[9px] text-neo-muted">({d.prob}%)</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}


export function WindSection({
  dash,
  locale,
  units,
  onNavigateData,
  className,
  forceSummary,
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  units: "metric" | "imperial";
  onNavigateData?: (subTab: string) => void;
  className?: string;
  forceSummary?: boolean;
}) {
  const displayNull = useApp((s) => s.settings.displayNullValues);
  const t = COPY[locale];

  const [localSummary, setLocalSummary] = useState<boolean | null>(null);
  useEffect(() => {
    setLocalSummary(null);
  }, [forceSummary]);
  const isSummary = localSummary !== null ? localSummary : Boolean(forceSummary);

  const live = dash.live;
  const wind = live?.wind || {};
  const rose = wind.rose || [];
  const quality = dash.quality || {};
  const climate = (quality.climate || {}) as Record<string, unknown>;
  const series = dash.descriptive.series;

  const [windTab, setWindTab] = useState<"live" | "altitude" | "trend">("live");

  const speedKmh = wind.speed_kmh != null ? Number(wind.speed_kmh) : (climate.wind_10m != null ? Number(climate.wind_10m) : null);
  const beaufort = beaufortScale(speedKmh);

  const windGusts = climate.wind_gusts_10m != null ? Number(climate.wind_gusts_10m) : null;
  const windMax10m = climate.wind_10m_max != null ? Number(climate.wind_10m_max) : null;
  const windMean10m = climate.wind_10m_mean != null ? Number(climate.wind_10m_mean) : null;

  // Altitude wind profile (10m, 80m, 120m, 180m)
  const rawAltLevels = [
    {
      level: "180 m",
      name: "Lower Troposphere",
      speed: Number(climate.wind_180m ?? (climate.wind_10m != null ? Number(climate.wind_10m) * 1.45 : 0)),
      dir: Number(climate.wind_dir_180m ?? wind.direction_deg ?? 0),
      raw: climate.wind_180m,
      color: "#0284c7",
    },
    {
      level: "120 m",
      name: "Boundary Layer",
      speed: Number(climate.wind_120m ?? (climate.wind_10m != null ? Number(climate.wind_10m) * 1.3 : 0)),
      dir: Number(climate.wind_dir_120m ?? wind.direction_deg ?? 0),
      raw: climate.wind_120m,
      color: "#0ea5e9",
    },
    {
      level: "80 m",
      name: "Wind Turbine Hub",
      speed: Number(climate.wind_80m ?? (climate.wind_10m != null ? Number(climate.wind_10m) * 1.18 : 0)),
      dir: Number(climate.wind_dir_80m ?? wind.direction_deg ?? 0),
      raw: climate.wind_80m,
      color: "var(--accent)",
    },
    {
      level: "10 m",
      name: "Surface Layer",
      speed: Number(climate.wind_10m ?? speedKmh ?? 0),
      dir: Number(climate.wind_dir_10m ?? wind.direction_deg ?? 0),
      raw: climate.wind_10m ?? speedKmh,
      color: "#10b981",
    },
  ];
  const altLevels = displayNull ? rawAltLevels : rawAltLevels.filter((a) => a.raw != null && !isNaN(Number(a.raw)));

  const maxAltSpeed = Math.max(1, ...altLevels.map((a) => a.speed));

  // 24h trend data
  const wind24h = (series.wind_hourly || []).slice(0, 24).map((p) => ({
    t: hhmm(p.t),
    v: units === "imperial" ? Math.round(p.value * 0.621) : p.value,
  }));

  // Mini 8h data
  const wind8h = (wind.hourly && wind.hourly.length > 0 ? wind.hourly.slice(0, 8) : (series.wind_hourly || []).slice(0, 8)).map((h) => {
    const rawVal = "speed" in h ? Number(h.speed) : Number(h.value);
    return {
      t: hhmm(h.t),
      v: units === "imperial" ? Math.round(rawVal * 0.621) : Math.round(rawVal),
    };
  });

  return (
    <section
      onClick={() => setLocalSummary(!isSummary)}
      className={`neo neo-section-wind p-4 cursor-pointer transition hover:border-[color-mix(in_srgb,var(--accent)_35%,var(--line))] ${className || "sm:col-span-6 lg:col-span-4 flex flex-col justify-start select-none"}`}
      title="Click card to switch between detailed data and overview"
    >
      {/* Header with Segmented Navigation */}
      <div className="flex shrink-0 items-center justify-between gap-2 flex-wrap mb-2">
        <div className="flex items-center gap-1.5">
          <p className="text-[11px] font-black uppercase tracking-[0.18em] text-teal-700 dark:text-teal-400">{t.windProfile}</p>
        </div>
        {!isSummary && (
          <div className="inline-flex rounded-xl bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] p-0.5 border border-[var(--line)] shadow-inner">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setWindTab("live");
              }}
              className={`rounded-lg px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${windTab === "live"
                  ? "bg-neo-accent text-white shadow-sm"
                  : "text-neo-muted hover:text-neo-text"
                }`}
            >
              Live
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setWindTab("altitude");
              }}
              className={`rounded-lg px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${windTab === "altitude"
                  ? "bg-neo-accent text-white shadow-sm"
                  : "text-neo-muted hover:text-neo-text"
                }`}
              title="Atmospheric wind profile from 10m to 180m"
            >
              10–180m
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setWindTab("trend");
              }}
              className={`rounded-lg px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${windTab === "trend"
                  ? "bg-neo-accent text-white shadow-sm"
                  : "text-neo-muted hover:text-neo-text"
                }`}
              title="24-hour wind forecast graph"
            >
              24h
            </button>
          </div>
        )}
      </div>

      <div className="w-full">
        {isSummary ? (
          <LaymanSummaryBody summary={getWindLaymanSummary(dash, locale, units)} />
        ) : (
          <>
            {/* Tab 1: Live & Compass */}
            {windTab === "live" && (
              <div key="wind-live" className="fade-in-scale space-y-2">
                <div className="flex items-center gap-2.5 sm:gap-3">
                  <WindRose
                    fromDeg={wind.direction_deg ?? null}
                    flowDeg={wind.flow_deg ?? null}
                    rose={rose}
                    compass={wind.compass || "—"}
                    flow={wind.flow_compass || "—"}
                  />
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <div className="flex items-center justify-between gap-1">
                      <div>
                        <p className="text-[9px] uppercase tracking-widest text-neo-muted font-bold">Speed</p>
                        <p className="font-mono text-xl sm:text-2xl font-black text-neo-accent leading-none mt-0.5">
                          {speed(speedKmh, units)}
                        </p>
                      </div>
                      <span className="chip text-[9px] font-bold uppercase px-2 py-0.5 whitespace-nowrap bg-[color-mix(in_srgb,var(--accent)_12%,transparent)] text-neo-accent border border-[color-mix(in_srgb,var(--accent)_25%,transparent)] shadow-xs">
                        {beaufort.label}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-xs py-0.5 border-t border-[color-mix(in_srgb,var(--line)_50%,transparent)]">
                      <span className="text-neo-muted text-[9px] uppercase tracking-wider font-semibold">Heading</span>
                      <span className="font-bold font-mono text-[11px] flex items-center gap-1">
                        <span>{wind.compass || "—"}</span>
                        <span className="text-neo-muted text-[9px]">({wind.direction_deg ?? "—"}°)</span>
                        <span className="text-neo-accent font-black">→</span>
                        <span>{wind.flow_compass || "—"}</span>
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-1.5 text-[10px]">
                      {(displayNull || windGusts != null) && (
                        <div className="neo-in px-2 py-1 rounded-xl">
                          <span className="text-neo-muted block text-[8px] uppercase tracking-wider font-bold">
                            {locale === "hi" ? "झोंके" : locale === "bn" ? "দমকা" : "Gusts"}
                          </span>
                          <span className="font-mono font-extrabold text-neo-warn">{windGusts != null ? speed(windGusts, units) : "—"}</span>
                        </div>
                      )}
                      {(displayNull || windMax10m != null) && (
                        <div className="neo-in px-2 py-1 rounded-xl">
                          <span className="text-neo-muted block text-[8px] uppercase tracking-wider font-bold">
                            {locale === "hi" ? "अधिकतम 10m" : locale === "bn" ? "সর্বোচ্চ ১০ মি" : "10m Max"}
                          </span>
                          <span className="font-mono font-extrabold text-neo-accent">{windMax10m != null ? speed(windMax10m, units) : "—"}</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {wind8h.length > 0 && (
                  <div className="h-14 pt-1.5 border-t border-[color-mix(in_srgb,var(--line)_40%,transparent)]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={wind8h} margin={{ top: 2, right: 2, left: -20, bottom: 0 }}>
                        <XAxis dataKey="t" stroke="var(--muted)" fontSize={8} tickLine={false} />
                        <Tooltip contentStyle={tip} />
                        <Bar dataKey="v" fill="var(--accent)" radius={[3, 3, 0, 0]} opacity={0.85} name={`Wind (${units === "imperial" ? "mph" : "km/h"})`} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            )}

            {/* Tab 2: Altitude Profile 10m–180m */}
            {windTab === "altitude" && (
              <div key="wind-altitude" className="fade-in-scale space-y-1.5">
                <div className="flex items-center justify-between text-[10px] text-neo-muted font-semibold pb-1 border-b border-[color-mix(in_srgb,var(--line)_50%,transparent)]">
                  <span>Altitude & Layer</span>
                  <span>Speed & Heading</span>
                </div>
                <div className="space-y-1.5">
                  {altLevels.map((a) => {
                    const pct = Math.min(100, Math.round((a.speed / Math.max(maxAltSpeed, 1)) * 100));
                    return (
                      <div key={a.level} className="neo-in px-2 py-1 rounded-xl flex items-center justify-between gap-2 group transition-all hover:bg-[color-mix(in_srgb,var(--card)_80%,transparent)]">
                        <div className="min-w-0 flex items-center gap-1.5">
                          <span className="chip px-1.5 py-0 text-[8px] font-bold uppercase shrink-0" style={{ color: a.color }}>
                            {a.level}
                          </span>
                          <span className="text-[10px] font-medium text-neo-muted truncate hidden sm:inline">{a.name}</span>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          {/* Bar indicator */}
                          <div className="w-12 sm:w-16 h-1.5 rounded-full bg-[var(--line)] overflow-hidden">
                            <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, backgroundColor: a.color }} />
                          </div>
                          <span className="font-mono text-xs font-bold text-neo-text min-w-[3.5rem] text-right">
                            {speed(a.speed, units)}
                          </span>
                          <span
                            className="inline-flex items-center justify-center h-4 w-4 rounded-full bg-[color-mix(in_srgb,var(--bg)_90%,transparent)] border border-[var(--line)] text-[8px] text-neo-muted font-bold transition-transform duration-300"
                            style={{ transform: `rotate(${a.dir}deg)` }}
                            title={`${a.dir}°`}
                          >
                            ↑
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
                {altLevels.length >= 2 && (
                  <p className="text-[9px] text-neo-muted text-center pt-0.5">
                    Wind Shear: +{speed(Math.max(0, altLevels[0].speed - altLevels[altLevels.length - 1].speed), units)} gradient ({altLevels[altLevels.length - 1].level} → {altLevels[0].level})
                  </p>
                )}
              </div>
            )}

            {/* Tab 3: 24h Trend Forecast */}
            {windTab === "trend" && (
              <div key="wind-trend" className="fade-in-scale space-y-1.5">
                <div className="flex items-center justify-between text-[10px]">
                  <span className="text-neo-muted font-semibold">
                    {locale === "hi" ? "24-घंटे का पवन पूर्वानुमान" : locale === "bn" ? "২৪ ঘণ্টার বাতাসের পূর্বাভাস" : "24-Hour Wind Forecast Curve"}
                  </span>
                  <span className="font-mono font-bold text-neo-accent">{speed(windMax10m ?? speedKmh, units)} {locale === "hi" ? "शिखर" : locale === "bn" ? "শীর্ষ" : "peak"}</span>
                </div>
                <div className="h-24 sm:h-28">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={wind24h}>
                      <defs>
                        <linearGradient id="windGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.4} />
                          <stop offset="95%" stopColor="var(--accent)" stopOpacity={0.02} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid stroke="var(--line)" vertical={false} strokeDasharray="3 3" />
                      <XAxis dataKey="t" stroke="var(--muted)" fontSize={8} interval={4} />
                      <YAxis stroke="var(--muted)" fontSize={8} width={24} />
                      <Tooltip contentStyle={tip} />
                      <Area
                        type="monotone"
                        dataKey="v"
                        stroke="var(--accent)"
                        strokeWidth={2.5}
                        fill="url(#windGrad)"
                        name={`Wind (${units === "imperial" ? "mph" : "km/h"})`}
                        isAnimationActive={true}
                        animationDuration={350}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
                <div className="grid grid-cols-3 gap-1 text-center pt-1 border-t border-[color-mix(in_srgb,var(--line)_50%,transparent)]">
                  <div>
                    <span className="text-[8px] uppercase tracking-wider text-neo-muted block">
                      {locale === "hi" ? "औसत" : locale === "bn" ? "গড়" : "Mean"}
                    </span>
                    <span className="font-mono text-[11px] font-bold text-neo-text">{windMean10m != null ? speed(windMean10m, units) : "—"}</span>
                  </div>
                  <div>
                    <span className="text-[8px] uppercase tracking-wider text-neo-muted block">
                      {locale === "hi" ? "अधिकतम 10m" : locale === "bn" ? "সর্বোচ্চ ১০ মি" : "Max 10m"}
                    </span>
                    <span className="font-mono text-[11px] font-bold text-neo-accent">{windMax10m != null ? speed(windMax10m, units) : "—"}</span>
                  </div>
                  <div>
                    <span className="text-[8px] uppercase tracking-wider text-neo-muted block">
                      {locale === "hi" ? "झोंके" : locale === "bn" ? "দমকা" : "Gusts"}
                    </span>
                    <span className="font-mono text-[11px] font-bold text-neo-warn">{windGusts != null ? speed(windGusts, units) : "—"}</span>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}


export function WindRose({
  fromDeg,
  flowDeg,
  rose,
  compass,
  flow,
}: {
  fromDeg: number | null;
  flowDeg: number | null;
  rose: { dir: string; count: number; avg_speed: number }[];
  compass: string;
  flow: string;
}) {
  const max = Math.max(1, ...rose.map((r) => r.count));
  return (
    <svg viewBox="0 0 200 200" className="h-20 w-20 shrink-0 sm:h-24 sm:w-24 wind-compass-svg">
      <circle cx="100" cy="100" r="86" className="wind-compass-dial" fill="color-mix(in srgb, var(--card) 80%, transparent)" stroke="var(--line)" />
      <circle cx="100" cy="100" r="58" fill="none" stroke="var(--line)" strokeDasharray="3 4" opacity="0.6" />
      {["N", "E", "S", "W"].map((lab, i) => {
        const ang = (i * 90 - 90) * (Math.PI / 180);
        const x = 100 + Math.cos(ang) * 74;
        const y = 100 + Math.sin(ang) * 74;
        return (
          <text
            key={lab}
            x={x}
            y={y}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize="10"
            fontWeight="800"
            fill={lab === "N" ? "var(--accent)" : "var(--muted)"}
            className="wind-compass-cardinal"
          >
            {lab}
          </text>
        );
      })}
      {rose.map((b, i) => {
        const ang = i * 22.5;
        const len = 12 + (b.count / max) * 28;
        return (
          <line
            key={b.dir}
            x1="100"
            y1="100"
            x2="100"
            y2={100 - len}
            stroke="var(--rain)"
            strokeWidth={b.count ? 4 : 1}
            strokeLinecap="round"
            opacity={b.count ? 0.85 : 0.25}
            transform={`rotate(${ang} 100 100)`}
          />
        );
      })}
      {fromDeg != null ? (
        <g transform={`rotate(${fromDeg} 100 100)`}>
          <polygon points="100,22 108,70 100,62 92,70" fill="var(--accent2)" />
        </g>
      ) : null}
      {flowDeg != null ? (
        <g transform={`rotate(${flowDeg} 100 100)`}>
          <polygon points="100,34 106,78 100,72 94,78" fill="var(--accent)" />
        </g>
      ) : null}
      <circle cx="100" cy="100" r="18" className="wind-compass-hub" fill="var(--card)" stroke="var(--line)" />
      <text x="100" y="98" textAnchor="middle" fontSize="9" fill="var(--accent)" fontWeight="800" className="wind-compass-text">
        {compass}
      </text>
      <text x="100" y="110" textAnchor="middle" fontSize="8" fill="var(--muted)" fontWeight="700" className="wind-compass-flow">
        →{flow}
      </text>
    </svg>
  );
}


export function SkyGlyph({ kind, day }: { kind: string; day: boolean }) {
  const sun = day ? "#e9b44c" : "#9aa6b2";
  return (
    <svg viewBox="0 0 88 88" className={`h-24 w-24 shrink-0 sky-glyph sky-${kind}`}>
      {kind === "clear" || kind === "partly" ? (
        <g className={day ? "sky-sun" : ""}>
          <circle cx={kind === "partly" ? 30 : 44} cy={kind === "partly" ? 30 : 40} r="14" fill={sun} />
          {day
            ? [0, 45, 90, 135, 180, 225, 270, 315].map((a) => (
              <line
                key={a}
                x1={kind === "partly" ? 30 : 44}
                y1={kind === "partly" ? 30 : 40}
                x2={kind === "partly" ? 30 : 44}
                y2={kind === "partly" ? 8 : 16}
                stroke={sun}
                strokeWidth="2"
                transform={`rotate(${a} ${kind === "partly" ? 30 : 44} ${kind === "partly" ? 30 : 40})`}
              />
            ))
            : null}
        </g>
      ) : null}
      {kind !== "clear" ? (
        <g className="sky-cloud">
          <ellipse cx="40" cy="50" rx="22" ry="14" fill="#8fa3ad" opacity="0.85" />
          <ellipse cx="56" cy="52" rx="16" ry="12" fill="#7d929c" opacity="0.85" />
          <ellipse cx="28" cy="54" rx="14" ry="10" fill="#a8b8c0" opacity="0.9" />
        </g>
      ) : null}
      {kind === "rain" || kind === "storm" ? (
        <g className="sky-drops">
          <line x1="32" y1="66" x2="28" y2="80" stroke="var(--rain)" strokeWidth="2" />
          <line x1="44" y1="68" x2="40" y2="82" stroke="var(--rain)" strokeWidth="2" />
          <line x1="56" y1="66" x2="52" y2="80" stroke="var(--rain)" strokeWidth="2" />
        </g>
      ) : null}
      {kind === "storm" ? <polygon points="48,48 40,64 46,64 38,78 58,60 50,60 56,48" fill="var(--accent2)" /> : null}
      {kind === "fog" ? (
        <g>
          <line x1="18" y1="62" x2="70" y2="62" stroke="var(--muted)" strokeWidth="3" />
          <line x1="22" y1="70" x2="66" y2="70" stroke="var(--muted)" strokeWidth="3" />
          <line x1="20" y1="78" x2="68" y2="78" stroke="var(--muted)" strokeWidth="3" />
        </g>
      ) : null}
    </svg>
  );
}
