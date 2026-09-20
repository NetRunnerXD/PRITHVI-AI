/** World weather grid from Open-Meteo on the user's IP. No invented millimetres. */

const SOUTH = -56,
  WEST = -180,
  NORTH = 72,
  EAST = 180;
const NY = 13,
  NX = 25;
const CHUNK = 20;
const HOURLY =
  "temperature_2m,relative_humidity_2m,precipitation,precipitation_probability,pressure_msl,wind_speed_10m,wind_direction_10m,cloud_cover,cape,weather_code";

type OmHourly = Record<string, (number | null)[] | string[] | undefined>;
type OmRow = { hourly?: OmHourly };

let rawCache: { rows: OmRow[]; until: number } | null = null;
const hourCache = new Map<number, { pack: WeatherGridPack; until: number }>();
const TTL_MS = 8 * 60 * 1000;

export type WeatherGridPack = {
  ok: boolean;
  source: string;
  note?: string;
  scope: string;
  south: number;
  west: number;
  north: number;
  east: number;
  nx: number;
  ny: number;
  lats: number[];
  lons: number[];
  hour: number;
  valid?: string | null;
  n: number;
  fields: Record<string, (number | null)[]>;
  products: string[];
};

function lats(): number[] {
  const step = (NORTH - SOUTH) / (NY - 1);
  return Array.from({ length: NY }, (_, i) => Math.round((SOUTH + i * step) * 1000) / 1000);
}

function lons(): number[] {
  const step = (EAST - WEST) / (NX - 1);
  return Array.from({ length: NX }, (_, i) => Math.round((WEST + i * step) * 1000) / 1000);
}

function meshPts(): [number, number][] {
  const la = lats();
  const lo = lons();
  const pts: [number, number][] = [];
  for (const a of la) for (const b of lo) pts.push([a, b]);
  return pts;
}

function uv(speedKmh: number | null, dirDeg: number | null): [number | null, number | null] {
  if (speedKmh == null || dirDeg == null) return [null, null];
  const ms = speedKmh / 3.6;
  const rad = (dirDeg * Math.PI) / 180;
  return [Math.round(-ms * Math.sin(rad) * 1000) / 1000, Math.round(-ms * Math.cos(rad) * 1000) / 1000];
}

function at(seq: unknown, i: number): number | null {
  if (!Array.isArray(seq) || i < 0 || i >= seq.length) return null;
  const v = seq[i];
  if (v == null) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function hourIndex(times: string[], hour: number): number {
  const h = Math.max(0, Math.min(23, hour | 0));
  const now = new Date();
  now.setUTCMinutes(0, 0, 0);
  now.setUTCHours(now.getUTCHours() + h);
  const want = now.toISOString().slice(0, 13) + ":00";
  const idx = times.findIndex((t) => String(t).slice(0, 16) === want);
  if (idx >= 0) return idx;
  if (!times.length) return 0;
  return Math.min(h, times.length - 1);
}

async function fetchChunk(pts: [number, number][]): Promise<OmRow[]> {
  const params = new URLSearchParams({
    latitude: pts.map((p) => p[0]).join(","),
    longitude: pts.map((p) => p[1]).join(","),
    hourly: HOURLY,
    forecast_hours: "24",
    timezone: "GMT",
    wind_speed_unit: "kmh",
  });
  const run = async () => {
    const r = await fetch(`https://api.open-meteo.com/v1/forecast?${params}`);
    if (!r.ok) throw new Error(`om ${r.status}`);
    const body = await r.json();
    const rows = Array.isArray(body) ? body : [body];
    while (rows.length < pts.length) rows.push({});
    return rows.slice(0, pts.length) as OmRow[];
  };
  try {
    return await run();
  } catch {
    await new Promise((res) => setTimeout(res, 400));
    try {
      return await run();
    } catch {
      return pts.map(() => ({}));
    }
  }
}

async function fetchRaw(): Promise<OmRow[] | null> {
  if (rawCache && Date.now() < rawCache.until) return rawCache.rows;
  const pts = meshPts();
  const rows: OmRow[] = [];
  for (let i = 0; i < pts.length; i += CHUNK) {
    const part = await fetchChunk(pts.slice(i, i + CHUNK));
    rows.push(...part);
  }
  if (rows.length < pts.length) {
    while (rows.length < pts.length) rows.push({});
  } else if (rows.length > pts.length) {
    rows.length = pts.length;
  }
  if (!rows.some((r) => r?.hourly)) return null;
  rawCache = { rows, until: Date.now() + TTL_MS };
  return rows;
}

function slice(rows: OmRow[], hour: number): WeatherGridPack {
  const la = lats();
  const lo = lons();
  const times = ((rows[0]?.hourly?.time as string[]) || []).map(String);
  const idx = hourIndex(times, hour);
  const stamp = times[idx] || null;
  const fields: Record<string, (number | null)[]> = {
    temp_c: [],
    rh_pct: [],
    precip_mm: [],
    precip_prob_pct: [],
    pressure_hpa: [],
    wind_kmh: [],
    wind_dir_deg: [],
    wind_u: [],
    wind_v: [],
    cloud_pct: [],
    cape: [],
  };
  for (const row of rows) {
    const h = row.hourly || {};
    const temp = at(h.temperature_2m, idx);
    const rh = at(h.relative_humidity_2m, idx);
    const precip = at(h.precipitation, idx);
    const prob = at(h.precipitation_probability, idx);
    const pres = at(h.pressure_msl, idx);
    const wspd = at(h.wind_speed_10m, idx);
    const wdir = at(h.wind_direction_10m, idx);
    const cloud = at(h.cloud_cover, idx);
    const cape = at(h.cape, idx);
    const [u, v] = uv(wspd, wdir);
    fields.temp_c.push(temp == null ? null : Math.round(temp * 100) / 100);
    fields.rh_pct.push(rh == null ? null : Math.round(rh));
    fields.precip_mm.push(precip == null ? null : Math.round(precip * 100) / 100);
    fields.precip_prob_pct.push(prob == null ? null : Math.round(prob));
    fields.pressure_hpa.push(pres == null ? null : Math.round(pres * 10) / 10);
    fields.wind_kmh.push(wspd == null ? null : Math.round(wspd * 10) / 10);
    fields.wind_dir_deg.push(wdir == null ? null : Math.round(wdir));
    fields.wind_u.push(u);
    fields.wind_v.push(v);
    fields.cloud_pct.push(cloud == null ? null : Math.round(cloud));
    fields.cape.push(cape == null ? null : Math.round(cape));
  }
  return {
    ok: true,
    source: "open-meteo",
    note: "Global Open-Meteo field (not a rain-gauge). Storm cells stay India-only. Hours are UTC.",
    scope: "world",
    south: SOUTH,
    west: WEST,
    north: NORTH,
    east: EAST,
    nx: NX,
    ny: NY,
    lats: la,
    lons: lo,
    hour,
    valid: stamp,
    n: la.length * lo.length,
    fields,
    products: ["wind", "temp", "precip", "pressure", "clouds", "humidity", "cape", "radar", "satellite"],
  };
}

export async function fetchClientWeatherGrid(hour = 0): Promise<WeatherGridPack | null> {
  const h = Math.max(0, Math.min(23, Math.round(hour)));
  const hit = hourCache.get(h);
  if (hit && Date.now() < hit.until) return hit.pack;
  const raw = await fetchRaw();
  if (!raw) return null;
  const pack = slice(raw, h);
  hourCache.set(h, { pack, until: Date.now() + TTL_MS });
  return pack;
}
