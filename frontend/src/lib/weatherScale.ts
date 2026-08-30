export type WxLayer = "wind" | "temp" | "precip" | "pressure" | "clouds" | "humidity" | "cape" | "radar" | "satellite";

export type WeatherGrid = {
  nx: number;
  ny: number;
  lats: number[];
  lons: number[];
  hour: number;
  valid?: string | null;
  source?: string;
  note?: string;
  fields: Record<string, (number | null)[]>;
};

export const WX_LAYERS: WxLayer[] = [
  "wind",
  "temp",
  "precip",
  "pressure",
  "clouds",
  "humidity",
  "cape",
  "radar",
  "satellite",
];

const STOPS: Record<string, [number, string][]> = {
  temp: [
    [-5, "#2c3e8c"],
    [10, "#3d8ec9"],
    [20, "#5ec4b6"],
    [26, "#f0e27a"],
    [32, "#e67e22"],
    [40, "#c0392b"],
    [48, "#6d1a4a"],
  ],
  precip: [
    [0, "rgba(0,0,0,0)"],
    [0.2, "rgba(80,180,255,0.25)"],
    [1, "rgba(40,120,220,0.55)"],
    [4, "rgba(80,40,180,0.7)"],
    [12, "rgba(220,40,140,0.85)"],
    [30, "rgba(180,20,40,0.95)"],
  ],
  wind: [
    [0, "#1b4f72"],
    [8, "#1a7a6d"],
    [18, "#7dbe3c"],
    [35, "#f4d03f"],
    [55, "#e67e22"],
    [80, "#922b21"],
  ],
  pressure: [
    [990, "#6c3483"],
    [1000, "#2471a3"],
    [1008, "#f4f6f7"],
    [1016, "#d68910"],
    [1028, "#922b21"],
  ],
  clouds: [
    [0, "rgba(255,255,255,0)"],
    [30, "rgba(220,230,240,0.25)"],
    [60, "rgba(200,210,220,0.5)"],
    [100, "rgba(180,190,200,0.8)"],
  ],
  humidity: [
    [10, "#8d6e63"],
    [40, "#cddc39"],
    [70, "#26a69a"],
    [95, "#1565c0"],
  ],
  cape: [
    [0, "rgba(0,0,0,0)"],
    [200, "#f9e79f"],
    [800, "#e67e22"],
    [2000, "#c0392b"],
    [3500, "#6c3483"],
  ],
};

export function fieldKey(layer: WxLayer): string | null {
  if (layer === "wind") return "wind_kmh";
  if (layer === "temp") return "temp_c";
  if (layer === "precip") return "precip_mm";
  if (layer === "pressure") return "pressure_hpa";
  if (layer === "clouds") return "cloud_pct";
  if (layer === "humidity") return "rh_pct";
  if (layer === "cape") return "cape";
  return null;
}

export function unitOf(layer: WxLayer): string {
  if (layer === "wind") return "km/h";
  if (layer === "temp") return "°C";
  if (layer === "precip") return "mm";
  if (layer === "pressure") return "hPa";
  if (layer === "clouds" || layer === "humidity") return "%";
  if (layer === "cape") return "J/kg";
  return "";
}

function parseColor(c: string): [number, number, number, number] {
  if (c.startsWith("rgba")) {
    const m = c.match(/[\d.]+/g) || [];
    return [Number(m[0] || 0), Number(m[1] || 0), Number(m[2] || 0), Number(m[3] ?? 1) * 255];
  }
  const h = c.replace("#", "");
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16), 220];
}

export function colorAt(layer: WxLayer, v: number | null): [number, number, number, number] {
  if (v == null || Number.isNaN(v)) return [0, 0, 0, 0];
  const stops = STOPS[layer === "radar" || layer === "satellite" ? "precip" : layer] || STOPS.temp;
  if (v <= stops[0][0]) return parseColor(stops[0][1]);
  if (v >= stops[stops.length - 1][0]) return parseColor(stops[stops.length - 1][1]);
  for (let i = 1; i < stops.length; i++) {
    const [aV, aC] = stops[i - 1];
    const [bV, bC] = stops[i];
    if (v <= bV) {
      const t = (v - aV) / (bV - aV || 1);
      const A = parseColor(aC);
      const B = parseColor(bC);
      return [A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t, A[2] + (B[2] - A[2]) * t, A[3] + (B[3] - A[3]) * t];
    }
  }
  return parseColor(stops[stops.length - 1][1]);
}

export function legendStops(layer: WxLayer): { v: number; color: string }[] {
  const stops = STOPS[layer === "radar" || layer === "satellite" ? "precip" : layer] || STOPS.temp;
  return stops.map(([v, color]) => ({ v, color }));
}

function idx(nx: number, i: number, j: number) {
  return i * nx + j;
}

export function sampleGrid(
  grid: WeatherGrid,
  lat: number,
  lon: number,
  key: string
): number | null {
  const { nx, ny, lats, lons, fields } = grid;
  const arr = fields[key];
  if (!arr || ny < 2 || nx < 2) return null;
  let x = lon;
  if (x > 180) x -= 360;
  if (x < -180) x += 360;
  if (lat < lats[0] || lat > lats[ny - 1] || x < lons[0] || x > lons[nx - 1]) return null;
  const dy = lats[1] - lats[0];
  const dx = lons[1] - lons[0];
  const fi = (lat - lats[0]) / dy;
  const fj = (x - lons[0]) / dx;
  const i0 = Math.max(0, Math.min(ny - 2, Math.floor(fi)));
  const j0 = Math.max(0, Math.min(nx - 2, Math.floor(fj)));
  const ti = fi - i0;
  const tj = fj - j0;
  const q11 = arr[idx(nx, i0, j0)];
  const q21 = arr[idx(nx, i0, j0 + 1)];
  const q12 = arr[idx(nx, i0 + 1, j0)];
  const q22 = arr[idx(nx, i0 + 1, j0 + 1)];
  if (q11 == null || q21 == null || q12 == null || q22 == null) return q11 ?? q21 ?? q12 ?? q22;
  const a = q11 * (1 - tj) + q21 * tj;
  const b = q12 * (1 - tj) + q22 * tj;
  return a * (1 - ti) + b * ti;
}
