/** Framework-free API origin. Works in Next, Vite, Expo, and React Native. */

export type ApiConfig = {
  /** Origin only, no trailing slash. Example: http://127.0.0.1:8000 */
  baseUrl: string;
  fetch?: typeof fetch;
};

export function normalizeBase(baseUrl: string): string {
  return (baseUrl || "").replace(/\/+$/, "");
}

export function joinApi(baseUrl: string, path: string): string {
  const base = normalizeBase(baseUrl);
  let p = path.startsWith("/") ? path : `/${path}`;
  if (!p.startsWith("/api")) p = `/api${p}`;
  return base ? `${base}${p}` : p;
}

export function withQuery(url: string, query?: Record<string, string | number | boolean | null | undefined>): string {
  if (!query) return url;
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null || v === "") continue;
    q.set(k, String(v));
  }
  const s = q.toString();
  return s ? `${url}?${s}` : url;
}
