/** Browser Open-Meteo relay. Connects out to the API; never accepts unknown hosts. */

const ALLOW = new Set([
  "api.open-meteo.com",
  "flood-api.open-meteo.com",
  "air-quality-api.open-meteo.com",
  "marine-api.open-meteo.com",
  "archive-api.open-meteo.com",
  "geocoding-api.open-meteo.com",
  "customer-api.open-meteo.com",
  "customer-flood-api.open-meteo.com",
  "customer-air-quality-api.open-meteo.com",
  "customer-marine-api.open-meteo.com",
  "customer-archive-api.open-meteo.com",
  "customer-geocoding-api.open-meteo.com",
]);

export const OM_TOKEN_KEY = "prithvi.omRelayToken";

export function omWsUrl(apiBase: string, token: string): string {
  const base = (apiBase || "").replace(/\/+$/, "");
  let ws: string;
  if (base.startsWith("https://")) ws = "wss://" + base.slice("https://".length);
  else if (base.startsWith("http://")) ws = "ws://" + base.slice("http://".length);
  else ws = (typeof location !== "undefined" && location.protocol === "https:" ? "wss://" : "ws://") + (typeof location !== "undefined" ? location.host : "127.0.0.1:8000") + (base || "");
  return `${ws}/api/om/worker?token=${encodeURIComponent(token)}`;
}

function okUrl(url: string): boolean {
  try {
    const u = new URL(url);
    return (u.protocol === "https:" || u.protocol === "http:") && ALLOW.has(u.hostname.toLowerCase()) && u.pathname.startsWith("/v1/");
  } catch {
    return false;
  }
}

export function startOmRelay(apiBase: string, token: string, onStatus: (on: boolean) => void): () => void {
  if (!token.trim()) {
    onStatus(false);
    return () => undefined;
  }
  let closed = false;
  let ws: WebSocket | null = null;
  let timer: number | undefined;

  function connect() {
    if (closed) return;
    try {
      ws = new WebSocket(omWsUrl(apiBase, token.trim()));
    } catch {
      onStatus(false);
      timer = window.setTimeout(connect, 8000);
      return;
    }
    ws.onopen = () => onStatus(true);
    ws.onclose = () => {
      onStatus(false);
      if (!closed) timer = window.setTimeout(connect, 5000);
    };
    ws.onerror = () => undefined;
    ws.onmessage = (ev) => {
      let msg: { type?: string; id?: string; url?: string; params?: Record<string, string> };
      try {
        msg = JSON.parse(String(ev.data));
      } catch {
        return;
      }
      if (msg.type !== "fetch" || !msg.id) return;
      const url = String(msg.url || "");
      if (!okUrl(url)) {
        ws?.send(JSON.stringify({ type: "error", id: msg.id, error: "url not allowlisted" }));
        return;
      }
      const u = new URL(url);
      const params = msg.params || {};
      Object.entries(params).forEach(([k, v]) => u.searchParams.set(k, String(v)));
      void fetch(u.toString())
        .then(async (r) => {
          if (!r.ok) throw new Error(`http ${r.status}`);
          const json = await r.json();
          ws?.send(JSON.stringify({ type: "result", id: msg.id, json }));
        })
        .catch((e) => {
          ws?.send(JSON.stringify({ type: "error", id: msg.id, error: String(e).slice(0, 240) }));
        });
    };
  }

  connect();
  return () => {
    closed = true;
    if (timer) window.clearTimeout(timer);
    try {
      ws?.close();
    } catch {
      /* ignore */
    }
    onStatus(false);
  };
}
