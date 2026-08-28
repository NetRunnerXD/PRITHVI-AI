import { createClient } from "../../clients/js/src";

export function apiBase(): string {
  const raw = process.env.EXPO_PUBLIC_API_BASE || "http://127.0.0.1:8000";
  return raw.replace(/\/+$/, "");
}

export const api = createClient({ baseUrl: apiBase() });
