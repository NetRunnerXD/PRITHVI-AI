import type { ChatMsg, DashboardSnapshot, Location } from "@/types/dashboard";
import { apiUrl } from "./config";
import { getLastOmPack, type OmClientPack } from "./openMeteoClient";
import type { ClientObsPack } from "./clientObs";
import { questionToEnglish } from "./mtClient";

export { apiUrl, API_BASE } from "./config";

export async function fetchNowcastLive(loc?: Location): Promise<Record<string, unknown> | null> {
  const q = new URLSearchParams();
  if (loc?.district) q.set("district", loc.district);
  if (loc?.place_name) q.set("place", loc.place_name);
  if (loc?.lat != null) q.set("lat", String(loc.lat));
  if (loc?.lon != null) q.set("lon", String(loc.lon));
  const qs = q.toString();
  try {
    const r = await fetch(`${apiUrl("/nowcast/live")}?${qs}`);
    if (!r.ok) return null;
    const data = (await r.json()) as Record<string, unknown>;
    if (data.gap || data.hours || data.knots || data.nowcast) return data;
  } catch {
    return null;
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
  try {
    const r = await fetch(`${apiUrl("/nowcast/sat")}?${qs}`);
    if (!r.ok) return null;
    const data = (await r.json()) as Record<string, unknown>;
    if (data.sat || data.formula || data.engine === "sat_kalman") return data;
  } catch {
    return null;
  }
  return null;
}

export async function fetchDashboard(
  loc?: Location,
  signal?: AbortSignal,
  disabled?: string[],
  om?: OmClientPack,
  obs?: ClientObsPack
): Promise<DashboardSnapshot> {
  const q = new URLSearchParams();
  if (loc?.district) q.set("district", loc.district);
  if (loc?.place_name) q.set("place", loc.place_name);
  if (loc?.lat != null) q.set("lat", String(loc.lat));
  if (loc?.lon != null) q.set("lon", String(loc.lon));
  if (disabled && disabled.length > 0) q.set("disable", disabled.join(","));

  if (om?.forecast) {
    const r = await fetch(apiUrl("/dashboard"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        location: loc || undefined,
        district: loc?.district,
        place: loc?.place_name,
        lat: loc?.lat,
        lon: loc?.lon,
        disable: disabled?.join(",") || undefined,
        om: {
          forecast: om.forecast,
          air: om.air || undefined,
          flood: om.flood || undefined,
          marine: om.marine || undefined,
          models: om.models || undefined,
          era5: om.era5 || undefined,
        },
        fetched_at: om.fetched_at,
        usgs_csv: obs?.usgs_csv || undefined,
        nasa_power: obs?.nasa_power || undefined,
      }),
      signal,
    });
    if (!r.ok) throw new Error(`dashboard ${r.status}`);
    return await r.json();
  }

  const r = await fetch(`${apiUrl("/dashboard")}?${q.toString()}`, { signal });
  if (!r.ok) throw new Error(`dashboard ${r.status}`);
  return await r.json();
}

export function pingReady(): void {
  void fetch(apiUrl("/ready"), { method: "GET", cache: "no-store" }).catch(() => undefined);
}

export async function searchPlaces(q: string, signal?: AbortSignal, local = false): Promise<Location[]> {
  const qs = new URLSearchParams({ q });
  if (local) qs.set("local", "true");
  const r = await fetch(`${apiUrl("/geo/search")}?${qs.toString()}`, { signal });
  if (!r.ok) return [];
  const data = await r.json();
  return data.results || [];
}

export type SpeechStatus = {
  stt: boolean;
  tts: boolean;
  stt_langs: string[];
  tts_langs: string[];
};

export async function fetchSpeechStatus(): Promise<SpeechStatus | null> {
  try {
    const r = await fetch(apiUrl("/speech/status"));
    if (!r.ok) return null;
    return (await r.json()) as SpeechStatus;
  } catch {
    return null;
  }
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
    occurred_at?: string;
    first_seen?: string;
    t?: string | null;
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
  predicted_unverified?: StormIncident[];
  fires?: {
    id: string;
    lat: number;
    lon: number;
    place?: string;
    n?: number;
    frp_mw?: number;
    phase?: string;
    title?: string;
    occurred_at?: string;
    occurred_ms?: number;
    first_seen?: string;
    t?: string | null;
  }[];
  landslides?: {
    id: string;
    lat: number;
    lon: number;
    place?: string;
    phase?: string;
    title?: string;
    window_start?: string | null;
    window_end?: string | null;
    occurred_at?: string;
    occurred_ms?: number;
    first_seen?: string;
    t?: string | null;
  }[];
  counts?: {
    lightning?: number;
    cloudburst?: number;
    downburst?: number;
    storm?: number;
    predicted?: number;
    predicted_storm?: number;
    past_lightning?: number;
    past_storm?: number;
    fire?: number;
    landslide?: number;
    all?: number;
  };
  sensors?: Record<string, boolean | string>;
  imerg_mm_h?: number | null;
  incidents?: StormIncident[];
  stale?: boolean;
  ingest_age_s?: number;
  need_second_frame?: boolean;
  past_h?: number;
  processing?: {
    ready?: boolean;
    message?: string;
    satellites?: { id?: string; name?: string; status?: string; detail?: string }[];
    age_s?: number | null;
  };
};

export type StormStroke = {
  lat: number;
  lon: number;
  distance_km?: number;
  t?: string | null;
  timestamp_utc?: string | null;
  past_mins?: number | null;
  occurred_at?: string;
  occurred_ms?: number;
  first_seen?: string;
  last_seen?: string;
  saved_at?: string;
  lead_h?: number;
  place?: string;
  kind?: string;
  phase?: string;
  started_ms?: number;
  engine?: string;
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
  label?: string;
  phase?: string;
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
  area_km2?: number;
  p_lightning?: number;
  p_cloudburst?: number;
  engine?: string;
  remain_min?: number;
  lifetime_min?: number;
  ring?: number[][];
  confidence?: number;
  confidence_band?: string;
  t?: string | null;
  occurred_at?: string;
  occurred_ms?: number;
  first_seen?: string;
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
  const { fetchClientWeatherGrid } = await import("./weatherGridClient");
  const local = await fetchClientWeatherGrid(hour);
  if (local?.ok && local.fields) return local;
  return null;
}

type RadarPack = {
  ok: boolean;
  host: string;
  radar: { time: number; path: string }[];
  satellite: { time: number; path: string }[];
};

function rainViewerPack(body: {
  host?: string;
  radar?: { past?: { time: number; path: string }[]; nowcast?: { time: number; path: string }[] };
  satellite?: { infrared?: { time: number; path: string }[] };
}): RadarPack {
  const radar = body.radar || {};
  const sat = body.satellite || {};
  const past = listOrEmpty(radar.past).slice(-8);
  const nowcast = listOrEmpty(radar.nowcast).slice(0, 4);
  const infrared = listOrEmpty(sat.infrared).slice(-4);
  return {
    ok: true,
    host: body.host || "https://tilecache.rainviewer.com",
    radar: [...past, ...nowcast],
    satellite: infrared,
  };
}

function listOrEmpty<T>(v: T[] | undefined): T[] {
  return Array.isArray(v) ? v : [];
}

export async function fetchRadarFrames(): Promise<RadarPack | null> {
  const { fetchClientRadar, rainViewerPack: packFn } = await import("./mapCatalog");
  const local = await fetchClientRadar();
  if (local?.ok && (local.radar.length || local.satellite.length)) return local;
  try {
    const r = await fetch(apiUrl("/map/radar"));
    if (r.ok) {
      const body = (await r.json()) as RadarPack & { ok?: boolean };
      if (body?.ok && (body.radar?.length || body.satellite?.length || body.host)) return body;
    }
  } catch {
    /* keep client miss */
  }
  try {
    const r = await fetch("https://api.rainviewer.com/public/weather-maps.json");
    if (!r.ok) return null;
    return packFn(await r.json());
  } catch {
    return null;
  }
}

export async function fetchStormMap(state: string, pastHours?: number): Promise<StormMapPack | null> {
  const params = new URLSearchParams({ state });
  if (pastHours != null) params.set("past_h", String(pastHours));
  const q = params.toString();
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
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), 180000);
  try {
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
        om: getLastOmPack()
          ? {
              forecast: getLastOmPack()!.forecast,
              air: getLastOmPack()!.air,
              flood: getLastOmPack()!.flood,
              marine: getLastOmPack()!.marine,
              models: getLastOmPack()!.models,
              era5: getLastOmPack()!.era5,
            }
          : undefined,
        fetched_at: getLastOmPack()?.fetched_at,
        question_en: await questionToEnglish(message, locale),
      }),
      signal: ac.signal,
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
  } finally {
    clearTimeout(timer);
  }
}
