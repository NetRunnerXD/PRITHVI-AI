"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Circle,
  CircleMarker,
  GeoJSON,
  MapContainer,
  Marker,
  Polygon,
  Popup,
  Rectangle,
  ScaleControl,
  TileLayer,
  WMSTileLayer,
  useMap,
  useMapEvents,
} from "react-leaflet";
import L from "leaflet";
import type { Location } from "@/types/dashboard";
import { COPY, type Locale } from "@/i18n/copy";
import type { StormIncident, StormMapPack, StormMapTools, StormStroke } from "@/lib/api";
import { apiUrl, reverseGeocode } from "@/lib/api";
import { WeatherOverlay, WindParticles } from "./WeatherOverlay";
import { fieldKey, sampleGrid, unitOf, type WeatherGrid, type WxLayer } from "@/lib/weatherScale";

function normalizeStateName(s?: string | null): string {
  const n = (s || "").trim().toLowerCase();
  if (!n || n === "all" || n === "all india") return "";
  const map: Record<string, string> = {
    "orissa": "odisha",
    "uttaranchal": "uttarakhand",
    "pondicherry": "puducherry",
    "wb": "west bengal",
    "bengal": "west bengal",
    "up": "uttar pradesh",
    "mp": "madhya pradesh",
    "ap": "andhra pradesh",
    "ts": "telangana",
    "tg": "telangana",
    "tn": "tamil nadu",
    "hp": "himachal pradesh",
    "uk": "uttarakhand",
    "j&k": "jammu and kashmir",
    "jk": "jammu and kashmir",
    "la": "ladakh",
    "a&n": "andaman and nicobar islands",
    "andaman": "andaman and nicobar islands",
    "andaman and nicobar": "andaman and nicobar islands",
    "dnh": "dadra and nagar haveli and daman and diu",
    "dnhdd": "dadra and nagar haveli and daman and diu",
    "daman and diu": "dadra and nagar haveli and daman and diu",
    "dadra and nagar haveli": "dadra and nagar haveli and daman and diu",
  };
  return map[n] || n;
}

let cachedStatesGeoJson: any = null;
let cachedCountryGeoJson: any = null;

function IndiaCountryBoundary() {
  const [geoData, setGeoData] = useState<any>(cachedCountryGeoJson);

  useEffect(() => {
    if (cachedCountryGeoJson) return;
    let dead = false;
    fetch("/india_country_simplified.json")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!dead && data) {
          cachedCountryGeoJson = data;
          setGeoData(data);
        }
      })
      .catch(() => {});
    return () => {
      dead = true;
    };
  }, []);

  if (!geoData) return null;

  return (
    <GeoJSON
      key="india-country-boundary"
      data={geoData}
      style={{
        color: "#38bdf8",
        weight: 2.2,
        opacity: 0.9,
        fillColor: "#0284c7",
        fillOpacity: 0.02,
        dashArray: "5 4",
      }}
      onEachFeature={(_f, layer) => {
        layer.bindTooltip("India (Official Boundary · PoK & CoK included)", { sticky: true, opacity: 0.9 });
      }}
    />
  );
}

function StateBoundaryHighlight({ stateName }: { stateName?: string | null }) {
  const norm = normalizeStateName(stateName);
  const [geoData, setGeoData] = useState<any>(cachedStatesGeoJson);

  useEffect(() => {
    if (cachedStatesGeoJson) return;
    let dead = false;
    fetch("/india_states_simplified.json")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!dead && data) {
          cachedStatesGeoJson = data;
          setGeoData(data);
        }
      })
      .catch(() => {});
    return () => {
      dead = true;
    };
  }, []);

  const feature = useMemo(() => {
    if (!geoData || !norm || norm === "india") return null;
    return (
      geoData.features?.find((f: any) => {
        const fn = normalizeStateName(f.properties?.name);
        return fn === norm || fn.includes(norm) || norm.includes(fn);
      }) || null
    );
  }, [geoData, norm]);

  if (!feature) return null;

  return (
    <GeoJSON
      key={`state-${norm}`}
      data={feature}
      style={{
        color: "#38bdf8",
        weight: 2.4,
        opacity: 0.95,
        fillColor: "#0284c7",
        fillOpacity: 0,
        dashArray: "6 4",
      }}
      onEachFeature={(_f, layer) => {
        layer.bindTooltip(stateName || "State", { sticky: true, opacity: 0.9 });
      }}
    />
  );
}

const pin = L.divIcon({
  className: "",
  html: `<div style="width:14px;height:14px;border-radius:999px;background:#3a7ca5;border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,.25)"></div>`,
  iconSize: [14, 14],
  iconAnchor: [7, 7],
});

const pastStrikeIcon = L.divIcon({
  className: "",
  html: `<div style="width:20px;height:20px;border-radius:999px;background:#334155;border:1.5px solid #cbd5e1;display:flex;align-items:center;justify-content:center;color:#facc15;font-size:12px;box-shadow:0 1px 4px rgba(0,0,0,.4)">⚡</div>`,
  iconSize: [20, 20],
  iconAnchor: [10, 10],
});

const pastStormIcon = L.divIcon({
  className: "",
  html: `<div style="width:22px;height:22px;border-radius:999px;background:#1e293b;border:1.5px dashed #94a3b8;display:flex;align-items:center;justify-content:center;box-shadow:0 1px 4px rgba(0,0,0,.4)"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/></svg></div>`,
  iconSize: [22, 22],
  iconAnchor: [11, 11],
});

const liveStrikeIcon = L.divIcon({
  className: "",
  html: `<div style="width:18px;height:18px;display:flex;align-items:center;justify-content:center;color:#f5c542;font-size:16px;text-shadow:0 0 8px #f5c542">⚡</div>`,
  iconSize: [18, 18],
  iconAnchor: [9, 9],
});

const predStrikeIcon = L.divIcon({
  className: "",
  html: `<div style="width:16px;height:16px;display:flex;align-items:center;justify-content:center;color:#f39c12;font-size:14px;text-shadow:0 0 6px #f39c12">✦</div>`,
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

const predStormIcon = L.divIcon({
  className: "",
  html: `<div style="width:16px;height:16px;display:flex;align-items:center;justify-content:center;color:#8e44ad;font-size:14px">◆</div>`,
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

function Recenter({ lat, lon, zoom }: { lat: number; lon: number; zoom: number }) {
  const map = useMap();
  useEffect(() => {
    map.setView([lat, lon], zoom);
  }, [map, lat, lon, zoom]);
  return null;
}

function FitFrame({
  frame,
}: {
  frame?: { south: number; west: number; north: number; east: number } | null;
}) {
  const map = useMap();
  useEffect(() => {
    if (!frame) return;
    map.fitBounds(
      [
        [frame.south, frame.west],
        [frame.north, frame.east],
      ],
      { padding: [28, 28], maxZoom: frame.north - frame.south > 20 ? 5 : 9 }
    );
  }, [map, frame?.south, frame?.west, frame?.north, frame?.east]);
  return null;
}

function FitEvents({ nonce, points }: { nonce: number; points: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (!nonce || points.length < 1) return;
    map.fitBounds(points, { padding: [36, 36], maxZoom: 8 });
    // points are read for this nonce only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, nonce]);
  return null;
}

function Click({ onPick }: { onPick: (l: Location) => void }) {
  useMapEvents({
    click: async (e) => {
      try {
        const loc = await reverseGeocode(e.latlng.lat, e.latlng.lng);
        onPick({ ...loc, lat: e.latlng.lat, lon: e.latlng.lng });
      } catch {
        /* outside India or reverse failed */
      }
    },
  });
  return null;
}

function CursorReadout({
  grid,
  layer,
}: {
  grid?: WeatherGrid | null;
  layer?: WxLayer | null;
}) {
  const [txt, setTxt] = useState("");
  useMapEvents({
    mousemove: (e) => {
      const lat = e.latlng.lat;
      const lon = e.latlng.lng;
      let extra = "";
      const key = layer ? fieldKey(layer) : null;
      if (grid && key) {
        const v = sampleGrid(grid, lat, lon, key);
        if (v != null) extra = ` · ${v.toFixed(layer === "precip" ? 2 : 1)} ${unitOf(layer!)}`;
      }
      setTxt(`${lat.toFixed(3)}, ${lon.toFixed(3)}${extra}`);
    },
    mouseout: () => setTxt(""),
  });
  if (!txt) return null;
  return (
    <div className="pointer-events-none absolute bottom-7 left-2 z-[500] rounded-md bg-neo-card/90 px-2 py-0.5 font-mono text-[10px] text-neo-text shadow">
      {txt}
    </div>
  );
}

const BASE: Record<string, { url: string; attr: string; subdomains?: string; maxZoom?: number }> = {
  positron: {
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attr: "© OpenStreetMap",
    subdomains: "abc",
    maxZoom: 19,
  },
  streets: {
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attr: "© OpenStreetMap",
    subdomains: "abc",
    maxZoom: 19,
  },
  satellite: {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr: "Tiles © Esri",
    maxZoom: 18,
  },
  terrain: {
    url: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
    attr: "© OpenTopoMap",
    subdomains: "abc",
    maxZoom: 17,
  },
  dark: {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    attr: "Tiles © Esri",
    maxZoom: 16,
  },
};

const CELL_COLOR: Record<string, string> = {
  cloudburst: "#c0392b",
  downburst: "#e67e22",
  storm: "#8e44ad",
  cloud: "#2980b9",
  lightning: "#f1c40f",
  fire: "#ea580c",
  landslide: "#92400e",
};

function eventIcon(opts: {
  kind: string;
  phase?: string;
  selected?: boolean;
  count?: number;
}) {
  const kind = opts.kind || "storm";
  const phase = opts.phase || "live";
  const color = CELL_COLOR[kind] || "#64748b";
  const glyph =
    kind === "lightning" ? "⚡" :
    kind === "fire" ? "🔥" :
    kind === "landslide" ? "⛰" :
    kind === "cloudburst" ? "💧" :
    kind === "downburst" ? "↘" :
    phase === "predicted" ? "✦" : "☁";
  const live = phase === "live" || phase === "active";
  const past = phase === "past";
  const size = opts.selected ? 32 : past ? 20 : 26;
  const ring = live
    ? `<div style="position:absolute;inset:0;border-radius:9999px;border:2px solid ${color};opacity:.55;animation:ping 1.8s cubic-bezier(0,0,.2,1) infinite"></div>`
    : phase === "predicted"
      ? `<div style="position:absolute;inset:1px;border-radius:9999px;border:2px dashed ${color};opacity:.9"></div>`
      : "";
  const badge = opts.count && opts.count > 1
    ? `<span style="position:absolute;top:-4px;right:-4px;min-width:14px;height:14px;padding:0 3px;border-radius:9999px;background:#0f172a;color:#fff;font:700 9px/14px ui-sans-serif;border:1px solid ${color}">${opts.count > 99 ? "99+" : opts.count}</span>`
    : "";
  const bg = past ? "#334155" : "#0f172a";
  return L.divIcon({
    className: "prithvi-event-icon",
    html: `<div style="position:relative;width:${size}px;height:${size}px;filter:${opts.selected ? "drop-shadow(0 0 8px " + color + ")" : "none"}">
      ${ring}
      <div style="position:absolute;inset:${live ? 5 : 3}px;border-radius:9999px;background:${bg};border:2px solid ${past ? "#94a3b8" : "#fff"};display:flex;align-items:center;justify-content:center;font-size:${past ? 11 : 13}px;box-shadow:0 0 10px ${color}99">${glyph}</div>
      ${badge}
    </div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

const GIBS = "https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi";

function rainRadiusM(mm: number) {
  return Math.min(10_000, 2_000 + Math.max(0, Number(mm) || 0) * 60);
}

function cellRadiusM(areaKm2: number) {
  const rKm = Math.sqrt(Math.max(Number(areaKm2) || 20, 20) / Math.PI);
  return Math.min(18_000, Math.max(3_500, rKm * 1_000));
}

function metresPerPixel(lat: number, zoom: number) {
  return (156543.03392 * Math.cos((lat * Math.PI) / 180)) / 2 ** zoom;
}

/** Geographic size, but never smaller than ~8px or (when zoomed out) larger than ~18px. */
function visibleRadiusM(geoM: number, lat: number, zoom: number) {
  const mpp = metresPerPixel(lat, zoom);
  const minM = 8 * mpp;
  const maxM = zoom <= 6 ? 18 * mpp : zoom <= 8 ? 36 * mpp : 1e12;
  return Math.min(maxM, Math.max(geoM, minM));
}

function ZoomCircle({
  center,
  geoRadius,
  pathOptions,
  children,
}: {
  center: [number, number];
  geoRadius: number;
  pathOptions: Record<string, unknown>;
  children?: ReactNode;
}) {
  const map = useMap();
  const [r, setR] = useState(() => visibleRadiusM(geoRadius, center[0], map.getZoom()));
  useMapEvents({
    zoom: () => setR(visibleRadiusM(geoRadius, center[0], map.getZoom())),
    zoomend: () => setR(visibleRadiusM(geoRadius, center[0], map.getZoom())),
  });
  useEffect(() => {
    setR(visibleRadiusM(geoRadius, center[0], map.getZoom()));
  }, [geoRadius, center, map]);
  return (
    <Circle center={center} radius={r} pathOptions={pathOptions}>
      {children}
    </Circle>
  );
}

function parseTimeMs(raw: unknown): number | null {
  if (typeof raw === "number" && Number.isFinite(raw)) {
    return raw < 1e12 ? raw * 1000 : raw;
  }
  if (typeof raw === "string" && raw.trim()) {
    const s = raw.trim();
    const t = Date.parse(/[zZ]|[+-]\d{2}:?\d{2}$/.test(s) ? s : `${s}Z`);
    if (!Number.isNaN(t)) return t;
  }
  return null;
}

/** Age of a past observation. Occurrence time only — never window close (often still in the future). */
function eventAgeMs(s: Record<string, unknown>, now: number): number | null {
  if (typeof s.occurred_ms === "number" && Number.isFinite(s.occurred_ms)) {
    return Math.max(0, now - (s.occurred_ms < 1e12 ? s.occurred_ms * 1000 : s.occurred_ms));
  }
  if (typeof s.past_mins === "number" && Number.isFinite(s.past_mins)) return Math.max(0, s.past_mins * 60_000);
  if (typeof s.lead_h === "number" && s.lead_h < 0) return Math.max(0, Math.abs(s.lead_h) * 3600_000);
  const stamps = [s.occurred_at, s.last_seen, s.t, s.timestamp_utc, s.closes_at, s.first_seen, s.started_at, s.started_ms, s.saved_at];
  for (const raw of stamps) {
    const t = parseTimeMs(raw);
    if (t != null && t <= now + 120_000) return Math.max(0, now - t);
  }
  return null;
}

function inPastWindow(s: Record<string, unknown>, now: number, pastMs: number): boolean {
  const age = eventAgeMs(s, now);
  if (age == null) return false;
  return age <= pastMs;
}

function fmtIst(raw: unknown): string | null {
  const t = parseTimeMs(raw);
  if (t == null) return typeof raw === "string" && raw ? raw : null;
  return new Date(t).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", hour12: false });
}

function fmtIstHm(raw: unknown): string | null {
  const t = parseTimeMs(raw);
  if (t == null) return null;
  return new Date(t).toLocaleTimeString("en-IN", {
    timeZone: "Asia/Kolkata",
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
  });
}

function confOk(row: { confidence?: number; confidence_band?: string } | undefined, min: number) {
  if (!min) return true;
  if (row?.confidence_band === "low" && min >= 0.38) return false;
  return (row?.confidence ?? 0) >= min;
}

const DEFAULT_TOOLS: StormMapTools = {
  overlayOpacity: 0.7,
  showPin: true,
  pastHours: 6,
  minConfidence: 0,
  fitNonce: 0,
};

const NAMED_POLY = new Set(["storm", "cloud", "cloudburst", "downburst", "lightning", "fire", "landslide"]);

function polygonHighlightOn(
  p: { kind?: string; lead_min?: number; label?: string; place?: string; phase?: string },
  highlights: string[]
): boolean {
  if (!highlights || !highlights.length) return false;
  const kind = p.kind || "storm";
  if (!NAMED_POLY.has(kind)) return false;
  if (!(p.label || p.place)) return false;

  const phase = p.phase || ((p.lead_min || 0) > 0 ? "predicted" : "live");

  if (phase === "past") {
    if (kind === "lightning") return highlights.includes("past_lightning");
    return highlights.includes("past_storm");
  }

  if (phase === "predicted" || (p.lead_min || 0) > 0) {
    if (kind === "lightning") return highlights.includes("pred_lightning");
    if (kind === "storm") return highlights.includes("pred_storm");
    if (kind === "cloudburst") return highlights.includes("cloudburst");
    if (kind === "downburst") return highlights.includes("downburst");
    if (kind === "cloud") return highlights.includes("cloud");
    return highlights.includes("pred_storm");
  }

  // Live hazards
  if (kind === "lightning") return highlights.includes("lightning");
  if (kind === "storm") return highlights.includes("storm");
  if (kind === "cloudburst") return highlights.includes("cloudburst");
  if (kind === "downburst") return highlights.includes("downburst");
  if (kind === "cloud") return highlights.includes("cloud");
  if (kind === "fire") return highlights.includes("fire");
  if (kind === "landslide") return highlights.includes("landslide");

  return false;
}

export function MapView({
  lat,
  lon,
  label,
  rainMm,
  zoom,
  basemap,
  nearby,
  overlays = [],
  storm,
  highlights = [],
  focusPin,
  selectedId,
  tools,
  locale,
  weatherLayer,
  weatherGrid,
  particles,
  radarUrl,
  hazardEvents,
  onPick,
  onSelectIncident,
}: {
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
  weatherLayer?: WxLayer | null;
  weatherGrid?: WeatherGrid | null;
  particles?: boolean;
  radarUrl?: string | null;
  hazardEvents?: {
    id: string;
    kind: string;
    lat: number;
    lon: number;
    place?: string;
    phase?: string;
    title?: string;
    n?: number;
    frp_mw?: number;
    window_start?: string | null;
    window_end?: string | null;
  }[];
  onPick: (l: Location) => void;
  onSelectIncident?: (inc: StormIncident) => void;
}) {
  const t = COPY[locale || "en"];
  const opt = tools || DEFAULT_TOOLS;
  const tile = BASE[basemap] || BASE.positron;
  const frame = storm?.frame;
  const showIr = overlays.includes("gibs_ir") || (weatherLayer === "satellite" && !radarUrl);
  const showImerg = overlays.includes("gibs_imerg");
  const showField = weatherLayer && fieldKey(weatherLayer) && weatherGrid;
  const now = Date.now();
  const pastMs = Math.max(1, opt.pastHours) * 3600_000;

  const pastStrokes = useMemo(() => {
    const raw = [
      ...(storm?.past_strokes || []),
      ...(storm?.strokes || []),
      ...((storm?.incidents || []).filter((i) => i.phase === "past" && i.kind === "lightning") as StormStroke[]),
    ];
    const seen = new Set<string>();
    const out: StormStroke[] = [];
    for (const s of raw) {
      if (s.lat == null || s.lon == null) continue;
      const key = `${s.lat.toFixed(3)}:${s.lon.toFixed(3)}:${s.t || s.timestamp_utc || ""}`;
      if (seen.has(key)) continue;
      seen.add(key);
      if (!inPastWindow(s as unknown as Record<string, unknown>, now, pastMs)) continue;
      out.push(s);
    }
    return out;
  }, [storm, now, pastMs]);

  const predLtn = [
    ...(storm?.predicted || []),
    ...((storm?.predicted_unverified || []).filter((s) => s.kind === "lightning")),
  ].filter((s) => confOk(s, opt.minConfidence));
  const predStorms = [
    ...(storm?.predicted_storms || []),
    ...((storm?.predicted_unverified || []).filter((s) => s.kind !== "lightning")),
  ].filter((s) => confOk(s, opt.minConfidence));

  const liveByKind = (kind: string) => {
    const fromCells = (storm?.cells || []).filter((c) => (c.kind || "storm") === kind);
    const fromInc = (storm?.incidents || []).filter(
      (i) => (i.phase || "live") === "live" && i.kind === kind,
    );
    const seen = new Set<string>();
    const out: { lat: number; lon: number; id?: string; kind?: string; place?: string; rain_ir_mm_h?: number; min_tb_k?: number; area_km2?: number }[] = [];
    for (const c of [...fromCells, ...fromInc]) {
      if (c.lat == null || c.lon == null) continue;
      const key = `${c.lat.toFixed(3)}:${c.lon.toFixed(3)}:${c.kind || kind}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(c);
    }
    return out;
  };

  const pastCells = useMemo(() => {
    const raw = storm?.past_cells || [];
    return raw.filter((c) => {
      if (c.lat == null || c.lon == null) return false;
      const kind = String(c.kind || "storm");
      if (kind === "lightning") return false;
      return inPastWindow(c as unknown as Record<string, unknown>, now, pastMs);
    });
  }, [storm, now, pastMs]);

  const fitPts = useMemo(() => {
    const pts: [number, number][] = [];
    if (highlights.includes("past_lightning")) pastStrokes.forEach((s) => pts.push([s.lat, s.lon]));
    if (highlights.includes("pred_lightning")) predLtn.forEach((s) => pts.push([s.lat, s.lon]));
    if (highlights.includes("pred_storm")) predStorms.forEach((s) => pts.push([s.lat, s.lon]));
    if (highlights.includes("past_storm")) pastCells.forEach((s) => pts.push([s.lat, s.lon]));
    (storm?.cells || []).forEach((c) => {
      if (highlights.includes(c.kind || "storm") || (c.kind === "lightning" && highlights.includes("lightning"))) {
        pts.push([c.lat, c.lon]);
      }
    });
    return pts;
  }, [highlights, pastStrokes, predLtn, predStorms, pastCells, storm]);

  return (
    <MapContainer
      center={[lat, lon]}
      zoom={zoom}
      minZoom={3}
      maxZoom={18}
      preferCanvas
      maxBounds={[
        [-85, -180],
        [85, 180],
      ]}
      maxBoundsViscosity={1.0}
      worldCopyJump={false}
      className="relative h-full w-full"
      scrollWheelZoom
    >
      <TileLayer
        attribution={tile.attr}
        url={tile.url}
        subdomains={tile.subdomains || "abc"}
        noWrap={true}
        maxZoom={tile.maxZoom || 18}
      />
      <ScaleControl imperial={false} position="bottomleft" />
      {showField ? <WeatherOverlay grid={weatherGrid!} layer={weatherLayer!} opacity={opt.overlayOpacity} /> : null}
      {particles && weatherGrid ? <WindParticles grid={weatherGrid} on /> : null}
      {radarUrl ? (
        <TileLayer
          url={radarUrl}
          opacity={opt.overlayOpacity}
          attribution="RainViewer"
          pane="overlayPane"
          noWrap={true}
          maxZoom={18}
        />
      ) : null}
      {showIr ? (
        <WMSTileLayer
          url={GIBS}
          layers="Himawari_AHI_Band13_Clean_Infrared"
          format="image/png"
          transparent
          version="1.3.0"
          opacity={opt.overlayOpacity}
          attribution="NASA GIBS / Himawari IR"
          noWrap={true}
        />
      ) : null}
      {showImerg ? (
        <WMSTileLayer
          url={GIBS}
          layers="IMERG_Precipitation_Rate"
          format="image/png"
          transparent
          version="1.3.0"
          opacity={Math.max(0.2, opt.overlayOpacity - 0.08)}
          attribution="NASA GIBS / IMERG"
          noWrap={true}
        />
      ) : null}
      {overlays.includes("bhuvan_geomorph") ? (
        <WMSTileLayer
          url={apiUrl("/map/wms")}
          layers="gw_wfs:WB_LGEOM"
          format="image/png"
          transparent
          version="1.1.1"
          attribution="© NRSC / ISRO Bhuvan"
          noWrap={true}
        />
      ) : null}
      {overlays.includes("bhuvan_geomorph_in") ? (
        <WMSTileLayer
          url={apiUrl("/map/wms")}
          layers="gw_wfs:AN_LGEOM,gw_wfs:AP_LGEOM,gw_wfs:AR_LGEOM,gw_wfs:AS_LGEOM,gw_wfs:BR_LGEOM,gw_wfs:CG_LGEOM,gw_wfs:CH_LGEOM,gw_wfs:DL_LGEOM,gw_wfs:GA_LGEOM,gw_wfs:GJ_LGEOM,gw_wfs:HP_LGEOM,gw_wfs:HR_LGEOM,gw_wfs:JH_LGEOM,gw_wfs:JK_LGEOM,gw_wfs:KA_LGEOM,gw_wfs:KL_LGEOM,gw_wfs:LD_LGEOM,gw_wfs:MH_LGEOM,gw_wfs:ML_LGEOM,gw_wfs:MN_LGEOM,gw_wfs:MP_LGEOM,gw_wfs:MZ_LGEOM,gw_wfs:NL_LGEOM,gw_wfs:OR_LGEOM,gw_wfs:PB_LGEOM,gw_wfs:PY_LGEOM,gw_wfs:RJ_LGEOM,gw_wfs:SK_LGEOM,gw_wfs:TN_LGEOM,gw_wfs:TR_LGEOM,gw_wfs:TS_LGEOM,gw_wfs:UK_LGEOM,gw_wfs:UP_LGEOM,gw_wfs:WB_LGEOM"
          format="image/png"
          transparent
          version="1.1.1"
          attribution="© NRSC / ISRO Bhuvan"
          noWrap={true}
        />
      ) : null}
      {storm?.state && storm.state !== "India" && storm.state !== "All India" ? (
        <StateBoundaryHighlight stateName={storm.state} />
      ) : (
        <IndiaCountryBoundary />
      )}
      {focusPin ? (
        <Recenter lat={focusPin.lat} lon={focusPin.lon} zoom={focusPin.zoom ?? 8} />
      ) : frame ? (
        <FitFrame frame={frame} />
      ) : (
        <Recenter lat={lat} lon={lon} zoom={zoom} />
      )}
      <FitEvents nonce={opt.fitNonce} points={fitPts} />
      <CursorReadout grid={weatherGrid} layer={weatherLayer} />
      {opt.showPin ? (
        <>
          <Circle
            center={[lat, lon]}
            radius={rainRadiusM(rainMm)}
            pathOptions={{ color: "#38bdf8", fillColor: "#0284c7", fillOpacity: 0.12, weight: 1.5, dashArray: "4 3" }}
          >
            <Popup>
              <div className="text-xs font-sans">
                <strong className="text-sky-400">{label}</strong>
                <div className="text-[11px] text-slate-300 mt-0.5">3-day forecast rain: <span className="font-bold text-sky-300">{rainMm} mm</span></div>
              </div>
            </Popup>
          </Circle>
          <Marker
            position={[lat, lon]}
            icon={L.divIcon({
              className: "",
              html: `<div style="position:relative;width:28px;height:28px;display:flex;align-items:center;justify-content:center;cursor:pointer;">
                <div style="position:absolute;inset:-4px;border-radius:9999px;border:2px solid #0284c7;background:rgba(2,132,199,0.2);animation:ping 2s cubic-bezier(0,0,0.2,1) infinite;"></div>
                <div style="position:absolute;inset:0px;border-radius:9999px;background:rgba(56,189,248,0.3);box-shadow:0 0 16px rgba(56,189,248,0.8);"></div>
                <div style="width:14px;height:14px;border-radius:9999px;background:#0284c7;border:2.5px solid #ffffff;box-shadow:0 0 10px rgba(0,0,0,0.4);position:relative;z-index:2;display:flex;align-items:center;justify-content:center;">
                  <div style="width:4px;height:4px;border-radius:9999px;background:#ffffff;"></div>
                </div>
              </div>`,
              iconSize: [28, 28],
              iconAnchor: [14, 14],
            })}
          >
            <Popup>
              <div className="text-xs space-y-1.5 p-0.5 min-w-[150px]">
                <div className="flex items-center gap-1.5 border-b border-slate-700/50 pb-1">
                  <span className="h-2 w-2 rounded-full bg-sky-400 animate-pulse"></span>
                  <div className="font-black text-sm text-sky-400 truncate">{label}</div>
                </div>
                <div className="font-mono text-[11px] text-slate-300 flex items-center justify-between">
                  <span className="text-[10px] text-slate-400 uppercase font-bold">Coords</span>
                  <span>{lat.toFixed(4)}, {lon.toFixed(4)}</span>
                </div>
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-[10px] text-slate-400 uppercase font-bold">3-Day Rain</span>
                  <span className="font-black text-sky-300 bg-sky-500/20 px-1.5 py-0.2 rounded border border-sky-500/30 font-mono">
                    {rainMm} mm
                  </span>
                </div>
              </div>
            </Popup>
          </Marker>
        </>
      ) : null}
      {highlights.includes("past_lightning")
        ? pastStrokes.map((s, i) => (
            <Marker
              key={`past-ltn-${i}-${s.lat}-${s.lon}`}
              position={[s.lat, s.lon]}
              icon={eventIcon({ kind: "lightning", phase: "past" })}
              eventHandlers={{
                click: () => {
                  if (onSelectIncident) {
                    onSelectIncident({
                      id: `past-ltn-${i}`,
                      kind: "lightning",
                      phase: "past",
                      lat: s.lat,
                      lon: s.lon,
                      place: s.place || `${s.lat.toFixed(2)}, ${s.lon.toFixed(2)}`,
                    } as StormIncident);
                  }
                },
              }}
            >
              <Popup>
                <div className="text-xs space-y-1">
                  <div className="font-bold text-sm text-amber-500">⚡ {t.hlPastLightning}</div>
                  <div className="font-semibold">{s.place || `${s.lat.toFixed(3)}, ${s.lon.toFixed(3)}`}</div>
                  <div className="font-mono text-[11px] text-slate-400">{s.lat.toFixed(3)}, {s.lon.toFixed(3)}</div>
                  {fmtIst(s.occurred_at || s.t || s.timestamp_utc || s.first_seen) ? (
                    <div className="text-[11px] text-slate-400">{fmtIst(s.occurred_at || s.t || s.timestamp_utc || s.first_seen)} IST</div>
                  ) : null}
                  {eventAgeMs(s as unknown as Record<string, unknown>, now) != null ? (
                    <div className="text-[11px] text-amber-400">{Math.round((eventAgeMs(s as unknown as Record<string, unknown>, now) || 0) / 60000)} min ago</div>
                  ) : null}
                  {s.engine === "open-meteo-thunder" ? (
                    <div className="text-[10px] text-slate-400">Model thunder (not GPS)</div>
                  ) : s.engine ? (
                    <div className="text-[10px] text-slate-500">{s.engine}</div>
                  ) : null}
                  <button
                    type="button"
                    className="mt-2 w-full px-2 py-1 text-xs font-semibold rounded bg-sky-600 hover:bg-sky-500 text-white shadow-sm flex items-center justify-center gap-1 cursor-pointer"
                    onClick={() =>
                      onPick({
                        id: `past-ltn-${i}`,
                        label: s.place || `${s.lat.toFixed(2)}, ${s.lon.toFixed(2)}`,
                        lat: s.lat,
                        lon: s.lon,
                        district: s.place || "",
                        state: storm?.state || "",
                      } as Location)
                    }
                  >
                    📍 {t.stormSwitchToLocation || "Switch to this location"}
                  </button>
                </div>
              </Popup>
            </Marker>
          ))
        : null}
      {highlights.includes("lightning")
        ? liveByKind("lightning")
            .map((s, i) => (
              <Marker
                key={`live-ltn-${s.id || i}`}
                position={[s.lat, s.lon]}
                icon={eventIcon({ kind: "lightning", phase: "live", selected: Boolean(selectedId && s.id === selectedId) })}
                eventHandlers={{
                  click: () => {
                    if (onSelectIncident) {
                      onSelectIncident({
                        id: s.id || `live-ltn-${i}`,
                        kind: "lightning",
                        phase: "live",
                        lat: s.lat,
                        lon: s.lon,
                        place: s.place || `${s.lat.toFixed(2)}, ${s.lon.toFixed(2)}`,
                      } as StormIncident);
                    }
                  },
                }}
              >
                <Popup>
                  <div className="text-xs space-y-1">
                    <div className="font-bold text-sm text-yellow-400">{t.hlLiveLightning}</div>
                    <div>{s.place || `${s.lat.toFixed(3)}, ${s.lon.toFixed(3)}`}</div>
                    <div className="font-mono text-[11px] text-slate-400">{s.lat.toFixed(3)}, {s.lon.toFixed(3)}</div>
                    <button
                      type="button"
                      className="mt-2 w-full px-2 py-1 text-xs font-semibold rounded bg-sky-600 hover:bg-sky-500 text-white shadow-sm flex items-center justify-center gap-1 cursor-pointer"
                      onClick={() =>
                        onPick({
                          id: s.id || `live-ltn-${i}`,
                          label: s.place || `${s.lat.toFixed(2)}, ${s.lon.toFixed(2)}`,
                          lat: s.lat,
                          lon: s.lon,
                          district: s.place || "",
                          state: storm?.state || "",
                        } as Location)
                      }
                    >
                      📍 {t.stormSwitchToLocation || "Switch to this location"}
                    </button>
                  </div>
                </Popup>
              </Marker>
            ))
        : null}
      {highlights.includes("pred_lightning")
        ? predLtn.map((s) => (
            <Marker
              key={s.id}
              position={[s.lat, s.lon]}
              zIndexOffset={600}
              icon={eventIcon({ kind: "lightning", phase: "predicted", selected: Boolean(selectedId && s.id === selectedId) })}
              eventHandlers={{
                click: () => {
                  if (onSelectIncident) {
                    onSelectIncident({
                      id: s.id,
                      kind: "lightning",
                      phase: "predicted",
                      lat: s.lat,
                      lon: s.lon,
                      place: s.place,
                      lead_min: s.lead_min,
                      confidence: s.confidence,
                      confidence_band: s.confidence_band,
                      p_lightning: s.p_lightning,
                    } as StormIncident);
                  }
                },
              }}
            >
              <Popup>
                <div className="text-xs space-y-1">
                  <div className="font-bold text-sm text-amber-400">✦ {t.hlPredLightning}</div>
                  <div className="font-semibold">{s.place}</div>
                  <div className="font-mono text-[11px] text-slate-400">{s.lat.toFixed(3)}, {s.lon.toFixed(3)}</div>
                  {s.lead_min != null ? <div className="text-amber-400 font-medium">+{s.lead_min} min</div> : null}
                  {fmtIstHm(s.started_ms ?? s.started_at) && fmtIstHm(s.closes_ms ?? s.closes_at) ? (
                    <div className="text-[11px] text-slate-300">Expected {fmtIstHm(s.started_ms ?? s.started_at)} – {fmtIstHm(s.closes_ms ?? s.closes_at)} IST</div>
                  ) : null}
                  {s.confidence != null ? (
                    <div className="text-[11px] text-slate-300">
                      Confidence {(s.confidence * 100).toFixed(0)}% ({s.confidence_band || "—"})
                    </div>
                  ) : null}
                  {s.p_lightning != null ? <div className="text-[11px] text-slate-300">P(lightning) {(s.p_lightning * 100).toFixed(0)}%</div> : null}
                  {s.engine === "open-meteo-thunder" ? <div className="text-[10px] text-slate-400">Model thunder (not GPS)</div> : null}
                  {(s as { verify?: { note?: string } }).verify?.note ? (
                    <div className="text-[10px] text-slate-400">{(s as { verify?: { note?: string } }).verify?.note}</div>
                  ) : null}
                  <button
                    type="button"
                    className="mt-2 w-full px-2 py-1 text-xs font-semibold rounded bg-sky-600 hover:bg-sky-500 text-white shadow-sm flex items-center justify-center gap-1 cursor-pointer"
                    onClick={() =>
                      onPick({
                        id: s.id,
                        label: s.place,
                        lat: s.lat,
                        lon: s.lon,
                        district: s.place,
                        state: storm?.state || "",
                      } as Location)
                    }
                  >
                    📍 {t.stormSwitchToLocation || "Switch to this location"}
                  </button>
                </div>
              </Popup>
            </Marker>
          ))
        : null}
      {highlights.includes("pred_storm")
        ? predStorms.map((s) => (
            <Marker
              key={s.id}
              position={[s.lat, s.lon]}
              zIndexOffset={580}
              icon={eventIcon({ kind: s.kind || "storm", phase: "predicted", selected: Boolean(selectedId && s.id === selectedId) })}
              eventHandlers={{
                click: () => {
                  if (onSelectIncident) {
                    onSelectIncident({
                      id: s.id,
                      kind: "storm",
                      phase: "predicted",
                      lat: s.lat,
                      lon: s.lon,
                      place: s.place,
                      lead_min: s.lead_min,
                      confidence: s.confidence,
                      confidence_band: s.confidence_band,
                    } as StormIncident);
                  }
                },
              }}
            >
              <Popup>
                <div className="text-xs space-y-1">
                  <div className="font-bold text-sm text-purple-400">◆ {t.hlPredStorm}</div>
                  <div className="font-semibold">{s.place}</div>
                  <div className="font-mono text-[11px] text-slate-400">{s.lat.toFixed(3)}, {s.lon.toFixed(3)}</div>
                  {s.lead_min != null ? <div className="text-purple-400 font-medium">+{s.lead_min} min</div> : null}
                  {fmtIstHm(s.started_ms ?? s.started_at) && fmtIstHm(s.closes_ms ?? s.closes_at) ? (
                    <div className="text-[11px] text-slate-300">Expected {fmtIstHm(s.started_ms ?? s.started_at)} – {fmtIstHm(s.closes_ms ?? s.closes_at)} IST</div>
                  ) : null}
                  {s.confidence != null ? (
                    <div className="text-[11px] text-slate-300">
                      Confidence {(s.confidence * 100).toFixed(0)}% ({s.confidence_band || "—"})
                    </div>
                  ) : null}
                  <button
                    type="button"
                    className="mt-2 w-full px-2 py-1 text-xs font-semibold rounded bg-sky-600 hover:bg-sky-500 text-white shadow-sm flex items-center justify-center gap-1 cursor-pointer"
                    onClick={() =>
                      onPick({
                        id: s.id,
                        label: s.place,
                        lat: s.lat,
                        lon: s.lon,
                        district: s.place,
                        state: storm?.state || "",
                      } as Location)
                    }
                  >
                    📍 {t.stormSwitchToLocation || "Switch to this location"}
                  </button>
                </div>
              </Popup>
            </Marker>
          ))
        : null}
      {highlights.includes("past_storm")
        ? pastCells.map((c, i) => {
            const color = CELL_COLOR[c.kind || "storm"] || CELL_COLOR.storm;
            const popupContent = (
              <div className="text-xs space-y-1">
                <div className="font-bold text-sm text-slate-300">Past {(c.kind || "storm").toUpperCase()}</div>
                <div className="font-semibold">{c.place || `${c.lat.toFixed(3)}, ${c.lon.toFixed(3)}`}</div>
                <div className="font-mono text-[11px] text-slate-400">{c.lat.toFixed(3)}, {c.lon.toFixed(3)}</div>
                {fmtIst(c.occurred_at || c.first_seen || c.started_at) ? (
                  <div className="text-[11px] text-slate-400">{fmtIst(c.occurred_at || c.first_seen || c.started_at)} IST</div>
                ) : null}
                {eventAgeMs(c as unknown as Record<string, unknown>, now) != null ? (
                  <div className="text-[11px] text-amber-400">{Math.round((eventAgeMs(c as unknown as Record<string, unknown>, now) || 0) / 60000)} min ago</div>
                ) : null}
                <button
                  type="button"
                  className="mt-2 w-full px-2 py-1 text-xs font-semibold rounded bg-sky-600 hover:bg-sky-500 text-white shadow-sm flex items-center justify-center gap-1 cursor-pointer"
                  onClick={() =>
                    onPick({
                      id: c.id || `past-cell-${i}`,
                      label: c.place || `${c.lat.toFixed(2)}, ${c.lon.toFixed(2)}`,
                      lat: c.lat,
                      lon: c.lon,
                      district: c.place || "",
                      state: storm?.state || "",
                    } as Location)
                  }
                >
                  📍 {t.stormSwitchToLocation || "Switch to this location"}
                </button>
              </div>
            );

            return (
              <div key={c.id || `past-cell-grp-${i}`}>
                <Marker
                  position={[c.lat, c.lon]}
                  icon={eventIcon({ kind: c.kind || "storm", phase: "past" })}
                  eventHandlers={{
                    click: () => {
                      if (onSelectIncident) {
                        onSelectIncident({
                          id: c.id || `past-cell-${i}`,
                          kind: "storm",
                          phase: "past",
                          lat: c.lat,
                          lon: c.lon,
                          place: c.place || `${c.lat.toFixed(2)}, ${c.lon.toFixed(2)}`,
                        } as StormIncident);
                      }
                    },
                  }}
                >
                  <Popup>{popupContent}</Popup>
                </Marker>
                <ZoomCircle
                  center={[c.lat, c.lon]}
                  geoRadius={cellRadiusM(Number(c.area_km2 || 60))}
                  pathOptions={{ color, fillColor: color, fillOpacity: 0.12, weight: 1.5, dashArray: "3 6" }}
                >
                  <Popup>{popupContent}</Popup>
                </ZoomCircle>
              </div>
            );
          })
        : null}
      {(storm?.polygons || [])
        .filter((p) => polygonHighlightOn(p, highlights) && confOk(p, opt.minConfidence))
        .map((p) => {
          const kind = p.kind || "storm";
          const color = CELL_COLOR[kind] || CELL_COLOR.storm;
          const predicted = (p.lead_min || 0) > 0;
          const positions = (p.ring || [])
            .filter((pt) => Array.isArray(pt) && pt.length >= 2 && Number.isFinite(pt[0]) && Number.isFinite(pt[1]))
            .map((pt) => [pt[0], pt[1]] as [number, number]);
          if (positions.length < 4) return null;
          const lats = positions.map((x) => x[0]);
          const lons = positions.map((x) => x[1]);
          const dlat = Math.max(...lats) - Math.min(...lats);
          const dlon = Math.max(...lons) - Math.min(...lons);
          if (dlat < 0.015 && dlon < 0.015) return null;
          if (dlat > 6 || dlon > 7) return null;
          const centerLat = lats.reduce((a, b) => a + b, 0) / lats.length;
          const centerLon = lons.reduce((a, b) => a + b, 0) / lons.length;
          if (!p.label && !p.place) return null;
          const title = p.label || `Predicted ${kind} area`;
          return (
            <Polygon
              key={p.id}
              positions={positions}
              pathOptions={{
                color,
                fillColor: color,
                fillOpacity: predicted ? 0.12 : 0.2,
                weight: predicted ? 1.5 : 2,
                dashArray: predicted ? "7 5" : undefined,
              }}
              eventHandlers={{
                click: () => {
                  if (onSelectIncident) {
                    onSelectIncident({
                      id: p.id,
                      kind: p.kind || "storm",
                      phase: predicted ? "predicted" : "live",
                      lat: centerLat,
                      lon: centerLon,
                      place: p.place || "",
                      lead_min: p.lead_min,
                      confidence: p.confidence,
                      confidence_band: p.confidence_band,
                    } as StormIncident);
                  }
                },
              }}
            >
              <Popup>
                <div className="text-xs space-y-1">
                  <div className="font-bold text-sm" style={{ color }}>
                    {predicted ? "◆ " : "☁ "}
                    {title}
                  </div>
                  {p.place ? <div className="font-semibold">{p.place}</div> : null}
                  <div className="font-mono text-[11px] text-slate-400">{centerLat.toFixed(3)}, {centerLon.toFixed(3)}</div>
                  {p.lead_min ? <div className="text-amber-400 font-medium">+{p.lead_min} min</div> : null}
                  {p.confidence != null ? (
                    <div className="text-[11px] text-slate-300">
                      Confidence {(p.confidence * 100).toFixed(0)}% ({p.confidence_band || "—"})
                    </div>
                  ) : null}
                  <button
                    type="button"
                    className="mt-2 w-full px-2 py-1 text-xs font-semibold rounded bg-sky-600 hover:bg-sky-500 text-white shadow-sm flex items-center justify-center gap-1 cursor-pointer"
                    onClick={() =>
                      onPick({
                        id: p.id,
                        label: p.place || `${centerLat.toFixed(2)}, ${centerLon.toFixed(2)}`,
                        lat: centerLat,
                        lon: centerLon,
                        district: p.place || "",
                        state: storm?.state || "",
                      } as Location)
                    }
                  >
                    📍 {t.stormSwitchToLocation || "Switch to this location"}
                  </button>
                </div>
              </Popup>
            </Polygon>
          );
        })}
      {[
        ...(storm?.cells || []),
        ...((storm?.incidents || []).filter((i) => (i.phase || "live") === "live" && i.kind !== "lightning" && i.kind !== "fire" && i.kind !== "landslide")),
      ]
        .filter((c, i, arr) => {
          const kind = c.kind || "storm";
          if (kind === "lightning" || kind === "fire" || kind === "landslide") return false;
          if (!highlights.includes(kind)) return false;
          if (c.lat == null || c.lon == null) return false;
          const key = `${Number(c.lat).toFixed(3)}:${Number(c.lon).toFixed(3)}:${kind}`;
          return arr.findIndex((x) => `${Number(x.lat).toFixed(3)}:${Number(x.lon).toFixed(3)}:${x.kind || "storm"}` === key) === i;
        })
        .map((c, i) => {
          const color = CELL_COLOR[c.kind || "cloud"] || CELL_COLOR.cloud;
          const selected = Boolean(selectedId && c.id === selectedId);
          return (
            <ZoomCircle
              key={c.id || `cell-${i}`}
              center={[c.lat, c.lon]}
              geoRadius={cellRadiusM(Number(c.area_km2 || 80))}
              pathOptions={{ color, fillColor: color, fillOpacity: selected ? 0.4 : 0.22, weight: selected ? 3 : 2 }}
            >
              <Popup>
                <div className="text-xs space-y-1">
                  <div className="font-bold text-sm" style={{ color }}>
                    {(c.kind || "cell").toUpperCase()}
                  </div>
                  <div className="font-semibold">{c.place || `${c.lat.toFixed(3)}, ${c.lon.toFixed(3)}`}</div>
                  <div className="font-mono text-[11px] text-slate-400">{c.lat.toFixed(3)}, {c.lon.toFixed(3)}</div>
                  {c.rain_ir_mm_h != null ? <div className="text-[11px] text-sky-300">{c.rain_ir_mm_h} mm/h IR</div> : null}
                  {c.min_tb_k != null ? <div className="text-[11px] text-slate-300">Min Tb: {c.min_tb_k} K</div> : null}
                  {c.area_km2 != null ? <div className="text-[11px] text-slate-300">Area: {c.area_km2} km²</div> : null}
                  <button
                    type="button"
                    className="mt-2 w-full px-2 py-1 text-xs font-semibold rounded bg-sky-600 hover:bg-sky-500 text-white shadow-sm flex items-center justify-center gap-1 cursor-pointer"
                    onClick={() =>
                      onPick({
                        id: c.id || `cell-${i}`,
                        label: c.place || `${c.lat.toFixed(2)}, ${c.lon.toFixed(2)}`,
                        lat: c.lat,
                        lon: c.lon,
                        district: c.place || "",
                        state: storm?.state || "",
                      } as Location)
                    }
                  >
                    📍 {t.stormSwitchToLocation || "Switch to this location"}
                  </button>
                </div>
              </Popup>
            </ZoomCircle>
          );
        })}
      {highlights.includes("fire")
        ? [
            ...(storm?.fires || []).map((f) => ({
              id: f.id,
              kind: "fire" as const,
              lat: f.lat,
              lon: f.lon,
              place: f.place,
              n: f.n,
              frp_mw: f.frp_mw,
              phase: f.phase || "live",
              title: f.place,
              t: (f as any).t,
              timestamp_utc: (f as any).timestamp_utc,
              occurred_at: (f as any).occurred_at,
              occurred_ms: (f as any).occurred_ms,
              started_at: (f as any).started_at,
              started_ms: (f as any).started_ms,
            })),
            ...(hazardEvents || []).filter((h) => h.kind === "fire"),
          ]
            .filter((f, i, arr) => arr.findIndex((x) => x.id === f.id || (Math.abs(x.lat - f.lat) < 0.05 && Math.abs(x.lon - f.lon) < 0.05)) === i)
            .map((f, i) => (
              <Marker
                key={`fire-${f.id || i}-${f.lat}-${f.lon}`}
                position={[f.lat, f.lon]}
                icon={eventIcon({ kind: "fire", phase: f.phase || "live", count: f.n, selected: Boolean(selectedId && f.id === selectedId) })}
                zIndexOffset={400}
                eventHandlers={{
                  click: () => {
                    onSelectIncident?.({
                      id: f.id,
                      kind: "fire",
                      phase: f.phase || "live",
                      lat: f.lat,
                      lon: f.lon,
                      place: f.place || f.title || "Forest fire",
                    } as StormIncident);
                  },
                }}
              >
                <Popup>
                  <div className="text-xs space-y-1">
                    <div className="font-bold text-sm text-orange-400">🔥 Forest fire</div>
                    <div className="font-semibold">{f.place || f.title}</div>
                    <div className="font-mono text-[11px] text-slate-400">{f.lat.toFixed(3)}, {f.lon.toFixed(3)}</div>
                    {f.n != null ? <div>{f.n} VIIRS hotspot{f.n === 1 ? "" : "s"}</div> : null}
                    {f.frp_mw != null ? <div>FRP {f.frp_mw} MW</div> : null}
                    <div className="text-[10px] text-slate-400">NASA FIRMS thermal · not burned area</div>
                    {fmtIst((f as { occurred_at?: string }).occurred_at || (f as { t?: string }).t) ? (
                      <div className="text-[11px] text-slate-400">{fmtIst((f as { occurred_at?: string }).occurred_at || (f as { t?: string }).t)} IST</div>
                    ) : null}
                    {(f as any).window_start && (f as any).window_end ? (
                      <div className="text-[11px] text-slate-300">Expected {fmtIstHm((f as any).window_start)} – {fmtIstHm((f as any).window_end)} IST</div>
                    ) : null}
                    <button
                      type="button"
                      className="mt-2 w-full px-2 py-1 text-xs font-semibold rounded bg-sky-600 hover:bg-sky-500 text-white"
                      onClick={() =>
                        onPick({
                          id: f.id,
                          label: f.place || "Forest fire",
                          lat: f.lat,
                          lon: f.lon,
                          district: f.place || "",
                          state: storm?.state || "",
                        } as Location)
                      }
                    >
                      📍 {t.stormSwitchToLocation || "Switch to this location"}
                    </button>
                  </div>
                </Popup>
              </Marker>
            ))
        : null}
      {highlights.includes("landslide")
        ? [
            ...(storm?.landslides || [])
            .map((s) => ({
              id: s.id,
              kind: "landslide" as const,
              lat: s.lat,
              lon: s.lon,
              place: s.place,
              phase: s.phase || "live",
              title: s.place,
              window_start: s.window_start,
              window_end: s.window_end,
              t: (s as any).t,
              timestamp_utc: (s as any).timestamp_utc,
              occurred_at: (s as any).occurred_at,
              occurred_ms: (s as any).occurred_ms,
              started_at: (s as any).started_at,
              started_ms: (s as any).started_ms,
            })),
            ...(hazardEvents || []).filter((h) => h.kind === "landslide"),
          ]
            .filter((s) => (s.phase === "past" ? inPastWindow(s as unknown as Record<string, unknown>, now, pastMs) : true))
            .filter((h, i, arr) => h.lat != null && h.lon != null && arr.findIndex((x) => x.id === h.id) === i)
            .map((h, i) => (
              <Marker
                key={`slide-${h.id || i}-${h.lat}-${h.lon}`}
                position={[h.lat, h.lon]}
                icon={eventIcon({ kind: "landslide", phase: h.phase || "live", selected: Boolean(selectedId && h.id === selectedId) })}
                zIndexOffset={350}
                eventHandlers={{
                  click: () => {
                    onSelectIncident?.({
                      id: h.id,
                      kind: "landslide",
                      phase: h.phase || "live",
                      lat: h.lat,
                      lon: h.lon,
                      place: h.place || h.title || "Landslide",
                    } as StormIncident);
                  },
                }}
              >
                <Popup>
                  <div className="text-xs space-y-1">
                    <div className="font-bold text-sm text-amber-700">⛰ Landslide</div>
                    <div className="font-semibold">{h.place || h.title}</div>
                    <div className="font-mono text-[11px] text-slate-400">{h.lat.toFixed(3)}, {h.lon.toFixed(3)}</div>
                    {fmtIst((h as { occurred_at?: string }).occurred_at || h.window_start) ? (
                      <div className="text-[11px] text-slate-400">{fmtIst((h as { occurred_at?: string }).occurred_at)} IST</div>
                    ) : null}
                    {h.window_start && h.window_end ? (
                      <div className="text-[11px] text-slate-300">Watch {fmtIstHm(h.window_start)} – {fmtIstHm(h.window_end)} IST (not GSI)</div>
                    ) : null}
                    <button
                      type="button"
                      className="mt-2 w-full px-2 py-1 text-xs font-semibold rounded bg-sky-600 hover:bg-sky-500 text-white"
                      onClick={() =>
                        onPick({
                          id: h.id,
                          label: h.place || "Landslide",
                          lat: h.lat,
                          lon: h.lon,
                          district: h.place || "",
                          state: storm?.state || "",
                        } as Location)
                      }
                    >
                      📍 {t.stormSwitchToLocation || "Switch to this location"}
                    </button>
                  </div>
                </Popup>
              </Marker>
            ))
        : null}
    </MapContainer>
  );
}
