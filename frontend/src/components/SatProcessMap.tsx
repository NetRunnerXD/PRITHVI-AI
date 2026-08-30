"use client";

import "leaflet/dist/leaflet.css";
import { useMemo, useState } from "react";
import { CircleMarker, ImageOverlay, MapContainer, Polygon, Polyline, Rectangle, TileLayer, WMSTileLayer, useMap } from "react-leaflet";
import { useEffect } from "react";
import type { VeraPack } from "@/types/dashboard";
import { apiUrl } from "@/lib/config";

const STAGES = [
  { id: "asia", title: "Asia frame" },
  { id: "india", title: "India crop" },
  { id: "mask", title: "Mask" },
  { id: "pin", title: "Pin patch" },
  { id: "cells", title: "Cells" },
  { id: "rain", title: "IR rain" },
  { id: "imerg", title: "IMERG" },
  { id: "motion", title: "Motion" },
  { id: "weights", title: "Gate RGB" },
] as const;

const GIBS = "https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi";

function Fit({ south, west, north, east }: { south: number; west: number; north: number; east: number }) {
  const map = useMap();
  useEffect(() => {
    map.fitBounds(
      [
        [south, west],
        [north, east],
      ],
      { padding: [24, 24], maxZoom: 7 }
    );
  }, [map, south, west, north, east]);
  return null;
}

export function SatProcessMap({ vera, lat, lon }: { vera: VeraPack; lat: number; lon: number }) {
  const m = vera.cv?.map;
  const [on, setOn] = useState<string[]>(["asia", "india", "pin", "cells"]);
  const stages = m?.stages || STAGES.map((s) => ({ id: s.id, title: s.title, note: "" }));
  const asia = m?.asia;
  const india = m?.india;
  const pin = m?.pin || { lat, lon };

  const caption = useMemo(() => {
    const missing: string[] = [];
    if (on.includes("rain") && !m?.rain_url) missing.push("IR rain raster not in this snapshot");
    if (on.includes("imerg") && !m?.imerg_wms && !m?.imerg_layer) missing.push("IMERG WMS not configured");
    if (on.includes("cells") && !(m?.cells || []).some((c) => c.lat != null && c.lon != null)) missing.push("no cells with lat/lon");
    if (on.includes("weights") && !(m?.gate_rgb || vera.gate?.weight_map_rgb)) missing.push("no gate RGB");
    const notes = stages
      .filter((s) => on.includes(s.id))
      .map((s) => `${s.title}: ${s.note || ""}`)
      .join(" · ");
    return [notes, missing.join(" · ")].filter(Boolean).join(" — ");
  }, [on, stages, m, vera.gate?.weight_map_rgb]);

  function tog(id: string) {
    setOn((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  }

  const irUrl = asia?.url ? (asia.url.startsWith("http") ? asia.url : apiUrl(asia.url.replace(/^\/api/, ""))) : undefined;
  const imergWms = m?.imerg_wms || GIBS;
  const imergLayer = m?.imerg_layer || "IMERG_Precipitation_Rate";
  const rainUrl = m?.rain_url;
  const gateRgb = m?.gate_rgb || vera.gate?.weight_map_rgb;
  const dx = Number(m?.amv?.dx || 0);
  const dy = Number(m?.amv?.dy || 0);

  const fitIndia = on.some((id) => ["india", "mask", "pin", "cells", "rain", "imerg", "motion", "weights"].includes(id)) && !on.includes("asia");
  const fitBox = fitIndia && india ? india : asia;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1">
        {STAGES.map((s) => (
          <button key={s.id} type="button" className={`neo-btn text-[11px] ${on.includes(s.id) ? "neo-btn-on" : ""}`} onClick={() => tog(s.id)}>
            {s.title}
          </button>
        ))}
      </div>
      <p className="text-[11px] text-neo-muted">{caption || "Select a processing stage."}</p>
      <div className="h-[420px] overflow-hidden rounded-2xl">
        <MapContainer center={[pin.lat, pin.lon]} zoom={5} className="h-full w-full" scrollWheelZoom>
          <TileLayer url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png" attribution="&copy; OSM &copy; CARTO" />
          {fitBox ? <Fit south={fitBox.south} west={fitBox.west} north={fitBox.north} east={fitBox.east} /> : null}
          {on.includes("asia") && asia && irUrl ? (
            <ImageOverlay
              url={irUrl}
              bounds={[[asia.south, asia.west], [asia.north, asia.east]]}
              opacity={0.78}
              crossOrigin="anonymous"
            />
          ) : null}
          {on.includes("asia") && asia ? (
            <Rectangle bounds={[[asia.south, asia.west], [asia.north, asia.east]]} pathOptions={{ color: "#1b4f72", weight: 1.5, fill: false, dashArray: "6 4" }} />
          ) : null}
          {on.includes("india") && india ? (
            <Rectangle bounds={[[india.south, india.west], [india.north, india.east]]} pathOptions={{ color: "#0e7c66", weight: 2.5, fillColor: "#0e7c66", fillOpacity: 0.06 }} />
          ) : null}
          {on.includes("mask") && india ? (
            <Rectangle bounds={[[india.south, india.west], [india.north, india.east]]} pathOptions={{ color: "#b9770e", weight: 2, dashArray: "2 6", fillColor: "#b9770e", fillOpacity: 0.05 }} />
          ) : null}
          {on.includes("pin") ? (
            <>
              <Rectangle
                bounds={[
                  [pin.lat - 0.55, pin.lon - 0.55],
                  [pin.lat + 0.55, pin.lon + 0.55],
                ]}
                pathOptions={{ color: "#146b7a", weight: 1, fillOpacity: 0.08 }}
              />
              <CircleMarker center={[pin.lat, pin.lon]} radius={14} pathOptions={{ color: "#146b7a", fillOpacity: 0.2 }} />
            </>
          ) : null}
          {on.includes("cells")
            ? (m?.cells || []).map((c, i) =>
                c.lat != null && c.lon != null ? (
                  <CircleMarker
                    key={i}
                    center={[c.lat, c.lon]}
                    radius={Math.max(6, Math.min(16, 6 + (c.rain_mmh || 0)))}
                    pathOptions={{ color: "#6c3483", fillColor: "#8e44ad", fillOpacity: 0.55, weight: 1 }}
                  />
                ) : null
              )
            : null}
          {on.includes("cells")
            ? (m?.cells || []).map((c, i) =>
                c.ring && c.ring.length > 2 ? (
                  <Polygon key={`r${i}`} positions={c.ring as [number, number][]} pathOptions={{ color: "#6c3483", weight: 2, fillColor: "#bb8fce", fillOpacity: 0.18 }} />
                ) : null
              )
            : null}
          {on.includes("rain") && rainUrl ? (
            <ImageOverlay
              url={rainUrl}
              bounds={[
                [pin.lat - 0.55, pin.lon - 0.55],
                [pin.lat + 0.55, pin.lon + 0.55],
              ]}
              opacity={0.75}
            />
          ) : null}
          {on.includes("imerg") ? (
            <WMSTileLayer
              url={imergWms}
              layers={imergLayer}
              format="image/png"
              transparent
              version="1.3.0"
              opacity={0.7}
              attribution="NASA GIBS / IMERG"
            />
          ) : null}
          {on.includes("motion") ? (
            <Polyline
              positions={[
                [pin.lat, pin.lon],
                [pin.lat + (dy || 0.35), pin.lon + (dx || 0.25)],
              ]}
              pathOptions={{ color: "#c0392b", weight: 4 }}
            />
          ) : null}
          {on.includes("weights") && gateRgb ? (
            <ImageOverlay
              url={gateRgb}
              bounds={[
                [pin.lat - 0.55, pin.lon - 0.55],
                [pin.lat + 0.55, pin.lon + 0.55],
              ]}
              opacity={0.75}
            />
          ) : null}
          <CircleMarker center={[pin.lat, pin.lon]} radius={5} pathOptions={{ color: "#fff", fillColor: "#146b7a", fillOpacity: 1 }} />
        </MapContainer>
      </div>
      <div className="flex flex-wrap gap-2 text-[10px] text-neo-muted">
        <span className="rounded-full bg-[#1b4f72]/15 px-2 py-0.5">Asia IR 40–110°E, 10°S–45°N (chrome cropped)</span>
        <span className="rounded-full bg-[#0e7c66]/15 px-2 py-0.5">India crop</span>
        <span className="rounded-full bg-[#6c3483]/15 px-2 py-0.5">Cells</span>
        <span className="rounded-full bg-[#1a5276]/15 px-2 py-0.5">IMERG rain</span>
        <span className="rounded-full bg-[#c0392b]/15 px-2 py-0.5">Motion</span>
      </div>
      <p className="text-[11px] text-neo-muted">
        Frame is the IMD Asiamer JPEG with title/colorbar stripped, stretched to 40–110°E / 10°S–45°N. Tb {vera.cv?.tb_k ?? "—"} K · AMV dx {m?.amv?.dx ?? "—"} dy {m?.amv?.dy ?? "—"}.
      </p>
    </div>
  );
}
