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
import { dist, localizeDigits, rain, rainUnit, speed, temp, tempUnit } from "@/lib/units";
import { LaymanSummaryBody } from "../LaymanSummaryView";
import {
  getAirLaymanSummary,
  getMarineLaymanSummary,
  getNowcastLaymanSummary,
  getSoilLaymanSummary,
} from "@/lib/laymanSummaries";
import { tWord, translateAqiCategory, translateSeverity } from "./i18n";
import { cpcbCategory, feelsLikeC, hhmm, pinAqi, seaState, getPollenAssessment, tip } from "./helpers";
import { getHazardTheme, IconCyclone, IconSeismic, IconTsunamiWave } from "./icons";

export function AirCard({
  dash,
  locale,
  onNavigateData,
  forceSummary,
  className,
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  onNavigateData?: (subTab: string) => void;
  forceSummary?: boolean;
  className?: string;
}) {
  const displayNull = useApp((s) => s.settings.displayNullValues);
  const [tab, setTab] = useState<"live" | "gases" | "pollen" | "trend">("live");

  const [localSummary, setLocalSummary] = useState<boolean | null>(null);
  useEffect(() => {
    setLocalSummary(null);
  }, [forceSummary]);
  const isSummary = localSummary !== null ? localSummary : Boolean(forceSummary);

  const q = dash.quality || {};
  const air = (q.air || {}) as Record<string, unknown>;
  const cpcb = (air.cpcb || {}) as Record<string, unknown>;
  const pollen = (air.pollen || {}) as Record<string, unknown>;
  const series = dash.descriptive.series;

  const aqiObj = pinAqi(dash);
  const aqiVal = aqiObj.val;
  const aqiInfo = cpcbCategory(aqiVal);
  const cpcbVal = cpcb.value != null ? Number(cpcb.value) : (dash.descriptive.current.aqi != null ? Number(dash.descriptive.current.aqi) : null);
  const cpcbCat = cpcb.category != null ? String(cpcb.category) : (dash.descriptive.current.aqi_category ? String(dash.descriptive.current.aqi_category) : null);
  const cpcbStation = (cpcb.station || dash.descriptive.current.aqi_station) ? String(cpcb.station || dash.descriptive.current.aqi_station) : "";

  const aqi24h = (series.aqi_hourly || []).slice(0, 24).map((p) => ({
    t: hhmm(p.t),
    v: p.value,
  }));
  if (aqi24h.length && aqiVal != null) {
    aqi24h[0] = { ...aqi24h[0], v: aqiVal };
  }

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
    {
      k: "Grass Pollen",
      species: "Poaceae / Gramineae",
      v: pollen.grass,
      type: "grass" as const,
      remark: getPollenAssessment("grass", pollen.grass),
    },
    {
      k: "Ragweed",
      species: "Parthenium / Asteraceae",
      v: pollen.ragweed,
      type: "ragweed" as const,
      remark: getPollenAssessment("ragweed", pollen.ragweed),
    },
  ];
  const pollenList = displayNull ? rawPollen : rawPollen.filter((p) => p.v != null && String(p.v).trim() !== "" && String(p.v) !== "—");
  const t = COPY[locale];

  return (
    <section
      onClick={() => setLocalSummary(!isSummary)}
      className={`neo neo-section-air p-4 flex flex-col justify-start select-none cursor-pointer transition min-h-[220px] hover:border-[color-mix(in_srgb,var(--accent)_35%,var(--line))] ${className || ""}`}
      title="Click card to switch between detailed data and overview"
    >
      <div className="flex shrink-0 items-center justify-between gap-2 flex-wrap mb-2">
        <div className="flex items-center gap-1.5">
          <p className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-700 dark:text-slate-300">{t.airQualityPollen || "AIR QUALITY & POLLEN"}</p>
        </div>
        {!isSummary && (
          <div className="inline-flex rounded-xl bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] p-0.5 border border-[var(--line)] shadow-inner">
            {(["live", "gases", "pollen", "trend"] as const).map((id) => (
              <button
                key={id}
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setTab(id);
                }}
                className={`rounded-lg px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${tab === id ? "bg-neo-accent text-white shadow-sm" : "text-neo-muted hover:text-neo-text"
                  }`}
              >
                {id === "live" ? "AQI" : id === "gases" ? "Gases" : id === "pollen" ? "Pollen" : "24h"}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="w-full">
        {isSummary ? (
          <LaymanSummaryBody summary={getAirLaymanSummary(dash, locale)} />
        ) : (
          <>
            {tab === "live" && (
              <div key="air-live" className="fade-in-scale space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="text-[9px] uppercase tracking-widest text-neo-muted font-bold">
                      {aqiObj.source === "cpcb" ? "CPCB NAQI (data.gov.in)" : "AQI (Open-Meteo)"}
                    </p>
                    <div className="flex items-baseline gap-2 mt-0.5">
                      <span className="font-mono text-2xl font-black text-neo-accent leading-none">
                        {aqiVal != null ? String(aqiVal) : "—"}
                      </span>
                      <span
                        className="chip text-[9px] font-bold uppercase px-2 py-0.5"
                        style={{ color: aqiInfo.color, backgroundColor: aqiInfo.bg }}
                      >
                        {cpcbCat || aqiInfo.label}
                      </span>
                    </div>
                    {cpcbStation ? (
                      <p className="text-[9px] text-neo-muted mt-1">
                        CPCB Station: {cpcbStation}
                      </p>
                    ) : null}
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
              <div key="air-pollen" className="fade-in-scale space-y-2">
                <div className="flex items-center justify-between text-[10px] text-neo-muted font-semibold pb-1 border-b border-[color-mix(in_srgb,var(--line)_50%,transparent)]">
                  <span>Allergen Target</span>
                  <div className="flex items-center gap-4">
                    <span>Concentration</span>
                    <span>Remark</span>
                  </div>
                </div>
                {pollenList.length > 0 ? (
                  pollenList.map((p) => (
                    <div key={p.k} className="neo-in px-2.5 py-1.5 rounded-xl flex items-center justify-between gap-2 text-xs">
                      <div className="min-w-0">
                        <p className="font-bold text-neo-text leading-tight">{p.k}</p>
                        <p className="text-[9px] text-neo-muted truncate">{p.species}</p>
                      </div>
                      <div className="flex items-center gap-2.5 shrink-0">
                        <span className="font-mono text-xs font-bold text-neo-accent">
                          {p.v != null ? `${p.v} gr/m³` : "Nominal"}
                        </span>
                        <span
                          className="chip text-[9px] font-black uppercase px-2 py-0.5 rounded-md"
                          style={{ color: p.remark.color, backgroundColor: p.remark.bg }}
                        >
                          {p.remark.label}
                        </span>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-center text-xs text-neo-muted py-6">No pollen counts available.</p>
                )}
                <p className="text-[8px] text-neo-muted italic pt-0.5">
                  Source: India Aerobiology Climatological Model (Bose Institute / Gangetic surveys scaled with weather washout).
                </p>
              </div>
            )}

            {tab === "trend" && (
              <div key="air-trend" className="fade-in-scale space-y-1">
                <div className="flex items-center justify-between text-[10px]">
                  <span className="text-neo-muted font-semibold">24-Hour AQI Trend</span>
                  <span className="font-mono font-bold text-neo-accent">
                    {aqiVal != null ? `Now: ${aqiVal}${aqiObj.source === "cpcb" ? " (CPCB)" : ""}` : ""}
                  </span>
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
          </>
        )}
      </div>
    </section>
  );
}


export function LandWeatherCard({
  dash,
  locale,
  units,
  onNavigateData,
  forceSummary,
  className,
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  units: "metric" | "imperial";
  onNavigateData?: (subTab: string) => void;
  forceSummary?: boolean;
  className?: string;
}) {
  const displayNull = useApp((s) => s.settings.displayNullValues);
  const t = COPY[locale];
  const [tab, setTab] = useState<"soil" | "thermal" | "trend">("thermal");

  const [localSummary, setLocalSummary] = useState<boolean | null>(null);
  useEffect(() => {
    setLocalSummary(null);
  }, [forceSummary]);
  const isSummary = localSummary !== null ? localSummary : Boolean(forceSummary);

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
    <section
      onClick={() => setLocalSummary(!isSummary)}
      className={`neo neo-section-land p-4 flex flex-col justify-start select-none cursor-pointer transition min-h-[220px] hover:border-[color-mix(in_srgb,var(--accent)_35%,var(--line))] ${className || ""}`}
      title="Click card to switch between detailed data and overview"
    >
      <div className="flex shrink-0 items-center justify-between gap-2 flex-wrap mb-2">
        <div className="flex items-center gap-1.5">
          <p className="text-[11px] font-black uppercase tracking-[0.18em] text-emerald-700 dark:text-emerald-400">{t.landWeather}</p>
        </div>
        {!isSummary && (
          <div className="inline-flex rounded-xl bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] p-0.5 border border-[var(--line)] shadow-inner">
            {(["thermal", "soil", "trend"] as const).map((id) => (
              <button
                key={id}
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setTab(id);
                }}
                className={`rounded-lg px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${tab === id ? "bg-neo-accent text-white shadow-sm" : "text-neo-muted hover:text-neo-text"
                  }`}
              >
                {id === "thermal" ? "Thermal & ET" : id === "soil" ? "Soil Moisture" : "24h"}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="w-full">
        {isSummary ? (
          <LaymanSummaryBody summary={getSoilLaymanSummary(dash, locale)} />
        ) : (
          <>
            {tab === "soil" && (
              <div key="land-soil" className="fade-in-scale space-y-1.5">
                <div className="flex items-center justify-between text-[10px] text-neo-muted font-semibold pb-1 border-b border-[color-mix(in_srgb,var(--line)_50%,transparent)]">
                  <span>Depth Stratum</span>
                  <span>Moisture (m³/m³)</span>
                </div>
                <div className="space-y-1 max-h-[148px] overflow-y-auto modal-scrollbar pr-0.5">
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
                      <span className="text-[8px] uppercase tracking-wider text-neo-muted font-bold block truncate" title="Vapour Pressure Deficit">Vapour Pressure Deficit</span>
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
          </>
        )}
      </div>
    </section>
  );
}


export function MarineWeatherCard({
  dash,
  locale,
  units,
  onNavigateData,
  forceSummary,
  className,
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  units: "metric" | "imperial";
  onNavigateData?: (subTab: string) => void;
  forceSummary?: boolean;
  className?: string;
}) {
  const displayNull = useApp((s) => s.settings.displayNullValues);
  const t = COPY[locale];
  const [tab, setTab] = useState<"waves" | "ocean" | "hydro">("waves");

  const [localSummary, setLocalSummary] = useState<boolean | null>(null);
  useEffect(() => {
    setLocalSummary(null);
  }, [forceSummary]);
  const isSummary = localSummary !== null ? localSummary : Boolean(forceSummary);

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
    <section
      onClick={() => setLocalSummary(!isSummary)}
      className={`neo neo-section-marine p-4 flex flex-col justify-start select-none cursor-pointer transition min-h-[220px] hover:border-[color-mix(in_srgb,var(--accent)_35%,var(--line))] ${className || ""}`}
      title="Click card to switch between detailed data and overview"
    >
      <div className="flex shrink-0 items-center justify-between gap-2 flex-wrap mb-2">
        <div className="flex items-center gap-1.5">
          <p className="text-[11px] font-black uppercase tracking-[0.18em] text-cyan-700 dark:text-cyan-400">{t.marineWeather}</p>
        </div>
        {!isSummary && (
          <div className="inline-flex rounded-xl bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] p-0.5 border border-[var(--line)] shadow-inner">
            {(["waves", "ocean", "hydro"] as const).map((id) => (
              <button
                key={id}
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setTab(id);
                }}
                className={`rounded-lg px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${tab === id ? "bg-neo-accent text-white shadow-sm" : "text-neo-muted hover:text-neo-text"
                  }`}
              >
                {id === "waves" ? "Waves & Swell" : id === "ocean" ? "Ocean & SST" : "Hydrology"}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="w-full">
        {isSummary ? (
          <LaymanSummaryBody summary={getMarineLaymanSummary(dash, locale)} />
        ) : (
          <>
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
          </>
        )}
      </div>
    </section>
  );
}


export function CycloneRadarScope({ active }: { active: boolean }) {
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


export function SeismicOscilloscope({ active }: { active: boolean }) {
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


export function TropicalCycloneCard({
  dash,
  locale,
  units,
  onNavigateData,
  forceSummary,
  className,
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  units: "metric" | "imperial";
  onNavigateData?: (subTab: string) => void;
  forceSummary?: boolean;
  className?: string;
}) {
  const t = COPY[locale];

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

  const [dataTab, setDataTab] = useState<"overview" | "dynamics">("overview");
  const [showAdvisory, setShowAdvisory] = useState<boolean>(false);

  useEffect(() => {
    if (hasCycloneAlert && forceSummary != null) {
      setShowAdvisory(Boolean(forceSummary));
    }
  }, [forceSummary, hasCycloneAlert]);

  const isAdvisoryActive = hasCycloneAlert && showAdvisory;
  const currentTab = isAdvisoryActive ? "advisory" : dataTab;

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

  // When no activity is detected: keep data section only (Overview & Dynamics)
  const availableTabs = hasCycloneAlert
    ? (["overview", "dynamics", "advisory"] as const)
    : (["overview", "dynamics"] as const);

  return (
    <section
      onClick={() => {
        if (hasCycloneAlert) {
          setShowAdvisory(!isAdvisoryActive);
        }
      }}
      className={`neo neo-section-cyclone p-4 flex flex-col justify-start select-none transition min-h-[220px] ${hasCycloneAlert
          ? "cursor-pointer hover:border-[color-mix(in_srgb,var(--accent)_35%,var(--line))]"
          : "cursor-default"
        } ${className || ""}`}
      title={hasCycloneAlert ? "Click card to switch between data and emergency advisory" : undefined}
    >
      <div className="flex shrink-0 items-center justify-between gap-2 flex-wrap mb-2">
        <div className="flex items-center gap-1.5">
          <div className="flex h-5 w-5 items-center justify-center rounded-md bg-rose-500/15 text-rose-600 dark:text-rose-400">
            <IconCyclone className="w-3.5 h-3.5" />
          </div>
          <p className="text-[11px] font-black uppercase tracking-[0.18em] text-rose-700 dark:text-rose-400">
            {t.tropicalCyclones || "TROPICAL CYCLONES"}
          </p>
        </div>
        <div className="inline-flex rounded-xl bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] p-0.5 border border-[var(--line)] shadow-inner">
          {availableTabs.map((id) => (
            <button
              key={id}
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                if (id === "advisory") {
                  setShowAdvisory(true);
                } else {
                  setShowAdvisory(false);
                  setDataTab(id);
                }
              }}
              className={`rounded-lg px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${currentTab === id
                  ? "bg-neo-accent text-white shadow-sm"
                  : id === "advisory"
                    ? "text-rose-600 dark:text-rose-400 font-extrabold animate-pulse"
                    : "text-neo-muted hover:text-neo-text"
                }`}
            >
              {id === "overview" ? "Overview" : id === "dynamics" ? "Dynamics" : "Advisory"}
            </button>
          ))}
        </div>
      </div>

      <div className="w-full min-h-[160px] flex flex-col justify-between">
        {currentTab === "overview" && (
          <div key="cyclone-overview" className="fade-in-scale space-y-2.5">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="text-[9px] uppercase tracking-widest text-neo-muted font-bold">Basin Alert Status</p>
                  <span
                    className={`chip text-[8px] font-extrabold uppercase px-2 py-0.5 ${hasCycloneAlert
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

        {currentTab === "dynamics" && (
          <div key="cyclone-dynamics" className="fade-in-scale space-y-2">
            <div className="flex items-center justify-between text-[10px] text-neo-muted font-semibold pb-1 border-b border-[color-mix(in_srgb,var(--line)_50%,transparent)]">
              <span>IMD Intensity Classification</span>
              <span>Sustained Winds</span>
            </div>
            <div className="space-y-1 max-h-[148px] overflow-y-auto modal-scrollbar pr-0.5">
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
                  className={`neo-in px-2 py-1 rounded-xl flex items-center justify-between gap-2 text-[10px] ${tier.active ? "ring-1 ring-[var(--danger)] bg-[color-mix(in_srgb,var(--danger)_8%,transparent)]" : ""
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

        {currentTab === "advisory" && (
          <div key="cyclone-advisory" className="fade-in-scale h-full flex flex-col justify-between space-y-2">
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


export function EarthquakeTsunamiCard({
  dash,
  locale,
  units,
  onNavigateData,
  forceSummary,
  className,
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  units: "metric" | "imperial";
  onNavigateData?: (subTab: string) => void;
  forceSummary?: boolean;
  className?: string;
}) {
  const t = COPY[locale];

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

  const [dataTab, setDataTab] = useState<"seismic" | "tsunami">("seismic");
  const [showAdvisory, setShowAdvisory] = useState<boolean>(false);

  useEffect(() => {
    if (hasEarthquakeTsunamiAlert && forceSummary != null) {
      setShowAdvisory(Boolean(forceSummary));
    }
  }, [forceSummary, hasEarthquakeTsunamiAlert]);

  const isAdvisoryActive = hasEarthquakeTsunamiAlert && showAdvisory;
  const currentTab = isAdvisoryActive ? "safety" : dataTab;

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

  // When no activity is detected: keep data section only (Seismic & Tsunami)
  const availableTabs = hasEarthquakeTsunamiAlert
    ? (["seismic", "tsunami", "safety"] as const)
    : (["seismic", "tsunami"] as const);

  return (
    <section
      onClick={() => {
        if (hasEarthquakeTsunamiAlert) {
          setShowAdvisory(!isAdvisoryActive);
        }
      }}
      className={`neo neo-section-seismic p-4 flex flex-col justify-start select-none transition min-h-[220px] ${hasEarthquakeTsunamiAlert
          ? "cursor-pointer hover:border-[color-mix(in_srgb,var(--accent)_35%,var(--line))]"
          : "cursor-default"
        } ${className || ""}`}
      title={hasEarthquakeTsunamiAlert ? "Click card to switch between data and emergency advisory" : undefined}
    >
      <div className="flex shrink-0 items-center justify-between gap-2 flex-wrap mb-2">
        <div className="flex items-center gap-1.5">
          <div className="flex h-5 w-5 items-center justify-center rounded-md bg-amber-500/15 text-amber-600 dark:text-amber-400">
            <IconSeismic className="w-3.5 h-3.5" />
          </div>
          <p className="text-[11px] font-black uppercase tracking-[0.18em] text-amber-700 dark:text-amber-400">
            {t.earthquakeAndTsunami || "EARTHQUAKE & TSUNAMI"}
          </p>
        </div>
        <div className="inline-flex rounded-xl bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] p-0.5 border border-[var(--line)] shadow-inner">
          {availableTabs.map((id) => (
            <button
              key={id}
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                if (id === "safety") {
                  setShowAdvisory(true);
                } else {
                  setShowAdvisory(false);
                  setDataTab(id);
                }
              }}
              className={`rounded-lg px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${currentTab === id
                  ? "bg-neo-accent text-white shadow-sm"
                  : id === "safety"
                    ? "text-amber-600 dark:text-amber-400 font-extrabold animate-pulse"
                    : "text-neo-muted hover:text-neo-text"
                }`}
            >
              {id === "seismic" ? "Seismic" : id === "tsunami" ? "Tsunami" : "Advisory"}
            </button>
          ))}
        </div>
      </div>

      <div className="w-full min-h-[160px] flex flex-col justify-between">
        {currentTab === "seismic" && (
          <div key="quake-seismic" className="fade-in-scale space-y-2.5">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="text-[9px] uppercase tracking-widest text-neo-muted font-bold">Seismic Monitor</p>
                  <span
                    className={`chip text-[8px] font-extrabold uppercase px-2 py-0.5 ${hasEarthquakeTsunamiAlert
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

        {currentTab === "tsunami" && (
          <div key="quake-tsunami" className="fade-in-scale space-y-2">
            <div className="flex items-center justify-between text-[10px]">
              <span className="text-neo-muted font-bold uppercase tracking-wider">INCOIS ITEWS Tsunami Watch</span>
              <span
                className={`chip text-[9px] font-bold uppercase ${tsuThreat ? "text-neo-danger bg-[color-mix(in_srgb,var(--danger)_15%,transparent)]" : "text-neo-accent"
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
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-sky-500/10 text-sky-600 dark:text-sky-400 ml-2">
                  <IconTsunamiWave className="w-5 h-5" />
                </div>
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

        {currentTab === "safety" && (
          <div key="quake-safety" className="fade-in-scale h-full flex flex-col justify-between space-y-2">
            <div className="flex items-center justify-between text-[10px]">
              <span className="text-neo-muted font-bold uppercase tracking-wider">NDMA Earthquake & Tsunami Guidelines</span>
              <span className="chip text-[9px] font-bold uppercase text-neo-accent">
                {hasEarthquakeTsunamiAlert ? "Emergency Active" : "Emergency Ready"}
              </span>
            </div>
            {nearestQuake && hasEarthquakeTsunamiAlert && (
              <div className="neo-in p-2 rounded-xl text-xs space-y-0.5">
                <p className="font-bold text-neo-danger">{nearestQuake.place || "Active Seismic Event"}</p>
                <p className="text-[10px] text-neo-muted">Magnitude: {magVal} · Depth: {depthVal} · Distance: {distVal}</p>
              </div>
            )}
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


export function NowcastSection({
  dash,
  locale,
  units,
  className,
  forceSummary,
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  units: "metric" | "imperial";
  className?: string;
  forceSummary?: boolean;
}) {
  const t = COPY[locale];

  const [localSummary, setLocalSummary] = useState<boolean | null>(null);
  useEffect(() => {
    setLocalSummary(null);
  }, [forceSummary]);
  const isSummary = localSummary !== null ? localSummary : Boolean(forceSummary);

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
    <section
      onClick={() => setLocalSummary(!isSummary)}
      className={`neo neo-section-nowcast p-4 flex flex-col justify-start select-none cursor-pointer transition min-h-[220px] hover:border-[color-mix(in_srgb,var(--accent)_35%,var(--line))] ${className || ""}`}
      title="Click card to switch between detailed data and overview"
    >
      <div className="flex shrink-0 items-center justify-between gap-2 flex-wrap mb-2">
        <div className="flex items-center gap-1.5">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
          <p className="text-[11px] font-black uppercase tracking-[0.18em] text-indigo-700 dark:text-indigo-400">
            {t.next6h}
          </p>
        </div>
        {!isSummary && (
          <div className="inline-flex rounded-xl bg-[color-mix(in_srgb,var(--bg)_80%,transparent)] p-0.5 border border-[var(--line)] shadow-inner">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setNext6Mode("numbers");
              }}
              className={`rounded-lg px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${next6Mode === "numbers" ? "bg-neo-accent text-white shadow-sm" : "text-neo-muted hover:text-neo-text"
                }`}
            >
              Slots
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setNext6Mode("plot");
              }}
              className={`rounded-lg px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all ${next6Mode === "plot"
                  ? "bg-neo-accent text-white shadow-sm"
                  : "text-neo-muted hover:text-neo-text"
                }`}
              title="Open-Meteo vs Blend (MoE) comparison"
            >
              Blend
            </button>
          </div>
        )}
      </div>

      <div className="w-full min-h-[160px] flex flex-col justify-between">
        {isSummary ? (
          <LaymanSummaryBody summary={getNowcastLaymanSummary(dash, locale, units)} />
        ) : (
          <>
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
                        className={`rounded px-1.5 py-0.5 text-[9px] font-bold tracking-wide transition-all ${next6Var === k
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
          </>
        )}
      </div>
    </section>
  );
}

