import type { UnitSys } from "@/types/dashboard";
import type { Locale } from "@/i18n/copy";

export function localizeDigits(
  strOrNum: string | number | null | undefined,
  locale?: Locale | string
): string {
  if (strOrNum == null) return "";
  const s = String(strOrNum);
  if (locale === "hi") {
    const hiDigits = ["०", "१", "२", "३", "४", "५", "६", "७", "८", "९"];
    return s.replace(/[0-9]/g, (d) => hiDigits[Number(d)]);
  }
  if (locale === "bn") {
    const bnDigits = ["০", "১", "২", "৩", "৪", "৫", "৬", "৭", "৮", "৯"];
    return s.replace(/[0-9]/g, (d) => bnDigits[Number(d)]);
  }
  return s;
}

export function rain(mm: number | null | undefined, u: UnitSys, locale?: Locale | string): string {
  if (mm == null || Number.isNaN(Number(mm))) return "—";
  const n = Number(mm);
  const val = u === "imperial" ? (n / 25.4).toFixed(2) : n.toFixed(1);
  const unit = u === "imperial" ? "in" : "mm";
  return `${localizeDigits(val, locale)} ${unit}`;
}

export function temp(c: number | null | undefined, u: UnitSys, locale?: Locale | string): string {
  if (c == null || Number.isNaN(Number(c))) return "—";
  const n = Number(c);
  const val = u === "imperial" ? ((n * 9) / 5 + 32).toFixed(0) : n.toFixed(1);
  const unit = u === "imperial" ? "°F" : "°C";
  return `${localizeDigits(val, locale)}\u00A0${unit}`;
}

export function speed(kmh: number | null | undefined, u: UnitSys, locale?: Locale | string): string {
  if (kmh == null || Number.isNaN(Number(kmh))) return "—";
  const n = Number(kmh);
  const val = u === "imperial" ? (n * 0.621).toFixed(0) : n.toFixed(1);
  const unit = u === "imperial" ? "mph" : "km/h";
  return `${localizeDigits(val, locale)} ${unit}`;
}

export function dist(km: number | null | undefined, u: UnitSys, locale?: Locale | string): string {
  if (km == null || Number.isNaN(Number(km))) return "—";
  const n = Number(km);
  const val = u === "imperial" ? (n * 0.621).toFixed(1) : n.toFixed(1);
  const unit = u === "imperial" ? "mi" : "km";
  return `${localizeDigits(val, locale)} ${unit}`;
}

export function height(m: number | null | undefined, u: UnitSys, locale?: Locale | string): string {
  if (m == null || Number.isNaN(Number(m))) return "—";
  const n = Number(m);
  const val = u === "imperial" ? (n * 3.281).toFixed(1) : n.toFixed(1);
  const unit = u === "imperial" ? "ft" : "m";
  return `${localizeDigits(val, locale)} ${unit}`;
}

export function rainUnit(u: UnitSys) {
  return u === "imperial" ? "in" : "mm";
}
export function tempUnit(u: UnitSys) {
  return u === "imperial" ? "°F" : "°C";
}

