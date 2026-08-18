"use client";

import { useEffect } from "react";
import { CircleMarker, MapContainer, Marker, Popup, TileLayer, WMSTileLayer, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import type { Location } from "@/types/dashboard";
import { apiUrl, reverseGeocode } from "@/lib/api";

const pin = L.divIcon({
  className: "",
  html: `<div style="width:14px;height:14px;border-radius:999px;background:#3a7ca5;border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,.25)"></div>`,
  iconSize: [14, 14],
  iconAnchor: [7, 7],
});

function Recenter({ lat, lon, zoom }: { lat: number; lon: number; zoom: number }) {
  const map = useMap();
  useEffect(() => {
    map.setView([lat, lon], zoom);
  }, [map, lat, lon, zoom]);
  return null;
}

function Click({ onPick }: { onPick: (l: Location) => void }) {
  useMapEvents({
    click: async (e) => {
      const loc = await reverseGeocode(e.latlng.lat, e.latlng.lng);
      onPick({ ...loc, lat: e.latlng.lat, lon: e.latlng.lng });
    },
  });
  return null;
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

export function MapView({
  lat,
  lon,
  label,
  rainMm,
  zoom,
  basemap,
  nearby,
  overlays = [],
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
  onPick: (l: Location) => void;
}) {
  const tile = BASE[basemap] || BASE.positron;
  const radius = 16 + Math.min(36, rainMm);
  return (
    <MapContainer center={[lat, lon]} zoom={zoom} className="h-full w-full" scrollWheelZoom>
      <TileLayer attribution={tile.attr} url={tile.url} />
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
          layers="gw_wfs:AN_LGEOM,gw_wfs:AP_LGEOM,gw_wfs:AS_LGEOM,gw_wfs:BR_LGEOM,gw_wfs:GA_LGEOM,gw_wfs:JH_LGEOM,gw_wfs:KA_LGEOM,gw_wfs:KL_LGEOM,gw_wfs:MH_LGEOM,gw_wfs:MP_LGEOM,gw_wfs:OR_LGEOM,gw_wfs:PB_LGEOM,gw_wfs:RJ_LGEOM,gw_wfs:TN_LGEOM,gw_wfs:TS_LGEOM,gw_wfs:UK_LGEOM,gw_wfs:UP_LGEOM,gw_wfs:WB_LGEOM"
          format="image/png"
          transparent
          version="1.1.1"
          attribution="© NRSC / ISRO Bhuvan"
        />
      ) : null}
      <Recenter lat={lat} lon={lon} zoom={zoom} />
      <Click onPick={onPick} />
      <CircleMarker
        center={[lat, lon]}
        radius={radius}
        pathOptions={{ color: "#3a7ca5", fillColor: "#3a7ca5", fillOpacity: 0.22, weight: 2 }}
      >
        <Popup>
          <strong>{label}</strong>
          <br />
          3-day rain {rainMm} mm
        </Popup>
      </CircleMarker>
      {nearby.map((n) => (
        <Marker
          key={n.id}
          position={[n.lat, n.lon]}
          icon={pin}
          eventHandlers={{ click: () => onPick(n) }}
        >
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
