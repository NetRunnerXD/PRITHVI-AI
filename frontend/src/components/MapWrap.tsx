"use client";

import dynamic from "next/dynamic";
import type { Location } from "@/types/dashboard";
import type { StormMapPack, StormMapTools } from "@/lib/api";

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
  onPick: (l: Location) => void;
}) {
  return <MapView {...props} />;
}
