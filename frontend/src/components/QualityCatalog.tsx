"use client";

import type { ReactNode } from "react";
import type { DashboardSnapshot } from "@/types/dashboard";

function fmt(v: unknown): string {
  if (v == null || v === "") return "—";
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "number" && Number.isFinite(v)) {
    return Number.isInteger(v) ? String(v) : String(Math.round(v * 1000) / 1000);
  }
  return String(v);
}

function clock(iso: unknown): string {
  if (iso == null || iso === "") return "—";
  const s = String(iso);
  const i = s.indexOf("T");
  if (i >= 0) return s.slice(i + 1, i + 6);
  return s;
}

function dur(sec: unknown): string {
  if (sec == null || sec === "") return "—";
  const n = Number(sec);
  if (!Number.isFinite(n)) return "—";
  const h = n / 3600;
  return `${h.toFixed(2)} h`;
}

function Stat({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex flex-col justify-center rounded-xl px-3 py-2.5 bg-[color-mix(in_srgb,var(--accent)_3%,transparent)] border border-[color-mix(in_srgb,var(--accent)_10%,transparent)] transition-all hover:bg-[color-mix(in_srgb,var(--accent)_6%,transparent)] hover:border-[color-mix(in_srgb,var(--accent)_20%,transparent)] group">
      <p className="text-[9px] font-bold uppercase tracking-widest text-neo-muted transition-colors group-hover:text-neo-accent">{k}</p>
      <p className="mt-1 break-all font-mono text-sm font-extrabold text-[var(--text)]">{v}</p>
    </div>
  );
}

function Sector({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <section className="neo flex flex-col p-5 bg-[var(--card)] hover:ring-2 hover:ring-[var(--accent)] transition-all duration-300 break-inside-avoid mb-4">
      <div className="mb-4">
        <p className="text-[12px] font-bold uppercase tracking-[0.18em] text-neo-accent">{title}</p>
        {note ? <p className="mt-1.5 text-[11px] text-neo-muted leading-relaxed">{note}</p> : null}
      </div>
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">{children}</div>
    </section>
  );
}

const QUAKE_FIELDS: { k: string; label: string }[] = [
  { k: "time_iso", label: "Time" },
  { k: "lat", label: "Latitude" },
  { k: "lon", label: "Longitude" },
  { k: "depth_km", label: "Depth (km)" },
  { k: "mag", label: "Magnitude" },
  { k: "magType", label: "magType" },
  { k: "nst", label: "nst" },
  { k: "gap", label: "gap" },
  { k: "dmin", label: "dmin" },
  { k: "rms", label: "rms" },
  { k: "net", label: "net" },
  { k: "id", label: "id" },
  { k: "updated_iso", label: "updated" },
  { k: "place", label: "place" },
  { k: "type", label: "type" },
  { k: "locationSource", label: "locationSource" },
  { k: "magSource", label: "magSource" },
  { k: "horizontalError", label: "horizontalError" },
  { k: "depthError", label: "depthError" },
  { k: "magError", label: "magError" },
  { k: "magNst", label: "magNst" },
  { k: "status", label: "status" },
];

export function QualityCatalog({ dash, group }: { dash: DashboardSnapshot; group?: string }) {
  const q = dash.quality || {};
  const air = (q.air || {}) as Record<string, unknown>;
  const climate = (q.climate || {}) as Record<string, unknown>;
  const marine = (q.marine || {}) as Record<string, unknown>;
  const moon = (q.moon || {}) as Record<string, unknown>;
  const pollen = (air.pollen || {}) as Record<string, unknown>;
  const flood = (q.flood || {}) as Record<string, unknown>;
  const seismic = (q.seismic || dash.live?.quakes || []) as Record<string, unknown>[];
  const tsunami = (q.tsunami || dash.live?.tsunami || []) as Record<string, unknown>[];
  const gdacs = (q.gdacs || []) as Record<string, unknown>[];
  const quake = seismic[0] || {};
  const ts0 = tsunami[0] || {};
  const cpcb = (air.cpcb || dash.descriptive.current) as Record<string, unknown>;
  const inland = Boolean(marine.inland);
  const visKm =
    climate.visibility_m != null && Number.isFinite(Number(climate.visibility_m))
      ? (Number(climate.visibility_m) / 1000).toFixed(2)
      : null;

  return (
    <div className="columns-1 lg:columns-2 2xl:columns-3 gap-4 space-y-4">
      {(!group || group === "environment") && (
        <>
          <h2 style={{ columnSpan: "all" } as any} className="mb-4 mt-8 first:mt-0 text-[13px] font-extrabold uppercase tracking-[0.2em] text-neo-muted border-b border-[var(--line)] pb-2">
            Environment & Air Quality
          </h2>
          <Sector title="Air quality indices" note="CPCB + Open-Meteo CAMS. Dash = not in the fetched sample.">
            <Stat
              k={cpcb.value != null ? "AQI (CPCB)" : "AQI (CAMS)"}
              v={fmt(cpcb.value ?? dash.descriptive.current.aqi ?? air.us_aqi)}
            />
            <Stat k="AQI category" v={fmt(cpcb.category ?? dash.descriptive.current.aqi_category)} />
            <Stat k="US AQI (CAMS)" v={fmt(air.us_aqi)} />
            <Stat k="European AQI" v={fmt(air.european_aqi)} />
            <Stat k="UV index" v={fmt(air.uv_index ?? climate.uv_index)} />
            <Stat k="UV index (clear sky)" v={fmt(air.uv_index_clear_sky ?? climate.uv_index_clear_sky)} />
          </Sector>

          <Sector title="Particulates">
            <Stat k="PM10" v={fmt(air.pm10)} />
            <Stat k="PM2.5" v={fmt(air.pm2_5)} />
            <Stat k="Dust" v={fmt(air.dust)} />
          </Sector>

          <Sector title="Gases">
            <Stat k="CO" v={fmt(air.co)} />
            <Stat k="CO2" v={fmt(air.co2)} />
            <Stat k="NO2" v={fmt(air.no2)} />
            <Stat k="SO2" v={fmt(air.so2)} />
            <Stat k="O3" v={fmt(air.o3)} />
            <Stat k="NH3" v={fmt(air.nh3)} />
            <Stat k="CH4" v={fmt(air.ch4)} />
          </Sector>

          <Sector title="Pollen" note="India aerobiology climatology (CAMS pollen is Europe-only).">
            <Stat k="Pollen · alder" v={fmt(pollen.alder)} />
            <Stat k="Pollen · birch" v={fmt(pollen.birch)} />
            <Stat k="Pollen · grass" v={fmt(pollen.grass)} />
            <Stat k="Pollen · mugwort" v={fmt(pollen.mugwort)} />
            <Stat k="Pollen · olive" v={fmt(pollen.olive)} />
            <Stat k="Pollen · ragweed" v={fmt(pollen.ragweed)} />
            <Stat k="Pollen source" v={fmt(pollen.source)} />
          </Sector>

          <Sector title="Soil">
            <Stat k="Soil temperature 0 cm" v={fmt(climate.soil_t_0)} />
            <Stat k="Soil temperature 6 cm" v={fmt(climate.soil_t_6)} />
            <Stat k="Soil temperature 18 cm" v={fmt(climate.soil_t_18)} />
            <Stat k="Soil temperature 54 cm" v={fmt(climate.soil_t_54)} />
            <Stat k="Soil moisture 0–1 cm" v={fmt(climate.soil_m_0_1)} />
            <Stat k="Soil moisture 1–3 cm" v={fmt(climate.soil_m_1_3)} />
            <Stat k="Soil moisture 3–9 cm" v={fmt(climate.soil_m_3_9)} />
            <Stat k="Soil moisture 9–27 cm" v={fmt(climate.soil_m_9_27)} />
            <Stat k="Soil moisture 27–81 cm" v={fmt(climate.soil_m_27_81)} />
          </Sector>
        </>
      )}

      {(!group || group === "meteorology") && (
        <>
          <h2 style={{ columnSpan: "all" } as any} className="mb-4 mt-8 first:mt-0 text-[13px] font-extrabold uppercase tracking-[0.2em] text-neo-muted border-b border-[var(--line)] pb-2">
            Meteorology & Climate
          </h2>
          <Sector title="Humidity & dew">
            <Stat k="RH now (2 m)" v={fmt(climate.rh_now)} />
            <Stat k="RH max (2 m)" v={fmt(climate.rh_max)} />
            <Stat k="RH min (2 m)" v={fmt(climate.rh_min)} />
            <Stat k="RH mean (2 m)" v={fmt(climate.rh_mean)} />
            <Stat k="Dew point now (2 m)" v={fmt(climate.dew_point_c)} />
            <Stat k="Dew point max (2 m)" v={fmt(climate.dew_max)} />
            <Stat k="Dew point min (2 m)" v={fmt(climate.dew_min)} />
            <Stat k="Dew point mean (2 m)" v={fmt(climate.dew_mean)} />
          </Sector>

          <Sector title="Apparent temperature">
            <Stat k="Apparent temp now" v={fmt(climate.apparent_temp_c)} />
            <Stat k="Apparent temp max" v={fmt(climate.apparent_max)} />
            <Stat k="Apparent temp min" v={fmt(climate.apparent_min)} />
          </Sector>

          <Sector title="Precipitation">
            <Stat k="Precip probability" v={fmt(climate.precip_prob_now ?? climate.precip_prob_max)} />
            <Stat k="Precipitation (rain+showers+snow)" v={fmt(climate.precip_now)} />
            <Stat k="Rain" v={fmt(climate.rain_now ?? climate.rain_sum)} />
            <Stat k="Showers" v={fmt(climate.showers_now ?? climate.showers_sum)} />
            <Stat k="Snowfall" v={fmt(climate.snowfall_now ?? climate.snowfall_sum)} />
            <Stat k="Snow depth" v={fmt(climate.snow_depth_m)} />
            <Stat k="Weather code" v={fmt(climate.weather_code)} />
          </Sector>

          <Sector title="Pressure">
            <Stat k="Sea level pressure" v={fmt(climate.pressure_msl_hpa)} />
            <Stat k="Surface pressure" v={fmt(climate.surface_pressure_hpa)} />
          </Sector>

          <Sector title="Cloud cover">
            <Stat k="Cloud cover total" v={fmt(climate.cloud_cover_pct)} />
            <Stat k="Cloud cover low" v={fmt(climate.cloud_low)} />
            <Stat k="Cloud cover mid" v={fmt(climate.cloud_mid)} />
            <Stat k="Cloud cover high" v={fmt(climate.cloud_high)} />
          </Sector>

          <Sector title="Visibility">
            <Stat k="Visibility (km)" v={visKm ?? "—"} />
          </Sector>

          <Sector title="Evapotranspiration">
            <Stat k="Evapotranspiration" v={fmt(climate.et_now)} />
            <Stat k="Reference ET (ET₀)" v={fmt(climate.et0_today)} />
            <Stat k="Vapour pressure deficit" v={fmt(climate.vpd_now)} />
          </Sector>

          <Sector title="Temperature">
            <Stat k="Temp max (2 m)" v={fmt(climate.temp_max)} />
            <Stat k="Temp min (2 m)" v={fmt(climate.temp_min)} />
            <Stat k="Temp mean (2 m)" v={fmt(climate.temp_mean)} />
            <Stat k="Temp 80 m" v={fmt(climate.temp_80m)} />
            <Stat k="Temp 120 m" v={fmt(climate.temp_120m)} />
            <Stat k="Temp 180 m" v={fmt(climate.temp_180m)} />
          </Sector>

          <Sector title="Wind">
            <Stat k="Wind speed max (10 m)" v={fmt(climate.wind_10m_max)} />
            <Stat k="Wind speed mean (10 m)" v={fmt(climate.wind_10m_mean)} />
            <Stat k="Wind speed now (10 m)" v={fmt(climate.wind_10m)} />
            <Stat k="Wind speed 80 m" v={fmt(climate.wind_80m)} />
            <Stat k="Wind speed 120 m" v={fmt(climate.wind_120m)} />
            <Stat k="Wind speed 180 m" v={fmt(climate.wind_180m)} />
            <Stat k="Wind direction (10 m)" v={fmt(climate.wind_dir_10m)} />
            <Stat k="Wind direction (80 m)" v={fmt(climate.wind_dir_80m)} />
            <Stat k="Wind direction (120 m)" v={fmt(climate.wind_dir_120m)} />
            <Stat k="Wind direction (180 m)" v={fmt(climate.wind_dir_180m)} />
            <Stat k="Wind gusts (10 m)" v={fmt(climate.wind_gusts_10m)} />
          </Sector>

          <Sector title="Sun & moon">
            <Stat k="Sunrise" v={clock(climate.sunrise)} />
            <Stat k="Sunset" v={clock(climate.sunset)} />
            <Stat k="Moonrise" v={clock(moon.moonrise)} />
            <Stat k="Moonset" v={clock(moon.moonset)} />
            <Stat k="Daylight duration" v={dur(climate.daylight_s)} />
            <Stat k="Sunshine duration" v={dur(climate.sunshine_s)} />
            <Stat k="Moon phase" v={fmt(moon.phase)} />
            <Stat k="Moon illumination" v={fmt(moon.illumination)} />
            <Stat k="Shortwave radiation sum" v={fmt(climate.shortwave_sum)} />
            <Stat k="UV index (daily max)" v={fmt(climate.uv_index_max)} />
            <Stat k="UV index clear-sky max" v={fmt(climate.uv_clear_max)} />
          </Sector>
        </>
      )}

      {(!group || group === "hydrology") && (
        <>
          <h2 style={{ columnSpan: "all" } as any} className="mb-4 mt-8 first:mt-0 text-[13px] font-extrabold uppercase tracking-[0.2em] text-neo-muted border-b border-[var(--line)] pb-2">
            Hydrology & Marine
          </h2>
          <Sector
            title="Marine"
            note={inland ? "Inland pin — Open-Meteo marine may be empty or snapped to the nearest Indian coast." : "Open-Meteo marine weather."}
          >
            <Stat k="Wave height" v={fmt(marine.wave_height_m)} />
            <Stat k="Wave direction" v={fmt(marine.wave_dir_deg)} />
            <Stat k="Wave period" v={fmt(marine.wave_period_s)} />
            <Stat k="Wave peak period" v={fmt(marine.wave_peak_period_s)} />
            <Stat k="Wind wave height" v={fmt(marine.wind_wave_height_m)} />
            <Stat k="Wind wave direction" v={fmt(marine.wind_wave_dir_deg)} />
            <Stat k="Wind wave period" v={fmt(marine.wind_wave_period_s)} />
            <Stat k="Wind wave peak period" v={fmt(marine.wind_wave_peak_period_s)} />
            <Stat k="Swell height" v={fmt(marine.swell_height_m)} />
            <Stat k="Swell direction" v={fmt(marine.swell_dir_deg)} />
            <Stat k="Swell period" v={fmt(marine.swell_period_s)} />
            <Stat k="Swell peak period" v={fmt(marine.swell_peak_period_s)} />
            <Stat k="Secondary swell height" v={fmt(marine.swell2_height_m)} />
            <Stat k="Secondary swell direction" v={fmt(marine.swell2_dir_deg)} />
            <Stat k="Secondary swell period" v={fmt(marine.swell2_period_s)} />
            <Stat k="Tertiary swell height" v={fmt(marine.swell3_height_m)} />
            <Stat k="Tertiary swell direction" v={fmt(marine.swell3_dir_deg)} />
            <Stat k="Tertiary swell period" v={fmt(marine.swell3_period_s)} />
            <Stat k="Sea level height (incl. tides)" v={fmt(marine.sea_level_m)} />
            <Stat k="Sea surface temperature" v={fmt(marine.sst_c)} />
            <Stat k="Ocean current velocity" v={fmt(marine.ocean_current_ms)} />
            <Stat k="Ocean current direction" v={fmt(marine.ocean_current_dir)} />
          </Sector>

          <Sector title="Flood" note="Open-Meteo GloFAS.">
            <Stat k="River discharge trend" v={fmt(flood.trend ?? dash.predictive.flood_discharge_trend)} />
            <Stat k="River discharge (now)" v={fmt((flood.discharge as number[] | undefined)?.[0] ?? dash.predictive.river_discharge?.[0])} />
            <Stat k="Flood source" v={fmt(flood.source)} />
          </Sector>

          <Sector title="Tsunami" note="INCOIS ITEWS.">
            <Stat k="ITEWS title" v={fmt(ts0.title)} />
            <Stat k="ITEWS body" v={fmt(ts0.body)} />
            <Stat k="ITEWS threat" v={fmt(ts0.threat)} />
            <Stat k="ITEWS source" v={fmt(ts0.source)} />
          </Sector>

          <Sector title="Cyclones" note="GDACS.">
            <Stat k="GDACS events" v={String(gdacs.length)} />
            <Stat k="GDACS latest" v={fmt(gdacs[0]?.title)} />
            <Stat k="GDACS type" v={fmt(gdacs[0]?.event_type)} />
          </Sector>
        </>
      )}

      {(!group || group === "seismology") && (
        <>
          <h2 style={{ columnSpan: "all" } as any} className="mb-4 mt-8 first:mt-0 text-[13px] font-extrabold uppercase tracking-[0.2em] text-neo-muted border-b border-[var(--line)] pb-2">
            Seismology
          </h2>
          <Sector title="Earthquake / seismic" note="Nearest event in the India–Indian Ocean box (USGS FDSN, EMSC). NCS has no public JSON.">
            {QUAKE_FIELDS.map((row) => (
              <Stat key={row.k} k={row.label} v={fmt(quake[row.k] ?? (row.k === "updated_iso" ? quake.updated : undefined))} />
            ))}
            <Stat k="distance_km" v={fmt(quake.distance_km)} />
            <Stat k="source" v={fmt(quake.source)} />
          </Sector>
        </>
      )}
    </div>
  );
}
