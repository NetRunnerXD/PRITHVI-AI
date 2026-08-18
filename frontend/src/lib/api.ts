import type { ChatMsg, DashboardSnapshot, Location } from "@/types/dashboard";
import { apiUrl } from "./config";

export { apiUrl, API_BASE } from "./config";

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
  return r.json();
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
  regenerate?: boolean
): Promise<ChatMsg | null> {
  const r = await fetch(apiUrl("/chat"), {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({
      message,
      locale_hint: locale,
      output_locale: outputLocale || locale,
      location,
      history: history.slice(-6),
      regenerate: Boolean(regenerate),
    }),
  });
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
