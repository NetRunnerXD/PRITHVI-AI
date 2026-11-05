/** Worldwide NOAA GFS background grid (1°, 80°S–80°N) from /api/map/gfs, decoded from 8-bit
 * PNGs (~20–35 KB each). Only the fields the current layer needs are fetched. */
import { apiUrl } from "./config";
import type { WeatherGrid, WxLayer } from "./weatherScale";

type Quant = { min: number; max: number; transform: "lin" | "log1p" };
type Meta = {
  ok: boolean;
  status?: string;
  error?: string | null;
  cycle?: string;
  step?: number;
  valid?: string;
  grid?: { nx: number; ny: number; south: number; north: number; west: number; dlon: number; dlat: number };
  quant?: Record<string, Quant>;
  fields?: string[];
};

export type GfsLoad = { grid: WeatherGrid | null; status: string };

const fieldCache = new Map<string, Float32Array>();
let metaCache: { hour: number; at: number; meta: Meta } | null = null;

export function gfsFieldsFor(layer: WxLayer | null, particles: boolean): string[] {
  const out = new Set<string>();
  if (layer === "wind" || particles) {
    out.add("wind_u");
    out.add("wind_v");
  }
  const map: Partial<Record<WxLayer, string>> = {
    temp: "temp_c",
    precip: "precip_mm",
    pressure: "pressure_hpa",
    clouds: "cloud_pct",
    humidity: "rh_pct",
    cape: "cape",
  };
  if (layer && map[layer]) out.add(map[layer]!);
  return Array.from(out);
}

async function getMeta(hour: number): Promise<Meta | null> {
  if (metaCache && metaCache.hour === hour && Date.now() - metaCache.at < 10 * 60_000 && metaCache.meta.ok) return metaCache.meta;
  try {
    const r = await fetch(`${apiUrl("/map/gfs/meta")}?hour=${hour}`);
    if (!r.ok) return null;
    const m = (await r.json()) as Meta;
    metaCache = { hour, at: Date.now(), meta: m };
    return m;
  } catch {
    return null;
  }
}

async function decode(url: string, nx: number, ny: number, q: Quant): Promise<Float32Array | null> {
  const r = await fetch(url);
  if (!r.ok) return null;
  const bmp = await createImageBitmap(await r.blob());
  const c = document.createElement("canvas");
  c.width = nx;
  c.height = ny;
  const ctx = c.getContext("2d", { willReadFrequently: true });
  if (!ctx) return null;
  ctx.drawImage(bmp, 0, 0);
  const px = ctx.getImageData(0, 0, nx, ny).data;
  const out = new Float32Array(nx * ny);
  for (let row = 0; row < ny; row++) {
    const i = ny - 1 - row; // PNG row 0 = north; grid row 0 = south
    for (let j = 0; j < nx; j++) {
      const g = px[(row * nx + j) * 4] / 255;
      const v = q.min + g * (q.max - q.min);
      out[i * nx + j] = q.transform === "log1p" ? Math.expm1(v) : v;
    }
  }
  return out;
}

export async function fetchGfsGrid(hour: number, keys: string[]): Promise<GfsLoad> {
  if (!keys.length) return { grid: null, status: "" };
  const m = await getMeta(hour);
  if (!m?.ok || !m.grid || !m.quant || m.step == null) {
    return { grid: null, status: m?.status || m?.error || "loading" };
  }
  const { nx, ny, south, west, dlat, dlon } = m.grid;
  const fields: Record<string, (number | null)[]> = {};
  await Promise.all(
    keys.map(async (k) => {
      const ck = `${m.cycle}:${m.step}:${k}`;
      let arr = fieldCache.get(ck);
      if (!arr) {
        const q = m.quant![k];
        if (!q) return;
        const got = await decode(`${apiUrl(`/map/gfs/${k}.png`)}?step=${m.step}&cycle=${encodeURIComponent(m.cycle || "")}`, nx, ny, q);
        if (!got) return;
        arr = got;
        if (fieldCache.size > 24) fieldCache.clear();
        fieldCache.set(ck, arr);
      }
      fields[k] = Array.from(arr);
    })
  );
  if (fields.wind_u && fields.wind_v) {
    const u = fields.wind_u as number[];
    const v = fields.wind_v as number[];
    fields.wind_kmh = u.map((uu, i) => Math.hypot(uu, v[i]) * 3.6);
    fields.wind_dir_deg = u.map((uu, i) => ((Math.atan2(-uu, -v[i]) * 180) / Math.PI + 360) % 360);
  }
  if (!Object.keys(fields).length) return { grid: null, status: m.status || "empty" };
  return {
    grid: {
      nx,
      ny,
      lats: Array.from({ length: ny }, (_, i) => south + i * dlat),
      lons: Array.from({ length: nx }, (_, j) => west + j * dlon),
      hour,
      valid: m.valid,
      source: "NOAA GFS",
      fields,
    },
    status: "ok",
  };
}
