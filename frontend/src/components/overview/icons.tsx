"use client";

import type { CSSProperties } from "react";

export function IconPin({ className, style }: { className?: string; style?: CSSProperties }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style} className={className || "w-3.5 h-3.5"}>
      <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  );
}


export function IconShieldAlert({ className, style }: { className?: string; style?: CSSProperties }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style} className={className || "w-3.5 h-3.5"}>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="M12 8v4" />
      <path d="M12 16h.01" />
    </svg>
  );
}


export function IconWarningSign({ className, style }: { className?: string; style?: CSSProperties }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style} className={className || "w-3.5 h-3.5"}>
      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}


export function IconFileBulletin({ className, style }: { className?: string; style?: CSSProperties }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style} className={className || "w-3.5 h-3.5"}>
      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <line x1="10" y1="9" x2="8" y2="9" />
    </svg>
  );
}


export function IconMapNavigator({ className, style }: { className?: string; style?: CSSProperties }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style} className={className || "w-3.5 h-3.5"}>
      <polygon points="3 11 22 2 13 21 11 13 3 11" />
    </svg>
  );
}


export function IconExternal({ className, style }: { className?: string; style?: CSSProperties }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style} className={className || "w-3 h-3"}>
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <polyline points="15 3 21 3 21 9" />
      <line x1="10" y1="14" x2="21" y2="3" />
    </svg>
  );
}


export function IconCross({ className, style }: { className?: string; style?: CSSProperties }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style} className={className || "w-4 h-4"}>
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}


export function IconChevronDown({ className, style }: { className?: string; style?: CSSProperties }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style} className={className || "w-4 h-4"}>
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}


export function IconSparkle({ className, style }: { className?: string; style?: CSSProperties }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style} className={className || "w-3.5 h-3.5"}>
      <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
    </svg>
  );
}


export function IconCyclone({ className, style }: { className?: string; style?: CSSProperties }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style} className={className || "w-4 h-4"}>
      <path d="M12 2a10 10 0 0 0-7.07 17.07M12 22a10 10 0 0 0 7.07-17.07" />
      <circle cx="12" cy="12" r="3" />
      <path d="M8.5 8.5a5 5 0 0 1 7 0" />
      <path d="M15.5 15.5a5 5 0 0 1-7 0" />
    </svg>
  );
}


export function IconSeismic({ className, style }: { className?: string; style?: CSSProperties }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style} className={className || "w-4 h-4"}>
      <path d="M2 12h3l2.5-6 4 12 3.5-9 2 6 2-3h5" />
    </svg>
  );
}


export function IconTsunamiWave({ className, style }: { className?: string; style?: CSSProperties }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style} className={className || "w-5 h-5"}>
      <path d="M2 6c.6.5 1.2 1 2.5 1C7 7 7 5 9.5 5c2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1" />
      <path d="M2 12c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1" />
      <path d="M2 18c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1" />
    </svg>
  );
}

// Vivid, Eye-Catching Emergency & Hazard Theme Palette

export const HAZARD_THEMES: Record<
  string,
  {
    color: string;
    borderClass: string;
    badgeBg: string;
    badgeText: string;
    cardBg: string;
    label: string;
  }
> = {
  rainfall: {
    color: "#2563eb",
    borderClass: "border-l-blue-500 dark:border-l-blue-400",
    badgeBg: "rgba(37, 99, 235, 0.12)",
    badgeText: "#2563eb",
    cardBg: "linear-gradient(135deg, color-mix(in srgb, var(--card) 92%, #2563eb 8%), var(--card))",
    label: "Heavy Rainfall",
  },
  flood: {
    color: "#0284c7",
    borderClass: "border-l-sky-500 dark:border-l-sky-400",
    badgeBg: "rgba(2, 132, 199, 0.12)",
    badgeText: "#0284c7",
    cardBg: "linear-gradient(135deg, color-mix(in srgb, var(--card) 92%, #0284c7 8%), var(--card))",
    label: "Flood & Inundation",
  },
  thunderstorm: {
    color: "#8b5cf6",
    borderClass: "border-l-violet-500 dark:border-l-violet-400",
    badgeBg: "rgba(139, 92, 246, 0.12)",
    badgeText: "#8b5cf6",
    cardBg: "linear-gradient(135deg, color-mix(in srgb, var(--card) 92%, #8b5cf6 8%), var(--card))",
    label: "Thunderstorm Squall",
  },
  lightning: {
    color: "#a855f7",
    borderClass: "border-l-purple-500 dark:border-l-purple-400",
    badgeBg: "rgba(168, 85, 247, 0.12)",
    badgeText: "#a855f7",
    cardBg: "linear-gradient(135deg, color-mix(in srgb, var(--card) 92%, #a855f7 8%), var(--card))",
    label: "Lightning Hazard",
  },
  cloudburst: {
    color: "#4f46e5",
    borderClass: "border-l-indigo-500 dark:border-l-indigo-400",
    badgeBg: "rgba(79, 70, 229, 0.12)",
    badgeText: "#4f46e5",
    cardBg: "linear-gradient(135deg, color-mix(in srgb, var(--card) 92%, #4f46e5 8%), var(--card))",
    label: "Cloudburst conditions",
  },
  extreme_rain: {
    color: "#4f46e5",
    borderClass: "border-l-indigo-500 dark:border-l-indigo-400",
    badgeBg: "rgba(79, 70, 229, 0.12)",
    badgeText: "#4f46e5",
    cardBg: "linear-gradient(135deg, color-mix(in srgb, var(--card) 92%, #4f46e5 8%), var(--card))",
    label: "Extreme rain nowcast",
  },
  cyclone: {
    color: "#e11d48",
    borderClass: "border-l-rose-500 dark:border-l-rose-400",
    badgeBg: "rgba(225, 29, 72, 0.12)",
    badgeText: "#e11d48",
    cardBg: "linear-gradient(135deg, color-mix(in srgb, var(--card) 92%, #e11d48 8%), var(--card))",
    label: "Tropical Cyclone",
  },
  heatwave: {
    color: "#ea580c",
    borderClass: "border-l-orange-500 dark:border-l-orange-400",
    badgeBg: "rgba(234, 88, 12, 0.12)",
    badgeText: "#ea580c",
    cardBg: "linear-gradient(135deg, color-mix(in srgb, var(--card) 92%, #ea580c 8%), var(--card))",
    label: "Heatwave Advisory",
  },
  drought: {
    color: "#d97706",
    borderClass: "border-l-amber-500 dark:border-l-amber-400",
    badgeBg: "rgba(217, 119, 6, 0.12)",
    badgeText: "#d97706",
    cardBg: "linear-gradient(135deg, color-mix(in srgb, var(--card) 92%, #d97706 8%), var(--card))",
    label: "Agricultural Drought",
  },
  aqi: {
    color: "#059669",
    borderClass: "border-l-emerald-500 dark:border-l-emerald-400",
    badgeBg: "rgba(5, 150, 105, 0.12)",
    badgeText: "#059669",
    cardBg: "linear-gradient(135deg, color-mix(in srgb, var(--card) 92%, #059669 8%), var(--card))",
    label: "Air Quality (AQI)",
  },
  seismic: {
    color: "#c2410c",
    borderClass: "border-l-amber-600 dark:border-l-amber-500",
    badgeBg: "rgba(194, 65, 12, 0.12)",
    badgeText: "#c2410c",
    cardBg: "linear-gradient(135deg, color-mix(in srgb, var(--card) 92%, #c2410c 8%), var(--card))",
    label: "Seismic Motion",
  },
  tsunami: {
    color: "#0d9488",
    borderClass: "border-l-teal-500 dark:border-l-teal-400",
    badgeBg: "rgba(13, 148, 136, 0.12)",
    badgeText: "#0d9488",
    cardBg: "linear-gradient(135deg, color-mix(in srgb, var(--card) 92%, #0d9488 8%), var(--card))",
    label: "Tsunami Early Watch",
  },
  marine: {
    color: "#0284c7",
    borderClass: "border-l-cyan-500 dark:border-l-cyan-400",
    badgeBg: "rgba(2, 132, 199, 0.12)",
    badgeText: "#0284c7",
    cardBg: "linear-gradient(135deg, color-mix(in srgb, var(--card) 92%, #0284c7 8%), var(--card))",
    label: "Marine Sea-State",
  },
  wind: {
    color: "#06b6d4",
    borderClass: "border-l-cyan-500 dark:border-l-cyan-400",
    badgeBg: "rgba(6, 182, 212, 0.12)",
    badgeText: "#06b6d4",
    cardBg: "linear-gradient(135deg, color-mix(in srgb, var(--card) 92%, #06b6d4 8%), var(--card))",
    label: "High Wind Squall",
  },
  fog: {
    color: "#64748b",
    borderClass: "border-l-slate-500 dark:border-l-slate-400",
    badgeBg: "rgba(100, 116, 139, 0.12)",
    badgeText: "#64748b",
    cardBg: "linear-gradient(135deg, color-mix(in srgb, var(--card) 92%, #64748b 8%), var(--card))",
    label: "Dense Fog",
  },
  uv: {
    color: "#ca8a04",
    borderClass: "border-l-yellow-500 dark:border-l-yellow-400",
    badgeBg: "rgba(202, 138, 4, 0.12)",
    badgeText: "#ca8a04",
    cardBg: "linear-gradient(135deg, color-mix(in srgb, var(--card) 92%, #ca8a04 8%), var(--card))",
    label: "High-risk UV",
  },
  fire: {
    color: "#ea580c",
    borderClass: "border-l-orange-600 dark:border-l-orange-500",
    badgeBg: "rgba(234, 88, 12, 0.14)",
    badgeText: "#ea580c",
    cardBg: "linear-gradient(135deg, color-mix(in srgb, var(--card) 92%, #ea580c 8%), var(--card))",
    label: "Forest Fire",
  },
  landslide: {
    color: "#92400e",
    borderClass: "border-l-amber-800 dark:border-l-amber-700",
    badgeBg: "rgba(146, 64, 14, 0.14)",
    badgeText: "#92400e",
    cardBg: "linear-gradient(135deg, color-mix(in srgb, var(--card) 92%, #92400e 8%), var(--card))",
    label: "Landslide Watch",
  },
};


export function getHazardTheme(hazardOrKind?: string) {
  const k = (hazardOrKind || "").toLowerCase().trim();
  if (k.includes("rain") || k.includes("precip")) return HAZARD_THEMES.rainfall;
  if (k.includes("flood") || k.includes("discharge")) return HAZARD_THEMES.flood;
  if (k.includes("cloudburst")) return HAZARD_THEMES.cloudburst;
  if (k.includes("thunder") || k.includes("squall")) return HAZARD_THEMES.thunderstorm;
  if (k.includes("lightning")) return HAZARD_THEMES.lightning;
  if (k.includes("cyclone") || k.includes("depression")) return HAZARD_THEMES.cyclone;
  if (k.includes("heat")) return HAZARD_THEMES.heatwave;
  if (k.includes("drought")) return HAZARD_THEMES.drought;
  if (k.includes("aqi") || k.includes("air") || k.includes("pm2")) return HAZARD_THEMES.aqi;
  if (k.includes("seismic") || k.includes("earthquake") || k.includes("quake")) return HAZARD_THEMES.seismic;
  if (k.includes("tsunami")) return HAZARD_THEMES.tsunami;
  if (k.includes("marine") || k.includes("wave")) return HAZARD_THEMES.marine;
  if (k.includes("wind") || k.includes("gale")) return HAZARD_THEMES.wind;
  if (k.includes("fog") || k.includes("visibility")) return HAZARD_THEMES.fog;
  if (k.includes("uv") || k.includes("radiation") || k.includes("ultraviolet")) return HAZARD_THEMES.uv;
  if (k.includes("fire") || k.includes("wildfire")) return HAZARD_THEMES.fire;
  if (k.includes("landslide") || k.includes("mudslide")) return HAZARD_THEMES.landslide;
  return HAZARD_THEMES.rainfall;
}

