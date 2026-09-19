"use client";

import type { DashboardSnapshot } from "@/types/dashboard";
import { COPY, type Locale } from "@/i18n/copy";
import { useApp } from "@/lib/store";
import { rainUnit, tempUnit } from "@/lib/units";
import { Forecast7DayDeck } from "../Forecast7DayDeck";
import { SkyRainHero } from "../SkyRainHero";
import { feelsLikeC, hhmm } from "./helpers";
import { RiskAlertPanel, HomeHazardStrip } from "./RiskAlertPanel";
import { RainfallSection, WindSection, Spark } from "./rainWind";

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

    return out;
  })();

  const viewMode = useApp((s) => s.viewMode);
  const allSummary = viewMode === "overview";

  return (
    <div className="space-y-3">
      {/* ── Top Unified Grid: Left (Sky on top + Rain & Wind side-by-side) & Right (Extended Alert & Risk Panel) ── */}
      <div className="grid gap-3 grid-cols-1 lg:grid-cols-12 items-start">
        {/* Left Column: Sky on top, followed by Mobile Risk Panel, then Rain & Wind */}
        <div className="w-full lg:col-span-7 xl:col-span-8 flex flex-col gap-3">
          <SkyRainHero dash={dash} locale={locale} onNavigateData={onNavigateData} forceSummary={allSummary} />

          {/* Mobile-only collapsible Risk & Alert Panel (placed directly below Sky & Atmosphere) */}
          <div className="w-full lg:hidden">
            <RiskAlertPanel
              dash={dash}
              locale={locale}
              onNavigateData={onNavigateData}
              allAlerts={allAlerts}
              className="w-full"
              isMobileCollapsible
            />
          </div>

          <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 items-start">
            <RainfallSection
              dash={dash}
              locale={locale}
              units={units}
              onNavigateData={onNavigateData}
              forceSummary={allSummary}
              className="w-full flex flex-col justify-start select-none"
            />

            <WindSection
              dash={dash}
              locale={locale}
              units={units}
              onNavigateData={onNavigateData}
              forceSummary={allSummary}
              className="w-full flex flex-col justify-start select-none"
            />
          </div>
        </div>

        {/* Right Column: Desktop Alert & Risk Panel (hidden on mobile, visible lg+) */}
        <div className="hidden lg:flex w-full lg:col-span-5 xl:col-span-4 flex-col justify-start">
          <RiskAlertPanel
            dash={dash}
            locale={locale}
            onNavigateData={onNavigateData}
            allAlerts={allAlerts}
            className="w-full"
          />
        </div>
      </div>

      {/* ── Row 2: Environmental & Geo-Hazard Cards (Air, Land, Marine | Cyclone, Earthquake/Tsunami, Nowcasting) ── */}
      <HomeHazardStrip dash={dash} locale={locale} units={units} onNavigateData={onNavigateData} forceSummary={allSummary} />

      {/* ── Row 3: 7-Day Interactive Forecast & Chrono-Deck (At Bottom) ── */}
      <Forecast7DayDeck dash={dash} locale={locale} forceSummary={allSummary} />
    </div>
  );
}

// Precision Vector SVG Icons for Professional Alert Presentation (Zero Emojis)

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

