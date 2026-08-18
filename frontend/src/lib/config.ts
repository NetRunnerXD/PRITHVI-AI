/**
 * API origin. This Next app is a client — FastAPI publishes the API on its own.
 * NEXT_PUBLIC_API_BASE empty → same-origin `/api` (optional Next rewrite).
 * Default is the standalone backend on :8000.
 */
const raw = process.env.NEXT_PUBLIC_API_BASE;
export const API_BASE = raw === undefined ? "http://127.0.0.1:8000" : String(raw).replace(/\/+$/, "");

export function apiUrl(path: string): string {
  let p = path.startsWith("/") ? path : `/${path}`;
  if (!p.startsWith("/api")) p = `/api${p}`;
  return API_BASE ? `${API_BASE}${p}` : p;
}
