"use client";

import { useMemo, useState } from "react";
import { COPY, type Locale } from "@/i18n/copy";
import type { DashboardSnapshot, Location } from "@/types/dashboard";
import { MapWrap } from "./MapWrap";

const LAYERS = ["positron", "streets", "satellite", "terrain"] as const;

export function SquareMap({
  dash,
  locale,
  onPick,
  focus,
}: {
  dash: DashboardSnapshot;
  locale: Locale;
  onPick: (l: Location) => void;
  focus?: { center: [number, number]; zoom?: number } | null;
}) {
  const t = COPY[locale];
  const [basemap, setBasemap] = useState<string>("positron");
  const [zoom, setZoom] = useState(focus?.zoom || dash.map.zoom || 8);
  const [overlays, setOverlays] = useState<string[]>([]);
  const [wide, setWide] = useState(true);
  const [copied, setCopied] = useState(false);
  const nearby = dash.ogd?.nearby || [];
  const rain = dash.predictive.precip_next_3d_mm;
  const box = useMemo(
    () => (
      <MapWrap
        lat={focus?.center[0] ?? dash.location.lat}
        lon={focus?.center[1] ?? dash.location.lon}
        label={dash.location.label}
        rainMm={rain}
        zoom={focus?.zoom ?? zoom}
        basemap={basemap}
        nearby={nearby}
        overlays={overlays}
        onPick={onPick}
      />
    ),
    [dash.location, rain, zoom, basemap, nearby, overlays, onPick, focus]
  );

  function toggleOverlay(id: string) {
    setOverlays((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  }

  function locate() {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition((pos) => {
      onPick({
        ...dash.location,
        lat: pos.coords.latitude,
        lon: pos.coords.longitude,
        label: "My location",
        id: "geo",
      });
    });
  }

  function copyCoords() {
    void navigator.clipboard.writeText(`${dash.location.lat.toFixed(4)}, ${dash.location.lon.toFixed(4)}`);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }

  return (
    <div className={`grid gap-3 ${wide ? "lg:grid-cols-[minmax(0,1fr)_16rem]" : "lg:grid-cols-1"}`}>
      <div className="neo p-2">
        <div className={`w-full overflow-hidden rounded-[16px] ${wide ? "h-[min(640px,70vh)]" : "aspect-square max-h-[520px]"}`}>
          {box}
        </div>
      </div>
      <div className="space-y-3">
        <section className="neo p-3">
          <p className="text-[11px] font-bold uppercase tracking-wide text-neo-muted">{t.layers}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {LAYERS.map((id) => (
              <button key={id} className={`neo-btn text-xs capitalize ${basemap === id ? "neo-btn-on" : ""}`} onClick={() => setBasemap(id)}>
                {id}
              </button>
            ))}
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <button className="neo-btn text-xs" onClick={() => setZoom((z) => Math.min(14, z + 1))}>+</button>
            <button className="neo-btn text-xs" onClick={() => setZoom((z) => Math.max(5, z - 1))}>−</button>
            <button className="neo-btn text-xs" onClick={() => setZoom(8)}>{t.reset}</button>
            <button className="neo-btn text-xs" onClick={locate}>{t.locate}</button>
            <button className="neo-btn text-xs" onClick={() => setWide((v) => !v)}>{t.fullscreen}</button>
          </div>
          <p className="mt-2 font-mono text-[11px] text-neo-muted">
            {dash.location.lat.toFixed(4)}, {dash.location.lon.toFixed(4)}
          </p>
          <button className="neo-btn mt-1 text-xs" onClick={copyCoords}>
            {copied ? t.copied : t.copyCoords}
          </button>
        </section>
        <section className="neo p-3">
          <p className="text-[11px] font-bold uppercase tracking-wide text-neo-muted">{t.bhuvan}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <button className={`neo-btn text-xs ${overlays.includes("bhuvan_geomorph") ? "neo-btn-on" : ""}`} onClick={() => toggleOverlay("bhuvan_geomorph")}>
              WB
            </button>
            <button className={`neo-btn text-xs ${overlays.includes("bhuvan_geomorph_in") ? "neo-btn-on" : ""}`} onClick={() => toggleOverlay("bhuvan_geomorph_in")}>
              IN
            </button>
          </div>
        </section>
        <section className="neo p-3">
          <p className="text-[11px] font-bold uppercase tracking-wide text-neo-muted">{t.nearbyList}</p>
          <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto text-sm">
            {nearby.map((n) => (
              <li key={n.id}>
                <button className="w-full rounded-lg px-2 py-1 text-left hover:bg-neo-bg" onClick={() => onPick(n)}>
                  {n.district}
                  <span className="ml-2 font-mono text-[10px] text-neo-muted">{n.lat.toFixed(2)}, {n.lon.toFixed(2)}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
