"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Circle,
  CircleMarker,
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
import type { StormMapPack, StormMapTools, StormStroke } from "@/lib/api";
import { apiUrl, reverseGeocode } from "@/lib/api";

const pin = L.divIcon({
  className: "",
  html: `<div style="width:14px;height:14px;border-radius:999px;background:#3a7ca5;border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,.25)"></div>`,
  iconSize: [14, 14],
  iconAnchor: [7, 7],
});

const pastStrikeIcon = L.divIcon({
  className: "",
  html: `<div style="width:16px;height:16px;display:flex;align-items:center;justify-content:center;color:#7f8c8d;font-size:14px;opacity:.9">⚡</div>`,
  iconSize: [16, 16],
  iconAnchor: [8, 8],
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

function CursorReadout() {
  const [txt, setTxt] = useState("");
  useMapEvents({
    mousemove: (e) => setTxt(`${e.latlng.lat.toFixed(3)}, ${e.latlng.lng.toFixed(3)}`),
    mouseout: () => setTxt(""),
  });
  if (!txt) return null;
  return (
    <div className="pointer-events-none absolute bottom-7 left-2 z-[500] rounded-md bg-neo-card/90 px-2 py-0.5 font-mono text-[10px] text-neo-text shadow">
      {txt}
    </div>
  );
}

const BASE: Record<string, { url: string; attr: string }> = {
  positron: {
    url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
    attr: "© OpenStreetMap © CARTO",
  },
  streets: {
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attr: "© OpenStreetMap",
  },
  satellite: {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr: "Tiles © Esri",
  },
  terrain: {
    url: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
    attr: "© OpenTopoMap",
  },
};

const CELL_COLOR: Record<string, string> = {
  cloudburst: "#c0392b",
  downburst: "#e67e22",
  storm: "#8e44ad",
  cloud: "#2980b9",
  lightning: "#f1c40f",
};

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

function strokeAgeMs(s: StormStroke, now: number) {
  if (typeof s.past_mins === "number" && Number.isFinite(s.past_mins)) return s.past_mins * 60_000;
  if (typeof s.started_ms === "number") return Math.max(0, now - s.started_ms);
  const raw = s.timestamp_utc || s.t;
  if (raw) {
    const t = Date.parse(raw);
    if (!Number.isNaN(t)) return Math.max(0, now - t);
  }
  return 0;
}

function confOk(row: { confidence?: number } | undefined, min: number) {
  if (!min) return true;
  return (row?.confidence ?? 0) >= min;
}

const DEFAULT_TOOLS: StormMapTools = {
  overlayOpacity: 0.7,
  showPin: true,
  pastHours: 6,
  minConfidence: 0,
  fitNonce: 0,
};

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
  highlights = ["past_lightning", "pred_lightning", "past_storm", "pred_storm", "lightning", "storm"],
  focusPin,
  selectedId,
  tools,
  locale,
  onPick,
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
  onPick: (l: Location) => void;
}) {
  const t = COPY[locale || "en"];
  const opt = tools || DEFAULT_TOOLS;
  const tile = BASE[basemap] || BASE.positron;
  const frame = storm?.frame;
  const showIr = overlays.includes("gibs_ir") || basemap === "ir";
  const showImerg = overlays.includes("gibs_imerg") || basemap === "rain";
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
      if (strokeAgeMs(s, now) > pastMs) continue;
      out.push(s);
    }
    return out;
  }, [storm, now, pastMs]);

  const predLtn = (storm?.predicted || []).filter((s) => confOk(s, opt.minConfidence));
  const predStorms = (storm?.predicted_storms || []).filter((s) => confOk(s, opt.minConfidence));
  const pastCells = storm?.past_cells || [];

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
    <MapContainer center={[lat, lon]} zoom={zoom} className="relative h-full w-full" scrollWheelZoom>
      <TileLayer attribution={tile.attr} url={tile.url} />
      <ScaleControl imperial={false} position="bottomleft" />
      {showIr ? (
        <WMSTileLayer
          url={GIBS}
          layers="Himawari_AHI_Band13_Clean_Infrared"
          format="image/png"
          transparent
          version="1.3.0"
          opacity={opt.overlayOpacity}
          attribution="NASA GIBS / Himawari IR"
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
        />
      ) : null}
      {frame && !frame.all_india && frame.north - frame.south < 20 ? (
        <Rectangle
          bounds={[
            [frame.south, frame.west],
            [frame.north, frame.east],
          ]}
          pathOptions={{ color: "#3a7ca5", weight: 1.5, fillOpacity: 0.03, dashArray: "6 4" }}
        />
      ) : null}
      {focusPin ? (
        <Recenter lat={focusPin.lat} lon={focusPin.lon} zoom={focusPin.zoom ?? 8} />
      ) : frame ? (
        <FitFrame frame={frame} />
      ) : (
        <Recenter lat={lat} lon={lon} zoom={zoom} />
      )}
      <FitEvents nonce={opt.fitNonce} points={fitPts} />
      <Click onPick={onPick} />
      <CursorReadout />
      {opt.showPin ? (
        <ZoomCircle
          center={[lat, lon]}
          geoRadius={rainRadiusM(rainMm)}
          pathOptions={{ color: "#3a7ca5", fillColor: "#3a7ca5", fillOpacity: 0.18, weight: 2 }}
        >
          <Popup>
            <strong>{label}</strong>
            <br />
            3-day rain {rainMm} mm
          </Popup>
        </ZoomCircle>
      ) : null}
      {highlights.includes("past_lightning")
        ? pastStrokes.map((s, i) => (
            <CircleMarker
              key={`past-ltn-${i}-${s.lat}-${s.lon}`}
              center={[s.lat, s.lon]}
              radius={7}
              pathOptions={{ color: "#8e6b1f", fillColor: "#f1c40f", fillOpacity: 0.85, weight: 1.5 }}
            >
              <Popup>
                <strong>{t.hlPastLightning}</strong>
                <br />
                {s.place || `${s.lat.toFixed(2)}, ${s.lon.toFixed(2)}`}
                {s.t || s.timestamp_utc ? (
                  <>
                    <br />
                    {s.t || s.timestamp_utc}
                  </>
                ) : null}
                {s.past_mins != null ? (
                  <>
                    <br />
                    {Math.round(s.past_mins)} min ago
                  </>
                ) : null}
                <br />
                {s.engine || "weatherbit"}
              </Popup>
            </CircleMarker>
          ))
        : null}
      {highlights.includes("lightning")
        ? (storm?.cells || [])
            .filter((c) => c.kind === "lightning")
            .map((s, i) => (
              <Marker key={`live-ltn-${s.id || i}`} position={[s.lat, s.lon]} icon={liveStrikeIcon}>
                <Popup>
                  <strong>{t.hlLiveLightning}</strong>
                  <br />
                  {s.place || `${s.lat.toFixed(2)}, ${s.lon.toFixed(2)}`}
                </Popup>
              </Marker>
            ))
        : null}
      {highlights.includes("pred_lightning")
        ? predLtn.map((s) => (
            <Marker key={s.id} position={[s.lat, s.lon]} icon={predStrikeIcon}>
              <Popup>
                <strong>{t.hlPredLightning}</strong>
                <br />
                {s.place}
                {s.lead_min != null ? (
                  <>
                    <br />+{s.lead_min} min
                  </>
                ) : null}
                {s.confidence != null ? (
                  <>
                    <br />
                    Confidence {(s.confidence * 100).toFixed(0)}% ({s.confidence_band || "—"})
                  </>
                ) : null}
                {s.p_lightning != null ? (
                  <>
                    <br />
                    P(ltn) {(s.p_lightning * 100).toFixed(0)}%
                  </>
                ) : null}
              </Popup>
            </Marker>
          ))
        : null}
      {highlights.includes("pred_storm")
        ? predStorms.map((s) => (
            <Marker key={s.id} position={[s.lat, s.lon]} icon={predStormIcon}>
              <Popup>
                <strong>{t.hlPredStorm}</strong>
                <br />
                {s.place}
                {s.lead_min != null ? (
                  <>
                    <br />+{s.lead_min} min
                  </>
                ) : null}
                {s.confidence != null ? (
                  <>
                    <br />
                    Confidence {(s.confidence * 100).toFixed(0)}% ({s.confidence_band || "—"})
                  </>
                ) : null}
              </Popup>
            </Marker>
          ))
        : null}
      {highlights.includes("past_storm")
        ? pastCells.map((c, i) => {
            const color = CELL_COLOR[c.kind || "storm"] || CELL_COLOR.storm;
            return (
              <ZoomCircle
                key={c.id || `past-cell-${i}`}
                center={[c.lat, c.lon]}
                geoRadius={cellRadiusM(Number(c.area_km2 || 60))}
                pathOptions={{ color, fillColor: color, fillOpacity: 0.08, weight: 1, dashArray: "2 6" }}
              >
                <Popup>
                  <strong>Past {(c.kind || "storm").toUpperCase()}</strong>
                  <br />
                  {c.place || `${c.lat.toFixed(2)}, ${c.lon.toFixed(2)}`}
                  {c.closes_at ? (
                    <>
                      <br />
                      ended {c.closes_at}
                    </>
                  ) : null}
                </Popup>
              </ZoomCircle>
            );
          })
        : null}
      {(storm?.polygons || [])
        .filter((p) => {
          const predicted = (p.lead_min || 0) > 0;
          if (predicted) {
            if (p.kind === "lightning") return highlights.includes("pred_lightning") && confOk(p, opt.minConfidence);
            return highlights.includes("pred_storm") && confOk(p, opt.minConfidence);
          }
          return highlights.includes(p.kind || "storm");
        })
        .map((p) => {
          const color = CELL_COLOR[p.kind || "storm"] || CELL_COLOR.storm;
          const predicted = (p.lead_min || 0) > 0;
          const positions = (p.ring || []).map((pt) => [pt[0], pt[1]] as [number, number]);
          if (positions.length < 3) return null;
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
            >
              <Popup>
                <strong>{predicted ? "Predicted storm area" : (p.kind || "storm").toUpperCase()}</strong>
                <br />
                {p.place || ""}
                {p.lead_min ? (
                  <>
                    <br />+{p.lead_min} min
                  </>
                ) : null}
                {p.confidence != null ? (
                  <>
                    <br />
                    Confidence {(p.confidence * 100).toFixed(0)}% ({p.confidence_band || "—"})
                  </>
                ) : null}
              </Popup>
            </Polygon>
          );
        })}
      {(storm?.cells || [])
        .filter((c) => c.kind !== "lightning" && highlights.includes(c.kind || "storm"))
        .map((c, i) => {
          const color = CELL_COLOR[c.kind || "cloud"] || CELL_COLOR.cloud;
          const selected = Boolean(selectedId && c.id === selectedId);
          const hasPoly = (storm?.polygons || []).some((p) => p.id === `poly-${c.id}` || p.id === c.id);
          if (hasPoly && !selected) return null;
          return (
            <ZoomCircle
              key={c.id || `cell-${i}`}
              center={[c.lat, c.lon]}
              geoRadius={cellRadiusM(Number(c.area_km2 || 80))}
              pathOptions={{ color, fillColor: color, fillOpacity: selected ? 0.4 : 0.22, weight: selected ? 3 : 2 }}
            >
              <Popup>
                <strong>{(c.kind || "cell").toUpperCase()}</strong>
                <br />
                {c.place || `${c.lat.toFixed(2)}, ${c.lon.toFixed(2)}`}
                {c.rain_ir_mm_h != null ? (
                  <>
                    <br />
                    {c.rain_ir_mm_h} mm/h
                  </>
                ) : null}
                {c.min_tb_k != null ? (
                  <>
                    <br />
                    {c.min_tb_k} K
                  </>
                ) : null}
              </Popup>
            </ZoomCircle>
          );
        })}
      {nearby.map((n) => (
        <Marker key={n.id} position={[n.lat, n.lon]} icon={pin} eventHandlers={{ click: () => onPick(n) }}>
          <Popup>
            <button type="button" onClick={() => onPick(n)}>
              {n.label}
            </button>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
