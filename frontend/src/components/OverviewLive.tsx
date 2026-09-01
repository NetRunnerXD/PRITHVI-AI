"use client";

import { useMemo, useState } from "react";
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
import { dist, rain, rainUnit, speed, temp, tempUnit } from "@/lib/units";
import { Forecast7DayDeck } from "./Forecast7DayDeck";
import { SkyRainHero } from "./SkyRainHero";

function hhmm(t: string) {
  const i = t.indexOf("T");
  return i >= 0 ? t.slice(i + 1, i + 6) : t.slice(-5);
}

function weekday(iso?: string) {
  if (!iso) return "—";
  const d = new Date(iso.includes("T") ? iso : `${iso}T12:00:00`);
  return Number.isNaN(d.getTime()) ? iso.slice(5) : d.toLocaleDateString("en-IN", { weekday: "short" });
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
  return Math.round(hi * 10) / 10;
}

const tip = {
  background: "var(--card)",
  border: "1px solid var(--line)",
  borderRadius: 12,
  fontSize: 12,
  color: "var(--text)",
};

// ── Suggestion severity helper ──────────────────────────────────────
function suggestionLevel(id: string, v: string): "ok" | "watch" | "alert" | "danger" {
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

const suggLevel: Record<string, { bg: string; text: string; dot: string }> = {
  ok: { bg: "bg-[color-mix(in_srgb,var(--accent)_10%,transparent)]", text: "text-neo-accent", dot: "bg-[var(--accent)]" },
  watch: { bg: "bg-[color-mix(in_srgb,var(--warn)_12%,transparent)]", text: "text-neo-warn", dot: "bg-[var(--warn)]" },
  alert: { bg: "bg-[color-mix(in_srgb,var(--accent2)_12%,transparent)]", text: "text-neo-accent2", dot: "bg-[var(--accent2)]" },
  danger: { bg: "bg-[color-mix(in_srgb,var(--danger)_12%,transparent)]", text: "text-neo-danger", dot: "bg-[var(--danger)]" },
};

// Alert severity colors for the sidebar panel
const alertTone: Record<string, string> = {
  extreme: "border-l-[var(--danger)] bg-[color-mix(in_srgb,var(--danger)_7%,transparent)]",
  warning: "border-l-[var(--warn)]   bg-[color-mix(in_srgb,var(--warn)_7%,transparent)]",
  alert: "border-l-[var(--accent2)] bg-[color-mix(in_srgb,var(--accent2)_6%,transparent)]",
  watch: "border-l-[var(--accent)]  bg-[color-mix(in_srgb,var(--accent)_6%,transparent)]",
};
const alertDot: Record<string, string> = {
  extreme: "text-neo-danger",
  warning: "text-neo-warn",
  alert: "text-neo-accent2",
  watch: "text-neo-accent",
};

function openAlert(w: { url?: string | null; href_kind?: string | null; lat?: number | null; lon?: number | null; kind?: string | null }, onNavigateData?: (sub: string) => void, setTab?: (t: "map" | "analytics" | "model" | "data") => void, setMapFocus?: (c: [number, number]) => void) {
  if (w.url && (w.href_kind === "bulletin" || /^https?:/i.test(w.url))) {
    window.open(w.url, "_blank", "noopener,noreferrer");
    return;
  }
  if (w.lat != null && w.lon != null && setMapFocus && setTab && (w.href_kind === "map" || !w.href_kind)) {
    setMapFocus([Number(w.lat), Number(w.lon)]);
    setTab("map");
    return;
  }
  if (w.href_kind === "nowcast") {
    setTab?.("analytics");
    return;
  }
  if (w.href_kind === "predicted") {
    setTab?.("model");
    return;
  }
  if (w.href_kind === "map") {
    setTab?.("map");
    return;
  }
  onNavigateData?.(w.kind === "aqi" ? "environment" : w.kind === "seismic" || w.kind === "tsunami" ? "seismology" : "risks");
}

export function OverviewLive({ dash, locale, onNavigateData }: { dash: DashboardSnapshot; locale: Locale; onNavigateData?: (subTab: string) => void }) {
  const t = COPY[locale];
  const units = useApp((s) => s.settings.units);
  const setTab = useApp((s) => s.setTab);
  const applySuggestion = useApp((s) => s.applySuggestion);
  const live = dash.live;
  const sky = live?.sky || {};
  const wind = live?.wind || {};
  const rose = wind.rose || [];
  const cur = dash.descriptive.current;
  const series = dash.descriptive.series;

  const todayRain =
    dash.predictive.outlook_days?.[0]?.precip_mm ??
    series.precip_daily?.[0]?.value ??
    sky.precip_1h_mm ??
    null;
  const feels = feelsLikeC(sky.temp_c ?? cur.temp_c, sky.humidity_pct ?? cur.humidity_pct);

  const hourly = (series.temp_hourly || []).slice(0, 18).map((p, i) => ({
    t: hhmm(p.t),
    temp: p.value,
    rain: series.precip_hourly?.[i]?.value ?? 0,
    wind: series.wind_hourly?.[i]?.value ?? 0,
  }));
  const allAlerts = (() => {
    const raw = dash.prescriptive.warnings || [];
    const seen = new Set<string>();
    const out: typeof raw = [];

    for (const w of raw) {
      const lowTitle = (w.title || "").toLowerCase().trim();
      const lowBody = (w.body || "").toLowerCase().trim();
      const combined = `${lowTitle} ${lowBody}`;

      // Filter out negative non-threat bulletins
      if (w.hazard === "tsunami" && /no threat|does not exist|all clear|nil/.test(combined)) continue;
      if (w.hazard === "seismic" && /no damage|no threat|all clear/.test(combined)) continue;
      if (!["extreme", "warning"].includes(w.severity)) continue;

      // Normalize key for deduplication
      const normTitle = lowTitle.replace(/[^a-z0-9]/g, "");
      const normBody = lowBody.slice(0, 40).replace(/[^a-z0-9]/g, "");
      const key = `${w.hazard || "gen"}_${normTitle}_${normBody}`;

      if (seen.has(key) || seen.has(normTitle)) continue;
      seen.add(key);
      seen.add(normTitle);

      // Clean up body so it doesn't just duplicate the title verbatim
      let cleanBody = (w.body || "").trim();
      if (cleanBody.toLowerCase() === lowTitle || cleanBody.length < 3) {
        cleanBody = "";
      }

      out.push({
        ...w,
        body: cleanBody,
      });
    }

    return out.slice(0, 24);
  })();

  return (
    <div className="space-y-3">
      {/* ── Top Unified Grid: Left (Sky on top + Rain & Wind side-by-side) & Right (Extended Alert & Risk Panel) ── */}
      <div className="grid gap-3 grid-cols-1 lg:grid-cols-12 items-stretch">
        {/* Left Column: Sky on top, followed by Rain & Wind side-by-side */}
        <div className="w-full lg:col-span-7 xl:col-span-8 flex flex-col gap-3">
          <SkyRainHero dash={dash} locale={locale} onNavigateData={onNavigateData} />

          <div className="grid gap-3 grid-cols-1 sm:grid-cols-2">
            <RainfallSection
              dash={dash}
              locale={locale}
              units={units}
              onNavigateData={onNavigateData}
              className="w-full flex flex-col justify-between select-none min-h-[240px]"
            />

            <WindSection
              dash={dash}
              locale={locale}
              units={units}
              onNavigateData={onNavigateData}
              className="w-full flex flex-col justify-between select-none min-h-[240px]"
            />
          </div>
        </div>

        {/* Right Column: Alert & Risk Panel (Responsive height & smooth scrolling) */}
        <div className="w-full lg:col-span-5 xl:col-span-4 flex flex-col justify-start">
          <RiskAlertPanel
            dash={dash}
            locale={locale}
            onNavigateData={onNavigateData}
            allAlerts={allAlerts}
            className="w-full h-[360px] sm:h-[400px] lg:h-[460px] max-h-[460px]"
          />
        </div>
      </div>

      {/* ── Row 2: Environmental & Geo-Hazard Cards (Air, Land, Marine | Cyclone, Earthquake/Tsunami, Nowcasting) ── */}
      <HomeHazardStrip dash={dash} locale={locale} units={units} onNavigateData={onNavigateData} />

      {/* ── Row 3: 7-Day Interactive Forecast & Chrono-Deck (At Bottom) ── */}
      <Forecast7DayDeck dash={dash} locale={locale} />
    </div>
  );
}

function RiskAlertPanel({
  dash,
  locale,
  onNavigateData,
  allAlerts,
  className,
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  onNavigateData?: (subTab: string) => void;
  allAlerts: any[];
  className?: string;
}) {
  const t = COPY[locale];
  const setTab = useApp((s) => s.setTab);
  const applySuggestion = useApp((s) => s.applySuggestion);
  const [panelTab, setPanelTab] = useState<"alerts" | "risks">("alerts");
  const risks = useMemo(() => {
    return [...(dash.risks || [])].sort((a, b) => (b.score_pct ?? 0) - (a.score_pct ?? 0));
  }, [dash.risks]);

  return (
    <aside className={`neo flex flex-col overflow-hidden select-none ${className || "h-[460px] max-h-[460px]"}`}>
      {/* Header with Segmented Navigation */}
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-[var(--line)] px-3 py-2">
        <div className="flex items-center gap-1.5">
          <span className="live-dot" aria-hidden />
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">
            {panelTab === "alerts" ? t.alertsPanel || "Alerts" : "Risk Index"}
          </p>
        </div>

        <div className="inline-flex rounded-xl bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] p-0.5 border border-[var(--line)] shadow-inner">
          <button
            type="button"
            onClick={() => setPanelTab("alerts")}
            className={`rounded-lg px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all flex items-center gap-1 ${
              panelTab === "alerts"
                ? "bg-neo-accent text-white shadow-sm"
                : "text-neo-muted hover:text-neo-text"
            }`}
          >
            <span>Alerts</span>
            {allAlerts.length > 0 && (
              <span className="rounded-full bg-neo-danger text-white px-1.5 py-0 text-[8px] font-extrabold leading-none">
                {allAlerts.length}
              </span>
            )}
          </button>
          <button
            type="button"
            onClick={() => setPanelTab("risks")}
            className={`rounded-lg px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${
              panelTab === "risks"
                ? "bg-neo-accent text-white shadow-sm"
                : "text-neo-muted hover:text-neo-text"
            }`}
          >
            Risks ({risks.length})
          </button>
        </div>
      </div>

      {/* Content Area */}
      <div className="min-h-0 flex-1 overflow-y-auto p-2.5 space-y-2">
        {panelTab === "alerts" ? (
          allAlerts.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full min-h-[140px] text-center p-3">
              <div className="h-8 w-8 rounded-full bg-[color-mix(in_srgb,var(--accent)_12%,transparent)] flex items-center justify-center text-neo-accent mb-2">
                ✓
              </div>
              <p className="text-xs font-bold text-neo-text">{t.allClear || "No urgent bulletin"}</p>
              <p className="text-[10px] text-neo-muted mt-0.5 max-w-[200px] leading-relaxed">
                Quiet watches for flood, air, marine, seismic & tsunami stay active below.
              </p>
            </div>
          ) : (
            allAlerts.map((w) => (
              <button
                key={w.id}
                type="button"
                className={`w-full rounded-xl border-l-[3px] px-2.5 py-2 text-left transition-colors hover:brightness-110 ${
                  alertTone[w.severity] ?? "border-l-[var(--line)]"
                }`}
                onClick={() =>
                  openAlert(w, onNavigateData, setTab, (c) => applySuggestion({ center: c, tab: "map", zoom: 7 }))
                }
              >
                <div className="flex items-center gap-2">
                  <p className={`text-[9px] font-bold uppercase tracking-widest ${alertDot[w.severity] ?? "text-neo-muted"}`}>
                    {w.severity}
                  </p>
                  {w.scope === "india" ? (
                    <span className="chip ml-auto text-[9px] px-1.5 py-0">India</span>
                  ) : (
                    <span className="chip ml-auto text-[9px] px-1.5 py-0 capitalize">
                      {w.kind || (w.hazard === "seismic" ? "Earthquake" : w.hazard === "air" ? "Air Quality" : w.hazard)}
                    </span>
                  )}
                </div>
                <p className="mt-0.5 text-xs font-semibold leading-snug">{w.title}</p>
                {w.body ? (
                  <p className="mt-0.5 line-clamp-2 text-[10px] leading-snug text-neo-muted">{w.body}</p>
                ) : null}
                <p className="mt-0.5 text-[9px] uppercase tracking-wide text-neo-muted">
                  {w.source}
                  {w.url ? " · bulletin" : ""}
                </p>
              </button>
            ))
          )
        ) : (
          <div className="space-y-2">
            {risks.length === 0 ? (
              <p className="text-center text-xs text-neo-muted py-6">No risk factors evaluated.</p>
            ) : (
              risks.map((r) => {
                const isHigh = r.severity === "danger" || r.severity === "alert" || r.score_pct >= 50;
                return (
                  <div
                    key={r.id}
                    className="neo-in p-2.5 rounded-xl cursor-pointer hover:border-neo-accent transition-all"
                    onClick={() => onNavigateData?.("risks")}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-bold text-neo-text">{r.label}</span>
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono text-xs font-black text-neo-accent">{r.score_pct}%</span>
                        <span
                          className={`chip text-[8px] font-extrabold uppercase px-1.5 py-0 ${
                            isHigh
                              ? "bg-[color-mix(in_srgb,var(--danger)_15%,transparent)] text-neo-danger"
                              : "bg-[color-mix(in_srgb,var(--accent)_10%,transparent)] text-neo-accent"
                          }`}
                        >
                          {r.severity}
                        </span>
                      </div>
                    </div>
                    {/* Progress bar */}
                    <div className="mt-1.5 h-1.5 w-full rounded-full bg-[var(--line)] overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${Math.min(100, Math.max(5, r.score_pct))}%`,
                          backgroundColor: isHigh ? "var(--danger)" : "var(--accent)",
                        }}
                      />
                    </div>
                    {r.factors?.[0] && (
                      <p className="mt-1 text-[9px] text-neo-muted truncate">
                        Primary driver: <span className="font-medium text-neo-text">{r.factors[0].label}</span> ({r.factors[0].contribution_pct}%)
                      </p>
                    )}
                  </div>
                );
              })
            )}
            <button
              type="button"
              onClick={() => onNavigateData?.("risks")}
              className="w-full text-center text-[10px] font-bold text-neo-accent hover:underline py-1"
            >
              View Full Risk Matrix & Insights →
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}

function AlertStat({ label, value }: { label: string; value: string }) {
  const displayNull = useApp((s) => s.settings.displayNullValues);
  if (!displayNull && (value == null || value === "—" || value === "" || value === "undefined" || value === "null")) {
    return null;
  }
  return (
    <div className="neo-in rounded-xl px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-widest text-neo-muted">{label}</p>
      <p className="mt-0.5 truncate font-mono text-xs font-semibold">{value}</p>
    </div>
  );
}

function aqiCategory(aqiNum?: unknown) {
  if (aqiNum == null || isNaN(Number(aqiNum))) return { label: "No Data", color: "var(--muted)", bg: "transparent" };
  const v = Number(aqiNum);
  if (v <= 50) return { label: "Good", color: "#10b981", bg: "rgba(16,185,129,0.12)" };
  if (v <= 100) return { label: "Moderate", color: "#eab308", bg: "rgba(234,179,8,0.12)" };
  if (v <= 200) return { label: "Poor", color: "#f97316", bg: "rgba(249,115,22,0.12)" };
  if (v <= 300) return { label: "Very Poor", color: "#ef4444", bg: "rgba(239,68,68,0.12)" };
  return { label: "Severe", color: "#7f1d1d", bg: "rgba(127,29,29,0.15)" };
}

function seaState(waveHeightM?: unknown) {
  if (waveHeightM == null || isNaN(Number(waveHeightM))) return { label: "Inland / Calm", color: "var(--muted)" };
  const h = Number(waveHeightM);
  if (h < 0.5) return { label: "Calm (Glassy)", color: "#10b981" };
  if (h < 1.25) return { label: "Smooth / Slight", color: "#0ea5e9" };
  if (h < 2.5) return { label: "Moderate", color: "#f59e0b" };
  if (h < 4.0) return { label: "Rough", color: "#f97316" };
  if (h < 6.0) return { label: "Very Rough", color: "#ef4444" };
  return { label: "High / Storm", color: "#dc2626" };
}

function AirCard({
  dash,
  locale,
  onNavigateData,
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  onNavigateData?: (subTab: string) => void;
}) {
  const displayNull = useApp((s) => s.settings.displayNullValues);
  const [tab, setTab] = useState<"live" | "gases" | "pollen" | "trend">("live");
  const q = dash.quality || {};
  const air = (q.air || {}) as Record<string, unknown>;
  const cpcb = (air.cpcb || {}) as Record<string, unknown>;
  const pollen = (air.pollen || {}) as Record<string, unknown>;
  const series = dash.descriptive.series;

  const aqiVal = cpcb.value ?? dash.descriptive.current.aqi ?? air.us_aqi;
  const aqiInfo = aqiCategory(aqiVal);

  const aqi24h = (series.aqi_hourly || []).slice(0, 24).map((p) => ({
    t: hhmm(p.t),
    v: p.value,
  }));

  const rawParticulates = [
    { k: "PM2.5", v: air.pm2_5, max: 60, color: "#f97316" },
    { k: "PM10", v: air.pm10, max: 100, color: "#eab308" },
    { k: "Dust", v: air.dust, max: 80, color: "#a1887f" },
  ];
  const particulates = displayNull ? rawParticulates : rawParticulates.filter((p) => p.v != null && !isNaN(Number(p.v)));

  const rawGases = [
    { k: "NO₂", v: air.no2, unit: "µg/m³" },
    { k: "SO₂", v: air.so2, unit: "µg/m³" },
    { k: "O₃", v: air.o3, unit: "µg/m³" },
    { k: "CO", v: air.co, unit: "µg/m³" },
    { k: "NH₃", v: air.nh3, unit: "µg/m³" },
    { k: "CO₂", v: air.co2, unit: "ppm" },
  ];
  const gases = displayNull ? rawGases : rawGases.filter((g) => g.v != null && !isNaN(Number(g.v)));

  const rawPollen = [
    { k: "Grass Pollen", v: pollen.grass, icon: "🌾" },
    { k: "Ragweed", v: pollen.ragweed, icon: "🌿" },
    { k: "Birch", v: pollen.birch, icon: "🌳" },
    { k: "Olive / Alder", v: pollen.olive ?? pollen.alder, icon: "🍃" },
  ];
  const pollenList = displayNull ? rawPollen : rawPollen.filter((p) => p.v != null && String(p.v).trim() !== "" && String(p.v) !== "—");

  return (
    <section className="neo p-4 flex flex-col justify-between select-none min-h-[220px]">
      <div className="flex items-center justify-between gap-2 flex-wrap mb-2">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">AIR QUALITY</p>
        <div className="inline-flex rounded-xl bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] p-0.5 border border-[var(--line)] shadow-inner">
          {(["live", "gases", "pollen", "trend"] as const).map((id) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`rounded-lg px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${
                tab === id ? "bg-neo-accent text-white shadow-sm" : "text-neo-muted hover:text-neo-text"
              }`}
            >
              {id === "live" ? "Live" : id === "gases" ? "Gases" : id === "pollen" ? "Pollen" : "24h"}
            </button>
          ))}
        </div>
      </div>

      <div className="min-h-[160px] flex flex-col justify-between">
        {tab === "live" && (
          <div key="air-live" className="fade-in-scale space-y-2">
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="text-[9px] uppercase tracking-widest text-neo-muted font-bold">AQI Index</p>
                <div className="flex items-baseline gap-2 mt-0.5">
                  <span className="font-mono text-2xl font-black text-neo-accent leading-none">
                    {aqiVal != null ? String(aqiVal) : "—"}
                  </span>
                  <span
                    className="chip text-[9px] font-bold uppercase px-2 py-0.5"
                    style={{ color: aqiInfo.color, backgroundColor: aqiInfo.bg }}
                  >
                    {String(cpcb.category ?? aqiInfo.label)}
                  </span>
                </div>
              </div>
              {(displayNull || air.uv_index != null) && (
                <div className="text-right">
                  <span className="text-[9px] uppercase tracking-wider text-neo-muted font-bold block">UV Index</span>
                  <span className="font-mono text-sm font-extrabold text-amber-500">
                    {air.uv_index != null ? `${air.uv_index}` : "—"}
                  </span>
                </div>
              )}
            </div>

            <div className="space-y-1.5 pt-1 border-t border-[color-mix(in_srgb,var(--line)_50%,transparent)]">
              {particulates.map((p) => {
                const val = Number(p.v ?? 0);
                const pct = Math.min(100, Math.round((val / p.max) * 100));
                return (
                  <div key={p.k} className="flex items-center justify-between gap-2 text-[10px]">
                    <span className="font-bold text-neo-muted w-10 shrink-0">{p.k}</span>
                    <div className="flex-1 h-1.5 rounded-full bg-[var(--line)] overflow-hidden">
                      <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, backgroundColor: p.color }} />
                    </div>
                    <span className="font-mono font-bold text-neo-text min-w-[3rem] text-right">
                      {p.v != null ? `${p.v}` : "—"}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {tab === "gases" && (
          <div key="air-gases" className="fade-in-scale grid grid-cols-3 gap-1.5">
            {gases.length > 0 ? (
              gases.map((g) => (
                <div key={g.k} className="neo-in p-1.5 rounded-xl text-center">
                  <span className="text-[9px] uppercase tracking-wider text-neo-muted font-bold block">{g.k}</span>
                  <span className="font-mono text-xs font-black text-neo-accent mt-0.5 block truncate">
                    {g.v != null ? `${g.v}` : "—"}
                  </span>
                  <span className="text-[8px] text-neo-muted block">{g.unit}</span>
                </div>
              ))
            ) : (
              <p className="col-span-3 text-center text-xs text-neo-muted py-6">No gas sensor data available.</p>
            )}
          </div>
        )}

        {tab === "pollen" && (
          <div key="air-pollen" className="fade-in-scale space-y-1.5">
            <div className="flex items-center justify-between text-[10px] text-neo-muted font-semibold pb-1 border-b border-[color-mix(in_srgb,var(--line)_50%,transparent)]">
              <span>Allergen Species</span>
              <span>Count (grains/m³)</span>
            </div>
            {pollenList.length > 0 ? (
              pollenList.map((p) => (
                <div key={p.k} className="neo-in px-2 py-1 rounded-xl flex items-center justify-between text-[10px]">
                  <span className="flex items-center gap-1.5 font-medium text-neo-text">
                    <span>{p.icon}</span>
                    <span>{p.k}</span>
                  </span>
                  <span className="font-mono font-bold text-neo-accent">
                    {p.v != null ? `${p.v}` : "Low / Quiet"}
                  </span>
                </div>
              ))
            ) : (
              <p className="text-center text-xs text-neo-muted py-6">No pollen counts available.</p>
            )}
          </div>
        )}

        {tab === "trend" && (
          <div key="air-trend" className="fade-in-scale space-y-1">
            <div className="flex items-center justify-between text-[10px]">
              <span className="text-neo-muted font-semibold">24-Hour AQI Trend</span>
              <span className="font-mono font-bold text-neo-accent">{aqiVal != null ? `Now: ${aqiVal}` : ""}</span>
            </div>
            <div className="h-28">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={aqi24h}>
                  <defs>
                    <linearGradient id="aqiGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--accent2)" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="var(--accent2)" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="var(--line)" vertical={false} strokeDasharray="3 3" />
                  <XAxis dataKey="t" stroke="var(--muted)" fontSize={8} interval={4} />
                  <YAxis stroke="var(--muted)" fontSize={8} width={24} />
                  <Tooltip contentStyle={tip} />
                  <Area type="monotone" dataKey="v" stroke="var(--accent2)" strokeWidth={2} fill="url(#aqiGrad)" name="AQI" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function LandWeatherCard({
  dash,
  locale,
  units,
  onNavigateData,
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  units: "metric" | "imperial";
  onNavigateData?: (subTab: string) => void;
}) {
  const displayNull = useApp((s) => s.settings.displayNullValues);
  const t = COPY[locale];
  const [tab, setTab] = useState<"soil" | "thermal" | "trend">("soil");
  const q = dash.quality || {};
  const climate = (q.climate || {}) as Record<string, unknown>;
  const series = dash.descriptive.series;

  const rawSoilMoistureDepths = [
    { depth: "0–1 cm", name: "Surface", val: Number(climate.soil_m_0_1 ?? dash.descriptive.current.soil_moisture_m3m3 ?? 0), raw: climate.soil_m_0_1 ?? dash.descriptive.current.soil_moisture_m3m3, color: "#10b981" },
    { depth: "1–3 cm", name: "Topsoil", val: Number(climate.soil_m_1_3 ?? 0), raw: climate.soil_m_1_3, color: "#14b8a6" },
    { depth: "3–9 cm", name: "Root Shallow", val: Number(climate.soil_m_3_9 ?? 0), raw: climate.soil_m_3_9, color: "#0ea5e9" },
    { depth: "9–27 cm", name: "Root Deep", val: Number(climate.soil_m_9_27 ?? 0), raw: climate.soil_m_9_27, color: "#6366f1" },
    { depth: "27–81 cm", name: "Subsoil", val: Number(climate.soil_m_27_81 ?? 0), raw: climate.soil_m_27_81, color: "#8b5cf6" },
  ];
  const soilMoistureDepths = displayNull ? rawSoilMoistureDepths : rawSoilMoistureDepths.filter((s) => s.raw != null && !isNaN(Number(s.raw)));

  const rawSoilTempDepths = [
    { depth: "0 cm", val: climate.soil_t_0 },
    { depth: "6 cm", val: climate.soil_t_6 },
    { depth: "18 cm", val: climate.soil_t_18 },
    { depth: "54 cm", val: climate.soil_t_54 },
  ];
  const soilTempDepths = displayNull ? rawSoilTempDepths : rawSoilTempDepths.filter((st) => st.val != null && !isNaN(Number(st.val)));

  const soil24h = (series.soil_hourly || []).slice(0, 24).map((p) => ({
    t: hhmm(p.t),
    v: p.value,
  }));

  return (
    <section className="neo p-4 flex flex-col justify-between select-none min-h-[220px]">
      <div className="flex items-center justify-between gap-2 flex-wrap mb-2">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.landWeather}</p>
        <div className="inline-flex rounded-xl bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] p-0.5 border border-[var(--line)] shadow-inner">
          {(["soil", "thermal", "trend"] as const).map((id) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`rounded-lg px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${
                tab === id ? "bg-neo-accent text-white shadow-sm" : "text-neo-muted hover:text-neo-text"
              }`}
            >
              {id === "soil" ? "Soil Moisture" : id === "thermal" ? "Thermal & ET" : "24h"}
            </button>
          ))}
        </div>
      </div>

      <div className="min-h-[160px] flex flex-col justify-between">
        {tab === "soil" && (
          <div key="land-soil" className="fade-in-scale space-y-1.5">
            <div className="flex items-center justify-between text-[10px] text-neo-muted font-semibold pb-1 border-b border-[color-mix(in_srgb,var(--line)_50%,transparent)]">
              <span>Depth Stratum</span>
              <span>Moisture (m³/m³)</span>
            </div>
            <div className="space-y-1">
              {soilMoistureDepths.map((s) => {
                const pct = Math.min(100, Math.round((s.val / 0.5) * 100));
                return (
                  <div key={s.depth} className="neo-in px-2 py-1 rounded-xl flex items-center justify-between gap-2 text-[10px]">
                    <div className="min-w-0 flex items-center gap-1.5">
                      <span className="chip px-1.5 py-0 text-[8px] font-bold uppercase shrink-0" style={{ color: s.color }}>
                        {s.depth}
                      </span>
                      <span className="text-[10px] font-medium text-neo-muted truncate hidden sm:inline">{s.name}</span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <div className="w-12 sm:w-16 h-1.5 rounded-full bg-[var(--line)] overflow-hidden">
                        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, backgroundColor: s.color }} />
                      </div>
                      <span className="font-mono text-xs font-bold text-neo-text min-w-[3rem] text-right">
                        {s.raw != null && !isNaN(Number(s.raw)) ? `${Number(s.raw).toFixed(3)}` : "—"}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {tab === "thermal" && (
          <div key="land-thermal" className="fade-in-scale space-y-2">
            <div className="grid grid-cols-4 gap-1">
              {soilTempDepths.map((st) => (
                <div key={st.depth} className="neo-in p-1.5 rounded-xl text-center">
                  <span className="text-[8px] uppercase tracking-wider text-neo-muted font-bold block">{st.depth}</span>
                  <span className="font-mono text-xs font-black text-neo-accent mt-0.5 block">
                    {st.val != null ? temp(Number(st.val), units) : "—"}
                  </span>
                  <span className="text-[8px] text-neo-muted block">Soil Temp</span>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-3 gap-1.5 pt-1 border-t border-[color-mix(in_srgb,var(--line)_50%,transparent)]">
              {(displayNull || climate.et0_today != null) && (
                <div className="neo-in p-1.5 rounded-xl text-center">
                  <span className="text-[8px] uppercase tracking-wider text-neo-muted font-bold block">Ref ET₀</span>
                  <span className="font-mono text-xs font-bold text-emerald-600 dark:text-emerald-400">
                    {climate.et0_today != null ? `${climate.et0_today} mm` : "—"}
                  </span>
                </div>
              )}
              {(displayNull || climate.vpd_now != null) && (
                <div className="neo-in p-1.5 rounded-xl text-center">
                  <span className="text-[8px] uppercase tracking-wider text-neo-muted font-bold block">VPD Deficit</span>
                  <span className="font-mono text-xs font-bold text-neo-text">
                    {climate.vpd_now != null ? `${climate.vpd_now} kPa` : "—"}
                  </span>
                </div>
              )}
              {(displayNull || climate.dew_point_c != null) && (
                <div className="neo-in p-1.5 rounded-xl text-center">
                  <span className="text-[8px] uppercase tracking-wider text-neo-muted font-bold block">Dew Point</span>
                  <span className="font-mono text-xs font-bold text-neo-accent">
                    {climate.dew_point_c != null ? temp(Number(climate.dew_point_c), units) : "—"}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {tab === "trend" && (
          <div key="land-trend" className="fade-in-scale space-y-1">
            <div className="flex items-center justify-between text-[10px]">
              <span className="text-neo-muted font-semibold">24-Hour Soil Moisture Profile</span>
              <span className="font-mono font-bold text-neo-accent">
                {climate.soil_m_0_1 != null ? `${climate.soil_m_0_1} m³/m³` : ""}
              </span>
            </div>
            <div className="h-28">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={soil24h}>
                  <defs>
                    <linearGradient id="soilGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#8d6e63" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#8d6e63" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="var(--line)" vertical={false} strokeDasharray="3 3" />
                  <XAxis dataKey="t" stroke="var(--muted)" fontSize={8} interval={4} />
                  <YAxis stroke="var(--muted)" fontSize={8} width={28} />
                  <Tooltip contentStyle={tip} />
                  <Area type="monotone" dataKey="v" stroke="#8d6e63" strokeWidth={2} fill="url(#soilGrad)" name="Soil Moisture" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function MarineWeatherCard({
  dash,
  locale,
  units,
  onNavigateData,
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  units: "metric" | "imperial";
  onNavigateData?: (subTab: string) => void;
}) {
  const displayNull = useApp((s) => s.settings.displayNullValues);
  const t = COPY[locale];
  const [tab, setTab] = useState<"waves" | "ocean" | "hydro">("waves");
  const q = dash.quality || {};
  const marine = (q.marine || {}) as Record<string, unknown>;
  const flood = (q.flood || {}) as Record<string, unknown>;
  const series = dash.descriptive.series;
  const live = dash.live;

  const waveM = marine.wave_height_m != null ? Number(marine.wave_height_m) : null;
  const state = seaState(waveM);

  const discharge7d = (live?.flood?.discharge || dash.predictive.river_discharge || []).map((v, i) => ({
    t: `d+${i}`,
    v,
  }));

  return (
    <section className="neo p-4 flex flex-col justify-between select-none min-h-[220px]">
      <div className="flex items-center justify-between gap-2 flex-wrap mb-2">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.marineWeather}</p>
        <div className="inline-flex rounded-xl bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] p-0.5 border border-[var(--line)] shadow-inner">
          {(["waves", "ocean", "hydro"] as const).map((id) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`rounded-lg px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${
                tab === id ? "bg-neo-accent text-white shadow-sm" : "text-neo-muted hover:text-neo-text"
              }`}
            >
              {id === "waves" ? "Waves & Swell" : id === "ocean" ? "Ocean & SST" : "Hydrology"}
            </button>
          ))}
        </div>
      </div>

      <div className="min-h-[160px] flex flex-col justify-between">
        {tab === "waves" && (
          <div key="marine-waves" className="fade-in-scale space-y-2">
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="text-[9px] uppercase tracking-widest text-neo-muted font-bold">Sig. Wave Height</p>
                <div className="flex items-baseline gap-2 mt-0.5">
                  <span className="font-mono text-2xl font-black text-neo-rain leading-none">
                    {waveM != null ? `${waveM.toFixed(2)} m` : "—"}
                  </span>
                  <span
                    className="chip text-[9px] font-bold uppercase px-2 py-0.5"
                    style={{ color: state.color }}
                  >
                    {state.label}
                  </span>
                </div>
              </div>
              {(displayNull || marine.wave_period_s != null) && (
                <div className="text-right">
                  <span className="text-[9px] uppercase tracking-wider text-neo-muted font-bold block">Wave Period</span>
                  <span className="font-mono text-sm font-extrabold text-neo-text">
                    {marine.wave_period_s != null ? `${marine.wave_period_s} s` : "—"}
                  </span>
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 gap-1.5 pt-1 border-t border-[color-mix(in_srgb,var(--line)_50%,transparent)] text-[10px]">
              {(displayNull || marine.swell_height_m != null) && (
                <div className="neo-in p-1.5 rounded-xl">
                  <span className="text-[8px] uppercase tracking-wider text-neo-muted font-bold block">Primary Swell</span>
                  <span className="font-mono font-extrabold text-sky-600 dark:text-sky-400 block mt-0.5">
                    {marine.swell_height_m != null ? `${marine.swell_height_m} m` : "—"}
                    {marine.swell_dir_deg != null && <span className="ml-1 text-[9px] text-neo-muted">({String(marine.swell_dir_deg)}°)</span>}
                  </span>
                </div>
              )}
              {(displayNull || marine.wind_wave_height_m != null) && (
                <div className="neo-in p-1.5 rounded-xl">
                  <span className="text-[8px] uppercase tracking-wider text-neo-muted font-bold block">Wind Wave</span>
                  <span className="font-mono font-extrabold text-neo-text block mt-0.5">
                    {marine.wind_wave_height_m != null ? `${marine.wind_wave_height_m} m` : "—"}
                    {marine.wind_wave_dir_deg != null && <span className="ml-1 text-[9px] text-neo-muted">({String(marine.wind_wave_dir_deg)}°)</span>}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {tab === "ocean" && (
          <div key="marine-ocean" className="fade-in-scale space-y-2">
            <div className="grid grid-cols-3 gap-1.5">
              {(displayNull || marine.sst_c != null) && (
                <div className="neo-in p-2 rounded-xl text-center">
                  <span className="text-[8px] uppercase tracking-wider text-neo-muted font-bold block">Sea Temp (SST)</span>
                  <span className="font-mono text-base font-black text-cyan-600 dark:text-cyan-400 mt-0.5 block">
                    {marine.sst_c != null ? temp(Number(marine.sst_c), units) : "—"}
                  </span>
                </div>
              )}
              {(displayNull || marine.ocean_current_ms != null) && (
                <div className="neo-in p-2 rounded-xl text-center">
                  <span className="text-[8px] uppercase tracking-wider text-neo-muted font-bold block">Ocean Current</span>
                  <span className="font-mono text-base font-black text-neo-accent mt-0.5 block">
                    {marine.ocean_current_ms != null ? `${marine.ocean_current_ms} m/s` : "—"}
                  </span>
                </div>
              )}
              {(displayNull || marine.sea_level_m != null) && (
                <div className="neo-in p-2 rounded-xl text-center">
                  <span className="text-[8px] uppercase tracking-wider text-neo-muted font-bold block">Sea Level</span>
                  <span className="font-mono text-base font-black text-neo-text mt-0.5 block">
                    {marine.sea_level_m != null ? `${marine.sea_level_m} m` : "—"}
                  </span>
                </div>
              )}
            </div>
            {marine.ocean_current_dir != null && (
              <p className="text-[9px] text-neo-muted text-center pt-1">
                Current Heading: {String(marine.ocean_current_dir)}° · Open-Meteo Marine
              </p>
            )}
          </div>
        )}

        {tab === "hydro" && (
          <div key="marine-hydro" className="fade-in-scale space-y-1">
            <div className="flex items-center justify-between text-[10px]">
              <span className="text-neo-muted font-semibold">River Discharge Trend (GloFAS)</span>
              <span className="chip px-1.5 py-0 text-[8px] font-bold uppercase text-neo-rain">
                {String(flood.trend ?? dash.predictive.flood_discharge_trend ?? "Normal")}
              </span>
            </div>
            <div className="h-28">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={discharge7d}>
                  <CartesianGrid stroke="var(--line)" vertical={false} strokeDasharray="3 3" />
                  <XAxis dataKey="t" stroke="var(--muted)" fontSize={8} />
                  <YAxis stroke="var(--muted)" fontSize={8} width={24} />
                  <Tooltip contentStyle={tip} />
                  <Bar dataKey="v" fill="var(--flood)" radius={[3, 3, 0, 0]} name="Discharge (m³/s)" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function CycloneRadarScope({ active }: { active: boolean }) {
  return (
    <svg viewBox="0 0 100 100" className="h-16 w-16 shrink-0 sm:h-20 sm:w-20">
      <defs>
        <radialGradient id="radarGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={active ? "var(--danger)" : "var(--accent)"} stopOpacity={active ? 0.35 : 0.15} />
          <stop offset="100%" stopColor={active ? "var(--danger)" : "var(--accent)"} stopOpacity={0} />
        </radialGradient>
      </defs>
      <circle cx="50" cy="50" r="46" fill="var(--bg)" stroke="var(--line)" />
      <circle cx="50" cy="50" r="46" fill="url(#radarGlow)" />
      <circle cx="50" cy="50" r="32" fill="none" stroke="var(--line)" strokeDasharray="2 3" opacity={0.6} />
      <circle cx="50" cy="50" r="18" fill="none" stroke="var(--line)" strokeDasharray="2 3" opacity={0.4} />
      <line x1="50" y1="4" x2="50" y2="96" stroke="var(--line)" opacity={0.4} />
      <line x1="4" y1="50" x2="96" y2="50" stroke="var(--line)" opacity={0.4} />
      {active ? (
        <g className="animate-spin" style={{ transformOrigin: "50px 50px", animationDuration: "3s" }}>
          <path
            d="M 50 50 A 24 24 0 0 1 70 30"
            fill="none"
            stroke="var(--danger)"
            strokeWidth="2.5"
            strokeLinecap="round"
          />
          <path
            d="M 50 50 A 24 24 0 0 1 30 70"
            fill="none"
            stroke="var(--warn)"
            strokeWidth="2.5"
            strokeLinecap="round"
          />
          <circle cx="50" cy="50" r="4" fill="var(--danger)" />
        </g>
      ) : (
        <g className="animate-spin" style={{ transformOrigin: "50px 50px", animationDuration: "8s" }}>
          <line x1="50" y1="50" x2="86" y2="24" stroke="var(--accent)" strokeWidth="1.5" opacity={0.7} strokeLinecap="round" />
          <circle cx="50" cy="50" r="3" fill="var(--accent)" />
        </g>
      )}
    </svg>
  );
}

function SeismicOscilloscope({ active }: { active: boolean }) {
  return (
    <svg viewBox="0 0 120 60" className="h-14 w-24 shrink-0 sm:h-16 sm:w-28">
      <defs>
        <linearGradient id="seismicGrad" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor={active ? "var(--danger)" : "var(--accent)"} stopOpacity={0.2} />
          <stop offset="50%" stopColor={active ? "var(--danger)" : "var(--accent)"} stopOpacity={1} />
          <stop offset="100%" stopColor={active ? "var(--danger)" : "var(--accent)"} stopOpacity={0.2} />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="116" height="56" rx="8" fill="var(--bg)" stroke="var(--line)" />
      <line x1="6" y1="30" x2="114" y2="30" stroke="var(--line)" strokeDasharray="2 3" opacity={0.5} />
      {active ? (
        <path
          d="M 6 30 L 25 30 L 32 12 L 40 48 L 48 8 L 56 52 L 64 16 L 72 42 L 80 24 L 88 34 L 96 30 L 114 30"
          fill="none"
          stroke="var(--danger)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ) : (
        <path
          d="M 6 30 L 35 30 L 42 27 L 48 33 L 55 28 L 62 32 L 68 29 L 75 31 L 82 30 L 114 30"
          fill="none"
          stroke="var(--accent)"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity={0.8}
        />
      )}
    </svg>
  );
}

function TropicalCycloneCard({
  dash,
  locale,
  units,
  onNavigateData,
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  units: "metric" | "imperial";
  onNavigateData?: (subTab: string) => void;
}) {
  const t = COPY[locale];
  const [tab, setTab] = useState<"overview" | "dynamics" | "advisory">("overview");

  // Cyclone alerts detection
  const cycloneWarnings = (dash.prescriptive.warnings || []).filter(
    (w) =>
      w.hazard === "cyclone" ||
      w.kind === "cyclone" ||
      /cyclone|depression|deep depression|landfall/i.test(w.title || "") ||
      /cyclone|depression|landfall/i.test(w.body || "")
  );
  const gdacsCyclone = (dash.quality?.gdacs || []).find((g: any) => g.event_type === "TC");
  const cycloneRisk = (dash.risks || []).find((r) => r.id === "cyclone");
  const activeAlert = cycloneWarnings[0] || (gdacsCyclone ? {
    title: String(gdacsCyclone.title || "GDACS TC Event"),
    body: String(gdacsCyclone.body || ""),
    severity: String(gdacsCyclone.alert_level || "").toLowerCase() === "red" ? "extreme" : String(gdacsCyclone.alert_level || "").toLowerCase() === "orange" ? "warning" : "alert",
    source: "GDACS",
    distance_km: null,
  } : null);

  const hasCycloneAlert =
    cycloneWarnings.length > 0 ||
    !!gdacsCyclone ||
    (cycloneRisk != null &&
      (cycloneRisk.severity === "alert" ||
        cycloneRisk.severity === "danger" ||
        cycloneRisk.severity === "warning" ||
        cycloneRisk.score_pct >= 45));

  const stormName = activeAlert?.title || (hasCycloneAlert ? "Active Cyclone Alert" : "—");
  const intensityCategory = hasCycloneAlert
    ? (activeAlert?.title && /super/i.test(activeAlert.title)
      ? "Super Cyclonic Storm"
      : activeAlert?.title && /extremely severe/i.test(activeAlert.title)
      ? "Extremely Severe CS"
      : activeAlert?.title && /very severe/i.test(activeAlert.title)
      ? "Very Severe CS"
      : activeAlert?.title && /severe/i.test(activeAlert.title)
      ? "Severe Cyclonic Storm"
      : activeAlert?.title && /deep depression/i.test(activeAlert.title)
      ? "Deep Depression"
      : activeAlert?.title && /depression/i.test(activeAlert.title)
      ? "Depression"
      : "Cyclonic Storm / Alert")
    : "—";

  const maxWind = hasCycloneAlert
    ? (activeAlert && (activeAlert as any).wind_kmh ? `${(activeAlert as any).wind_kmh} km/h` : "65–90 km/h")
    : "—";
  const centralPressure = hasCycloneAlert
    ? (activeAlert && (activeAlert as any).pressure_hpa ? `${(activeAlert as any).pressure_hpa} hPa` : "988–994 hPa")
    : "—";
  const distanceKm = hasCycloneAlert && activeAlert?.distance_km != null
    ? `${Math.round(activeAlert.distance_km)} km`
    : "—";

  return (
    <section className="neo p-4 flex flex-col justify-between select-none min-h-[240px]">
      <div className="flex items-center justify-between gap-2 flex-wrap mb-2">
        <div className="flex items-center gap-1.5">
          <span className="text-base">🌀</span>
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">
            {t.tropicalCyclones || "TROPICAL CYCLONES"}
          </p>
        </div>
        <div className="inline-flex rounded-xl bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] p-0.5 border border-[var(--line)] shadow-inner">
          {(["overview", "dynamics", "advisory"] as const).map((id) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`rounded-lg px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${
                tab === id ? "bg-neo-accent text-white shadow-sm" : "text-neo-muted hover:text-neo-text"
              }`}
            >
              {id === "overview" ? "Overview" : id === "dynamics" ? "Dynamics" : "Advisory"}
            </button>
          ))}
        </div>
      </div>

      <div className="min-h-[165px] flex flex-col justify-between">
        {tab === "overview" && (
          <div key="cyclone-overview" className="fade-in-scale space-y-2.5">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="text-[9px] uppercase tracking-widest text-neo-muted font-bold">Basin Alert Status</p>
                  <span
                    className={`chip text-[8px] font-extrabold uppercase px-2 py-0.5 ${
                      hasCycloneAlert
                        ? "bg-[color-mix(in_srgb,var(--danger)_15%,transparent)] text-neo-danger border-neo-danger animate-pulse"
                        : "bg-[color-mix(in_srgb,var(--accent)_10%,transparent)] text-neo-accent"
                    }`}
                  >
                    {hasCycloneAlert ? "Active Cyclone Watch" : "Quiet / Normal"}
                  </span>
                </div>
                <p className="mt-1 text-xs font-bold text-neo-text truncate">
                  {hasCycloneAlert ? stormName : "No active tropical storm or depression bulletin"}
                </p>
              </div>
              <CycloneRadarScope active={hasCycloneAlert} />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 pt-1 border-t border-[color-mix(in_srgb,var(--line)_50%,transparent)]">
              <div className="neo-in p-1.5 rounded-xl text-center">
                <span className="text-[8px] uppercase tracking-wider text-neo-muted font-bold block">Category</span>
                <span className="font-mono text-xs font-bold text-neo-accent mt-0.5 block truncate">
                  {intensityCategory}
                </span>
              </div>
              <div className="neo-in p-1.5 rounded-xl text-center">
                <span className="text-[8px] uppercase tracking-wider text-neo-muted font-bold block">Max Winds</span>
                <span className="font-mono text-xs font-bold text-neo-warn mt-0.5 block truncate">
                  {maxWind}
                </span>
              </div>
              <div className="neo-in p-1.5 rounded-xl text-center">
                <span className="text-[8px] uppercase tracking-wider text-neo-muted font-bold block">Pressure</span>
                <span className="font-mono text-xs font-bold text-neo-text mt-0.5 block truncate">
                  {centralPressure}
                </span>
              </div>
              <div className="neo-in p-1.5 rounded-xl text-center">
                <span className="text-[8px] uppercase tracking-wider text-neo-muted font-bold block">Distance</span>
                <span className="font-mono text-xs font-bold text-neo-rain mt-0.5 block truncate">
                  {distanceKm}
                </span>
              </div>
            </div>
          </div>
        )}

        {tab === "dynamics" && (
          <div key="cyclone-dynamics" className="fade-in-scale space-y-2">
            <div className="flex items-center justify-between text-[10px] text-neo-muted font-semibold pb-1 border-b border-[color-mix(in_srgb,var(--line)_50%,transparent)]">
              <span>IMD Intensity Classification</span>
              <span>Sustained Winds</span>
            </div>
            <div className="space-y-1">
              {[
                { name: "Super Cyclonic Storm (SuCS)", speed: "≥ 222 km/h", color: "#7f1d1d", active: hasCycloneAlert && /super/i.test(stormName) },
                { name: "Extremely Severe CS (ESCS)", speed: "167–221 km/h", color: "#dc2626", active: hasCycloneAlert && /extremely/i.test(stormName) },
                { name: "Very Severe CS (VSCS)", speed: "118–166 km/h", color: "#ea580c", active: hasCycloneAlert && /very severe/i.test(stormName) },
                { name: "Severe Cyclonic Storm (SCS)", speed: "89–117 km/h", color: "#d97706", active: hasCycloneAlert && /severe/i.test(stormName) },
                { name: "Cyclonic Storm (CS)", speed: "62–88 km/h", color: "#0284c7", active: hasCycloneAlert && /cyclone/i.test(stormName) },
                { name: "Depression / Deep Depression", speed: "31–61 km/h", color: "#10b981", active: hasCycloneAlert && /depression/i.test(stormName) },
              ].map((tier) => (
                <div
                  key={tier.name}
                  className={`neo-in px-2 py-1 rounded-xl flex items-center justify-between gap-2 text-[10px] ${
                    tier.active ? "ring-1 ring-[var(--danger)] bg-[color-mix(in_srgb,var(--danger)_8%,transparent)]" : ""
                  }`}
                >
                  <span className="font-medium text-neo-text truncate">{tier.name}</span>
                  <span className="font-mono font-bold text-neo-muted shrink-0" style={{ color: tier.active ? tier.color : undefined }}>
                    {tier.speed}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === "advisory" && (
          <div key="cyclone-advisory" className="fade-in-scale space-y-2">
            <div className="flex items-center justify-between text-[10px]">
              <span className="text-neo-muted font-bold uppercase tracking-wider">IMD RSMC & Disaster Management Protocol</span>
              <span className="chip text-[9px] font-bold uppercase text-neo-accent">
                {hasCycloneAlert ? "Emergency Action" : "Standard Readiness"}
              </span>
            </div>
            {hasCycloneAlert && activeAlert?.body ? (
              <div className="neo-in p-2.5 rounded-xl text-xs space-y-1">
                <p className="font-semibold text-neo-danger leading-snug">{activeAlert.title}</p>
                <p className="text-[11px] text-neo-text leading-relaxed line-clamp-3">{activeAlert.body}</p>
                <p className="text-[9px] uppercase text-neo-muted pt-0.5">Source: {activeAlert.source || "IMD / GDACS"}</p>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-1.5 text-[10px]">
                <div className="neo-in p-2 rounded-xl">
                  <span className="font-bold text-neo-text block">Maritime Protocol</span>
                  <span className="text-neo-muted block mt-0.5 text-[9px] leading-snug">
                    Standard operations in coastal waters. Monitor IMD coastal bulletins for sudden cyclogenesis.
                  </span>
                </div>
                <div className="neo-in p-2 rounded-xl">
                  <span className="font-bold text-neo-text block">Inland Preparedness</span>
                  <span className="text-neo-muted block mt-0.5 text-[9px] leading-snug">
                    Maintain drainage clearances and secure loose structures during pre-monsoon and post-monsoon transition.
                  </span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

function EarthquakeTsunamiCard({
  dash,
  locale,
  units,
  onNavigateData,
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  units: "metric" | "imperial";
  onNavigateData?: (subTab: string) => void;
}) {
  const t = COPY[locale];
  const [tab, setTab] = useState<"seismic" | "tsunami" | "safety">("seismic");

  // Seismic & Tsunami alerts detection
  const seismicWarnings = (dash.prescriptive.warnings || []).filter(
    (w) =>
      w.hazard === "seismic" ||
      w.hazard === "tsunami" ||
      w.kind === "seismic" ||
      w.kind === "tsunami" ||
      /earthquake|quake|tsunami|itews/i.test(w.title || "") ||
      /earthquake|quake|tsunami|itews/i.test(w.body || "")
  );
  const tsuThreat =
    (dash.live?.tsunami || []).some((t: any) => t.threat || /warning|alert|watch/i.test(t.title || "")) ||
    (dash.quality?.tsunami || []).some((t: any) => t.threat || /warning|alert|watch/i.test(t.title || "")) ||
    dash.predictions?.hazards?.tsunami?.threat === true;

  const quakes = ((dash.live?.quakes || dash.quality?.seismic || []) as any[]).filter(
    (q) => q && (q.mag != null || q.place)
  );
  const nearestQuake = quakes[0];
  const hasQuakeAlert =
    (nearestQuake &&
      ((nearestQuake.mag != null && Number(nearestQuake.mag) >= 5.0) ||
        (nearestQuake.mag != null &&
          Number(nearestQuake.mag) >= 4.0 &&
          (nearestQuake.distance_km ?? 9999) < 250) ||
        nearestQuake.tsunami_flag)) ||
    false;

  const hasEarthquakeTsunamiAlert = seismicWarnings.length > 0 || tsuThreat || hasQuakeAlert;

  const magVal = hasEarthquakeTsunamiAlert && nearestQuake?.mag != null
    ? `M ${Number(nearestQuake.mag).toFixed(1)}`
    : "—";
  const depthVal = hasEarthquakeTsunamiAlert && nearestQuake?.depth_km != null
    ? `${nearestQuake.depth_km} km`
    : "—";
  const distVal = hasEarthquakeTsunamiAlert && nearestQuake?.distance_km != null
    ? `${Math.round(nearestQuake.distance_km)} km`
    : "—";
  const tsunamiWatchStatus = tsuThreat
    ? "ITEWS Watch / Threat Issued"
    : hasEarthquakeTsunamiAlert && nearestQuake?.tsunami_flag
    ? "USGS Tsunami Flagged"
    : "—";

  return (
    <section className="neo p-4 flex flex-col justify-between select-none min-h-[240px]">
      <div className="flex items-center justify-between gap-2 flex-wrap mb-2">
        <div className="flex items-center gap-1.5">
          <span className="text-base">⚡</span>
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">
            {t.earthquakeAndTsunami || "EARTHQUAKE & TSUNAMI"}
          </p>
        </div>
        <div className="inline-flex rounded-xl bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] p-0.5 border border-[var(--line)] shadow-inner">
          {(["seismic", "tsunami", "safety"] as const).map((id) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`rounded-lg px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${
                tab === id ? "bg-neo-accent text-white shadow-sm" : "text-neo-muted hover:text-neo-text"
              }`}
            >
              {id === "seismic" ? "Seismic" : id === "tsunami" ? "Tsunami" : "Safety"}
            </button>
          ))}
        </div>
      </div>

      <div className="min-h-[165px] flex flex-col justify-between">
        {tab === "seismic" && (
          <div key="quake-seismic" className="fade-in-scale space-y-2.5">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="text-[9px] uppercase tracking-widest text-neo-muted font-bold">Seismic Monitor</p>
                  <span
                    className={`chip text-[8px] font-extrabold uppercase px-2 py-0.5 ${
                      hasEarthquakeTsunamiAlert
                        ? "bg-[color-mix(in_srgb,var(--danger)_15%,transparent)] text-neo-danger border-neo-danger animate-pulse"
                        : "bg-[color-mix(in_srgb,var(--accent)_10%,transparent)] text-neo-accent"
                    }`}
                  >
                    {hasEarthquakeTsunamiAlert ? "Seismic Alert Active" : "Stable / Nominal"}
                  </span>
                </div>
                <p className="mt-1 text-xs font-bold text-neo-text truncate">
                  {hasEarthquakeTsunamiAlert && nearestQuake?.place
                    ? nearestQuake.place
                    : "No significant earthquake alert detected for this region"}
                </p>
              </div>
              <SeismicOscilloscope active={hasEarthquakeTsunamiAlert} />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 pt-1 border-t border-[color-mix(in_srgb,var(--line)_50%,transparent)]">
              <div className="neo-in p-1.5 rounded-xl text-center">
                <span className="text-[8px] uppercase tracking-wider text-neo-muted font-bold block">Magnitude</span>
                <span className="font-mono text-xs font-bold text-neo-accent mt-0.5 block truncate">
                  {magVal}
                </span>
              </div>
              <div className="neo-in p-1.5 rounded-xl text-center">
                <span className="text-[8px] uppercase tracking-wider text-neo-muted font-bold block">Focal Depth</span>
                <span className="font-mono text-xs font-bold text-neo-text mt-0.5 block truncate">
                  {depthVal}
                </span>
              </div>
              <div className="neo-in p-1.5 rounded-xl text-center">
                <span className="text-[8px] uppercase tracking-wider text-neo-muted font-bold block">Epicenter</span>
                <span className="font-mono text-xs font-bold text-neo-rain mt-0.5 block truncate">
                  {distVal}
                </span>
              </div>
              <div className="neo-in p-1.5 rounded-xl text-center">
                <span className="text-[8px] uppercase tracking-wider text-neo-muted font-bold block">Tsunami Watch</span>
                <span className="font-mono text-xs font-bold text-neo-warn mt-0.5 block truncate">
                  {tsunamiWatchStatus}
                </span>
              </div>
            </div>
          </div>
        )}

        {tab === "tsunami" && (
          <div key="quake-tsunami" className="fade-in-scale space-y-2">
            <div className="flex items-center justify-between text-[10px]">
              <span className="text-neo-muted font-bold uppercase tracking-wider">INCOIS ITEWS Tsunami Watch</span>
              <span
                className={`chip text-[9px] font-bold uppercase ${
                  tsuThreat ? "text-neo-danger bg-[color-mix(in_srgb,var(--danger)_15%,transparent)]" : "text-neo-accent"
                }`}
              >
                {tsuThreat ? "Threat Active" : "No Threat to Coast"}
              </span>
            </div>
            {tsuThreat ? (
              <div className="neo-in p-2.5 rounded-xl text-xs space-y-1">
                <p className="font-bold text-neo-danger">INCOIS Tsunami Early Warning Bulletin</p>
                <p className="text-[11px] text-neo-text leading-relaxed">
                  {(dash.live?.tsunami?.[0] as any)?.body || (dash.quality?.tsunami?.[0] as any)?.body || "Tsunami watch active for coastal areas. Avoid beaches and low-lying coastal zones."}
                </p>
              </div>
            ) : (
              <div className="neo-in p-2.5 rounded-xl text-xs flex items-center justify-between">
                <div>
                  <p className="font-semibold text-neo-text">Indian Ocean Tsunami Early Warning System</p>
                  <p className="text-[10px] text-neo-muted mt-0.5">
                    INCOIS ITEWS DSS past-90-days catalog and real-time RSS feeds report normal baseline with zero coastal threat.
                  </p>
                </div>
                <span className="text-2xl ml-2">🌊</span>
              </div>
            )}
            <div className="grid grid-cols-3 gap-1 text-center pt-1 border-t border-[color-mix(in_srgb,var(--line)_50%,transparent)]">
              <div>
                <span className="text-[8px] uppercase tracking-wider text-neo-muted block">Coastal Runup</span>
                <span className="font-mono text-xs font-bold text-neo-text">{tsuThreat ? "Active Evaluation" : "—"}</span>
              </div>
              <div>
                <span className="text-[8px] uppercase tracking-wider text-neo-muted block">Travel Time</span>
                <span className="font-mono text-xs font-bold text-neo-accent">{tsuThreat ? "In Progress" : "—"}</span>
              </div>
              <div>
                <span className="text-[8px] uppercase tracking-wider text-neo-muted block">Sea Level</span>
                <span className="font-mono text-xs font-bold text-neo-rain">
                  {(dash.quality?.marine as any)?.sea_level_m != null ? `${(dash.quality?.marine as any).sea_level_m} m` : "—"}
                </span>
              </div>
            </div>
          </div>
        )}

        {tab === "safety" && (
          <div key="quake-safety" className="fade-in-scale space-y-2">
            <div className="flex items-center justify-between text-[10px]">
              <span className="text-neo-muted font-bold uppercase tracking-wider">NDMA Earthquake & Tsunami Guidelines</span>
              <span className="chip text-[9px] font-bold uppercase text-neo-accent">Emergency Ready</span>
            </div>
            <div className="grid grid-cols-2 gap-1.5 text-[10px]">
              <div className="neo-in p-2 rounded-xl space-y-1">
                <span className="font-bold text-neo-text block">1. Drop, Cover, Hold On</span>
                <span className="text-neo-muted block text-[9px] leading-snug">
                  Get under a sturdy table or desk. Stay away from glass windows and heavy unanchored objects.
                </span>
              </div>
              <div className="neo-in p-2 rounded-xl space-y-1">
                <span className="font-bold text-neo-text block">2. Coastal Tsunami Evacuation</span>
                <span className="text-neo-muted block text-[9px] leading-snug">
                  If you feel severe shaking near the coast, immediately move inland or to higher ground without waiting for official siren.
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function NowcastSection({
  dash,
  locale,
  units,
  className,
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  units: "metric" | "imperial";
  className?: string;
}) {
  const t = COPY[locale];
  const series = dash.descriptive.series;
  const hourly = (series.temp_hourly || []).slice(0, 18).map((p, i) => ({
    t: hhmm(p.t),
    temp: p.value,
    rain: series.precip_hourly?.[i]?.value ?? 0,
    wind: series.wind_hourly?.[i]?.value ?? 0,
  }));
  const sixHour = (dash.predictive.hourly || []).slice(0, 6).map((h) => ({
    t: h.hour || hhmm(h.t),
    rain: h.precip_mm ?? 0,
    temp: h.temp_c ?? 0,
    wind: h.wind_kmh ?? 0,
  }));
  const six = sixHour.length ? sixHour : hourly.slice(0, 6);

  const [next6Mode, setNext6Mode] = useState<"numbers" | "plot">("numbers");
  const [next6Var, setNext6Var] = useState<"rain" | "temp" | "wind">("rain");

  const next6Comparison = useMemo(() => {
    const veraHourly = (dash.predictions?.vera?.hourly || [])
      .filter((r) => (r.lead_h ?? 0) >= 0)
      .slice(0, 6);

    if (veraHourly.length) {
      return veraHourly.map((r, i) => {
        const timeLabel = r.t ? hhmm(r.t) : six[i]?.t || `+${i}h`;
        const rainOm = r.om ?? (six[i]?.rain ?? 0);
        const rainBlend = r.moe ?? (six[i]?.rain ?? 0);
        const tempOm = r.om_temp_c ?? (six[i]?.temp ?? 0);
        const tempBlend = r.moe_temp_c ?? (six[i]?.temp ?? 0);
        const windOm = r.om_wind_kmh ?? (six[i]?.wind ?? 0);
        const windBlend = r.moe_wind_kmh ?? (six[i]?.wind ?? 0);

        return {
          t: timeLabel,
          rain_om: rainOm != null ? (units === "imperial" ? Math.round((rainOm / 25.4) * 100) / 100 : rainOm) : 0,
          rain_blend: rainBlend != null ? (units === "imperial" ? Math.round((rainBlend / 25.4) * 100) / 100 : rainBlend) : 0,
          temp_om: tempOm != null ? (units === "imperial" ? Math.round((tempOm * 9) / 5 + 32) : tempOm) : 0,
          temp_blend: tempBlend != null ? (units === "imperial" ? Math.round((tempBlend * 9) / 5 + 32) : tempBlend) : 0,
          wind_om: windOm != null ? (units === "imperial" ? Math.round(windOm * 0.621) : windOm) : 0,
          wind_blend: windBlend != null ? (units === "imperial" ? Math.round(windBlend * 0.621) : windBlend) : 0,
        };
      });
    }

    return six.map((h) => ({
      t: h.t,
      rain_om: units === "imperial" ? Math.round(((h.rain || 0) / 25.4) * 100) / 100 : (h.rain || 0),
      rain_blend: units === "imperial" ? Math.round(((h.rain || 0) / 25.4) * 100) / 100 : (h.rain || 0),
      temp_om: units === "imperial" ? Math.round(((h.temp || 0) * 9) / 5 + 32) : (h.temp || 0),
      temp_blend: units === "imperial" ? Math.round(((h.temp || 0) * 9) / 5 + 32) : (h.temp || 0),
      wind_om: units === "imperial" ? Math.round((h.wind || 0) * 0.621) : (h.wind || 0),
      wind_blend: units === "imperial" ? Math.round((h.wind || 0) * 0.621) : (h.wind || 0),
    }));
  }, [dash.predictions?.vera?.hourly, six, units]);

  return (
    <section className={`neo p-4 flex flex-col justify-between select-none min-h-[240px] ${className || ""}`}>
      <div className="flex items-center justify-between gap-2 flex-wrap mb-2">
        <div className="flex items-center gap-1.5">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5 text-neo-accent">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">
            {t.next6h}
          </p>
        </div>
        <div className="inline-flex rounded-xl bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] p-0.5 border border-[var(--line)] shadow-inner">
          <button
            type="button"
            onClick={() => setNext6Mode("numbers")}
            className={`rounded-lg px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${
              next6Mode === "numbers"
                ? "bg-neo-accent text-white shadow-sm"
                : "text-neo-muted hover:text-neo-text"
            }`}
          >
            Slots
          </button>
          <button
            type="button"
            onClick={() => setNext6Mode("plot")}
            className={`rounded-lg px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${
              next6Mode === "plot"
                ? "bg-neo-accent text-white shadow-sm"
                : "text-neo-muted hover:text-neo-text"
            }`}
            title="Open-Meteo vs Blend (MoE) comparison"
          >
            Blend
          </button>
        </div>
      </div>

      <div className="min-h-[160px] flex flex-col justify-between">
        {next6Mode === "numbers" ? (
          <div key="numbers-view" className="fade-in-scale space-y-2">
            {six.length ? (
              <div className="grid grid-cols-3 sm:grid-cols-6 lg:grid-cols-3 xl:grid-cols-6 gap-1">
                {six.map((h) => (
                  <div
                    key={h.t}
                    className="neo-in flex flex-col items-center gap-0.5 rounded-xl py-1 px-1 text-center transition hover:bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] min-w-0"
                  >
                    <p className="text-[9px] font-semibold text-neo-muted truncate w-full">{h.t}</p>
                    <p className="font-mono text-xs font-bold text-neo-accent truncate w-full">{temp(h.temp, units)}</p>
                    <p className="text-[10px] font-mono text-neo-rain truncate w-full">{rain(h.rain, units)}</p>
                    <p className="text-[8px] text-neo-muted truncate w-full">{speed(h.wind, units)}</p>
                  </div>
                ))}
              </div>
            ) : null}
            <div className="h-14 sm:h-16 pt-1">
              {six.length ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={six} margin={{ top: 2, right: 2, left: -20, bottom: 0 }}>
                    <CartesianGrid stroke="var(--line)" vertical={false} strokeDasharray="2 3" />
                    <XAxis dataKey="t" stroke="var(--muted)" fontSize={8} tickLine={false} />
                    <YAxis stroke="var(--muted)" fontSize={8} width={20} />
                    <Tooltip contentStyle={tip} />
                    <Bar
                      dataKey="rain"
                      fill="var(--rain)"
                      radius={[3, 3, 0, 0]}
                      name={`Rain (${rainUnit(units)})`}
                      isAnimationActive={true}
                      animationDuration={300}
                    />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="flex h-full items-center justify-center text-xs text-neo-muted">—</p>
              )}
            </div>
          </div>
        ) : (
          <div key="plot-view" className="fade-in-scale space-y-2">
            <div className="flex items-center justify-between gap-1 flex-wrap">
              <div className="inline-flex rounded-lg bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] p-0.5 border border-[var(--line)] shadow-inner text-[10px]">
                {(["rain", "temp", "wind"] as const).map((k) => (
                  <button
                    key={k}
                    type="button"
                    onClick={() => setNext6Var(k)}
                    className={`rounded px-1.5 py-0.5 text-[9px] font-bold tracking-wide transition-all ${
                      next6Var === k
                        ? "bg-neo-accent text-white shadow-sm"
                        : "text-neo-muted hover:text-neo-text"
                    }`}
                  >
                    {k === "rain" ? "Rain" : k === "temp" ? "Temp" : "Wind"}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-2 text-[10px] font-medium">
                <span className="flex items-center gap-1 text-[#c45c26]">
                  <span className="inline-block h-1.5 w-1.5 rounded-full bg-[#c45c26]" /> OM
                </span>
                <span className="flex items-center gap-1 text-[#8e44ad]">
                  <span className="inline-block h-1.5 w-1.5 rounded-full bg-[#8e44ad]" /> Blend
                </span>
              </div>
            </div>

            <div className="h-24 sm:h-28">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={next6Comparison}>
                  <CartesianGrid stroke="var(--line)" vertical={false} />
                  <XAxis dataKey="t" stroke="var(--muted)" fontSize={8} />
                  <YAxis stroke="var(--muted)" fontSize={8} width={24} />
                  <Tooltip contentStyle={tip} />
                  <Line
                    type="monotone"
                    name="Open-Meteo"
                    dataKey={next6Var === "rain" ? "rain_om" : next6Var === "temp" ? "temp_om" : "wind_om"}
                    stroke="#c45c26"
                    strokeWidth={2}
                    strokeDasharray="4 3"
                    dot={{ r: 2, fill: "#c45c26" }}
                    isAnimationActive={true}
                    animationDuration={300}
                  />
                  <Line
                    type="monotone"
                    name="Blend (MoE)"
                    dataKey={next6Var === "rain" ? "rain_blend" : next6Var === "temp" ? "temp_blend" : "wind_blend"}
                    stroke="#8e44ad"
                    strokeWidth={2}
                    dot={{ r: 2.5, fill: "#8e44ad" }}
                    isAnimationActive={true}
                    animationDuration={300}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function HomeHazardStrip({
  dash,
  locale,
  units,
  onNavigateData,
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  units: "metric" | "imperial";
  onNavigateData?: (subTab: string) => void;
}) {
  return (
    <div className="space-y-3">
      {/* 3 Innovative Environmental & Earth Science Cards */}
      <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
        <AirCard dash={dash} locale={locale} onNavigateData={onNavigateData} />
        <LandWeatherCard dash={dash} locale={locale} units={units} onNavigateData={onNavigateData} />
        <MarineWeatherCard dash={dash} locale={locale} units={units} onNavigateData={onNavigateData} />
      </div>

      {/* 3 Dedicated Geo-Hazard & Disaster Early Warning Cards (Cyclone, Seismic/Tsunami, Nowcasting / Next 6h) */}
      <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
        <TropicalCycloneCard dash={dash} locale={locale} units={units} onNavigateData={onNavigateData} />
        <EarthquakeTsunamiCard dash={dash} locale={locale} units={units} onNavigateData={onNavigateData} />
        <NowcastSection dash={dash} locale={locale} units={units} className="w-full" />
      </div>
    </div>
  );
}

export function OverviewPlots({ dash, locale }: { dash: DashboardSnapshot; locale: Locale }) {
  const t = COPY[locale];
  const units = useApp((s) => s.settings.units);
  const live = dash.live;
  const series = dash.descriptive.series;
  const rainH = (series.precip_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: units === "imperial" ? p.value / 25.4 : p.value }));
  const tempH = (series.temp_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: units === "imperial" ? (p.value * 9) / 5 + 32 : p.value }));
  const wspd = (series.wind_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: units === "imperial" ? p.value * 0.621 : p.value }));
  const aqi = (series.aqi_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: p.value }));
  const aqiHist = (series.aqi_history || []).slice(-24).map((p) => ({ t: hhmm(p.t), v: p.value }));
  const wave = (series.wave_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: units === "imperial" ? p.value * 3.281 : p.value }));
  const discharge = (live?.flood?.discharge || dash.predictive.river_discharge || []).map((v, i) => ({
    t: `d+${i}`,
    v,
  }));
  const rh = (series.rh_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: p.value }));
  const soil = (series.soil_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: p.value }));
  const cloud = (series.cloud_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: p.value }));
  const dust = (series.dust_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: p.value }));
  const sst = (series.sst_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: p.value }));
  const swell = (series.swell_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: units === "imperial" ? p.value * 3.281 : p.value }));
  const rainD = (series.precip_daily || []).slice(0, 7).map((p) => ({ t: (p.t || "").slice(5), v: p.value }));
  const tmax = (series.tmax_daily || []).slice(0, 7).map((p) => ({ t: (p.t || "").slice(5), v: units === "imperial" ? (p.value * 9) / 5 + 32 : p.value }));
  const et0 = (series.et0_daily || []).slice(0, 7).map((p) => ({ t: (p.t || "").slice(5), v: p.value }));
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      <Spark title={`${t.tabForecast} · 24h`} data={rainH} color="var(--rain)" unit={rainUnit(units)} kind="bar" />
      <Spark title="Temperature · 24h" data={tempH} color="var(--gold)" unit={tempUnit(units)} />
      <Spark title={t.windSpeed} data={wspd} color="var(--accent)" unit={units === "imperial" ? "mph" : "km/h"} />
      <Spark title={t.humidity} data={rh} color="var(--accent)" unit="%" />
      <Spark title={t.cloud} data={cloud} color="#7aa2a8" unit="%" />
      <Spark title="SOIL MOISTURE" data={soil} color="#8d6e63" unit="m³/m³" />
      <Spark title={t.discharge} data={discharge} color="var(--flood)" unit="m³/s" />
      <Spark title="AQI" data={aqi} color="var(--accent2)" unit="" />
      <Spark title="PM10" data={(series.pm10_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: p.value }))} color="var(--accent2)" unit="µg/m³" />
      <Spark title="Dust" data={dust} color="#a1887f" unit="µg/m³" />
      <Spark title="UV" data={(series.uv_hourly || []).slice(0, 24).map((p) => ({ t: hhmm(p.t), v: p.value }))} color="var(--gold)" unit="UV" />
      <Spark title={t.waves} data={wave} color="var(--rain)" unit={units === "imperial" ? "ft" : "m"} />
      <Spark title="Swell" data={swell} color="#1565c0" unit={units === "imperial" ? "ft" : "m"} />
      <Spark title="Sea surface" data={sst} color="#00838f" unit={tempUnit(units)} />
      <Spark title="Daily rain" data={rainD} color="var(--rain)" unit={rainUnit(units)} kind="bar" />
      <Spark title="Daily Tmax" data={tmax} color="var(--gold)" unit={tempUnit(units)} />
      <Spark title="EVATRANSPIRATION" data={et0} color="#5d8a66" unit="mm" />
    </div>
  );
}

function Stat({ k, v }: { k: string; v: string }) {
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

function RainOdds({ k, pct, days }: { k: string; pct: number[]; days: string[] }) {
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

function Spark({
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

function beaufortScale(speedKmh?: unknown) {
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

function imdRainfallCategory(precipMm24h?: number | null) {
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

function RainfallSection({
  dash,
  locale,
  units,
  onNavigateData,
  className,
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  units: "metric" | "imperial";
  onNavigateData?: (subTab: string) => void;
  className?: string;
}) {
  const displayNull = useApp((s) => s.settings.displayNullValues);
  const t = COPY[locale];
  const [rainTab, setRainTab] = useState<"live" | "hourly" | "outlook">("live");

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
    <section className={`neo p-4 ${className || "sm:col-span-6 lg:col-span-4 flex flex-col justify-between select-none min-h-[240px]"}`}>
      {/* Header with Segmented Navigation */}
      <div className="flex items-center justify-between gap-2 flex-wrap mb-2">
        <div className="flex items-center gap-1.5">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5 text-neo-rain">
            <path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242" />
            <path d="M16 14v6M8 14v6M12 16v6" />
          </svg>
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">
            {t.rainfall || "Rainfall"}
          </p>
        </div>
        <div className="inline-flex rounded-xl bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] p-0.5 border border-[var(--line)] shadow-inner">
          <button
            type="button"
            onClick={() => setRainTab("live")}
            className={`rounded-lg px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${
              rainTab === "live"
                ? "bg-neo-accent text-white shadow-sm"
                : "text-neo-muted hover:text-neo-text"
            }`}
          >
            Live
          </button>
          <button
            type="button"
            onClick={() => setRainTab("hourly")}
            className={`rounded-lg px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${
              rainTab === "hourly"
                ? "bg-neo-accent text-white shadow-sm"
                : "text-neo-muted hover:text-neo-text"
            }`}
            title="24-hour hyetograph"
          >
            24h
          </button>
          <button
            type="button"
            onClick={() => setRainTab("outlook")}
            className={`rounded-lg px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${
              rainTab === "outlook"
                ? "bg-neo-accent text-white shadow-sm"
                : "text-neo-muted hover:text-neo-text"
            }`}
            title="7-Day precipitation & water budget"
          >
            7-Day
          </button>
        </div>
      </div>

      <div className="min-h-[160px] flex flex-col justify-between">
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
                className={`chip text-[9px] font-bold uppercase px-2 py-0.5 whitespace-nowrap border ${
                  imdCat.isAlert
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
      </div>
    </section>
  );
}

function WindSection({
  dash,
  locale,
  units,
  onNavigateData,
  className,
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  units: "metric" | "imperial";
  onNavigateData?: (subTab: string) => void;
  className?: string;
}) {
  const displayNull = useApp((s) => s.settings.displayNullValues);
  const t = COPY[locale];
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
    <section className={`neo p-4 ${className || "sm:col-span-6 lg:col-span-4 flex flex-col justify-between select-none min-h-[240px]"}`}>
      {/* Header with Segmented Navigation */}
      <div className="flex items-center justify-between gap-2 flex-wrap mb-2">
        <div className="flex items-center gap-1.5">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.windProfile}</p>
        </div>
        <div className="inline-flex rounded-xl bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] p-0.5 border border-[var(--line)] shadow-inner">
          <button
            type="button"
            onClick={() => setWindTab("live")}
            className={`rounded-lg px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${
              windTab === "live"
                ? "bg-neo-accent text-white shadow-sm"
                : "text-neo-muted hover:text-neo-text"
            }`}
          >
            Live
          </button>
          <button
            type="button"
            onClick={() => setWindTab("altitude")}
            className={`rounded-lg px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${
              windTab === "altitude"
                ? "bg-neo-accent text-white shadow-sm"
                : "text-neo-muted hover:text-neo-text"
            }`}
            title="Atmospheric wind profile from 10m to 180m"
          >
            10–180m
          </button>
          <button
            type="button"
            onClick={() => setWindTab("trend")}
            className={`rounded-lg px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${
              windTab === "trend"
                ? "bg-neo-accent text-white shadow-sm"
                : "text-neo-muted hover:text-neo-text"
            }`}
            title="24-hour wind forecast graph"
          >
            24h
          </button>
        </div>
      </div>

      <div className="min-h-[160px] flex flex-col justify-between">
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
                      <span className="text-neo-muted block text-[8px] uppercase tracking-wider font-bold">Gusts</span>
                      <span className="font-mono font-extrabold text-neo-warn">{windGusts != null ? speed(windGusts, units) : "—"}</span>
                    </div>
                  )}
                  {(displayNull || windMax10m != null) && (
                    <div className="neo-in px-2 py-1 rounded-xl">
                      <span className="text-neo-muted block text-[8px] uppercase tracking-wider font-bold">10m Max</span>
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
              <span className="text-neo-muted font-semibold">24-Hour Wind Forecast Curve</span>
              <span className="font-mono font-bold text-neo-accent">{speed(windMax10m ?? speedKmh, units)} peak</span>
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
                <span className="text-[8px] uppercase tracking-wider text-neo-muted block">Mean</span>
                <span className="font-mono text-[11px] font-bold text-neo-text">{windMean10m != null ? speed(windMean10m, units) : "—"}</span>
              </div>
              <div>
                <span className="text-[8px] uppercase tracking-wider text-neo-muted block">Max 10m</span>
                <span className="font-mono text-[11px] font-bold text-neo-accent">{windMax10m != null ? speed(windMax10m, units) : "—"}</span>
              </div>
              <div>
                <span className="text-[8px] uppercase tracking-wider text-neo-muted block">Gusts</span>
                <span className="font-mono text-[11px] font-bold text-neo-warn">{windGusts != null ? speed(windGusts, units) : "—"}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function WindRose({
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
    <svg viewBox="0 0 200 200" className="h-20 w-20 shrink-0 sm:h-24 sm:w-24">
      <circle cx="100" cy="100" r="86" fill="var(--bg)" stroke="var(--line)" />
      <circle cx="100" cy="100" r="58" fill="none" stroke="var(--line)" strokeDasharray="3 4" />
      {["N", "E", "S", "W"].map((lab, i) => {
        const ang = (i * 90 - 90) * (Math.PI / 180);
        const x = 100 + Math.cos(ang) * 74;
        const y = 100 + Math.sin(ang) * 74;
        return (
          <text key={lab} x={x} y={y} textAnchor="middle" dominantBaseline="middle" fontSize="10" fill="var(--muted)">
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
            opacity={b.count ? 0.7 : 0.2}
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
      <circle cx="100" cy="100" r="18" fill="var(--card)" stroke="var(--line)" />
      <text x="100" y="98" textAnchor="middle" fontSize="9" fill="var(--accent)" fontWeight="700">
        {compass}
      </text>
      <text x="100" y="110" textAnchor="middle" fontSize="8" fill="var(--muted)">
        →{flow}
      </text>
    </svg>
  );
}

function SkyGlyph({ kind, day }: { kind: string; day: boolean }) {
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
