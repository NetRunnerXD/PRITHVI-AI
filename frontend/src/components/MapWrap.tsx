"use client";

import dynamic from "next/dynamic";
import type { Location } from "@/types/dashboard";
import type { Locale } from "@/i18n/copy";
import type { StormMapPack, StormMapTools } from "@/lib/api";
import type { WeatherGrid, WxLayer } from "@/lib/weatherScale";

const MapView = dynamic(() => import("./MapView").then((m) => m.MapView), { ssr: false });

export function MapWrap(props: {
  lat: number;
  lon: number;
  label: string;
  rainMm: number;
  zoom: number;
  basemap: string;
  nearby: Location[];
  overlays?: string[];
  storm?: StormMapPack | null;
  highlights?: string[];
  focusPin?: { lat: number; lon: number; zoom?: number } | null;
  selectedId?: string | null;
  tools?: StormMapTools;
  locale?: Locale;
  weatherLayer?: WxLayer;
  weatherGrid?: WeatherGrid | null;
  particles?: boolean;
  radarUrl?: string | null;
  onPick: (l: Location) => void;
}) {
  return <MapView {...props} />;
}
