"use client";

import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import {
  Area,
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DashboardSnapshot } from "@/types/dashboard";
import { COPY, type Locale } from "@/i18n/copy";
import { dist, rain, rainUnit, speed, temp, tempUnit } from "@/lib/units";
import { useApp } from "@/lib/store";

/* -------------------------------------------------------------------------- */
/* Precision Vector SVG Icons (Zero Emojis)                                   */
/* -------------------------------------------------------------------------- */

function IconSun({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className || "w-4 h-4"}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
    </svg>
  );
}

function IconMoon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className || "w-4 h-4"}>
      <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
    </svg>
  );
}

function IconCloudRain({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className || "w-4 h-4"}>
      <path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242" />
      <path d="M16 14v6M8 14v6M12 16v6" />
    </svg>
  );
}

function IconDroplet({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className || "w-3.5 h-3.5"}>
      <path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z" />
    </svg>
  );
}

function IconCloud({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className || "w-3.5 h-3.5"}>
      <path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z" />
    </svg>
  );
}

function IconEye({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className || "w-3.5 h-3.5"}>
      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function IconGauge({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className || "w-3.5 h-3.5"}>
      <path d="m12 14 4-4" />
      <path d="M3.34 19a10 10 0 1 1 17.32 0" />
    </svg>
  );
}

function IconSparkles({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className || "w-3.5 h-3.5"}>
      <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
    </svg>
  );
}

function feelsLikeC(tempC?: number | null, rh?: number | null) {
  if (tempC == null) return null;
  const t = Number(tempC);
  const h = Number(rh ?? 50);
  if (t < 26) return t;
  const hi =
    -8.784695 +
    1.61139411 * t +
    2.338549 * h -
    0.14611605 * t * h -
    0.012308094 * t * t -
    0.016424828 * h * h +
    0.002211732 * t * t * h +
    0.00072546 * t * h * h -
    0.000003582 * t * t * h * h;
  return Number.isNaN(hi) ? t : Math.round(hi * 10) / 10;
}

const tip = {
  background: "var(--card)",
  border: "1px solid var(--line)",
  borderRadius: 10,
  fontSize: 11,
  color: "var(--text)",
  boxShadow: "0 8px 24px rgba(0,0,0,0.25)",
};

/* -------------------------------------------------------------------------- */
/* Dynamic Animated Atmospheric Diorama SVG                                   */
/* -------------------------------------------------------------------------- */

function AtmosphericDiorama({
  isDay,
  cloudCoverPct,
  precip1hMm,
  isStorm,
  windSpeedKmh,
  windDirDeg,
}: {
  isDay: boolean;
  cloudCoverPct: number;
  precip1hMm: number;
  isStorm: boolean;
  windSpeedKmh: number;
  windDirDeg: number;
}) {
  const isRaining = precip1hMm > 0.1 || isStorm;
  const rainIntensity = Math.min(10, Math.max(1, Math.round(precip1hMm * 2)));
  const rainAngle = Math.max(-25, Math.min(25, (windDirDeg % 90) - 45));

  return (
    <div className="relative w-28 h-24 sm:w-32 sm:h-28 shrink-0 rounded-2xl overflow-hidden bg-gradient-to-b from-[color-mix(in_srgb,var(--accent)_12%,var(--card))] to-[color-mix(in_srgb,var(--bg)_80%,transparent)] border border-[color-mix(in_srgb,var(--accent)_20%,var(--line))] shadow-inner flex items-center justify-center select-none">
      {/* Ambient background sky glow */}
      <div
        className="absolute inset-0 transition-opacity duration-1000"
        style={{
          background: isDay
            ? "radial-gradient(circle at 35% 35%, rgba(245, 158, 11, 0.18), transparent 70%)"
            : "radial-gradient(circle at 40% 40%, rgba(99, 102, 241, 0.2), transparent 70%)",
        }}
      />

      {/* SVG Diorama Scene */}
      <svg viewBox="0 0 100 100" className="w-full h-full">
        {/* Celestial Body: Sun or Moon */}
        {isDay ? (
          <g className="anim-celestial-drift">
            {/* Outer corona pulse */}
            <circle
              cx="38"
              cy="36"
              r="20"
              fill="none"
              stroke="rgba(245, 158, 11, 0.25)"
              strokeWidth="2"
              className="anim-solar-corona"
            />
            <circle
              cx="38"
              cy="36"
              r="14"
              fill="rgba(251, 191, 36, 0.3)"
              className="anim-solar-corona"
            />
            {/* Sun Core */}
            <circle cx="38" cy="36" r="10" fill="#f59e0b" />
          </g>
        ) : (
          <g className="anim-celestial-drift">
            {/* Lunar Glow */}
            <circle cx="42" cy="36" r="14" fill="rgba(165, 180, 252, 0.2)" />
            {/* Moon Crescent */}
            <path
              d="M44 26 A 10 10 0 0 0 54 36 A 10 10 0 1 1 44 26 Z"
              fill="#cbd5e1"
            />
            {/* Distant Twinkling Stars */}
            <circle cx="20" cy="24" r="1" fill="#e2e8f0" className="anim-star-twinkle" style={{ animationDelay: "0.2s" }} />
            <circle cx="75" cy="20" r="1.2" fill="#e2e8f0" className="anim-star-twinkle" style={{ animationDelay: "0.7s" }} />
            <circle cx="85" cy="40" r="0.8" fill="#e2e8f0" className="anim-star-twinkle" style={{ animationDelay: "1.2s" }} />
          </g>
        )}

        {/* Deep Cloud Layer (Parallax Background) */}
        {cloudCoverPct > 20 && (
          <g className="anim-cloud-deep opacity-75">
            <ellipse cx="65" cy="45" rx="22" ry="12" fill="color-mix(in srgb, var(--line) 80%, #94a3b8)" />
            <ellipse cx="48" cy="48" rx="16" ry="10" fill="color-mix(in srgb, var(--line) 70%, #94a3b8)" />
          </g>
        )}

        {/* Fore Cloud Layer (Parallax Foreground) */}
        {cloudCoverPct > 40 && (
          <g className="anim-cloud-fore">
            <ellipse cx="40" cy="56" rx="24" ry="13" fill="color-mix(in srgb, var(--card) 40%, #64748b)" opacity="0.9" />
            <ellipse cx="58" cy="54" rx="20" ry="12" fill="color-mix(in srgb, var(--card) 30%, #475569)" opacity="0.92" />
            <ellipse cx="26" cy="60" rx="14" ry="9" fill="color-mix(in srgb, var(--card) 50%, #94a3b8)" opacity="0.85" />
          </g>
        )}

        {/* Thunderstorm Lightning Arc Flash */}
        {isStorm && (
          <polygon
            points="52,48 44,65 50,65 42,82 62,62 54,62 60,48"
            fill="#fbbf24"
            className="anim-storm-flash"
          />
        )}

        {/* Wind-Skewed Dynamic Rain Particles Engine */}
        {isRaining && (
          <g transform={`rotate(${rainAngle} 50 60)`}>
            {[
              { x: 25, delay: "0s", dur: "0.8s" },
              { x: 38, delay: "0.25s", dur: "0.7s" },
              { x: 50, delay: "0.5s", dur: "0.85s" },
              { x: 62, delay: "0.15s", dur: "0.75s" },
              { x: 74, delay: "0.4s", dur: "0.8s" },
              { x: 32, delay: "0.6s", dur: "0.65s" },
              { x: 56, delay: "0.35s", dur: "0.72s" },
            ].slice(0, rainIntensity + 2).map((p, idx) => (
              <line
                key={idx}
                x1={p.x}
                y1="50"
                x2={p.x - 2}
                y2="66"
                stroke="var(--rain)"
                strokeWidth="1.8"
                strokeLinecap="round"
                className="anim-raindrop"
                style={{
                  animation: `raindrop-fall ${p.dur} linear infinite`,
                  animationDelay: p.delay,
                }}
              />
            ))}
          </g>
        )}

        {/* Mist / Fog Layer */}
        {cloudCoverPct > 80 && !isRaining && (
          <g className="anim-mist-wave">
            <line x1="15" y1="72" x2="85" y2="72" stroke="var(--muted)" strokeWidth="2.5" strokeLinecap="round" opacity="0.4" />
            <line x1="25" y1="80" x2="75" y2="80" stroke="var(--muted)" strokeWidth="2" strokeLinecap="round" opacity="0.3" />
          </g>
        )}
      </svg>

      {/* Live Badge Overlay */}
      <div className="absolute bottom-1.5 right-1.5 px-1.5 py-0.2 rounded-md bg-[color-mix(in_srgb,var(--card)_90%,transparent)] border border-[var(--line)] text-[8px] font-mono text-neo-muted">
        {isRaining ? `${rain(precip1hMm, "metric")}/h` : isDay ? "Daylight" : "Nocturnal"}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Main SkyRainHero Component                                                 */
/* -------------------------------------------------------------------------- */

export function SkyRainHero({
  dash,
  locale,
  onNavigateData,
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  onNavigateData?: (subTab: string) => void;
}) {
  const t = COPY[locale];
  const units = useApp((s) => s.settings.units);
  const displayNull = useApp((s) => s.settings.displayNullValues);

  const live = dash.live;
  const sky = live?.sky || {};
  const wind = live?.wind || {};
  const cur = dash.descriptive.current;
  const series = dash.descriptive.series;

  const todayRain =
    dash.predictive.outlook_days?.[0]?.precip_mm ??
    series.precip_daily?.[0]?.value ??
    sky.precip_1h_mm ??
    null;

  const feels = feelsLikeC(sky.temp_c ?? cur.temp_c, sky.humidity_pct ?? cur.humidity_pct);

  const [inspectorOpen, setInspectorOpen] = useState(false);

  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  // Close modal on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setInspectorOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const cloudPct = Math.round(Number(sky.cloud_cover_pct ?? 40));
  const precip1h = Number(sky.precip_1h_mm ?? (todayRain ? Number(todayRain) / 12 : 0));
  const isDay = sky.is_day !== false;
  const isStorm = (sky.kind || "").includes("storm") || (sky.label || "").toLowerCase().includes("thunder");
  const windSpeed = Number(wind.speed_kmh ?? 12);
  const windDeg = Number(wind.direction_deg ?? wind.flow_deg ?? 45);

  // Chart data for floating inspector
  const chartData = useMemo(() => {
    const hourly = (dash.predictive.hourly || []).slice(0, 24);
    if (hourly.length > 0) {
      return hourly.map((h) => ({
        t: (h.hour || "").slice(0, 5),
        temp: h.temp_c == null ? null : units === "imperial" ? (h.temp_c * 9) / 5 + 32 : h.temp_c,
        rain: units === "imperial" ? (h.precip_mm || 0) / 25.4 : h.precip_mm || 0,
        rh: h.rh_pct ?? null,
      }));
    }
    return (series.temp_hourly || []).slice(0, 18).map((p, i) => ({
      t: p.t.indexOf("T") >= 0 ? p.t.slice(p.t.indexOf("T") + 1, p.t.indexOf("T") + 6) : p.t.slice(-5),
      temp: p.value,
      rain: series.precip_hourly?.[i]?.value ?? 0,
      rh: 65,
    }));
  }, [dash.predictive.hourly, series, units]);

  // Rain probability odds
  const rainOdds = (dash.predictive.precip_probability_pct || []).slice(0, 3);

  return (
    <section className="neo p-4 relative overflow-hidden select-none transition-all">
      {/* Header Banner */}
      <div className="flex items-center justify-between gap-2 flex-wrap mb-3">
        <div className="flex items-center gap-2">
          <span className="live-dot" aria-hidden />
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">
            SKY
          </p>
          <span className="chip text-[9px] font-mono px-1.5 py-0">
            Live Telemetry
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setInspectorOpen(true)}
            className="neo-btn text-[10px] font-semibold px-2 py-1 flex items-center gap-1"
            title="Inspect full atmospheric diurnal curves"
          >
            <IconSparkles className="w-3 h-3 text-neo-accent" />
            <span className="hidden sm:inline">Synoptics</span>
          </button>
        </div>
      </div>

      {/* Main Grid: Left Animated Diorama & Core Weather, Right Unified Telemetry */}
      <div className="grid gap-4 lg:grid-cols-12 items-center">
        {/* Left Column: Atmospheric Diorama & Live Hero Status */}
        <div className="lg:col-span-6 flex items-center gap-3.5">
          <AtmosphericDiorama
            isDay={isDay}
            cloudCoverPct={cloudPct}
            precip1hMm={precip1h}
            isStorm={isStorm}
            windSpeedKmh={windSpeed}
            windDirDeg={windDeg}
          />

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h3 className="text-xl sm:text-2xl font-black text-neo-text truncate leading-tight">
                {sky.label || cur.sky_label || "Clear Sky"}
              </h3>
              <span className={`chip text-[8px] font-mono uppercase px-1.5 py-0 ${isDay ? "text-amber-600 bg-amber-500/10" : "text-indigo-500 bg-indigo-500/10"}`}>
                {isDay ? "Day" : "Night"}
              </span>
            </div>

            <div className="mt-1 flex items-baseline gap-2">
              <span className="font-mono text-3xl sm:text-4xl font-extrabold text-neo-accent">
                {temp(sky.temp_c ?? cur.temp_c, units)}
              </span>
              {feels != null && (
                <span className="text-[11px] font-mono text-neo-muted">
                  Feels {temp(feels, units)}
                </span>
              )}
            </div>

            <p className="text-[10px] text-neo-muted truncate mt-0.5">
              {sky.place ? `${sky.place} · ` : ""}
              {isStorm ? "Convective Thunder Activity" : precip1h > 0.5 ? "Active Inflow" : "Stable Boundary Layer"}
            </p>
          </div>
        </div>

        {/* Right Column: Unified Telemetry Deck */}
        <div className="lg:col-span-6 min-h-[90px] flex flex-col justify-center">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
            <div className="neo-in p-2 rounded-xl">
              <span className="text-[9px] uppercase tracking-wider text-neo-muted font-semibold flex items-center gap-1">
                <IconDroplet className="w-2.5 h-2.5 text-neo-rain" />
                Humidity
              </span>
              <p className="mt-0.5 font-mono text-sm font-bold text-neo-text">
                {sky.humidity_pct != null ? `${Math.round(Number(sky.humidity_pct))}%` : "—"}
              </p>
            </div>

            <div className="neo-in p-2 rounded-xl">
              <span className="text-[9px] uppercase tracking-wider text-neo-muted font-semibold flex items-center gap-1">
                <IconCloud className="w-2.5 h-2.5 text-neo-muted" />
                Cloud Cover
              </span>
              <p className="mt-0.5 font-mono text-sm font-bold text-neo-text">
                {sky.cloud_cover_pct != null ? `${Math.round(Number(sky.cloud_cover_pct))}%` : "—"}
              </p>
            </div>

            <div className="neo-in p-2 rounded-xl">
              <span className="text-[9px] uppercase tracking-wider text-neo-muted font-semibold flex items-center gap-1">
                <IconEye className="w-2.5 h-2.5 text-neo-accent" />
                Visibility
              </span>
              <p className="mt-0.5 font-mono text-sm font-bold text-neo-text">
                {sky.visibility_km != null ? dist(sky.visibility_km, units) : "—"}
              </p>
            </div>

            <div className="neo-in p-2 rounded-xl">
              <span className="text-[9px] uppercase tracking-wider text-neo-muted font-semibold flex items-center gap-1">
                <IconGauge className="w-2.5 h-2.5 text-neo-warn" />
                Last 1h Rain
              </span>
              <p className="mt-0.5 font-mono text-sm font-bold text-neo-rain">
                {rain(sky.precip_1h_mm, units)}
              </p>
            </div>

            <div className="neo-in p-2 rounded-xl">
              <span className="text-[9px] uppercase tracking-wider text-neo-muted font-semibold flex items-center gap-1">
                <IconCloudRain className="w-2.5 h-2.5 text-neo-rain" />
                Today Total
              </span>
              <p className="mt-0.5 font-mono text-sm font-bold text-neo-rain">
                {todayRain != null ? rain(todayRain, units) : "0 mm"}
              </p>
            </div>

            <div className="neo-in p-2 rounded-xl">
              <span className="text-[9px] uppercase tracking-wider text-neo-muted font-semibold flex items-center gap-1">
                <IconSparkles className="w-2.5 h-2.5 text-neo-accent" />
                3-Day Accum
              </span>
              <p className="mt-0.5 font-mono text-sm font-bold text-neo-text">
                {rain(dash.predictive.precip_next_3d_mm, units)}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Floating Synoptic Deep-Dive Modal (Portaled to document.body) */}
      {mounted && typeof document !== "undefined" && inspectorOpen
        ? createPortal(
            <div
              className="fixed inset-0 z-[99999] flex items-center justify-center p-3 sm:p-6 bg-black/60 backdrop-blur-sm transition-opacity duration-150 animate-in fade-in"
              onClick={() => setInspectorOpen(false)}
            >
              <div
                className="w-full max-w-2xl max-h-[86vh] flex flex-col rounded-2xl bg-[var(--card)] border border-[var(--line)] shadow-2xl overflow-hidden animate-in zoom-in-95 duration-150"
                onClick={(e) => e.stopPropagation()}
              >
                {/* Modal Header */}
                <div className="shrink-0 flex items-center justify-between gap-3 px-4 py-3 sm:px-5 sm:py-3.5 border-b border-[var(--line)] bg-[var(--card)]">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-xl flex items-center justify-center bg-[color-mix(in_srgb,var(--accent)_12%,transparent)] text-neo-accent">
                      <IconSparkles className="w-4 h-4" />
                    </div>
                    <div>
                      <h3 className="text-sm sm:text-base font-bold text-neo-text leading-tight">
                        Atmospheric & Precipitation Synoptic Timeline
                      </h3>
                      <p className="text-[11px] text-neo-muted font-normal mt-0.5">
                        24-Hour Diurnal Evolution & Hydrometeorological Dynamics
                      </p>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => setInspectorOpen(false)}
                    className="w-7 h-7 rounded-lg flex items-center justify-center text-neo-muted hover:text-neo-text hover:bg-[color-mix(in_srgb,var(--line)_60%,transparent)] transition text-xs font-semibold shrink-0"
                    aria-label="Close"
                  >
                    ✕
                  </button>
                </div>

                {/* Modal Content */}
                <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4 scrollbar-thin">
                  {/* Summary Stat Grid */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                    <div className="neo-in p-2.5 rounded-xl">
                      <span className="text-[9px] uppercase tracking-wider text-neo-muted font-semibold block">
                        Surface Temperature
                      </span>
                      <p className="mt-0.5 font-mono text-base font-bold text-neo-accent">
                        {temp(sky.temp_c ?? cur.temp_c, units)}
                      </p>
                    </div>

                    <div className="neo-in p-2.5 rounded-xl">
                      <span className="text-[9px] uppercase tracking-wider text-neo-muted font-semibold block">
                        Relative Humidity
                      </span>
                      <p className="mt-0.5 font-mono text-base font-bold text-neo-rain">
                        {sky.humidity_pct != null ? `${Math.round(Number(sky.humidity_pct))}%` : "—"}
                      </p>
                    </div>

                    <div className="neo-in p-2.5 rounded-xl">
                      <span className="text-[9px] uppercase tracking-wider text-neo-muted font-semibold block">
                        Cloud Cover
                      </span>
                      <p className="mt-0.5 font-mono text-base font-bold text-neo-text">
                        {cloudPct}%
                      </p>
                    </div>

                    <div className="neo-in p-2.5 rounded-xl">
                      <span className="text-[9px] uppercase tracking-wider text-neo-muted font-semibold block">
                        7-Day Water Balance
                      </span>
                      <p className={`mt-0.5 font-mono text-base font-bold ${Number(dash.predictive.water_balance_7d_mm ?? 0) >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"}`}>
                        {rain(dash.predictive.water_balance_7d_mm, units)}
                      </p>
                    </div>
                  </div>

                  {/* 24-Hour Synoptic Chart */}
                  <div className="space-y-2">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-neo-muted block">
                      24-Hour Temperature & Rainfall Evolution
                    </span>

                    <div className="h-48 sm:h-52">
                      <ResponsiveContainer width="100%" height="100%">
                        <ComposedChart data={chartData}>
                          <defs>
                            <linearGradient id="skyHeroTempGrad" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.35} />
                              <stop offset="95%" stopColor="var(--accent)" stopOpacity={0.02} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid stroke="var(--line)" vertical={false} strokeDasharray="3 3" />
                          <XAxis dataKey="t" stroke="var(--muted)" fontSize={9} interval={2} />
                          <YAxis yAxisId="left" stroke="var(--muted)" fontSize={9} width={28} unit={` ${tempUnit(units)}`} />
                          <YAxis yAxisId="right" orientation="right" stroke="var(--muted)" fontSize={9} width={28} unit={` ${rainUnit(units)}`} />
                          <Tooltip contentStyle={tip} />
                          <Area yAxisId="left" type="monotone" dataKey="temp" stroke="var(--accent)" strokeWidth={2} fill="url(#skyHeroTempGrad)" name={`Temperature (${tempUnit(units)})`} />
                          <Bar yAxisId="right" dataKey="rain" fill="var(--rain)" radius={[2, 2, 0, 0]} opacity={0.85} name={`Precipitation (${rainUnit(units)})`} />
                        </ComposedChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                </div>
              </div>
            </div>,
            document.body
          )
        : null}
    </section>
  );
}
