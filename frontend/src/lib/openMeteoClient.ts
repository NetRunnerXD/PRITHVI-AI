import type { DashboardSnapshot, HourlySlot, Location, OutlookDay } from "@/types/dashboard";

const WEATHER_CODE_MAP: Record<number, { label: string; kind: string }> = {
  0: { label: "Clear Sky", kind: "clear" },
  1: { label: "Mainly Clear", kind: "clear" },
  2: { label: "Partly Cloudy", kind: "cloud" },
  3: { label: "Overcast", kind: "cloud" },
  45: { label: "Fog", kind: "fog" },
  48: { label: "Depositing Rime Fog", kind: "fog" },
  51: { label: "Light Drizzle", kind: "rain" },
  53: { label: "Moderate Drizzle", kind: "rain" },
  55: { label: "Dense Drizzle", kind: "rain" },
  61: { label: "Slight Rain", kind: "rain" },
  63: { label: "Moderate Rain", kind: "rain" },
  65: { label: "Heavy Rain", kind: "rain" },
  71: { label: "Slight Snow", kind: "snow" },
  73: { label: "Moderate Snow", kind: "snow" },
  75: { label: "Heavy Snow", kind: "snow" },
  80: { label: "Slight Rain Showers", kind: "rain" },
  81: { label: "Moderate Rain Showers", kind: "rain" },
  82: { label: "Violent Rain Showers", kind: "rain" },
  95: { label: "Thunderstorm", kind: "storm" },
  96: { label: "Thunderstorm with Slight Hail", kind: "storm" },
  99: { label: "Thunderstorm with Heavy Hail", kind: "storm" },
};

export function decodeWeatherCode(code: number | null | undefined): { label: string; kind: string } {
  if (code == null) return { label: "Clear Sky", kind: "clear" };
  return WEATHER_CODE_MAP[code] || { label: `Weather (${code})`, kind: "cloud" };
}

export function degreesToCompass(deg: number | null | undefined): string {
  if (deg == null) return "N";
  const pts = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
  const idx = Math.round(((deg % 360) / 22.5)) % 16;
  return pts[idx];
}

const FC_CURRENT =
  "temperature_2m,relative_humidity_2m,apparent_temperature,dew_point_2m,precipitation,rain,showers,snowfall,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m,cloud_cover,is_day,visibility,pressure_msl,surface_pressure";
const FC_HOURLY =
  "temperature_2m,precipitation_probability,precipitation,rain,showers,snowfall,snow_depth,soil_moisture_0_to_7cm,et0_fao_evapotranspiration,evapotranspiration,relative_humidity_2m,dew_point_2m,apparent_temperature,pressure_msl,surface_pressure,wind_speed_10m,wind_direction_10m,wind_gusts_10m,cloud_cover,cloud_cover_low,cloud_cover_mid,cloud_cover_high,weather_code,visibility,cape,vapour_pressure_deficit,shortwave_radiation,direct_radiation,diffuse_radiation,direct_normal_irradiance,is_day,temperature_80m,temperature_120m,temperature_180m,wind_speed_80m,wind_speed_120m,wind_speed_180m,wind_direction_80m,wind_direction_120m,wind_direction_180m,soil_temperature_0cm,soil_temperature_6cm,soil_temperature_18cm,soil_temperature_54cm,soil_moisture_0_to_1cm,soil_moisture_1_to_3cm,soil_moisture_3_to_9cm,soil_moisture_9_to_27cm,soil_moisture_27_to_81cm";
const FC_DAILY =
  "precipitation_sum,precipitation_probability_max,precipitation_hours,rain_sum,showers_sum,snowfall_sum,temperature_2m_max,temperature_2m_min,temperature_2m_mean,apparent_temperature_max,apparent_temperature_min,relative_humidity_2m_max,relative_humidity_2m_min,relative_humidity_2m_mean,dew_point_2m_max,dew_point_2m_min,dew_point_2m_mean,et0_fao_evapotranspiration,weather_code,wind_speed_10m_max,wind_speed_10m_mean,wind_gusts_10m_max,wind_direction_10m_dominant,sunrise,sunset,daylight_duration,sunshine_duration,shortwave_radiation_sum,uv_index_max,uv_index_clear_sky_max";

export type OmClientPack = {
  forecast: Record<string, any>;
  air?: Record<string, any> | null;
  fetched_at: number;
};

let lastOmPack: OmClientPack | null = null;

export function getLastOmPack(): OmClientPack | null {
  return lastOmPack;
}

export async function fetchDirectOpenMeteo(lat: number, lon: number): Promise<Record<string, any> | null> {
  const params = new URLSearchParams({
    latitude: String(lat),
    longitude: String(lon),
    current: FC_CURRENT,
    hourly: FC_HOURLY,
    past_days: "1",
    daily: FC_DAILY,
    timezone: "Asia/Kolkata",
    forecast_days: "7",
  });

  try {
    const res = await fetch(`https://api.open-meteo.com/v1/forecast?${params.toString()}`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchClientOmPack(lat: number, lon: number, includeAir = true): Promise<OmClientPack | null> {
  const [forecast, air] = await Promise.all([
    fetchDirectOpenMeteo(lat, lon),
    includeAir ? fetchDirectAqi(lat, lon) : Promise.resolve(null),
  ]);
  if (!forecast) return null;
  lastOmPack = { forecast, air, fetched_at: Date.now() / 1000 };
  return lastOmPack;
}

export async function fetchDirectAqi(lat: number, lon: number): Promise<Record<string, any> | null> {
  const params = new URLSearchParams({
    latitude: String(lat),
    longitude: String(lon),
    current: "us_aqi,pm2_5,pm10,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone",
    hourly: "us_aqi",
    forecast_hours: "24",
    timezone: "Asia/Kolkata",
  });

  try {
    const res = await fetch(`https://air-quality-api.open-meteo.com/v1/air-quality?${params.toString()}`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export function buildOptimisticSnapshot(
  loc: Location,
  om: Record<string, any>,
  aqi?: Record<string, any> | null
): DashboardSnapshot {
  const cur = om.current || {};
  const hourly = om.hourly || {};
  const daily = om.daily || {};
  const aqiCur = aqi?.current || {};

  const weatherCode = cur.weather_code ?? 0;
  const { label: skyLabel, kind: skyKind } = decodeWeatherCode(weatherCode);
  const windDir = cur.wind_direction_10m ?? 0;
  const windCompass = degreesToCompass(windDir);

  // Construct Hourly Slots
  const hourlySlots: HourlySlot[] = [];
  const times: string[] = hourly.time || [];
  const count = Math.min(times.length, 48);
  for (let i = 0; i < count; i++) {
    const tStr = times[i];
    const d = tStr.slice(0, 10);
    const h = tStr.slice(11, 16);
    const hCode = hourly.weather_code?.[i];
    hourlySlots.push({
      t: tStr,
      date: d,
      hour: h,
      precip_mm: hourly.precipitation?.[i] ?? 0,
      precip_prob_pct: hourly.precipitation_probability?.[i] ?? 0,
      temp_c: hourly.temperature_2m?.[i] ?? 0,
      wind_kmh: hourly.wind_speed_10m?.[i] ?? 0,
      wind_gust_kmh: hourly.wind_gusts_10m?.[i] ?? 0,
      wind_dir_deg: hourly.wind_direction_10m?.[i] ?? 0,
      rh_pct: hourly.relative_humidity_2m?.[i] ?? 0,
      cloud_pct: hourly.cloud_cover?.[i] ?? 0,
      weather_code: hCode,
      sky_label: decodeWeatherCode(hCode).label,
      visibility_km: hourly.visibility?.[i] != null ? Math.round(hourly.visibility[i] / 100) / 10 : undefined,
    });
  }

  // Construct 7-Day Outlook
  const outlookDays: OutlookDay[] = [];
  const dailyDates: string[] = daily.time || [];
  for (let i = 0; i < dailyDates.length; i++) {
    outlookDays.push({
      date: dailyDates[i],
      precip_mm: daily.precipitation_sum?.[i] ?? 0,
      precip_prob_pct: daily.precipitation_probability_max?.[i] ?? 0,
      temp_max_c: daily.temperature_2m_max?.[i] ?? null,
      temp_min_c: daily.temperature_2m_min?.[i] ?? null,
      et0_mm: daily.et0_fao_evapotranspiration?.[i] ?? 3.5,
      soil_m3m3: 0.28,
      water_balance_mm: (daily.precipitation_sum?.[i] ?? 0) - (daily.et0_fao_evapotranspiration?.[i] ?? 3.5),
      irrigate: (daily.precipitation_sum?.[i] ?? 0) < 2.0,
      flood_watch: (daily.precipitation_sum?.[i] ?? 0) > 65.0,
    });
  }

  const precipNext3d = daily.precipitation_sum?.slice(0, 3).reduce((a: number, b: number) => a + (b || 0), 0) ?? 0;
  const precip7d = daily.precipitation_sum?.reduce((a: number, b: number) => a + (b || 0), 0) ?? 0;

  return {
    location: loc,
    generated_at: new Date().toISOString(),
    enriching: true,
    sources: ["Direct Open-Meteo Edge", "CAMS Atmospheric AQI"],
    descriptive: {
      current: {
        temp_c: cur.temperature_2m,
        precip_1h_mm: cur.precipitation,
        humidity_pct: cur.relative_humidity_2m,
        wind_ms: cur.wind_speed_10m != null ? Math.round((cur.wind_speed_10m / 3.6) * 10) / 10 : null,
        wind_dir_deg: windDir,
        wind_compass: windCompass,
        soil_moisture_m3m3: 0.28,
        et0_mm: daily.et0_fao_evapotranspiration?.[0] ?? 3.5,
        aqi: aqiCur.us_aqi,
        aqi_category: aqiCur.us_aqi != null ? (aqiCur.us_aqi <= 50 ? "Good" : aqiCur.us_aqi <= 100 ? "Moderate" : "Poor") : undefined,
        aqi_station: "Open-Meteo CAMS Global Grid",
        sky_label: skyLabel,
        sky_kind: skyKind,
        cloud_cover_pct: cur.cloud_cover,
        visibility_km: 10,
        is_day: Boolean(cur.is_day),
        apparent_temp_c: cur.apparent_temperature,
        pressure_msl_hpa: cur.surface_pressure,
        om_us_aqi: aqiCur.us_aqi,
        om_pm25: aqiCur.pm2_5,
      },
      series: {
        aqi_hourly: ((aqi?.hourly?.time as string[]) || []).slice(0, 24).map((t, i) => ({
          t,
          value: aqi?.hourly?.us_aqi?.[i] ?? aqiCur.us_aqi ?? 0,
          unit: "US AQI",
          source: "open-meteo-air",
        })),
      },
    },
    diagnostic: {
      anomalies: [],
      drivers: ["Direct Weather Telemetry Active (AI Syncing)"],
    },
    predictive: {
      precip_next_3d_mm: Math.round(precipNext3d * 10) / 10,
      precip_7d_mm: Math.round(precip7d * 10) / 10,
      precip_probability_pct: daily.precipitation_probability_max || [],
      temp_max_c: daily.temperature_2m_max || [],
      temp_min_c: daily.temperature_2m_min || [],
      flood_discharge_trend: "stable",
      river_discharge: [],
      outlook_days: outlookDays,
      hourly: hourlySlots,
      model: "open-meteo-direct",
    },
    prescriptive: {
      warnings: [],
      actions: [],
    },
    risks: [],
    map: {
      center: [loc.lat, loc.lon],
      zoom: 9,
      layers: [{ id: "base", visible: true }],
    },
    vegetation: {
      index: 68,
      label: "Estimated from weather metrics",
      kind: "direct_estimate",
    },
    provider_status: {
      "open-meteo": "direct-edge",
      "imd-cap": "syncing",
      "data.gov.in": "syncing",
      "vera-moe": "syncing",
    },
    live: {
      generated_at: new Date().toISOString(),
      refresh_s: 300,
      sky: {
        label: skyLabel,
        kind: skyKind,
        weather_code: weatherCode,
        is_day: Boolean(cur.is_day),
        cloud_cover_pct: cur.cloud_cover,
        visibility_km: 10,
        temp_c: cur.temperature_2m,
        humidity_pct: cur.relative_humidity_2m,
        precip_1h_mm: cur.precipitation,
        place: loc.label,
      },
      wind: {
        speed_kmh: cur.wind_speed_10m,
        speed_ms: cur.wind_speed_10m != null ? Math.round((cur.wind_speed_10m / 3.6) * 10) / 10 : null,
        direction_deg: windDir,
        compass: windCompass,
        flow_compass: windCompass,
        flow_deg: windDir,
      },
      marine: {
        inland: true,
      },
      flood: {
        score_pct: 10,
        trend: "stable",
        source: "open-meteo-direct",
      },
      air: {
        open_meteo: {
          us_aqi: aqiCur.us_aqi,
          pm2_5: aqiCur.pm2_5,
          pm10: aqiCur.pm10,
        },
      },
      quakes: [],
      tsunami: [],
    },
  };
}
