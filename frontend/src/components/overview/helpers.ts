"use client";

import type { DashboardSnapshot } from "@/types/dashboard";

export function hhmm(t: string) {
  const i = t.indexOf("T");
  return i >= 0 ? t.slice(i + 1, i + 6) : t.slice(-5);
}


export function weekday(iso?: string) {
  if (!iso) return "—";
  const d = new Date(iso.includes("T") ? iso : `${iso}T12:00:00`);
  return Number.isNaN(d.getTime()) ? iso.slice(5) : d.toLocaleDateString("en-IN", { weekday: "short" });
}


export function feelsLikeC(tempC?: number | null, rh?: number | null) {
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
  return Math.round(hi * 10) / 10;
}



export const tip = {
  background: "var(--card)",
  border: "1px solid var(--line)",
  borderRadius: 12,
  fontSize: 12,
  color: "var(--text)",
};

// ── Suggestion severity helper ──────────────────────────────────────

export function suggestionLevel(id: string, v: string): "ok" | "watch" | "alert" | "danger" {
  const val = v.toLowerCase().trim();
  if (val === "quiet" || val === "0" || val === "—") return "ok";
  if (val === "watch") return "watch";
  if (val === "warning" || val === "alert") return "alert";
  if (val === "danger" || val === "extreme") return "danger";
  // numeric heuristics
  const num = parseFloat(val);
  if (!isNaN(num)) {
    if (id === "flood" || id === "drought" || id === "heat") {
      if (num >= 75) return "danger";
      if (num >= 50) return "alert";
      if (num >= 25) return "watch";
      return "ok";
    }
    if (id === "uv") {
      if (num >= 11) return "danger";
      if (num >= 8) return "alert";
      if (num >= 3) return "watch";
      return "ok";
    }
    if (id === "fish") {
      if (num > 3) return "danger";
      if (num > 2) return "alert";
      if (num > 1) return "watch";
      return "ok";
    }
    if (num > 0) return "watch";
  }
  return "watch"; // non-empty, non-quiet = watch
}


export const suggLevel: Record<string, { bg: string; text: string; dot: string }> = {
  ok: { bg: "bg-[color-mix(in_srgb,var(--accent)_10%,transparent)]", text: "text-neo-accent", dot: "bg-[var(--accent)]" },
  watch: { bg: "bg-[color-mix(in_srgb,var(--warn)_12%,transparent)]", text: "text-neo-warn", dot: "bg-[var(--warn)]" },
  alert: { bg: "bg-[color-mix(in_srgb,var(--accent2)_12%,transparent)]", text: "text-neo-accent2", dot: "bg-[var(--accent2)]" },
  danger: { bg: "bg-[color-mix(in_srgb,var(--danger)_12%,transparent)]", text: "text-neo-danger", dot: "bg-[var(--danger)]" },
};

// Alert severity colors for the sidebar panel

export const alertTone: Record<string, string> = {
  extreme: "border-l-[var(--danger)] bg-[color-mix(in_srgb,var(--danger)_7%,transparent)]",
  warning: "border-l-[var(--warn)]   bg-[color-mix(in_srgb,var(--warn)_7%,transparent)]",
  alert: "border-l-[var(--accent2)] bg-[color-mix(in_srgb,var(--accent2)_6%,transparent)]",
  watch: "border-l-[var(--accent)]  bg-[color-mix(in_srgb,var(--accent)_6%,transparent)]",
};

export const alertDot: Record<string, string> = {
  extreme: "text-neo-danger",
  warning: "text-neo-warn",
  alert: "text-neo-accent2",
  watch: "text-neo-accent",
};

// Known Indian capitals & major cities coordinates for instant offline location switching

export function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
    Math.cos((lat2 * Math.PI) / 180) *
    Math.sin(dLon / 2) *
    Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return Math.round(R * c);
}

// Clean and parse official CAP JSON or text bulletins

export function cpcbCategory(aqiNum?: unknown) {
  if (aqiNum == null || isNaN(Number(aqiNum))) return { label: "No Data", color: "var(--muted)", bg: "transparent" };
  const v = Number(aqiNum);
  if (v <= 50) return { label: "Good", color: "#10b981", bg: "rgba(16,185,129,0.12)" };
  if (v <= 100) return { label: "Satisfactory", color: "#06b6d4", bg: "rgba(6,182,212,0.12)" };
  if (v <= 200) return { label: "Moderate", color: "#eab308", bg: "rgba(234,179,8,0.12)" };
  if (v <= 300) return { label: "Poor", color: "#f97316", bg: "rgba(249,115,22,0.12)" };
  if (v <= 400) return { label: "Very Poor", color: "#ef4444", bg: "rgba(239,68,68,0.12)" };
  return { label: "Severe", color: "#7f1d1d", bg: "rgba(127,29,29,0.15)" };
}


export function pinAqi(dash: DashboardSnapshot): { val: number | null; source: "cpcb" | "open-meteo" } {
  const air = (dash.quality?.air || {}) as Record<string, unknown>;
  const cpcb = (air.cpcb || {}) as Record<string, unknown>;
  const cpcbVal = cpcb.value ?? dash.descriptive.current.aqi;
  if (cpcbVal != null && !isNaN(Number(cpcbVal))) {
    return { val: Number(cpcbVal), source: "cpcb" };
  }
  const series = dash.descriptive.series;
  const hourlyNow = series.aqi_hourly?.[0]?.value;
  const om = dash.descriptive.current.om_us_aqi ?? air.us_aqi ?? hourlyNow;
  if (om != null && !isNaN(Number(om))) {
    return { val: Number(om), source: "open-meteo" };
  }
  return { val: null, source: "open-meteo" };
}


export function seaState(waveHeightM?: unknown) {
  if (waveHeightM == null || isNaN(Number(waveHeightM))) return { label: "Inland / Calm", color: "var(--muted)" };
  const h = Number(waveHeightM);
  if (h < 0.5) return { label: "Calm (Glassy)", color: "#10b981" };
  if (h < 1.25) return { label: "Smooth / Slight", color: "#0ea5e9" };
  if (h < 2.5) return { label: "Moderate", color: "#f59e0b" };
  if (h < 4.0) return { label: "Rough", color: "#f97316" };
  if (h < 6.0) return { label: "Very Rough", color: "#ef4444" };
  return { label: "High / Storm", color: "#dc2626" };
}


export function getPollenAssessment(type: "grass" | "ragweed", value?: unknown): {
  label: string;
  color: string;
  bg: string;
} {
  if (value == null || value === "—" || isNaN(Number(value))) {
    return { label: "Good", color: "#10b981", bg: "rgba(16, 185, 129, 0.12)" };
  }
  const n = Number(value);
  if (type === "grass") {
    if (n < 10) return { label: "Good", color: "#10b981", bg: "rgba(16, 185, 129, 0.12)" };
    if (n < 30) return { label: "Satisfactory", color: "#06b6d4", bg: "rgba(6, 182, 212, 0.12)" };
    if (n < 60) return { label: "Moderate", color: "#f59e0b", bg: "rgba(245, 158, 11, 0.12)" };
    if (n < 120) return { label: "Poor", color: "#f97316", bg: "rgba(249, 115, 22, 0.12)" };
    return { label: "Severe", color: "#ef4444", bg: "rgba(239, 68, 68, 0.12)" };
  } else {
    if (n < 10) return { label: "Good", color: "#10b981", bg: "rgba(16, 185, 129, 0.12)" };
    if (n < 25) return { label: "Satisfactory", color: "#06b6d4", bg: "rgba(6, 182, 212, 0.12)" };
    if (n < 50) return { label: "Moderate", color: "#f59e0b", bg: "rgba(245, 158, 11, 0.12)" };
    if (n < 90) return { label: "Poor", color: "#f97316", bg: "rgba(249, 115, 22, 0.12)" };
    return { label: "Severe", color: "#ef4444", bg: "rgba(239, 68, 68, 0.12)" };
  }
}


export function beaufortScale(speedKmh?: unknown) {
  if (speedKmh == null || isNaN(Number(speedKmh)) || Number(speedKmh) < 1) {
    return { force: 0, label: "Calm", desc: "Smoke rises vertically" };
  }
  const s = Number(speedKmh);
  if (s <= 5) return { force: 1, label: "Light Air", desc: "Smoke drift" };
  if (s <= 11) return { force: 2, label: "Light Breeze", desc: "Leaves rustle" };
  if (s <= 19) return { force: 3, label: "Gentle Breeze", desc: "Twigs move" };
  if (s <= 28) return { force: 4, label: "Moderate Breeze", desc: "Dust raises" };
  if (s <= 38) return { force: 5, label: "Fresh Breeze", desc: "Small trees sway" };
  if (s <= 49) return { force: 6, label: "Strong Breeze", desc: "Large branches move" };
  if (s <= 61) return { force: 7, label: "High Wind", desc: "Trees sway" };
  if (s <= 74) return { force: 8, label: "Gale", desc: "Twigs break" };
  if (s <= 88) return { force: 9, label: "Strong Gale", desc: "Structural damage" };
  if (s <= 102) return { force: 10, label: "Storm", desc: "Trees uprooted" };
  return { force: 11, label: "Violent Storm", desc: "Widespread damage" };
}


export function imdRainfallCategory(precipMm24h?: number | null) {
  if (precipMm24h == null || isNaN(Number(precipMm24h)) || Number(precipMm24h) <= 0.05) {
    return { label: "Dry / Nil", color: "var(--muted)", bg: "transparent", isAlert: false };
  }
  const v = Number(precipMm24h);
  if (v < 2.5) return { label: "Trace / Very Light", color: "#06b6d4", bg: "rgba(6, 182, 212, 0.12)", isAlert: false };
  if (v <= 15.5) return { label: "Light Rain", color: "#0284c7", bg: "rgba(2, 132, 199, 0.12)", isAlert: false };
  if (v <= 64.4) return { label: "Moderate Rain", color: "#3b82f6", bg: "rgba(59, 130, 246, 0.15)", isAlert: false };
  if (v <= 115.5) return { label: "Heavy Rain (IMD)", color: "#f59e0b", bg: "rgba(245, 158, 11, 0.15)", isAlert: true };
  if (v <= 204.4) return { label: "Very Heavy Rain", color: "#ef4444", bg: "rgba(239, 68, 68, 0.15)", isAlert: true };
  return { label: "Extremely Heavy Rain", color: "#dc2626", bg: "rgba(220, 38, 38, 0.2)", isAlert: true };
}

