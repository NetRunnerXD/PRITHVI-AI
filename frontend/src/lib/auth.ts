import { apiUrl } from "./config";

export type AuthLocation = {
  lat: number;
  lon: number;
  place?: string | null;
  district?: string | null;
  state?: string | null;
  captured_at?: string | null;
  source?: string | null;
};

export type AuthUser = {
  id: string;
  phone: string;
  display_name: string;
  email?: string | null;
  sms_opt_in: boolean;
  location: AuthLocation | null;
};

const TOKEN_KEY = "prithvi.auth";

export function readToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function writeToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

async function authFetch(path: string, init: RequestInit = {}) {
  const token = readToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  const r = await fetch(apiUrl(path), { ...init, headers });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = body?.detail;
    let detail = r.statusText;
    if (typeof d === "string") detail = d;
    else if (Array.isArray(d)) {
      detail = d
        .map((x: { loc?: unknown[]; msg?: string }) => {
          const field = Array.isArray(x.loc) ? x.loc.filter((p) => p !== "body").join(".") : "";
          return field && x.msg ? `${field}: ${x.msg}` : x.msg || "";
        })
        .filter(Boolean)
        .join("; ") || r.statusText;
    }
    throw new Error(detail || "auth_error");
  }
  return body;
}

export async function registerAccount(p: {
  phone: string;
  password: string;
  display_name?: string;
  sms_opt_in: boolean;
  lat?: number;
  lon?: number;
  place?: string;
  email?: string;
}): Promise<{ token: string; user: AuthUser }> {
  const payload: Record<string, unknown> = {
    phone: p.phone.trim(),
    password: p.password,
    sms_opt_in: Boolean(p.sms_opt_in),
  };
  if (p.display_name?.trim()) payload.display_name = p.display_name.trim();
  if (p.email?.trim()) payload.email = p.email.trim();
  if (p.lat != null && p.lon != null) {
    payload.lat = p.lat;
    payload.lon = p.lon;
  }
  if (p.place?.trim()) payload.place = p.place.trim();
  const body = await authFetch("/auth/register", { method: "POST", body: JSON.stringify(payload) });
  writeToken(body.token);
  return body;
}

export async function loginAccount(phone: string, password: string): Promise<{ token: string; user: AuthUser }> {
  const body = await authFetch("/auth/login", { method: "POST", body: JSON.stringify({ phone, password }) });
  writeToken(body.token);
  return body;
}

export async function fetchMe(): Promise<AuthUser | null> {
  if (!readToken()) return null;
  try {
    const body = await authFetch("/auth/me");
    return body.user as AuthUser;
  } catch {
    writeToken(null);
    return null;
  }
}

export async function patchProfile(p: Partial<{ display_name: string; email: string; sms_opt_in: boolean }>): Promise<AuthUser> {
  const body = await authFetch("/auth/me", { method: "PATCH", body: JSON.stringify(p) });
  return body.user as AuthUser;
}

export async function patchAlertLocation(p: {
  lat: number;
  lon: number;
  place?: string;
  source?: "gps" | "manual";
}): Promise<AuthUser> {
  const body = await authFetch("/auth/me/location", { method: "PATCH", body: JSON.stringify(p) });
  return body.user as AuthUser;
}

export async function forgotPassword(phone: string) {
  return authFetch("/auth/forgot", { method: "POST", body: JSON.stringify({ phone }) });
}

export async function resetPassword(phone: string, otp: string, password: string): Promise<{ token: string; user: AuthUser }> {
  const body = await authFetch("/auth/reset", { method: "POST", body: JSON.stringify({ phone, otp, password }) });
  writeToken(body.token);
  return body;
}

export function logoutAccount() {
  writeToken(null);
}

export function gpsFix(): Promise<{ lat: number; lon: number } | null> {
  if (typeof navigator === "undefined" || !navigator.geolocation) return Promise.resolve(null);
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 },
    );
  });
}
