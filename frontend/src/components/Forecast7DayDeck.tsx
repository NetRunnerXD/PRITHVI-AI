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
import type { DashboardSnapshot, HourlySlot } from "@/types/dashboard";
import { COPY, type Locale } from "@/i18n/copy";
import { rain, rainUnit, speed, temp, tempUnit } from "@/lib/units";
import { useApp } from "@/lib/store";
import { LaymanSummaryBody } from "@/components/LaymanSummaryView";
import { get7DayLaymanSummary } from "@/lib/laymanSummaries";

/* -------------------------------------------------------------------------- */
/* Professional Lucide-Style SVG Icons (Zero Emojis)                          */
/* -------------------------------------------------------------------------- */

function IconSun({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className || "w-4 h-4"}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
    </svg>
  );
}

function IconCloudSun({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className || "w-4 h-4"}>
      <path d="M12 2v2M4.93 4.93l1.41 1.41M20 12h2M19.07 4.93l-1.41 1.41M15.947 12.65a4 4 0 0 0-5.925-4.128" />
      <path d="M13 22H7a5 5 0 1 1 4.9-6H13a3 3 0 0 1 0 6z" />
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

function IconCloudLightning({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className || "w-4 h-4"}>
      <path d="M6 16.326A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 .5 8.973" />
      <path d="m13 12-3 5h4l-3 5" />
    </svg>
  );
}

function IconCloudFog({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className || "w-4 h-4"}>
      <path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242" />
      <path d="M16 17H7M17 21H9" />
    </svg>
  );
}

function IconDroplet({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className || "w-3 h-3"}>
      <path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z" />
    </svg>
  );
}

function IconWind({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className || "w-3.5 h-3.5"}>
      <path d="M17.7 7.7A2.5 2.5 0 1 1 19.5 12H2M12.6 19.4A2 2 0 1 0 14 16H2M14.7 4.6A2 2 0 1 1 16 8H2" />
    </svg>
  );
}

function IconActivity({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className || "w-3.5 h-3.5"}>
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
    </svg>
  );
}

function IconClock({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className || "w-3.5 h-3.5"}>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 6v6l4 2" />
    </svg>
  );
}

function IconLeaf({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className || "w-3.5 h-3.5"}>
      <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" />
      <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12" />
    </svg>
  );
}

const tip = {
  background: "var(--card)",
  border: "1px solid var(--line)",
  borderRadius: 10,
  fontSize: 11,
  color: "var(--text)",
  boxShadow: "0 8px 24px rgba(0,0,0,0.25)",
};

function weekdayName(iso?: string, short = true) {
  if (!iso) return "—";
  const d = new Date(iso.includes("T") ? iso : `${iso}T12:00:00`);
  if (Number.isNaN(d.getTime())) return iso.slice(5);
  return d.toLocaleDateString("en-IN", { weekday: short ? "short" : "long" });
}

function formatFullDate(iso?: string) {
  if (!iso) return "—";
  const d = new Date(iso.includes("T") ? iso : `${iso}T12:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-IN", {
    weekday: "long",
    day: "numeric",
    month: "short",
  });
}

function getWeatherIcon(weatherCode?: number | null, precipMm?: number | null, prob?: number | null) {
  if (weatherCode != null) {
    if ([95, 96, 99].includes(weatherCode)) {
      return {
        icon: <IconCloudLightning className="w-4 h-4 text-rose-500 dark:text-rose-400" />,
        label: "Thunderstorm",
        badgeColor: "text-rose-600 bg-rose-500/10 dark:text-rose-400",
      };
    }
    if ([71, 73, 75, 77, 85, 86].includes(weatherCode)) {
      return {
        icon: <IconCloudFog className="w-4 h-4 text-sky-400 dark:text-sky-300" />,
        label: "Snowfall",
        badgeColor: "text-sky-600 bg-sky-500/10 dark:text-sky-400",
      };
    }
    if ([61, 63, 65, 80, 81, 82].includes(weatherCode)) {
      return {
        icon: <IconCloudRain className="w-4 h-4 text-cyan-500 dark:text-cyan-400" />,
        label: "Rain Showers",
        badgeColor: "text-cyan-600 bg-cyan-500/10 dark:text-cyan-400",
      };
    }
    if ([51, 53, 55, 56, 57].includes(weatherCode)) {
      return {
        icon: <IconCloudRain className="w-4 h-4 text-teal-500 dark:text-teal-400" />,
        label: "Drizzle",
        badgeColor: "text-teal-600 bg-teal-500/10 dark:text-teal-400",
      };
    }
    if ([45, 48].includes(weatherCode)) {
      return {
        icon: <IconCloudFog className="w-4 h-4 text-slate-400 dark:text-slate-300" />,
        label: "Fog / Mist",
        badgeColor: "text-slate-600 bg-slate-500/10 dark:text-slate-400",
      };
    }
    if ([1, 2, 3].includes(weatherCode)) {
      return {
        icon: <IconCloudSun className="w-4 h-4 text-amber-500 dark:text-amber-400" />,
        label: "Partly Cloudy",
        badgeColor: "text-amber-600 bg-amber-500/10 dark:text-amber-400",
      };
    }
    if (weatherCode === 0) {
      return {
        icon: <IconSun className="w-4 h-4 text-amber-500 dark:text-amber-400" />,
        label: "Clear Sky",
        badgeColor: "text-amber-600 bg-amber-500/10 dark:text-amber-400",
      };
    }
  }
  if (precipMm != null && precipMm > 8) {
    return {
      icon: <IconCloudRain className="w-4 h-4 text-cyan-500 dark:text-cyan-400" />,
      label: "Heavy Rain",
      badgeColor: "text-cyan-600 bg-cyan-500/10 dark:text-cyan-400",
    };
  }
  if (precipMm != null && precipMm > 0.5) {
    return {
      icon: <IconCloudRain className="w-4 h-4 text-cyan-500 dark:text-cyan-400" />,
      label: "Rain Showers",
      badgeColor: "text-cyan-600 bg-cyan-500/10 dark:text-cyan-400",
    };
  }
  if (prob != null && prob > 65) {
    return {
      icon: <IconCloudRain className="w-4 h-4 text-cyan-500 dark:text-cyan-400" />,
      label: "Rain Likely",
      badgeColor: "text-cyan-600 bg-cyan-500/10 dark:text-cyan-400",
    };
  }
  if (prob != null && prob > 30) {
    return {
      icon: <IconCloudSun className="w-4 h-4 text-amber-500 dark:text-amber-400" />,
      label: "Scattered Clouds",
      badgeColor: "text-amber-600 bg-amber-500/10 dark:text-amber-400",
    };
  }
  return {
    icon: <IconSun className="w-4 h-4 text-amber-500 dark:text-amber-400" />,
    label: "Clear",
    badgeColor: "text-amber-600 bg-amber-500/10 dark:text-amber-400",
  };
}

export function Forecast7DayDeck({
  dash,
  locale,
  initialOpenDate,
  forceSummary,
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  initialOpenDate?: string;
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

  const days = useMemo(() => dash.predictive.outlook_days || [], [dash.predictive.outlook_days]);
  const hourly = useMemo(() => dash.predictive.hourly || [], [dash.predictive.hourly]);

  const [activeDate, setActiveDate] = useState<string | null>(initialOpenDate || null);
  const [inspectorTab, setInspectorTab] = useState<"curve" | "reel" | "agronomy">("curve");
  const [curveVar, setCurveVar] = useState<"combo" | "wind" | "humidity">("combo");

  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  // Close floating window on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setActiveDate(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Calculate week-wide min and max for temperature thermometer bars
  const { weekMin, weekMax } = useMemo(() => {
    let min = 999;
    let max = -999;
    for (const d of days) {
      if (d.temp_min_c != null && d.temp_min_c < min) min = d.temp_min_c;
      if (d.temp_max_c != null && d.temp_max_c > max) max = d.temp_max_c;
    }
    if (min === 999) min = 15;
    if (max === -999) max = 35;
    return { weekMin: min, weekMax: max };
  }, [days]);

  const selectedDay = useMemo(
    () => (activeDate ? days.find((d) => d.date === activeDate) : null),
    [days, activeDate]
  );

  const selectedDayIndex = useMemo(
    () => (activeDate ? days.findIndex((d) => d.date === activeDate) : -1),
    [days, activeDate]
  );

  // Hourly records for the selected day
  const hoursForDate = useMemo(() => {
    if (!activeDate) return [];
    return hourly.filter((h) => h.date === activeDate);
  }, [hourly, activeDate]);

  // Chart data for selected day
  const chartData = useMemo(() => {
    if (hoursForDate.length > 0) {
      return hoursForDate.map((h) => ({
        h: (h.hour || "").slice(0, 5),
        rain: units === "imperial" ? (h.precip_mm || 0) / 25.4 : h.precip_mm || 0,
        rainProb: h.precip_prob_pct || 0,
        temp: h.temp_c == null ? null : units === "imperial" ? (h.temp_c * 9) / 5 + 32 : h.temp_c,
        wind: h.wind_kmh == null ? null : units === "imperial" ? h.wind_kmh * 0.621 : h.wind_kmh,
        gust: h.wind_gust_kmh == null ? null : units === "imperial" ? h.wind_gust_kmh * 0.621 : h.wind_gust_kmh,
        rh: h.rh_pct ?? null,
        cloud: h.cloud_pct ?? null,
        sky: h.sky_label || "",
      }));
    }
    if (!selectedDay) return [];
    const tmax = selectedDay.temp_max_c ?? 30;
    const tmin = selectedDay.temp_min_c ?? 20;
    const pmm = selectedDay.precip_mm ?? 0;
    return [0, 3, 6, 9, 12, 15, 18, 21].map((hr) => {
      const isDay = hr >= 6 && hr <= 18;
      const factor = isDay ? Math.sin(((hr - 6) / 12) * Math.PI) : 0;
      const cTemp = tmin + (tmax - tmin) * factor;
      return {
        h: `${String(hr).padStart(2, "0")}:00`,
        rain: (pmm / 8) * (isDay ? 1.4 : 0.6),
        rainProb: selectedDay.precip_prob_pct ?? 0,
        temp: units === "imperial" ? (cTemp * 9) / 5 + 32 : cTemp,
        wind: 12 + Math.round(Math.sin(hr) * 5),
        gust: 18 + Math.round(Math.sin(hr) * 7),
        rh: Math.round(75 - factor * 20),
        cloud: 40,
        sky: pmm > 5 ? "Rain" : "Scattered clouds",
      };
    });
  }, [hoursForDate, selectedDay, units]);

  if (!days.length) {
    return null;
  }

  const selectedWeather = selectedDay
    ? getWeatherIcon(undefined, selectedDay.precip_mm, selectedDay.precip_prob_pct)
    : null;

  const diurnalSpread =
    selectedDay?.temp_max_c != null && selectedDay?.temp_min_c != null
      ? (selectedDay.temp_max_c - selectedDay.temp_min_c).toFixed(1)
      : null;

  return (
    <section
      onClick={() => setLocalSummary(!isSummary)}
      className="neo neo-section-forecast7d p-3.5 space-y-2.5 select-none cursor-pointer transition-all hover:border-[color-mix(in_srgb,var(--accent)_35%,var(--line))]"
      title="Click card to switch between detailed data and overview"
    >
      {/* Section Header */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-1.5">
          <p className="text-[11px] font-black uppercase tracking-[0.18em] text-amber-700 dark:text-amber-400">
            {t.forecast7 || "Forecast 7 Days"}
          </p>
        </div>
        {!isSummary && (
          <p className="text-[10px] text-neo-muted hidden sm:inline">
            Select any day to inspect full hourly curves & agronomy
          </p>
        )}
      </div>

      {isSummary ? (
        <div className="py-1">
          <LaymanSummaryBody summary={get7DayLaymanSummary(dash, locale)} isWide />
        </div>
      ) : (
        /* 7-Day Compact & Scrollable Day Strip */
        <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-thin sm:grid sm:grid-cols-7 sm:overflow-visible">
        {days.map((d, idx) => {
          const isSelected = activeDate === d.date;
          const isToday = idx === 0;
          const wInfo = getWeatherIcon(undefined, d.precip_mm, d.precip_prob_pct);

          // Thermometer bar span calculation
          const dayMin = d.temp_min_c ?? weekMin;
          const dayMax = d.temp_max_c ?? weekMax;
          const tempSpan = Math.max(1, weekMax - weekMin);
          const leftPct = Math.max(0, Math.min(90, ((dayMin - weekMin) / tempSpan) * 100));
          const widthPct = Math.max(10, Math.min(100 - leftPct, ((dayMax - dayMin) / tempSpan) * 100));

          return (
            <div
              key={d.date}
              onClick={(e) => {
                e.stopPropagation();
                setActiveDate(isSelected ? null : d.date);
              }}
              className={`min-w-[5.8rem] sm:min-w-0 cursor-pointer rounded-xl p-2 flex flex-col justify-between transition-all duration-150 border text-center group ${
                isSelected
                  ? "bg-[color-mix(in_srgb,var(--accent)_14%,var(--card))] border-[var(--accent)] shadow-sm ring-1 ring-[var(--accent)]"
                  : "bg-[color-mix(in_srgb,var(--card)_80%,transparent)] border-[var(--line)] hover:border-[color-mix(in_srgb,var(--accent)_30%,var(--line))] hover:bg-[color-mix(in_srgb,var(--accent)_4%,transparent)]"
              }`}
            >
              {/* Day & Date Tag */}
              <div className="flex items-center justify-between gap-1 text-[10px]">
                <span className={`font-semibold tracking-tight truncate ${isSelected ? "text-neo-accent" : "text-neo-text"}`}>
                  {isToday ? "Today" : weekdayName(d.date)}
                </span>
                <span className="font-mono text-[9px] text-neo-muted shrink-0">
                  {d.date.slice(5)}
                </span>
              </div>

              {/* Weather Icon & Condition */}
              <div className="my-1.5 flex flex-col items-center">
                <div className={`w-7 h-7 rounded-lg flex items-center justify-center transition-transform group-hover:scale-105 ${wInfo.badgeColor}`}>
                  {wInfo.icon}
                </div>
                <span className="text-[9px] font-medium text-neo-muted truncate max-w-full mt-1">
                  {wInfo.label}
                </span>
              </div>

              {/* Min/Max Temperature with Thermometer Bar */}
              <div className="space-y-1">
                <div className="flex items-baseline justify-between text-[10px] font-mono px-0.5">
                  <span className="font-bold text-neo-text">{temp(d.temp_max_c, units)}</span>
                  <span className="text-[9px] text-neo-muted">{temp(d.temp_min_c, units)}</span>
                </div>
                <div className="h-1 w-full bg-[var(--line)] rounded-full overflow-hidden relative">
                  <div
                    className="absolute top-0 bottom-0 rounded-full bg-gradient-to-r from-sky-400 via-teal-400 to-amber-500 dark:from-sky-500 dark:via-teal-400 dark:to-amber-400"
                    style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                  />
                </div>
              </div>

              {/* Rain & Probability */}
              <div className="mt-1.5 pt-1 border-t border-[color-mix(in_srgb,var(--line)_50%,transparent)] flex items-center justify-between text-[9px]">
                <span className="font-mono font-medium text-neo-rain truncate">
                  {d.precip_mm > 0 ? rain(d.precip_mm, units) : "0 mm"}
                </span>
                <span className="text-[9px] text-neo-muted shrink-0 flex items-center gap-0.5">
                  <IconDroplet className="w-2.5 h-2.5 opacity-70" />
                  {d.precip_prob_pct ?? 0}%
                </span>
              </div>

              {/* Hazard Badges */}
              {(d.flood_watch || d.irrigate) && (
                <div className="mt-1 flex flex-wrap gap-0.5 justify-center">
                  {d.flood_watch && (
                    <span className="chip level-alert text-[7px] font-semibold uppercase px-1 py-0">
                      {locale === "hi" ? "बाढ़" : locale === "bn" ? "বন্যা" : "Flood"}
                    </span>
                  )}
                  {d.irrigate && (
                    <span className="chip level-ok text-[7px] font-semibold uppercase px-1 py-0">
                      {locale === "hi" ? "सिंचाई" : locale === "bn" ? "সেচ" : "Irrigate"}
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
      )}

      {/* Floating Synoptic Detail Modal Window (Portaled to document.body) */}
      {mounted && typeof document !== "undefined" && activeDate && selectedDay && selectedWeather
        ? createPortal(
            <div
              className="fixed inset-0 z-[99999] flex items-center justify-center p-3 sm:p-6 bg-black/60 backdrop-blur-sm transition-opacity duration-150 animate-in fade-in"
              onClick={() => setActiveDate(null)}
            >
              <div
                className="w-full max-w-2xl max-h-[86vh] flex flex-col rounded-2xl bg-[var(--card)] border border-[var(--line)] shadow-2xl overflow-hidden animate-in zoom-in-95 duration-150"
                onClick={(e) => e.stopPropagation()}
              >
                {/* Sticky Header */}
                <div className="shrink-0 flex items-center justify-between gap-3 px-4 py-3 sm:px-5 sm:py-3.5 border-b border-[var(--line)] bg-[var(--card)]">
                  <div className="flex items-center gap-3">
                    <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${selectedWeather.badgeColor}`}>
                      {selectedWeather.icon}
                    </div>
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="text-sm sm:text-base font-bold text-neo-text leading-tight">
                          {formatFullDate(selectedDay.date)}
                        </h3>
                        <span className="chip text-[9px] font-mono uppercase px-1.5 py-0">
                          Day {selectedDayIndex + 1} of {days.length}
                        </span>
                      </div>
                      <p className="text-[11px] text-neo-muted font-normal mt-0.5">
                        {selectedWeather.label} · High: {temp(selectedDay.temp_max_c, units)} · Low: {temp(selectedDay.temp_min_c, units)}
                        {diurnalSpread && ` · Amplitude: ${diurnalSpread}°C`}
                      </p>
                    </div>
                  </div>

                  {/* Close Button */}
                  <button
                    type="button"
                    onClick={() => setActiveDate(null)}
                    className="w-7 h-7 rounded-lg flex items-center justify-center text-neo-muted hover:text-neo-text hover:bg-[color-mix(in_srgb,var(--line)_60%,transparent)] transition text-xs font-semibold shrink-0"
                    aria-label="Close"
                  >
                    ✕
                  </button>
                </div>

                {/* Scrollable Body */}
                <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-3.5 scrollbar-thin">
                  {/* Quick Synoptic Strip */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                    <div className="neo-in px-3 py-2 rounded-xl">
                      <span className="text-[9px] uppercase tracking-wider text-neo-muted font-semibold block">
                        {locale === "hi" ? "तापमान सीमा" : locale === "bn" ? "তাপমাত্রার বিস্তার" : "Thermal Range"}
                      </span>
                      <div className="flex items-baseline gap-1 mt-0.5">
                        <span className="font-mono text-sm font-bold text-amber-600 dark:text-amber-400">
                          {temp(selectedDay.temp_max_c, units)}
                        </span>
                        <span className="text-neo-muted text-[10px]">/</span>
                        <span className="font-mono text-xs font-medium text-sky-600 dark:text-sky-400">
                          {temp(selectedDay.temp_min_c, units)}
                        </span>
                      </div>
                    </div>

                    <div className="neo-in px-3 py-2 rounded-xl">
                      <span className="text-[9px] uppercase tracking-wider text-neo-muted font-semibold block">
                        {locale === "hi" ? "वर्षा की संभावना" : locale === "bn" ? "বৃষ্টিপাত ও সম্ভাবনা" : "Precipitation"}
                      </span>
                      <div className="flex items-baseline gap-1.5 mt-0.5">
                        <span className="font-mono text-sm font-bold text-neo-rain">
                          {rain(selectedDay.precip_mm, units)}
                        </span>
                        <span className="chip px-1.5 py-0 text-[8px] font-mono">
                          {selectedDay.precip_prob_pct}% {locale === "hi" ? "संभावना" : locale === "bn" ? "সম্ভাবনা" : "prob"}
                        </span>
                      </div>
                    </div>

                    {(displayNull || selectedDay.et0_mm != null || selectedDay.water_balance_mm != null) && (
                      <div className="neo-in px-3 py-2 rounded-xl">
                        <span className="text-[9px] uppercase tracking-wider text-neo-muted font-semibold block">
                          {locale === "hi" ? "जल संतुलन व ET₀" : locale === "bn" ? "জল ভারসাম্য ও ET₀" : "Water Balance & ET₀"}
                        </span>
                        <div className="flex items-baseline gap-1 mt-0.5">
                          <span className={`font-mono text-sm font-bold ${selectedDay.water_balance_mm >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"}`}>
                            {selectedDay.water_balance_mm > 0 ? `+${rain(selectedDay.water_balance_mm, units)}` : rain(selectedDay.water_balance_mm, units)}
                          </span>
                          <span className="text-[8px] text-neo-muted">
                            (ET₀: {rain(selectedDay.et0_mm, units)})
                          </span>
                        </div>
                      </div>
                    )}

                    {(displayNull || selectedDay.soil_m3m3 != null || selectedDay.irrigate != null) && (
                      <div className="neo-in px-3 py-2 rounded-xl">
                        <span className="text-[9px] uppercase tracking-wider text-neo-muted font-semibold block">
                          {locale === "hi" ? "खेत मार्गदर्शन" : locale === "bn" ? "মাঠ নির্দেশনা" : "Field Guidance"}
                        </span>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          <span className={`chip px-1.5 py-0 text-[8px] font-semibold uppercase ${selectedDay.irrigate ? "level-ok" : selectedDay.flood_watch ? "level-alert" : "text-neo-text"}`}>
                            {selectedDay.flood_watch
                              ? (locale === "hi" ? "बाढ़ चेतावनी" : locale === "bn" ? "বন্যা সতর্কতা" : "Flood Watch")
                              : selectedDay.irrigate
                              ? (locale === "hi" ? "सिंचाई अनुशंसित" : locale === "bn" ? "সেচ সুপারিশকৃত" : "Irrigation Recommended")
                              : (locale === "hi" ? "सिंचाई रोकें" : locale === "bn" ? "সেচ স্থগিত" : "Hold Irrigation")}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Segmented View Switcher */}
                  <div className="flex items-center justify-between gap-2 flex-wrap pt-0.5">
                    <div className="inline-flex rounded-lg bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] p-0.5 border border-[var(--line)]">
                      <button
                        type="button"
                        onClick={() => setInspectorTab("curve")}
                        className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold tracking-tight transition-all ${
                          inspectorTab === "curve"
                            ? "bg-neo-accent text-white shadow-xs"
                            : "text-neo-muted hover:text-neo-text"
                        }`}
                      >
                        <IconActivity className="w-3.5 h-3.5" />
                        {locale === "hi" ? "प्रति घंटा वक्र" : locale === "bn" ? "প্রতি ঘণ্টার বক্ররেখা" : "Hourly Curve"}
                      </button>
                      <button
                        type="button"
                        onClick={() => setInspectorTab("reel")}
                        className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold tracking-tight transition-all ${
                          inspectorTab === "reel"
                            ? "bg-neo-accent text-white shadow-xs"
                            : "text-neo-muted hover:text-neo-text"
                        }`}
                      >
                        <IconClock className="w-3.5 h-3.5" />
                        {locale === "hi" ? "प्रति घंटा रील" : locale === "bn" ? "প্রতি ঘণ্টার রিল" : "Hourly Reel"}
                      </button>
                      <button
                        type="button"
                        onClick={() => setInspectorTab("agronomy")}
                        className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold tracking-tight transition-all ${
                          inspectorTab === "agronomy"
                            ? "bg-neo-accent text-white shadow-xs"
                            : "text-neo-muted hover:text-neo-text"
                        }`}
                      >
                        <IconLeaf className="w-3.5 h-3.5" />
                        {locale === "hi" ? "कृषि व मृदा" : locale === "bn" ? "কৃষি ও মৃত্তিকা" : "Agronomy & Soil"}
                      </button>
                    </div>

                    {inspectorTab === "curve" && (
                      <div className="inline-flex rounded-lg bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] p-0.5 border border-[var(--line)]">
                        {(["combo", "wind", "humidity"] as const).map((mode) => (
                          <button
                            key={mode}
                            type="button"
                            onClick={() => setCurveVar(mode)}
                            className={`rounded-md px-2 py-0.5 text-[10px] font-medium transition-all ${
                              curveVar === mode
                                ? "bg-neo-accent text-white shadow-xs"
                                : "text-neo-muted hover:text-neo-text"
                            }`}
                          >
                            {mode === "combo"
                              ? (locale === "hi" ? "तापमान व वर्षा" : locale === "bn" ? "তাপমাত্রা ও বৃষ্টি" : "Temp & Rain")
                              : mode === "wind"
                              ? (locale === "hi" ? "पवन व झोंके" : locale === "bn" ? "বাতাস ও দমকা" : "Wind & Gusts")
                              : (locale === "hi" ? "आर्द्रता" : locale === "bn" ? "আর্দ্রতা" : "Humidity")}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Subtab Content */}
                  <div className="min-h-[160px]">
                    {/* View 1: Hourly Curve */}
                    {inspectorTab === "curve" && (
                      <div key="forecast-curve" className="fade-in-scale space-y-2">
                        <div className="h-44 sm:h-48">
                          <ResponsiveContainer width="100%" height="100%">
                            {curveVar === "combo" ? (
                              <ComposedChart data={chartData}>
                                <defs>
                                  <linearGradient id="tempGradPro" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.35} />
                                    <stop offset="95%" stopColor="var(--accent)" stopOpacity={0.02} />
                                  </linearGradient>
                                </defs>
                                <CartesianGrid stroke="var(--line)" vertical={false} strokeDasharray="3 3" />
                                <XAxis dataKey="h" stroke="var(--muted)" fontSize={9} interval={2} />
                                <YAxis yAxisId="left" stroke="var(--muted)" fontSize={9} width={28} unit={` ${tempUnit(units)}`} />
                                <YAxis yAxisId="right" orientation="right" stroke="var(--muted)" fontSize={9} width={28} unit={` ${rainUnit(units)}`} />
                                <Tooltip contentStyle={tip} />
                                <Area yAxisId="left" type="monotone" dataKey="temp" stroke="var(--accent)" strokeWidth={2} fill="url(#tempGradPro)" name={`Temperature (${tempUnit(units)})`} />
                                <Bar yAxisId="right" dataKey="rain" fill="var(--rain)" radius={[2, 2, 0, 0]} opacity={0.8} name={`Precipitation (${rainUnit(units)})`} />
                              </ComposedChart>
                            ) : curveVar === "wind" ? (
                              <ComposedChart data={chartData}>
                                <defs>
                                  <linearGradient id="windGradPro" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="var(--warn)" stopOpacity={0.25} />
                                    <stop offset="95%" stopColor="var(--warn)" stopOpacity={0.02} />
                                  </linearGradient>
                                </defs>
                                <CartesianGrid stroke="var(--line)" vertical={false} strokeDasharray="3 3" />
                                <XAxis dataKey="h" stroke="var(--muted)" fontSize={9} interval={2} />
                                <YAxis stroke="var(--muted)" fontSize={9} width={28} unit={` ${units === "imperial" ? "mph" : "km/h"}`} />
                                <Tooltip contentStyle={tip} />
                                <Area type="monotone" dataKey="gust" stroke="var(--warn)" strokeWidth={1.5} strokeDasharray="3 2" fill="url(#windGradPro)" name="Gusts" />
                                <Line type="monotone" dataKey="wind" stroke="var(--accent)" strokeWidth={2} dot={false} name="Wind Speed" />
                              </ComposedChart>
                            ) : (
                              <ComposedChart data={chartData}>
                                <CartesianGrid stroke="var(--line)" vertical={false} strokeDasharray="3 3" />
                                <XAxis dataKey="h" stroke="var(--muted)" fontSize={9} interval={2} />
                                <YAxis stroke="var(--muted)" fontSize={9} width={28} unit="%" />
                                <Tooltip contentStyle={tip} />
                                <Line type="monotone" dataKey="rh" stroke="var(--rain)" strokeWidth={2} dot={false} name="Relative Humidity (%)" />
                                <Line type="monotone" dataKey="cloud" stroke="var(--muted)" strokeWidth={1.5} strokeDasharray="3 2" dot={false} name="Cloud Cover (%)" />
                              </ComposedChart>
                            )}
                          </ResponsiveContainer>
                        </div>
                      </div>
                    )}

                    {/* View 2: Hour-by-Hour Reel */}
                    {inspectorTab === "reel" && (
                      <div key="forecast-reel" className="fade-in-scale space-y-2">
                        <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-thin">
                          {(hoursForDate.length > 0 ? hoursForDate : [
                            { hour: "00:00", temp_c: selectedDay.temp_min_c, precip_mm: 0, precip_prob_pct: 10, wind_kmh: 8, rh_pct: 82, sky_label: "Clear" },
                            { hour: "03:00", temp_c: (selectedDay.temp_min_c ?? 20) - 1, precip_mm: 0, precip_prob_pct: 10, wind_kmh: 7, rh_pct: 85, sky_label: "Clear" },
                            { hour: "06:00", temp_c: selectedDay.temp_min_c, precip_mm: 0.2, precip_prob_pct: 20, wind_kmh: 9, rh_pct: 80, sky_label: "Morning Sun" },
                            { hour: "09:00", temp_c: ((selectedDay.temp_min_c ?? 20) + (selectedDay.temp_max_c ?? 30)) / 2, precip_mm: 0.5, precip_prob_pct: 35, wind_kmh: 12, rh_pct: 68, sky_label: "Passing Clouds" },
                            { hour: "12:00", temp_c: selectedDay.temp_max_c, precip_mm: 2.5, precip_prob_pct: selectedDay.precip_prob_pct, wind_kmh: 16, rh_pct: 60, sky_label: "Rain Showers" },
                            { hour: "15:00", temp_c: (selectedDay.temp_max_c ?? 30) - 1, precip_mm: 1.8, precip_prob_pct: selectedDay.precip_prob_pct, wind_kmh: 15, rh_pct: 64, sky_label: "Cloudy" },
                            { hour: "18:00", temp_c: ((selectedDay.temp_min_c ?? 20) + (selectedDay.temp_max_c ?? 30)) / 2 + 1, precip_mm: 0.4, precip_prob_pct: 40, wind_kmh: 11, rh_pct: 72, sky_label: "Evening" },
                            { hour: "21:00", temp_c: (selectedDay.temp_min_c ?? 20) + 2, precip_mm: 0, precip_prob_pct: 15, wind_kmh: 9, rh_pct: 78, sky_label: "Night Clear" },
                          ]).map((h: Partial<HourlySlot>) => {
                            const hrIcon = getWeatherIcon(h.weather_code, h.precip_mm, h.precip_prob_pct);
                            return (
                              <div
                                key={String(h.hour)}
                                className="neo-in flex flex-col items-center gap-1 rounded-xl p-2.5 min-w-[5.25rem] text-center shrink-0 hover:bg-[color-mix(in_srgb,var(--accent)_6%,transparent)] transition-all"
                              >
                                <span className="text-[10px] font-mono text-neo-muted">
                                  {String(h.hour || "").slice(0, 5)}
                                </span>
                                <div className="my-0.5">{hrIcon.icon}</div>
                                <span className="font-mono text-xs font-bold text-neo-text">
                                  {temp(h.temp_c, units)}
                                </span>
                                <div className="w-full h-px bg-[var(--line)] my-0.5" />
                                <span className="font-mono text-[10px] font-medium text-neo-rain">
                                  {rain(h.precip_mm, units)}
                                </span>
                                <span className="text-[8px] text-neo-muted flex items-center gap-0.5">
                                  <IconDroplet className="w-2 h-2 opacity-60" />
                                  {h.precip_prob_pct ?? 0}%
                                </span>
                                <span className="text-[8px] font-mono text-neo-muted truncate max-w-full flex items-center gap-0.5">
                                  <IconWind className="w-2 h-2 opacity-60" />
                                  {speed(h.wind_kmh, units)}
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* View 3: Agronomy & Indices */}
                    {inspectorTab === "agronomy" && (
                      <div key="forecast-agronomy" className="fade-in-scale grid sm:grid-cols-2 gap-2.5">
                        {/* Diurnal Thermal Range */}
                        <div className="neo-in p-3 rounded-xl flex flex-col justify-between">
                          <span className="text-[9px] uppercase tracking-wider text-neo-muted font-semibold block">
                            {locale === "hi" ? "दैनिक तापमान विस्तार" : locale === "bn" ? "প্রাত্যহিক তাপমাত্রার বিস্তার" : "Thermal Amplitude"}
                          </span>
                          <div className="my-1">
                            <span className="font-mono text-lg font-bold text-amber-600 dark:text-amber-400">
                              {diurnalSpread ? `${diurnalSpread}°C` : "—"}
                            </span>
                            <p className="text-[10px] text-neo-muted mt-0.5">
                              {locale === "hi"
                                ? `अधिकतम (${temp(selectedDay.temp_max_c, units)}) और न्यूनतम (${temp(selectedDay.temp_min_c, units)}) के बीच अंतर।`
                                : locale === "bn"
                                ? `সর্বোচ্চ (${temp(selectedDay.temp_max_c, units)}) ও সর্বনিম্ন (${temp(selectedDay.temp_min_c, units)})-এর পার্থক্য।`
                                : `Spread between Tmax (${temp(selectedDay.temp_max_c, units)}) and Tmin (${temp(selectedDay.temp_min_c, units)}).`}
                            </p>
                          </div>
                          <span className="text-[8px] font-mono text-neo-accent uppercase tracking-wider">
                            {Number(diurnalSpread ?? 0) > 10
                              ? (locale === "hi" ? "उच्च तापमान उतार-चढ़ाव" : locale === "bn" ? "উচ্চ তাপমাত্রার ওঠানামা" : "Elevated Diurnal Variation")
                              : (locale === "hi" ? "सौम्य तापमान भिन्नता" : locale === "bn" ? "হালকা তাপমাত্রার পার্থক্য" : "Mild Temperature Variation")}
                          </span>
                        </div>

                        {/* Evaporative Water Deficit / Surplus */}
                        <div className="neo-in p-3 rounded-xl flex flex-col justify-between">
                          <span className="text-[9px] uppercase tracking-wider text-neo-muted font-semibold block">
                            {locale === "hi" ? "जल-वैज्ञानिक संतुलन" : locale === "bn" ? "জলতাত্ত্বিক ভারসাম্য" : "Hydrological Balance"}
                          </span>
                          <div className="my-1">
                            <span className={`font-mono text-lg font-bold ${selectedDay.water_balance_mm >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"}`}>
                              {selectedDay.water_balance_mm > 0 ? `+${rain(selectedDay.water_balance_mm, units)}` : rain(selectedDay.water_balance_mm, units)}
                            </span>
                            <p className="text-[10px] text-neo-muted mt-0.5">
                              {locale === "hi" ? "वर्षा" : locale === "bn" ? "বৃষ্টি" : "Rain"} ({rain(selectedDay.precip_mm, units)}) − ET₀ ({rain(selectedDay.et0_mm, units)})
                            </p>
                          </div>
                          <span className={`text-[8px] font-mono uppercase tracking-wider ${selectedDay.water_balance_mm >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"}`}>
                            {selectedDay.water_balance_mm >= 0
                              ? (locale === "hi" ? "जल अधिशेष (सरप्लस)" : locale === "bn" ? "জল উদ্বৃত্ত (সারপ্লাস)" : "Hydrological Surplus")
                              : (locale === "hi" ? "मृदा नमी घाटा" : locale === "bn" ? "মাটির আর্দ্রতা ঘাটতি" : "Soil Moisture Deficit")}
                          </span>
                        </div>

                        {/* Operational Spray Window */}
                        <div className="neo-in p-3 rounded-xl flex flex-col justify-between">
                          <span className="text-[9px] uppercase tracking-wider text-neo-muted font-semibold block">
                            {locale === "hi" ? "कीटनाशक छिड़काव उपयुक्तता" : locale === "bn" ? "কীটনাশক স্প্রে উপযুক্ততা" : "Operational Spray Window"}
                          </span>
                          <div className="my-1">
                            <span className="font-mono text-lg font-bold text-neo-accent">
                              {selectedDay.precip_prob_pct > 50
                                ? (locale === "hi" ? "बारिश का उच्च जोखिम" : locale === "bn" ? "বৃষ্টির উচ্চ ঝুঁকি" : "High Rain Risk")
                                : (locale === "hi" ? "अनुकूल" : locale === "bn" ? "অনুকূল" : "Favorable")}
                            </span>
                            <p className="text-[10px] text-neo-muted mt-0.5">
                              {locale === "hi"
                                ? "फसल छिड़काव और कृषि कार्यों के लिए उपयुक्तता।"
                                : locale === "bn"
                                ? "ফসল স্প্রে ও রাসায়নিক প্রয়োগের উপযোগিতা।"
                                : "Crop spraying and chemical application suitability."}
                            </p>
                          </div>
                          <span className="text-[8px] font-mono text-neo-muted uppercase tracking-wider">
                            {selectedDay.precip_prob_pct > 50
                              ? (locale === "hi" ? "छिड़काव कार्य स्थगित करें" : locale === "bn" ? "স্প্রে কার্যক্রম স্থগিত রাখুন" : "Postpone Field Application")
                              : (locale === "hi" ? "छिड़काव कार्य हेतु उपयुक्त समय" : locale === "bn" ? "ক্ষেতের কাজের উপযুক্ত সময়" : "Suitable Window for Operations")}
                          </span>
                        </div>

                        {/* Irrigation Guidance */}
                        <div className="neo-in p-3 rounded-xl flex flex-col justify-between">
                          <span className="text-[9px] uppercase tracking-wider text-neo-muted font-semibold block">
                            Irrigation Guidance
                          </span>
                          <div className="my-1">
                            <span className={`chip px-2 py-0.5 text-xs font-semibold uppercase ${selectedDay.irrigate ? "level-ok" : selectedDay.flood_watch ? "level-alert" : "text-neo-text"}`}>
                              {selectedDay.flood_watch ? "Flood Watch Active" : selectedDay.irrigate ? "Apply Irrigation" : "Hold Irrigation"}
                            </span>
                            <p className="text-[10px] text-neo-muted mt-1">
                              Soil Moisture: {selectedDay.soil_m3m3 != null ? `${selectedDay.soil_m3m3} m³/m³` : "Normal"}
                            </p>
                          </div>
                          <span className="text-[8px] font-mono text-neo-muted uppercase tracking-wider">
                            Prithvi Agricultural Model
                          </span>
                        </div>
                      </div>
                    )}
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
