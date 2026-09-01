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
  const days = (dash.predictive.outlook_days || []).slice(0, 7);

  const sixHour = (dash.predictive.hourly || []).slice(0, 6).map((h) => ({
    t: h.hour || hhmm(h.t),
    rain: h.precip_mm ?? 0,
    temp: h.temp_c ?? 0,
    wind: h.wind_kmh ?? 0,
  }));
  const sixFromSeries = hourly.slice(0, 6);
  const six = sixHour.length ? sixHour : sixFromSeries;

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
      {/* ── Row 1: Sky and Rainfall — Animated Atmospheric Diorama Deck ── */}
      <SkyRainHero dash={dash} locale={locale} onNavigateData={onNavigateData} />

      {/* ── Row 2: (Wind + Next 6h + 7-day forecast) on left & Alerts on right ── */}
      <div className="grid gap-3 lg:grid-cols-12 items-stretch">
        {/* Left column: Wind + 6h row & 7-day forecast */}
        <div className="space-y-3 lg:col-span-8 flex flex-col justify-between">
          {/* Wind + Next 6h */}
          <div className="grid gap-3 sm:grid-cols-12">
            {/* Innovative Multi-Metric Wind Section */}
            <WindSection
              dash={dash}
              locale={locale}
              units={units}
              onNavigateData={onNavigateData}
            />

            {/* Next 6h */}
            <section
              className="neo p-4 sm:col-span-7 flex flex-col justify-between cursor-pointer hover:ring-2 hover:ring-[var(--accent)] transition-all duration-200 select-none group min-h-[220px]"
              onClick={() => setNext6Mode((m) => (m === "numbers" ? "plot" : "numbers"))}
              title={next6Mode === "numbers" ? "Click to view Open-Meteo vs Blend plot" : "Click to view hourly numbers"}
            >
              <div className="flex items-center justify-between gap-2 mb-2">
                <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.next6h}</p>
              </div>

              <div className="min-h-[160px] flex flex-col justify-between">
                {next6Mode === "numbers" ? (
                  <div key="numbers-view" className="fade-in-scale space-y-2">
                    {six.length ? (
                      <div className="mt-2 grid grid-cols-3 gap-1 sm:grid-cols-6">
                        {six.map((h) => (
                          <div
                            key={h.t}
                            className="neo-in flex flex-col items-center gap-0.5 rounded-xl py-1.5 text-center transition group-hover:bg-[color-mix(in_srgb,var(--bg)_80%,transparent)]"
                          >
                            <p className="text-[9px] font-semibold text-neo-muted">{h.t}</p>
                            <p className="font-mono text-xs font-bold text-neo-accent">{temp(h.temp, units)}</p>
                            <p className="text-[10px] font-mono text-neo-rain">{rain(h.rain, units)}</p>
                            <p className="text-[9px] text-neo-muted">{speed(h.wind, units)}</p>
                          </div>
                        ))}
                      </div>
                    ) : null}
                    <div className="h-16 sm:h-20">
                      {six.length ? (
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={six}>
                            <CartesianGrid stroke="var(--line)" vertical={false} />
                            <XAxis dataKey="t" stroke="var(--muted)" fontSize={8} />
                            <YAxis stroke="var(--muted)" fontSize={8} width={20} />
                            <Tooltip contentStyle={tip} />
                            <Bar
                              dataKey="rain"
                              fill="var(--rain)"
                              radius={[3, 3, 0, 0]}
                              name="Rain"
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
                  <div key="plot-view" className="fade-in-scale space-y-2 mt-1">
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <div
                        className="inline-flex rounded-xl bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] p-0.5 border border-[var(--line)] shadow-inner"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {(["rain", "temp", "wind"] as const).map((k) => (
                          <button
                            key={k}
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setNext6Var(k);
                            }}
                            className={`rounded-lg px-2.5 py-1 text-xs font-semibold tracking-wide transition-all ${
                              next6Var === k
                                ? "bg-neo-accent text-white shadow-sm font-bold"
                                : "text-neo-muted hover:text-neo-text hover:bg-[color-mix(in_srgb,var(--card)_60%,transparent)]"
                            }`}
                          >
                            {k === "rain"
                              ? `Rain (${units === "imperial" ? "in" : "mm"})`
                              : k === "temp"
                              ? `Temp (${units === "imperial" ? "°F" : "°C"})`
                              : `Wind (${units === "imperial" ? "mph" : "km/h"})`}
                          </button>
                        ))}
                      </div>
                      <div className="flex items-center gap-3 text-xs font-medium" onClick={(e) => e.stopPropagation()}>
                        <span className="flex items-center gap-1.5 text-[#c45c26]">
                          <span className="inline-block h-2 w-2 rounded-full bg-[#c45c26]" /> Open-Meteo
                        </span>
                        <span className="flex items-center gap-1.5 text-[#8e44ad]">
                          <span className="inline-block h-2 w-2 rounded-full bg-[#8e44ad]" /> Blend (MoE)
                        </span>
                      </div>
                    </div>

                    <div className="h-24 sm:h-28">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={next6Comparison}>
                          <CartesianGrid stroke="var(--line)" vertical={false} />
                          <XAxis dataKey="t" stroke="var(--muted)" fontSize={9} />
                          <YAxis stroke="var(--muted)" fontSize={9} width={28} />
                          <Tooltip contentStyle={tip} />
                          <Line
                            type="monotone"
                            name="Open-Meteo"
                            dataKey={next6Var === "rain" ? "rain_om" : next6Var === "temp" ? "temp_om" : "wind_om"}
                            stroke="#c45c26"
                            strokeWidth={2}
                            strokeDasharray="4 3"
                            dot={{ r: 2.5, fill: "#c45c26" }}
                            isAnimationActive={true}
                            animationDuration={300}
                          />
                          <Line
                            type="monotone"
                            name="Blend (MoE)"
                            dataKey={next6Var === "rain" ? "rain_blend" : next6Var === "temp" ? "temp_blend" : "wind_blend"}
                            stroke="#8e44ad"
                            strokeWidth={2.5}
                            dot={{ r: 3, fill: "#8e44ad" }}
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
          </div>

          {/* 7-day Interactive Forecast & Floating Chrono-Deck */}
          <Forecast7DayDeck dash={dash} locale={locale} />
        </div>

        {/* Alerts sidebar — increased height by 2 rows */}
        <aside className="neo flex flex-col lg:col-span-4 lg:h-[31.5rem] lg:max-h-[31.5rem] overflow-hidden">
          {/* Header */}
          <div
            className="flex shrink-0 cursor-pointer items-center gap-2 border-b border-[var(--line)] px-3.5 py-2.5 hover:bg-[color-mix(in_srgb,var(--danger)_6%,transparent)]"
            onClick={() => onNavigateData?.("risks")}
          >
            <span className="live-dot" aria-hidden />
            <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">{t.alertsPanel}</p>
            {allAlerts.length > 0 && (
              <span className="ml-auto rounded-full bg-[color-mix(in_srgb,var(--danger)_15%,transparent)] px-2 py-0.5 text-[10px] font-bold text-neo-danger">
                {allAlerts.length}
              </span>
            )}
          </div>
          {/* Scrollable list */}
          <ul className="min-h-0 flex-1 space-y-2 overflow-y-auto p-2.5">
            {allAlerts.length === 0 ? (
              <li className="flex h-full items-center justify-center text-sm text-neo-muted">{t.allClear}</li>
            ) : (
              allAlerts.map((w) => (
                <li key={w.id}>
                  <button
                    type="button"
                    className={`w-full rounded-xl border-l-[3px] px-2.5 py-2 text-left transition-colors hover:brightness-110 ${alertTone[w.severity] ?? "border-l-[var(--line)]"}`}
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
                </li>
              ))
            )}
          </ul>
        </aside>
      </div>

      <HomeHazardStrip dash={dash} locale={locale} units={units} onNavigateData={onNavigateData} />
    </div>
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
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-neo-accent">AIR QUALITY & CAMS</p>
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
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <AirCard dash={dash} locale={locale} onNavigateData={onNavigateData} />
        <LandWeatherCard dash={dash} locale={locale} units={units} onNavigateData={onNavigateData} />
        <MarineWeatherCard dash={dash} locale={locale} units={units} onNavigateData={onNavigateData} />
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

function WindSection({
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
    <section className="neo p-4 sm:col-span-5 flex flex-col justify-between select-none min-h-[220px]">
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
