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
import { dist, localizeDigits, rain, rainUnit, speed, temp, tempUnit } from "@/lib/units";
import { useApp } from "@/lib/store";
import { LaymanSummaryBody } from "@/components/LaymanSummaryView";
import { getSkyLaymanSummary } from "@/lib/laymanSummaries";


const CONDITION_TRANSLATIONS: Record<string, Record<Locale, string>> = {
  clear: { en: "Clear Sky", hi: "साफ़ आसमान", bn: "পরিষ্কার আকাশ" },
  fair: { en: "Fair", hi: "साफ़ व शांत", bn: "স্বাভাবিক" },
  "partly cloudy": { en: "Partly Cloudy", hi: "आंशिक बादल", bn: "আংশিক মেঘলা" },
  overcast: { en: "Overcast", hi: "घने बादल", bn: "মেঘাচ্ছন্ন" },
  cloudy: { en: "Cloudy", hi: "बादल", bn: "মেঘলা" },
  rain: { en: "Rain", hi: "वर्षा", bn: "বৃষ্টি" },
  "light rain": { en: "Light Rain", hi: "हल्की वर्षा", bn: "হালকা বৃষ্টি" },
  "heavy rain": { en: "Heavy Rain", hi: "भारी वर्षा", bn: "ভারী বৃষ্টি" },
  thunderstorm: { en: "Thunderstorm", hi: "गरज-चमक के साथ बारिश", bn: "বজ্রবিদ্যুৎসহ ঝড়" },
  haze: { en: "Haze", hi: "धुंध", bn: "কুয়াশা" },
  fog: { en: "Fog", hi: "कोहरा", bn: "ঘন কুয়াশা" },
  mist: { en: "Mist", hi: "हल्का कोहरा", bn: "হালকা কুয়াশা" },
};

function translateSkyLabel(raw: string | undefined | null, locale: Locale): string {
  if (!raw) return locale === "hi" ? "साफ़ आसमान" : locale === "bn" ? "পরিষ্কার আকাশ" : "Clear Sky";
  const k = raw.toLowerCase().trim();
  if (CONDITION_TRANSLATIONS[k]?.[locale]) return CONDITION_TRANSLATIONS[k][locale];
  for (const [key, map] of Object.entries(CONDITION_TRANSLATIONS)) {
    if (k.includes(key)) return map[locale];
  }
  return raw;
}

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

function IconChevronDown({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className || "w-3.5 h-3.5"}>
      <path d="m6 9 6 6 6-6" />
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
  locale = "en",
}: {
  locale?: Locale;
  isDay: boolean;
  cloudCoverPct: number;
  precip1hMm: number;
  isStorm: boolean;
  windSpeedKmh: number;
  windDirDeg: number;
}) {
  const isRaining = precip1hMm > 0.1 || isStorm;
  const rainIntensity = Math.min(12, Math.max(2, Math.round(precip1hMm * 2.5)));
  const rainAngle = Math.max(-25, Math.min(25, (windDirDeg % 90) - 45));

  return (
    <div
      className={`atmospheric-diorama-container relative w-28 h-24 sm:w-32 sm:h-28 shrink-0 rounded-2xl overflow-hidden border shadow-[inset_0_1px_3px_rgba(255,255,255,0.2),0_6px_16px_rgba(0,0,0,0.15)] flex items-center justify-center select-none ${
        isDay
          ? "bg-gradient-to-b from-[color-mix(in_srgb,var(--accent)_14%,var(--card))] to-[color-mix(in_srgb,var(--bg)_85%,transparent)] border-[color-mix(in_srgb,var(--accent)_25%,var(--line))]"
          : "bg-gradient-to-b from-[#0b132b] via-[#1c2541] to-[#0a1128] border-indigo-500/30 text-white"
      }`}
    >
      {/* Dynamic Ambient Sky Backlight */}
      <div
        className="absolute inset-0 transition-opacity duration-1000"
        style={{
          background: isDay
            ? isRaining
              ? "radial-gradient(circle at 40% 30%, rgba(56, 189, 248, 0.22) 0%, rgba(148, 163, 184, 0.15) 60%, transparent 80%)"
              : "radial-gradient(circle at 38% 36%, rgba(251, 191, 36, 0.35) 0%, rgba(245, 158, 11, 0.15) 50%, transparent 75%)"
            : isRaining
            ? "radial-gradient(circle at 42% 38%, rgba(99, 102, 241, 0.35) 0%, rgba(15, 23, 42, 0.85) 65%, #050b14 100%)"
            : "radial-gradient(circle at 42% 38%, rgba(99, 102, 241, 0.45) 0%, rgba(30, 27, 75, 0.6) 45%, #0a0f1d 100%)",
        }}
      />

      {/* SVG Diorama Scene */}
      <svg viewBox="0 0 100 100" className="w-full h-full relative z-1">
        <defs>
          {/* Sun Gradient */}
          <radialGradient id="dioramaSunGrad" cx="35%" cy="32%" r="65%">
            <stop offset="0%" stopColor="#fffbeb" />
            <stop offset="40%" stopColor="#fde047" />
            <stop offset="75%" stopColor="#f59e0b" />
            <stop offset="100%" stopColor="#d97706" />
          </radialGradient>

          {/* Moon Gradient */}
          <radialGradient id="dioramaMoonGrad" cx="35%" cy="30%" r="65%">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="55%" stopColor="#e2e8f0" />
            <stop offset="100%" stopColor="#94a3b8" />
          </radialGradient>

          {/* Deep Cloud Gradient (Day vs Night) */}
          <linearGradient id="dioramaDeepCloud" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor={isDay ? "#ffffff" : "#334155"} stopOpacity={isDay ? "0.9" : "0.75"} />
            <stop offset="100%" stopColor={isDay ? "#94a3b8" : "#1e293b"} stopOpacity={isDay ? "0.85" : "0.85"} />
          </linearGradient>

          {/* Fore Cloud Gradient (Day vs Night) */}
          <linearGradient id="dioramaForeCloud" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor={isDay ? "#ffffff" : "#475569"} stopOpacity={isDay ? "0.98" : "0.85"} />
            <stop offset="100%" stopColor={isDay ? "#cbd5e1" : "#1e293b"} stopOpacity={isDay ? "0.92" : "0.95"} />
          </linearGradient>
        </defs>

        {/* Celestial Body: Sun or Moon */}
        {isDay ? (
          <g className="anim-celestial-drift">
            {/* Outer Diffuse Corona Glow */}
            <circle
              cx="38"
              cy="36"
              r="24"
              fill="rgba(254, 240, 138, 0.2)"
              className="anim-solar-corona"
            />
            <circle
              cx="38"
              cy="36"
              r="17"
              fill="rgba(251, 191, 36, 0.3)"
              className="anim-solar-corona"
            />

            {/* Rotating Sunbeam Rays */}
            <g className="anim-sunburst-spin">
              {[0, 45, 90, 135, 180, 225, 270, 315].map((angle) => (
                <line
                  key={angle}
                  x1="38"
                  y1="16"
                  x2="38"
                  y2="20"
                  stroke="#f59e0b"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  transform={`rotate(${angle} 38 36)`}
                  opacity="0.9"
                />
              ))}
              {[22.5, 67.5, 112.5, 157.5, 202.5, 247.5, 292.5, 337.5].map((angle) => (
                <line
                  key={angle}
                  x1="38"
                  y1="18"
                  x2="38"
                  y2="20"
                  stroke="#fbbf24"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  transform={`rotate(${angle} 38 36)`}
                  opacity="0.75"
                />
              ))}
            </g>

            {/* Sun Core Spherical Disc */}
            <circle cx="38" cy="36" r="11" fill="url(#dioramaSunGrad)" filter="drop-shadow(0 0 6px rgba(245, 158, 11, 0.6))" />
            <circle cx="35" cy="33" r="3.5" fill="#ffffff" opacity="0.65" />
          </g>
        ) : (
          <g className="anim-celestial-drift">
            {/* Outer Lunar Aura Glow */}
            <circle cx="42" cy="36" r="19" fill="rgba(165, 180, 252, 0.22)" className="anim-solar-corona" />
            <circle cx="42" cy="36" r="14" fill="rgba(199, 210, 254, 0.3)" />

            {/* Moon Body Crescent with Crater Detail */}
            <path
              d="M44 24 A 12 12 0 0 0 56 36 A 12 12 0 1 1 44 24 Z"
              fill="url(#dioramaMoonGrad)"
              filter="drop-shadow(0 0 6px rgba(165, 180, 252, 0.5))"
            />
            {/* Lunar Craters */}
            <circle cx="50" cy="34" r="1.5" fill="#94a3b8" opacity="0.45" />
            <circle cx="47" cy="39" r="1.2" fill="#94a3b8" opacity="0.4" />
            <circle cx="45" cy="30" r="1" fill="#94a3b8" opacity="0.35" />

            {/* Distant Twinkling Stars */}
            <g className="anim-star-twinkle">
              <circle cx="18" cy="22" r="1.2" fill="#ffffff" />
              <polygon points="18,19 19,22 22,22 19.5,23.5 20.5,26 18,24.5 15.5,26 16.5,23.5 14,22 17,22" fill="#e0e7ff" opacity="0.8" transform="scale(0.35) translate(28, 32)" />
            </g>
            <circle cx="78" cy="18" r="1.4" fill="#ffffff" className="anim-star-twinkle" style={{ animationDelay: "0.6s" }} />
            <circle cx="86" cy="38" r="1" fill="#c7d2fe" className="anim-star-twinkle" style={{ animationDelay: "1.2s" }} />
            <circle cx="28" cy="44" r="0.8" fill="#e0e7ff" className="anim-star-twinkle" style={{ animationDelay: "1.8s" }} />
          </g>
        )}

        {/* Dynamic Rainbow Arc for Light Rain in Daytime */}
        {isDay && isRaining && precip1hMm < 4 && (
          <g className="anim-rainbow pointer-events-none" opacity="0.65">
            <path d="M10,75 A 50 50 0 0 1 90 75" fill="none" stroke="#f43f5e" strokeWidth="1.2" opacity="0.5" />
            <path d="M11,75 A 49 49 0 0 1 89 75" fill="none" stroke="#f59e0b" strokeWidth="1.2" opacity="0.6" />
            <path d="M12,75 A 48 48 0 0 1 88 75" fill="none" stroke="#10b981" strokeWidth="1.2" opacity="0.6" />
            <path d="M13,75 A 47 47 0 0 1 87 75" fill="none" stroke="#0ea5e9" strokeWidth="1.2" opacity="0.5" />
          </g>
        )}

        {/* Deep Background Cloud Layer */}
        {cloudCoverPct > 15 && (
          <g className="anim-cloud-deep opacity-85">
            <ellipse cx="68" cy="45" rx="24" ry="14" fill="url(#dioramaDeepCloud)" filter="drop-shadow(0 2px 4px rgba(0,0,0,0.08))" />
            <ellipse cx="48" cy="49" rx="18" ry="12" fill="url(#dioramaDeepCloud)" />
            <ellipse cx="32" cy="52" rx="14" ry="9" fill="url(#dioramaDeepCloud)" />
          </g>
        )}

        {/* Foreground Volumetric Cloud Layer */}
        {cloudCoverPct > 35 && (
          <g className="anim-cloud-fore">
            <ellipse cx="42" cy="58" rx="26" ry="15" fill="url(#dioramaForeCloud)" filter="drop-shadow(0 4px 8px rgba(0,0,0,0.12))" />
            <ellipse cx="62" cy="55" rx="22" ry="13" fill="url(#dioramaForeCloud)" />
            <ellipse cx="24" cy="62" rx="16" ry="10" fill="url(#dioramaForeCloud)" />
            <circle cx="36" cy="48" r="12" fill="url(#dioramaForeCloud)" />
            <circle cx="54" cy="46" r="14" fill="url(#dioramaForeCloud)" />
          </g>
        )}

        {/* Thunderstorm Lightning Arc Flash */}
        {isStorm && (
          <g className="anim-storm-flash">
            <polygon
              points="54,46 44,65 52,65 42,86 64,62 55,62 62,46"
              fill="#fbbf24"
              filter="drop-shadow(0 0 8px #f59e0b)"
            />
            <polygon
              points="54,48 46,64 51,64 45,82 61,63 55,63 60,48"
              fill="#ffffff"
            />
          </g>
        )}

        {/* Wind-Skewed Dynamic Rain Particles Engine */}
        {isRaining && (
          <g transform={`rotate(${rainAngle} 50 60)`}>
            {[
              { x: 22, delay: "0s", dur: "0.7s" },
              { x: 34, delay: "0.22s", dur: "0.62s" },
              { x: 46, delay: "0.45s", dur: "0.75s" },
              { x: 58, delay: "0.12s", dur: "0.68s" },
              { x: 70, delay: "0.38s", dur: "0.72s" },
              { x: 80, delay: "0.55s", dur: "0.65s" },
              { x: 28, delay: "0.18s", dur: "0.60s" },
              { x: 52, delay: "0.32s", dur: "0.78s" },
              { x: 64, delay: "0.48s", dur: "0.66s" },
              { x: 40, delay: "0.28s", dur: "0.70s" },
            ].slice(0, rainIntensity).map((p, idx) => (
              <line
                key={idx}
                x1={p.x}
                y1="48"
                x2={p.x - 2}
                y2="66"
                stroke="var(--rain)"
                strokeWidth="2"
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

        {/* Atmospheric Mist / Rolling Fog Waves */}
        {cloudCoverPct > 75 && !isRaining && (
          <g className="anim-mist-wave">
            <path d="M12,74 Q30,68 50,74 T88,74" fill="none" stroke="#94a3b8" strokeWidth="2.5" strokeLinecap="round" opacity="0.6" />
            <path d="M20,82 Q40,76 60,82 T92,82" fill="none" stroke="#cbd5e1" strokeWidth="2" strokeLinecap="round" opacity="0.5" />
          </g>
        )}

        {/* Haze Waves for Low Visibility */}
        {cloudCoverPct <= 75 && !isRaining && (
          <g className="anim-haze-wave">
            <line x1="20" y1="80" x2="80" y2="80" stroke="#f59e0b" strokeWidth="1.5" strokeLinecap="round" opacity="0.3" />
            <line x1="30" y1="85" x2="70" y2="85" stroke="#f59e0b" strokeWidth="1.2" strokeLinecap="round" opacity="0.25" />
          </g>
        )}
      </svg>

      {/* Live State Floating Badge Overlay */}
      <div className="absolute bottom-1.5 right-1.5 px-2 py-0.5 rounded-full bg-[color-mix(in_srgb,var(--card)_90%,transparent)] border border-white/40 dark:border-white/20 text-[8.5px] font-bold text-neo-text backdrop-blur-md shadow-xs flex items-center gap-1">
        <span className={`h-1.5 w-1.5 rounded-full ${isRaining ? "bg-blue-500 animate-ping" : isDay ? "bg-amber-400 animate-pulse" : "bg-indigo-400"}`} />
        <span>{isRaining ? `${rain(precip1hMm, "metric", locale)}/h` : isDay ? (locale === "hi" ? "दिन" : locale === "bn" ? "দিন" : "Daylight") : (locale === "hi" ? "रात" : locale === "bn" ? "রাত" : "Night")}</span>
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
  forceSummary,
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  onNavigateData?: (subTab: string) => void;
  forceSummary?: boolean;
}) {
  const t = COPY[locale];
  const units = useApp((s) => s.settings.units);
  const displayNull = useApp((s) => s.settings.displayNullValues);

  const [localSummary, setLocalSummary] = useState<boolean | null>(null);
  useEffect(() => {
    setLocalSummary(null);
  }, [forceSummary]);
  const isSummary = localSummary !== null ? localSummary : Boolean(forceSummary);

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
    <section
      onClick={() => setLocalSummary(!isSummary)}
      className="neo neo-section-sky p-4 relative overflow-hidden select-none transition-all cursor-pointer hover:border-[color-mix(in_srgb,var(--accent)_35%,var(--line))]"
      title="Click card to switch between detailed data and overview"
    >
      {/* Header Banner */}
      <div className="flex items-center justify-between gap-2 flex-wrap mb-3">
        <div className="flex items-center gap-2">
          <span className="live-dot bg-sky-500 shadow-[0_0_8px_#0ea5e9]" aria-hidden />
          <p className="text-[11px] font-black uppercase tracking-[0.18em] text-sky-600 dark:text-sky-400">
            {locale === "hi" ? "आसमान और वातावरण" : locale === "bn" ? "আকাশ ও বায়ুমণ্ডল" : "SKY & ATMOSPHERE"}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {!isSummary && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setInspectorOpen(true);
              }}
              className="neo-btn text-[10px] font-semibold px-2 py-1 flex items-center gap-1"
              title="Inspect full atmospheric diurnal curves"
            >
              <IconSparkles className="w-3 h-3 text-neo-accent" />
              <span className="hidden sm:inline">{locale === "hi" ? "सिनॉप्टिक्स" : locale === "bn" ? "সিনপটিক্স" : "Synoptics"}</span>
            </button>
          )}
        </div>
      </div>

      {isSummary ? (
        <div className="py-1">
          <LaymanSummaryBody summary={getSkyLaymanSummary(dash, locale, units)} isWide />
        </div>
      ) : (
        /* Main Grid: Left Animated Diorama & Core Weather, Right Unified Telemetry */
        <div className="grid gap-3.5 lg:grid-cols-12 items-center">
          {/* Top/Left Column: Live Diorama & Core Weather Banner */}
          <div className="col-span-12 lg:col-span-6 flex items-center justify-between sm:justify-start gap-3 sm:gap-4 p-1">
            <div className="min-w-0 flex-1">
              {/* Main Temperature & Feels */}
              <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                <span className="font-mono text-2xl xs:text-3xl sm:text-4xl md:text-5xl font-black text-neo-text tracking-tight leading-none whitespace-nowrap">
                  {temp(sky.temp_c ?? cur.temp_c, units, locale)}
                </span>
                {feels != null && (
                  <span className="text-[10.5px] xs:text-[11px] sm:text-xs font-mono font-bold text-neo-muted whitespace-nowrap">
                    {locale === "hi" ? "महसूस " : locale === "bn" ? "অনুভূত " : "Feels "}{temp(feels, units, locale)}
                  </span>
                )}
              </div>

              {/* Weather Condition Label + Day/Night Chip */}
              <div className="mt-1.5 flex items-center gap-2 flex-wrap">
                <h3 className="text-base sm:text-lg font-black text-neo-text truncate leading-tight">
                  {translateSkyLabel(sky.label || cur.sky_label, locale)}
                </h3>
                <span className={`chip text-[8.5px] font-black uppercase px-2 py-0.5 rounded-full ${isDay ? "text-amber-700 bg-amber-400/20 border border-amber-400/30" : "text-indigo-600 bg-indigo-500/15 border border-indigo-400/30"}`}>
                  {isDay ? (locale === "hi" ? "दिन" : locale === "bn" ? "দিন" : "Day") : (locale === "hi" ? "रात" : locale === "bn" ? "রাত" : "Night")}
                </span>
              </div>

              {/* Atmospheric Boundary Layer Subtext */}
              <p className="text-[10px] sm:text-[11px] text-neo-muted font-medium mt-1 truncate">
                {sky.place || (locale === "hi" ? "वर्तमान स्थितियां · स्थिर वायुमंडलीय परत" : locale === "bn" ? "বর্তমান অবস্থা · স্থিতিশীল বায়ুমণ্ডলীয় স্তর" : "Current Conditions · Stable Boundary Layer")}
              </p>
            </div>

            {/* Right Hero Diorama Box */}
            <AtmosphericDiorama
              isDay={isDay}
              cloudCoverPct={cloudPct}
              precip1hMm={precip1h}
              isStorm={isStorm}
              windSpeedKmh={windSpeed}
              windDirDeg={windDeg}
              locale={locale}
            />
          </div>

          {/* Bottom/Right Column: Clean 6-Pack Unified Telemetry Sub-Cards */}
          <div className="col-span-12 lg:col-span-6 min-h-[90px] flex flex-col justify-center">
            <div className="grid grid-cols-3 gap-2 sm:gap-2.5 text-xs">
              <div className="neo-in p-2 sm:p-2.5 rounded-2xl flex flex-col justify-between transition-all hover:scale-[1.02]">
                <span className="text-[9.5px] uppercase tracking-wider text-neo-muted font-bold flex items-center gap-1">
                  <IconDroplet className="w-3 h-3 text-sky-500 shrink-0" />
                  <span className="truncate">{t.humidity || (locale === "hi" ? "आर्द्रता" : locale === "bn" ? "আর্দ্রতা" : "Humidity")}</span>
                </span>
                <p className="mt-1 font-mono text-sm sm:text-base font-extrabold text-neo-text">
                  {sky.humidity_pct != null ? `${localizeDigits(Math.round(Number(sky.humidity_pct)), locale)}%` : "—"}
                </p>
              </div>

              <div className="neo-in p-2 sm:p-2.5 rounded-2xl flex flex-col justify-between transition-all hover:scale-[1.02]">
                <span className="text-[9.5px] uppercase tracking-wider text-neo-muted font-bold flex items-center gap-1">
                  <IconCloud className="w-3 h-3 text-slate-400 shrink-0" />
                  <span className="truncate">{t.cloudCover || (locale === "hi" ? "बादल" : locale === "bn" ? "মেঘ" : "Cloud")}</span>
                </span>
                <p className="mt-1 font-mono text-sm sm:text-base font-extrabold text-neo-text">
                  {sky.cloud_cover_pct != null ? `${localizeDigits(Math.round(Number(sky.cloud_cover_pct)), locale)}%` : "—"}
                </p>
              </div>

              <div className="neo-in p-2 sm:p-2.5 rounded-2xl flex flex-col justify-between transition-all hover:scale-[1.02]">
                <span className="text-[9.5px] uppercase tracking-wider text-neo-muted font-bold flex items-center gap-1">
                  <IconEye className="w-3 h-3 text-teal-500 shrink-0" />
                  <span className="truncate">{t.visibility || (locale === "hi" ? "दृश्यता" : locale === "bn" ? "দৃশ্যমানতা" : "Visibility")}</span>
                </span>
                <p className="mt-1 font-mono text-sm sm:text-base font-extrabold text-neo-text">
                  {sky.visibility_km != null ? dist(sky.visibility_km, units, locale) : (locale === "hi" ? "सामान्य" : locale === "bn" ? "স্বাভাবিক" : "10 km")}
                </p>
              </div>

              <div className="neo-in p-2 sm:p-2.5 rounded-2xl flex flex-col justify-between transition-all hover:scale-[1.02]">
                <span className="text-[9.5px] uppercase tracking-wider text-neo-muted font-bold flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-sky-500 shrink-0" />
                  <span className="truncate">{t.lastHourRain || (locale === "hi" ? "बारिश 1h" : locale === "bn" ? "বৃষ্টি ১ঘ" : "Rain 1H")}</span>
                </span>
                <p className="mt-1 font-mono text-sm sm:text-base font-extrabold text-sky-600 dark:text-sky-400">
                  {rain(sky.precip_1h_mm, units, locale)}
                </p>
              </div>

              <div className="neo-in p-2 sm:p-2.5 rounded-2xl flex flex-col justify-between transition-all hover:scale-[1.02]">
                <span className="text-[9.5px] uppercase tracking-wider text-neo-muted font-bold flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-blue-600 shrink-0" />
                  <span className="truncate">{t.rainToday || (locale === "hi" ? "आज की कुल" : locale === "bn" ? "আজকের" : "Today")}</span>
                </span>
                <p className="mt-1 font-mono text-sm sm:text-base font-extrabold text-blue-600 dark:text-blue-400">
                  {todayRain != null ? rain(todayRain, units, locale) : `${localizeDigits(0, locale)} mm`}
                </p>
              </div>

              <div className="neo-in p-2 sm:p-2.5 rounded-2xl flex flex-col justify-between transition-all hover:scale-[1.02]">
                <span className="text-[9.5px] uppercase tracking-wider text-neo-muted font-bold flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-indigo-500 shrink-0" />
                  <span className="truncate">{locale === "hi" ? "3-दिन संचय" : locale === "bn" ? "৩-দিন সঞ্চয়" : "3-Day Acc"}</span>
                </span>
                <p className="mt-1 font-mono text-sm sm:text-base font-extrabold text-indigo-600 dark:text-indigo-400">
                  {rain(dash.predictive.precip_next_3d_mm, units, locale)}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

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
                        {locale === "hi"
                          ? "वायुमंडलीय और वर्षा सिनॉप्टिक समयरेखा"
                          : locale === "bn"
                          ? "বায়ুমণ্ডলীয় ও বৃষ্টিপাতের সিনপটিক টাইমলাইন"
                          : "Atmospheric & Precipitation Synoptic Timeline"}
                      </h3>
                      <p className="text-[11px] text-neo-muted font-normal mt-0.5">
                        {locale === "hi"
                          ? "24 घंटे का दैनिक चक्र व जल-मौसम विज्ञान विश्लेषण"
                          : locale === "bn"
                          ? "২৪ ঘণ্টার প্রাত্যহিক চক্র ও জল-আবহাওয়া গতিপ্রকৃতি"
                          : "24-Hour Diurnal Evolution & Hydrometeorological Dynamics"}
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
                        {locale === "hi" ? "सतह का तापमान" : locale === "bn" ? "পৃষ্ঠের তাপমাত্রা" : "Surface Temperature"}
                      </span>
                      <p className="mt-0.5 font-mono text-base font-bold text-neo-accent">
                        {temp(sky.temp_c ?? cur.temp_c, units, locale)}
                      </p>
                    </div>

                    <div className="neo-in p-2.5 rounded-xl">
                      <span className="text-[9px] uppercase tracking-wider text-neo-muted font-semibold block">
                        {locale === "hi" ? "सापेक्ष आर्द्रता" : locale === "bn" ? "আপেক্ষিক আর্দ্রতা" : "Relative Humidity"}
                      </span>
                      <p className="mt-0.5 font-mono text-base font-bold text-neo-rain">
                        {sky.humidity_pct != null ? `${localizeDigits(Math.round(Number(sky.humidity_pct)), locale)}%` : "—"}
                      </p>
                    </div>

                    <div className="neo-in p-2.5 rounded-xl">
                      <span className="text-[9px] uppercase tracking-wider text-neo-muted font-semibold block">
                        {locale === "hi" ? "बादल आवरण" : locale === "bn" ? "মেঘের কভারেজ" : "Cloud Cover"}
                      </span>
                      <p className="mt-0.5 font-mono text-base font-bold text-neo-text">
                        {localizeDigits(cloudPct, locale)}%
                      </p>
                    </div>

                    <div className="neo-in p-2.5 rounded-xl">
                      <span className="text-[9px] uppercase tracking-wider text-neo-muted font-semibold block">
                        {locale === "hi" ? "7-दिवसीय जल संतुलन" : locale === "bn" ? "৭ দিনের জল ভারসাম্য" : "7-Day Water Balance"}
                      </span>
                      <p className={`mt-0.5 font-mono text-base font-bold ${Number(dash.predictive.water_balance_7d_mm ?? 0) >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"}`}>
                        {rain(dash.predictive.water_balance_7d_mm, units, locale)}
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
