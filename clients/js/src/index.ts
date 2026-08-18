/**
 * Rituchakra HTTP client.
 * No React / Next / DOM. Use from a web app or React Native:
 *
 *   import { createClient } from "../clients/js/src";
 *   const api = createClient({ baseUrl: "http://127.0.0.1:8000" });
 */

import { joinApi, withQuery, type ApiConfig } from "./config";
import { readSse, type SseHandler } from "./sse";
import type { ChatMsg, ChatRequest, Health, LocQuery, Location, ServiceCard } from "./types";

export type { ApiConfig, ChatMsg, ChatRequest, Health, LocQuery, Location, ServiceCard, SseHandler };
export { joinApi } from "./config";

function locQuery(loc?: LocQuery | Location | null): Record<string, string | number | undefined> {
  if (!loc) return {};
  const place = "place_name" in loc ? loc.place_name : "place" in loc ? loc.place : undefined;
  return {
    district: loc.district,
    place: place || undefined,
    lat: loc.lat,
    lon: loc.lon,
  };
}

export function createClient(opts: ApiConfig) {
  const baseUrl = opts.baseUrl;
  const f = opts.fetch || globalThis.fetch.bind(globalThis);

  async function get<T>(path: string, query?: Record<string, string | number | boolean | null | undefined>): Promise<T> {
    const url = withQuery(joinApi(baseUrl, path), query);
    const r = await f(url);
    if (!r.ok) throw new Error(`${path} ${r.status}`);
    return r.json() as Promise<T>;
  }

  return {
    baseUrl,
    url: (path: string) => joinApi(baseUrl, path),

    health: () => get<Health>("/health"),
    catalog: () => get<ServiceCard>("/api"),
    ready: () => get<{ ok: boolean }>("/ready"),

    dashboard: (loc?: LocQuery | Location | null) => get<Record<string, unknown>>("/dashboard", locQuery(loc)),
    nowcast: (loc?: LocQuery | Location | null) => get<Record<string, unknown>>("/nowcast", locQuery(loc)),
    forecast: (loc?: LocQuery | Location | null) => get<Record<string, unknown>>("/forecast", locQuery(loc)),
    predictions: (loc?: LocQuery | Location | null, source = "both") =>
      get<Record<string, unknown>>("/predictions", { ...locQuery(loc), source }),
    outlook: (loc?: LocQuery | Location | null) => get<Record<string, unknown>>("/outlook", locQuery(loc)),
    risks: (loc?: LocQuery | Location | null) => get<Record<string, unknown>>("/risks", locQuery(loc)),
    science: (loc?: LocQuery | Location | null) => get<Record<string, unknown>>("/science", locQuery(loc)),
    insights: (loc?: LocQuery | Location | null) => get<Record<string, unknown>>("/insights", locQuery(loc)),

    searchPlaces: async (q: string): Promise<Location[]> => {
      const data = await get<{ results?: Location[] }>("/geo/search", { q });
      return data.results || [];
    },
    reverseGeocode: (lat: number, lon: number) => get<Location>("/geo/reverse", { lat, lon }),
    nearby: async (lat: number, lon: number, limit = 6): Promise<Location[]> => {
      const data = await get<{ results?: Location[] }>("/geo/nearby", { lat, lon, limit });
      return data.results || [];
    },
    mapLayers: () => get<Record<string, unknown>>("/map/layers"),
    wmsUrl: () => joinApi(baseUrl, "/map/wms"),

    compare: (a: string, b: string) => get<Record<string, unknown>>("/compare", { a, b }),
    states: () => get<{ states: string[] }>("/states"),
    districts: (state?: string) => get<Record<string, unknown>>("/districts", { state }),
    scan: (state: string, metric = "flood", limit = 30) => get<Record<string, unknown>>("/scan", { state, metric, limit }),

    async streamChat(body: ChatRequest, onEvent: SseHandler): Promise<ChatMsg | null> {
      const r = await f(joinApi(baseUrl, "/chat"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({
          message: body.message,
          locale_hint: body.locale_hint,
          output_locale: body.output_locale,
          location: body.location,
          history: (body.history || []).slice(-6),
          regenerate: Boolean(body.regenerate),
        }),
      });
      if (!r.ok) throw new Error(`chat ${r.status}`);
      let final: ChatMsg | null = null;
      await readSse(r.body, (ev) => {
        onEvent(ev);
        if (ev.type === "final") final = ev.message as ChatMsg;
      });
      return final;
    },
  };
}

export type RituchakraClient = ReturnType<typeof createClient>;
