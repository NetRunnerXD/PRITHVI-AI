"use client";

import { useEffect, useMemo } from "react";
import { ImageOverlay, useMap } from "react-leaflet";
import { colorAt, fieldKey, sampleGrid, type WeatherGrid, type WxLayer } from "@/lib/weatherScale";

function paint(grid: WeatherGrid, layer: WxLayer, key: string): string {
  const w = 960;
  const h = 420;
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return "";
  const img = ctx.createImageData(w, h);
  const data = img.data;
  const south = grid.lats[0];
  const north = grid.lats[grid.ny - 1];
  const west = grid.lons[0];
  const east = grid.lons[grid.nx - 1];
  for (let y = 0; y < h; y++) {
    const lat = north - ((north - south) * y) / (h - 1);
    for (let x = 0; x < w; x++) {
      const lon = west + ((east - west) * x) / (w - 1);
      const v = sampleGrid(grid, lat, lon, key);
      const [r, g, b, a] = colorAt(layer, v);
      const i = (y * w + x) * 4;
      data[i] = r;
      data[i + 1] = g;
      data[i + 2] = b;
      data[i + 3] = a;
    }
  }
  ctx.putImageData(img, 0, 0);
  return canvas.toDataURL("image/png");
}

export function WeatherOverlay({
  grid,
  layer,
  opacity,
}: {
  grid: WeatherGrid | null;
  layer: WxLayer;
  opacity: number;
}) {
  const key = fieldKey(layer);
  const url = useMemo(() => (grid && key ? paint(grid, layer, key) : ""), [grid, layer, key]);
  if (!grid || !key || !url) return null;
  const south = grid.lats[0];
  const north = grid.lats[grid.ny - 1];
  const west = grid.lons[0];
  const east = grid.lons[grid.nx - 1];
  return (
    <ImageOverlay
      url={url}
      bounds={[
        [south, west],
        [north, east],
      ]}
      opacity={opacity}
      zIndex={350}
    />
  );
}

export function WindParticles({
  grid,
  on,
}: {
  grid: WeatherGrid | null;
  on: boolean;
}) {
  const map = useMap();
  useEffect(() => {
    if (!on || !grid) return;
    const field = grid;
    const canvas = document.createElement("canvas");
    const pane = map.getPanes().overlayPane;
    canvas.style.position = "absolute";
    canvas.style.pointerEvents = "none";
    canvas.style.zIndex = "360";
    pane.appendChild(canvas);
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    type P = { lat: number; lon: number; age: number };
    let parts: P[] = [];
    let raf = 0;
    let dead = false;

    function sizeCanvas() {
      const b = map.getBounds();
      const nw = map.latLngToLayerPoint(b.getNorthWest());
      const se = map.latLngToLayerPoint(b.getSouthEast());
      canvas.width = Math.max(1, se.x - nw.x);
      canvas.height = Math.max(1, se.y - nw.y);
      canvas.style.width = `${canvas.width}px`;
      canvas.style.height = `${canvas.height}px`;
      canvas.style.left = `${nw.x}px`;
      canvas.style.top = `${nw.y}px`;
    }
    function spawn(): P {
      const b = map.getBounds();
      return {
        lat: b.getSouth() + Math.random() * (b.getNorth() - b.getSouth()),
        lon: b.getWest() + Math.random() * (b.getEast() - b.getWest()),
        age: Math.random() * 40,
      };
    }
    function tick() {
      if (dead || !ctx) return;
      sizeCanvas();
      ctx.globalCompositeOperation = "destination-out";
      ctx.fillStyle = "rgba(0,0,0,0.08)";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.globalCompositeOperation = "source-over";
      ctx.strokeStyle = "rgba(240,248,255,0.75)";
      ctx.lineWidth = 1.4;
      const n = Math.min(700, Math.floor((canvas.width * canvas.height) / 2200));
      while (parts.length < n) parts.push(spawn());
      const origin = map.getBounds().getNorthWest();
      const originPt = map.latLngToLayerPoint(origin);
      const zoomScale = Math.max(0.35, map.getZoom() / 5);
      for (const p of parts) {
        const u = sampleGrid(field, p.lat, p.lon, "wind_u");
        const v = sampleGrid(field, p.lat, p.lon, "wind_v");
        const spd = sampleGrid(field, p.lat, p.lon, "wind_kmh") ?? 0;
        const dir = sampleGrid(field, p.lat, p.lon, "wind_dir_deg");
        let ue = u;
        let vn = v;
        if ((ue == null || vn == null || (ue === 0 && vn === 0)) && dir != null) {
          const rad = (Number(dir) * Math.PI) / 180;
          const ms = Number(spd) / 3.6;
          ue = -ms * Math.sin(rad);
          vn = -ms * Math.cos(rad);
        }
        ue = ue ?? 0;
        vn = vn ?? 0;
        const pt = map.latLngToLayerPoint([p.lat, p.lon]);
        const x0 = pt.x - originPt.x;
        const y0 = pt.y - originPt.y;
        const dt = 0.012 * zoomScale;
        p.lat += vn * dt;
        p.lon += ue * dt * 1.15;
        p.age += 1;
        const pt2 = map.latLngToLayerPoint([p.lat, p.lon]);
        ctx.beginPath();
        ctx.moveTo(x0, y0);
        ctx.lineTo(pt2.x - originPt.x, pt2.y - originPt.y);
        ctx.stroke();
        const b = map.getBounds();
        if (p.age > 70 || p.lat < b.getSouth() || p.lat > b.getNorth() || p.lon < b.getWest() || p.lon > b.getEast()) {
          Object.assign(p, spawn());
        }
      }
      raf = window.requestAnimationFrame(tick);
    }
    sizeCanvas();
    parts = Array.from({ length: 360 }, spawn);
    map.on("zoomend moveend resize", sizeCanvas);
    raf = window.requestAnimationFrame(tick);
    return () => {
      dead = true;
      window.cancelAnimationFrame(raf);
      map.off("zoomend moveend resize", sizeCanvas);
      canvas.remove();
    };
  }, [map, grid, on]);
  return null;
}
