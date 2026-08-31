import type { ChatMsg, DashboardSnapshot, Location } from "@/types/dashboard";
import { apiUrl } from "./config";

export { apiUrl, API_BASE } from "./config";

export async function fetchNowcastLive(loc?: Location): Promise<Record<string, unknown> | null> {
  const q = new URLSearchParams();
  if (loc?.district) q.set("district", loc.district);
  if (loc?.place_name) q.set("place", loc.place_name);
  if (loc?.lat != null) q.set("lat", String(loc.lat));
  if (loc?.lon != null) q.set("lon", String(loc.lon));
  const qs = q.toString();
  const paths = ["/nowcast/live", "/nowcast-live", "/live-nowcast", "/nowcast"];
  for (const path of paths) {
    try {
      const r = await fetch(`${apiUrl(path)}?${qs}`);
      if (!r.ok) continue;
      const data = (await r.json()) as Record<string, unknown>;
      if (data.gap || data.hours || data.knots || data.nowcast) return data;
    } catch {
      continue;
    }
  }
  return null;
}

export async function fetchNowcastSat(
  loc?: Location,
  stride: 1 | 60 = 60
): Promise<Record<string, unknown> | null> {
  const q = new URLSearchParams();
  if (loc?.district) q.set("district", loc.district);
  if (loc?.place_name) q.set("place", loc.place_name);
  if (loc?.lat != null) q.set("lat", String(loc.lat));
  if (loc?.lon != null) q.set("lon", String(loc.lon));
  q.set("stride", String(stride));
  const qs = q.toString();
  const paths = ["/nowcast/sat", "/nowcast-sat"];
  for (const path of paths) {
    try {
      const r = await fetch(`${apiUrl(path)}?${qs}`);
      if (!r.ok) continue;
      const data = (await r.json()) as Record<string, unknown>;
      if (data.sat || data.formula || data.engine === "sat_kalman") return data;
    } catch {
      continue;
    }
  }
  return null;
}

export async function fetchDashboard(loc?: Location): Promise<DashboardSnapshot> {
  const q = new URLSearchParams();
  if (loc?.district) q.set("district", loc.district);
  if (loc?.place_name) q.set("place", loc.place_name);
  if (loc?.lat != null) q.set("lat", String(loc.lat));
  if (loc?.lon != null) q.set("lon", String(loc.lon));
  const r = await fetch(`${apiUrl("/dashboard")}?${q.toString()}`);
  if (!r.ok) throw new Error(`dashboard ${r.status}`);
  return r.json();
}

export async function searchPlaces(q: string): Promise<Location[]> {
  const r = await fetch(`${apiUrl("/geo/search")}?q=${encodeURIComponent(q)}`);
  if (!r.ok) return [];
  const data = await r.json();
  return data.results || [];
}

export async function reverseGeocode(lat: number, lon: number): Promise<Location> {
  const r = await fetch(`${apiUrl("/geo/reverse")}?lat=${lat}&lon=${lon}`);
  if (!r.ok) throw new Error(`reverse ${r.status}`);
  return r.json();
}

export type StormMapPack = {
  as_of?: string;
  as_of_ms?: number;
  state?: string;
  ok?: boolean;
  frame?: { south: number; west: number; north: number; east: number; lat: number; lon: number; n?: number; all_india?: boolean };
  strokes?: StormStroke[];
  past_strokes?: StormStroke[];
  past_cells?: {
    id?: string;
    lat: number;
    lon: number;
    kind?: string;
    place?: string;
    phase?: string;
    min_tb_k?: number;
    rain_ir_mm_h?: number;
    area_km2?: number;
    started_at?: string;
    closes_at?: string;
  }[];
  cells?: {
    id?: string;
    lat: number;
    lon: number;
    kind?: string;
    place?: string;
    min_tb_k?: number;
    rain_ir_mm_h?: number;
    trend?: string;
    area_km2?: number;
    p_lightning?: number;
    p_cloudburst?: number;
    ring?: number[][];
  }[];
  polygons?: StormPolygon[];
  predicted?: StormIncident[];
  predicted_storms?: StormIncident[];
  counts?: {
    lightning?: number;
    cloudburst?: number;
    downburst?: number;
    storm?: number;
    predicted?: number;
    predicted_storm?: number;
    past_lightning?: number;
    past_storm?: number;
    all?: number;
  };
  sensors?: Record<string, boolean | string>;
  imerg_mm_h?: number | null;
  incidents?: StormIncident[];
};

export type StormStroke = {
  lat: number;
  lon: number;
  distance_km?: number;
  t?: string | null;
  timestamp_utc?: string | null;
  past_mins?: number | null;
  place?: string;
  kind?: string;
  phase?: string;
  started_ms?: number;
  engine?: string;
  lead_h?: number;
};

export type StormPolygon = {
  id: string;
  kind?: string;
  lead_min?: number;
  ring: number[][];
  p_lightning?: number;
  place?: string;
  lat?: number;
  lon?: number;
  confidence?: number;
  confidence_band?: string;
};

export type StormIncident = {
  id: string;
  kind: string;
  lat: number;
  lon: number;
  place: string;
  started_at: string;
  closes_at: string;
  started_ms?: number;
  closes_ms?: number;
  lead_min?: number;
  phase?: string;
  trend?: string | null;
  rain_ir_mm_h?: number;
  min_tb_k?: number;
  p_lightning?: number;
  p_cloudburst?: number;
  engine?: string;
  remain_min?: number;
  lifetime_min?: number;
  ring?: number[][];
  confidence?: number;
  confidence_band?: string;
  t?: string | null;
  verify?: { weather_code?: number; precip_mm?: number; cape?: number; agrees?: boolean | null; note?: string };
};

export type StormMapTools = {
  overlayOpacity: number;
  showPin: boolean;
  pastHours: number;
  minConfidence: number;
  fitNonce: number;
};

export async function fetchStates(): Promise<string[]> {
  try {
    const r = await fetch(apiUrl("/states"));
    if (!r.ok) return [];
    const data = await r.json();
    return data.states || [];
  } catch {
    return [];
  }
}

export async function fetchWeatherGrid(hour = 0) {
  const r = await fetch(`${apiUrl("/map/weather-grid")}?hour=${hour}`);
  if (!r.ok) return null;
  return r.json();
}

export async function fetchRadarFrames() {
  const r = await fetch(apiUrl("/map/radar"));
  if (!r.ok) return null;
  return r.json() as Promise<{
    ok: boolean;
    host: string;
    radar: { time: number; path: string }[];
    satellite: { time: number; path: string }[];
  }>;
}

export async function fetchStormMap(state: string): Promise<StormMapPack | null> {
  const q = `state=${encodeURIComponent(state)}`;
  for (const path of ["/nowcast/storm-map", "/nowcast-storm-map"]) {
    try {
      const r = await fetch(`${apiUrl(path)}?${q}`);
      if (!r.ok) continue;
      return (await r.json()) as StormMapPack;
    } catch {
      continue;
    }
  }
  return null;
}

export async function fetchNearby(lat: number, lon: number): Promise<Location[]> {
  const r = await fetch(`${apiUrl("/geo/nearby")}?lat=${lat}&lon=${lon}&limit=6`);
  if (!r.ok) return [];
  return (await r.json()).results || [];
}

export async function fetchCompare(a: string, b: string) {
  const r = await fetch(`${apiUrl("/compare")}?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`);
  if (!r.ok) throw new Error("compare failed");
  return r.json();
}

export type SseHandler = (ev: Record<string, unknown>) => void;

export async function streamChat(
  message: string,
  location: Location | null,
  locale: string,
  history: ChatMsg[],
  onEvent: SseHandler,
  outputLocale?: string,
  regenerate?: boolean,
  conversationId?: string,
  llm?: string,
  showEvidence?: boolean
): Promise<ChatMsg | null> {
  const r = await fetch(apiUrl("/chat"), {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({
      message,
      locale_hint: locale,
      output_locale: outputLocale || "auto",
      location,
      history: history.slice(-6),
      regenerate: Boolean(regenerate),
      conversation_id: conversationId || undefined,
      llm: llm || undefined,
      show_evidence: Boolean(showEvidence),
    }),
  });
  if (!r.ok) throw new Error(`chat ${r.status}`);
  if (!r.body) throw new Error("no stream");
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  let final: ChatMsg | null = null;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() || "";
    for (const part of parts) {
      const line = part.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      try {
        const ev = JSON.parse(line.slice(6));
        onEvent(ev);
        if (ev.type === "final") final = ev.message as ChatMsg;
      } catch {
        /* ignore partial */
      }
    }
  }
  return final;
}
