"use client";

import type { Location } from "@/types/dashboard";
import type { Locale } from "@/i18n/copy";
import { haversineKm } from "./helpers";
import { getHazardTheme } from "./icons";

export const INDIA_CITIES_MAP: Record<string, { city: string; state: string; lat: number; lon: number }> = {
  patna: { city: "Patna", state: "Bihar", lat: 25.5941, lon: 85.1376 },
  delhi: { city: "Delhi", state: "Delhi", lat: 28.6139, lon: 77.209 },
  "new delhi": { city: "New Delhi", state: "Delhi", lat: 28.6139, lon: 77.209 },
  mumbai: { city: "Mumbai", state: "Maharashtra", lat: 19.076, lon: 72.8777 },
  kolkata: { city: "Kolkata", state: "West Bengal", lat: 22.5726, lon: 88.3639 },
  chennai: { city: "Chennai", state: "Tamil Nadu", lat: 13.0827, lon: 80.2707 },
  bengaluru: { city: "Bengaluru", state: "Karnataka", lat: 12.9716, lon: 77.5946 },
  bangalore: { city: "Bengaluru", state: "Karnataka", lat: 12.9716, lon: 77.5946 },
  hyderabad: { city: "Hyderabad", state: "Telangana", lat: 17.385, lon: 78.4867 },
  ahmedabad: { city: "Ahmedabad", state: "Gujarat", lat: 23.0225, lon: 72.5714 },
  gandhinagar: { city: "Gandhinagar", state: "Gujarat", lat: 23.2156, lon: 72.6369 },
  shillong: { city: "Shillong", state: "Meghalaya", lat: 25.5788, lon: 91.8933 },
  guwahati: { city: "Guwahati", state: "Assam", lat: 26.1445, lon: 91.7362 },
  bhubaneswar: { city: "Bhubaneswar", state: "Odisha", lat: 20.2961, lon: 85.8245 },
  puri: { city: "Puri", state: "Odisha", lat: 19.8135, lon: 85.8312 },
  jaipur: { city: "Jaipur", state: "Rajasthan", lat: 26.9124, lon: 75.7873 },
  lucknow: { city: "Lucknow", state: "Uttar Pradesh", lat: 26.8467, lon: 80.9462 },
  kanpur: { city: "Kanpur", state: "Uttar Pradesh", lat: 26.4499, lon: 80.3319 },
  varanasi: { city: "Varanasi", state: "Uttar Pradesh", lat: 25.3176, lon: 82.9739 },
  bhopal: { city: "Bhopal", state: "Madhya Pradesh", lat: 23.2599, lon: 77.4126 },
  indore: { city: "Indore", state: "Madhya Pradesh", lat: 22.7196, lon: 75.8577 },
  chandigarh: { city: "Chandigarh", state: "Chandigarh", lat: 30.7333, lon: 76.7794 },
  shimla: { city: "Shimla", state: "Himachal Pradesh", lat: 31.1048, lon: 77.1734 },
  dehradun: { city: "Dehradun", state: "Uttarakhand", lat: 30.3165, lon: 78.0322 },
  srinagar: { city: "Srinagar", state: "Jammu and Kashmir", lat: 34.0837, lon: 74.7973 },
  jammu: { city: "Jammu", state: "Jammu and Kashmir", lat: 32.7266, lon: 74.857 },
  ranchi: { city: "Ranchi", state: "Jharkhand", lat: 23.3441, lon: 85.3096 },
  raipur: { city: "Raipur", state: "Chhattisgarh", lat: 21.2514, lon: 81.6296 },
  amaravati: { city: "Amaravati", state: "Andhra Pradesh", lat: 16.5418, lon: 80.515 },
  visakhapatnam: { city: "Visakhapatnam", state: "Andhra Pradesh", lat: 17.6868, lon: 83.2185 },
  thiruvananthapuram: { city: "Thiruvananthapuram", state: "Kerala", lat: 8.5241, lon: 76.9366 },
  kochi: { city: "Kochi", state: "Kerala", lat: 9.9312, lon: 76.2673 },
  panaji: { city: "Panaji", state: "Goa", lat: 15.4909, lon: 73.8278 },
  gangtok: { city: "Gangtok", state: "Sikkim", lat: 27.3389, lon: 88.6065 },
  itanagar: { city: "Itanagar", state: "Arunachal Pradesh", lat: 27.0844, lon: 93.6053 },
  kohima: { city: "Kohima", state: "Nagaland", lat: 25.6751, lon: 94.1086 },
  imphal: { city: "Imphal", state: "Manipur", lat: 24.817, lon: 93.9368 },
  aizawl: { city: "Aizawl", state: "Mizoram", lat: 23.7271, lon: 92.7176 },
  agartala: { city: "Agartala", state: "Tripura", lat: 23.8315, lon: 91.2868 },
  "port blair": { city: "Port Blair", state: "Andaman and Nicobar", lat: 11.6234, lon: 92.7265 },
  puducherry: { city: "Puducherry", state: "Puducherry", lat: 11.9416, lon: 79.8083 },
  kavaratti: { city: "Kavaratti", state: "Lakshadweep", lat: 10.5667, lon: 72.6417 },
  silvassa: { city: "Silvassa", state: "Dadra and Nagar Haveli", lat: 20.2763, lon: 73.0083 },
  daman: { city: "Daman", state: "Daman and Diu", lat: 20.3974, lon: 72.8328 },
  leh: { city: "Leh", state: "Ladakh", lat: 34.1526, lon: 77.5771 },
};


export const STATE_NAMES = [
  "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat",
  "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra",
  "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim",
  "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
  "Andaman and Nicobar", "Chandigarh", "Dadra and Nagar Haveli", "Daman and Diu", "Delhi",
  "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry"
];


export function parseAlertLocation(w: any, currentLoc?: Location | null) {
  const rawTitle = (w.title || "").trim();
  const rawBody = (w.body || "").trim();
  const combined = `${rawTitle} ${rawBody} ${w.district || ""} ${w.state || ""}`;

  let city = (w.district || w.place_name || w.place || "").trim();
  let state = (w.state || (w.states && w.states[0]) || "").trim();
  let lat = w.lat != null ? Number(w.lat) : null;
  let lon = w.lon != null ? Number(w.lon) : null;

  // Sanitize national/generic keywords from city & state
  const isGeneric = (str: string) => {
    const s = str.toLowerCase().trim();
    return s === "india" || s === "national" || s === "pan-india" || s === "all india" || s === "cap-india" || s === "imd-cap";
  };

  if (isGeneric(city)) city = "";
  if (isGeneric(state)) state = "";

  // 1. Check if title starts with City (State), e.g. "Patna (Bihar) — Severe Flood Warning"
  const parenMatch = rawTitle.match(/^([A-Za-z\s]+)\s*\(([^)]+)\)/);
  if (parenMatch) {
    const p1 = parenMatch[1].trim();
    const p2 = parenMatch[2].trim();
    const isP1Generic = isGeneric(p1);
    const isP2Generic = isGeneric(p2);
    const isP2State = STATE_NAMES.some((s) => s.toLowerCase() === p2.toLowerCase());
    const isP1State = STATE_NAMES.some((s) => s.toLowerCase() === p1.toLowerCase());

    if (isP1Generic && isP2State) {
      state = p2;
    } else if (isP2Generic && isP1State) {
      state = p1;
    } else if (isP2State) {
      city = p1;
      state = p2;
    } else if (isP1State) {
      city = p2;
      state = p1;
    }
  }

  // 2. Check title with dash: e.g. "Predicted flood warning — Bihar (Patna)" or "Severe Weather Alert — Jharkhand"
  if (!city || !state) {
    const dashMatch = rawTitle.match(/—\s*([^—]+)$/);
    if (dashMatch) {
      const rest = dashMatch[1].trim();
      const subParen = rest.match(/^([A-Za-z\s]+)\s*\(([^)]+)\)/);
      if (subParen) {
        const s1 = subParen[1].trim();
        const s2 = subParen[2].trim();
        const isS1Generic = isGeneric(s1);
        const isS2Generic = isGeneric(s2);
        const isS1State = STATE_NAMES.some((s) => s.toLowerCase() === s1.toLowerCase());
        const isS2State = STATE_NAMES.some((s) => s.toLowerCase() === s2.toLowerCase());

        if (isS1Generic && isS2State) {
          state = s2;
        } else if (isS2Generic && isS1State) {
          state = s1;
        } else if (isS1State) {
          state = s1;
          city = s2;
        } else if (isS2State) {
          city = s1;
          state = s2;
        }
      } else if (rest.includes(",")) {
        const parts = rest.split(",");
        const cCandidate = parts[0].trim();
        const sCandidate = parts[1].trim();
        if (!isGeneric(cCandidate)) city = cCandidate;
        if (!isGeneric(sCandidate)) state = sCandidate;
      } else {
        const isState = STATE_NAMES.some((s) => s.toLowerCase() === rest.toLowerCase());
        if (isState) state = rest;
      }
    }
  }

  // 3. Scan for known cities in INDIA_CITIES_MAP
  if (!city || !state) {
    for (const [k, v] of Object.entries(INDIA_CITIES_MAP)) {
      const regex = new RegExp(`\\b${k}\\b`, "i");
      if (regex.test(combined)) {
        if (!city) city = v.city;
        if (!state) state = v.state;
        if (lat == null) lat = v.lat;
        if (lon == null) lon = v.lon;
        break;
      }
    }
  }

  // 4. Scan for known state names
  if (!state) {
    for (const s of STATE_NAMES) {
      const regex = new RegExp(`\\b${s}\\b`, "i");
      if (regex.test(combined)) {
        state = s;
        break;
      }
    }
  }

  // 5. Clean up any remaining generic words
  if (isGeneric(city)) city = "";
  if (isGeneric(state)) state = "";

  // 6. If city is empty but state is known, check capital
  if (!city && state) {
    const cap = Object.values(INDIA_CITIES_MAP).find((c) => c.state.toLowerCase() === state.toLowerCase());
    if (cap) {
      city = cap.city;
      if (lat == null) lat = cap.lat;
      if (lon == null) lon = cap.lon;
    }
  }

  // 7. Fallback to current dashboard location if completely blank
  if (!city && !state && currentLoc) {
    city = currentLoc.district || currentLoc.place_name || "Local Area";
    state = currentLoc.state || "India";
    if (lat == null) lat = currentLoc.lat;
    if (lon == null) lon = currentLoc.lon;
  }

  // Standardized formatting: District/City (State), e.g. Patna (Bihar) or Ranchi (Jharkhand)
  let placeFormatted = "";
  if (city && state && city.toLowerCase() !== state.toLowerCase()) {
    placeFormatted = `${city} (${state})`;
  } else if (city && !state) {
    placeFormatted = `${city} (India)`;
  } else if (state) {
    placeFormatted = `${state} (Statewide)`;
    city = state;
  } else {
    placeFormatted = "National Watch (India)";
    city = "India";
    state = "India";
  }

  // Clean hazard subtitle
  let hazardLabel = w.kind || w.hazard || "Warning";
  if (hazardLabel === "aqi" || hazardLabel === "air") hazardLabel = "Air Quality Warning";
  else if (hazardLabel === "rainfall") hazardLabel = "Heavy Rainfall Advisory";
  else if (hazardLabel === "flood") hazardLabel = "Severe Flood Warning";
  else if (hazardLabel === "cloudburst") hazardLabel = "Cloudburst conditions (watch)";
  else if (hazardLabel === "extreme_rain") hazardLabel = "Extreme rain nowcast";
  else if (hazardLabel === "thunderstorm" || hazardLabel === "lightning") hazardLabel = "Thunderstorm & Squall";
  else if (hazardLabel === "cyclone") hazardLabel = "Tropical Cyclone Alert";
  else if (hazardLabel === "heatwave") hazardLabel = "Heatwave Advisory";
  else if (hazardLabel === "drought") hazardLabel = "Agricultural Drought";
  else if (hazardLabel === "seismic") hazardLabel = "Earthquake Tremor";
  else if (hazardLabel === "tsunami") hazardLabel = "Tsunami Threat Watch";
  else if (hazardLabel === "marine") hazardLabel = "Marine Sea-State Alert";
  else if (hazardLabel === "wind") hazardLabel = "High Wind Squall";
  else hazardLabel = "Severe Weather Alert";

  return {
    placeFormatted,
    hazardLabel,
    city: city || state || "India",
    state: state || "India",
    lat,
    lon,
  };
}

export interface AlertCluster {
  id: string;
  placeFormatted: string;
  city: string;
  state: string;
  lat: number | null;
  lon: number | null;
  distKm: number | null;
  isCurrentLoc: boolean;
  highestSeverity: string;
  isExtreme: boolean;
  isWarning: boolean;
  alerts: any[];
  hazardItems: Array<{
    theme: any;
    label: string;
    hazardLabel: string;
    guidance: {
      category: string;
      threat: string;
      guidance: string;
      action: string;
    };
    alert: any;
  }>;
  compositeTitle: string;
  compositeGuidance: string;
  compositeAction: string;
  primaryTheme: any;
}


export function groupAlertsByLocation(
  alerts: any[],
  currentLoc?: Location | null
): AlertCluster[] {
  const map = new Map<string, any[]>();

  for (const w of alerts) {
    const locInfo = parseAlertLocation(w, currentLoc);
    const key = locInfo.placeFormatted.toLowerCase().trim();
    if (!map.has(key)) {
      map.set(key, []);
    }
    map.get(key)!.push(w);
  }

  const curLat = currentLoc?.lat;
  const curLon = currentLoc?.lon;

  const severityRank: Record<string, number> = {
    extreme: 10,
    danger: 9,
    critical: 8,
    severe: 8,
    warning: 7,
    alert: 6,
    watch: 5,
    advisory: 4,
    notice: 3,
    normal: 1,
  };

  const clusters: AlertCluster[] = [];

  map.forEach((rawGroup, key) => {
    const firstLoc = parseAlertLocation(rawGroup[0], currentLoc);
    const city = firstLoc.city;
    const state = firstLoc.state;
    const lat = firstLoc.lat;
    const lon = firstLoc.lon;
    const placeFormatted = firstLoc.placeFormatted;

    const isCurrentLoc =
      !!currentLoc &&
      (currentLoc.district.toLowerCase() === city.toLowerCase() ||
        (lat != null && lon != null && curLat != null && curLon != null && Math.abs(lat - curLat) < 0.05 && Math.abs(lon - curLon) < 0.05));

    const distKm =
      curLat != null && curLon != null && lat != null && lon != null
        ? haversineKm(curLat, curLon, lat, lon)
        : null;

    let maxRank = 0;
    let highestSeverity = "Warning";
    for (const item of rawGroup) {
      const s = (item.severity || "warning").toLowerCase();
      const r = severityRank[s] || 4;
      if (r > maxRank) {
        maxRank = r;
        highestSeverity = item.severity || "Warning";
      }
    }

    const isExtreme = maxRank >= 8;
    const isWarning = maxRank >= 6 && !isExtreme;

    // Build distinct hazard themes & guidance for items in this location
    const hazardItems = rawGroup.map((a) => {
      const l = parseAlertLocation(a, currentLoc);
      const theme = getHazardTheme(a.kind || a.hazard);
      const guidance = getGeneralizedAlertGuidance(a);
      return {
        theme,
        label: theme.label,
        hazardLabel: l.hazardLabel,
        guidance,
        alert: a,
      };
    });

    const primaryTheme = hazardItems[0].theme;

    let compositeTitle = "";
    let compositeGuidance = "";
    let compositeAction = "";

    if (rawGroup.length === 1) {
      const h0 = hazardItems[0];
      compositeTitle = h0.hazardLabel;
      compositeGuidance = h0.guidance.guidance;
      compositeAction = h0.guidance.action;
    } else {
      // Natural, clean multi-hazard headlines without messy brackets
      const distinctLabels = Array.from(new Set(hazardItems.map((h) => h.label)));
      if (distinctLabels.length === 2) {
        compositeTitle = `${distinctLabels[0]} & ${distinctLabels[1]}`;
      } else if (distinctLabels.length === 3) {
        compositeTitle = `${distinctLabels[0]}, ${distinctLabels[1]} & ${distinctLabels[2]}`;
      } else {
        compositeTitle = `${distinctLabels[0]}, ${distinctLabels[1]} & +${distinctLabels.length - 2} Hazards`;
      }

      const distinctThreats = Array.from(new Set(hazardItems.map((h) => h.guidance.guidance)));
      compositeGuidance = distinctThreats.slice(0, 2).join(" ");

      const distinctActions = Array.from(new Set(hazardItems.map((h) => h.guidance.action)));
      compositeAction = distinctActions.slice(0, 2).join("; ");
    }

    clusters.push({
      id: `cluster_${key}_${rawGroup.length}`,
      placeFormatted,
      city,
      state,
      lat,
      lon,
      distKm,
      isCurrentLoc,
      highestSeverity,
      isExtreme,
      isWarning,
      alerts: rawGroup,
      hazardItems,
      compositeTitle,
      compositeGuidance,
      compositeAction,
      primaryTheme,
    });
  });

  // Extreme first -> Active location -> Closest distance
  return clusters.sort((a, b) => {
    if (a.isExtreme && !b.isExtreme) return -1;
    if (!a.isExtreme && b.isExtreme) return 1;

    if (a.isCurrentLoc && !b.isCurrentLoc) return -1;
    if (!a.isCurrentLoc && b.isCurrentLoc) return 1;

    const distA = a.distKm ?? 9999;
    const distB = b.distKm ?? 9999;
    return distA - distB;
  });
}


export function getGeneralizedAlertGuidance(w: any) {
  const k = (w.kind || w.hazard || "").toLowerCase();
  const title = (w.title || "").toLowerCase();

  if (k === "rainfall" || title.includes("rain") || title.includes("precip")) {
    return {
      category: "Hydrometeorological Threat",
      threat: "Intense downpours with elevated precipitation rates.",
      guidance: "High probability of localized street waterlogging, urban drainage congestion, and slippery highways.",
      action: "Avoid waterlogged underpasses, check storm drains, and defer non-essential transit in low-lying sectors.",
    };
  }
  if (k === "flood" || title.includes("flood") || title.includes("discharge")) {
    return {
      category: "Hydrological Inundation",
      threat: "River discharge surge and rapid overland runoff.",
      guidance: "Riparian floodplains and low-lying settlements face imminent flood water ingress.",
      action: "Move valuables and livestock to higher ground, avoid riverbanks, and adhere to local emergency directives.",
    };
  }
  if (k === "cloudburst" || title.includes("cloudburst")) {
    return {
      category: "Convective Flash Flood",
      threat: "Extreme localized cloudburst downpour.",
      guidance: "Torrential runoff, sudden debris streams, and violent flash floods likely in hillside and drainage basins.",
      action: "Evacuate low riverbeds and mountain water channels immediately without waiting for warnings.",
    };
  }
  if (k === "thunderstorm" || k === "lightning" || title.includes("thunder") || title.includes("lightning") || title.includes("squall")) {
    return {
      category: "Severe Convective / Squall",
      threat: "Active thunderstorm cells with cloud-to-ground lightning.",
      guidance: "Sudden damaging wind gusts, lightning hazard, and intense short-duration rainfall.",
      action: "Take sturdy indoor shelter, stay away from tall trees and metal poles, and disconnect sensitive electronics.",
    };
  }
  if (k === "cyclone" || title.includes("cyclone") || title.includes("depression")) {
    return {
      category: "Tropical Cyclonic System",
      threat: "Deep cyclonic vortex generating gale-force squalls.",
      guidance: "Dangerous storm surges, destructive coastal gusts, and extensive squally rainbands.",
      action: "Secure lightweight rooftops, suspend all maritime/boating operations, and keep emergency supplies ready.",
    };
  }
  if (k === "heatwave" || title.includes("heat")) {
    return {
      category: "Thermal Heatwave Advisory",
      threat: "Dangerous ambient heat index and thermal stress.",
      guidance: "High risk of heat exhaustion, cramps, and dehydration, especially for elders and outdoor workers.",
      action: "Avoid midday sun between 11 AM – 4 PM, drink oral rehydration fluids, and wear light breathable clothing.",
    };
  }
  if (k === "drought" || title.includes("drought")) {
    return {
      category: "Agricultural Moisture Deficit",
      threat: "Prolonged rainfall deficit and root-zone moisture depletion.",
      guidance: "Crop water stress and depleting surface groundwater storage.",
      action: "Adopt soil mulching, implement deficit drip irrigation, and conserve domestic water supplies.",
    };
  }
  if (k === "aqi" || k === "air" || title.includes("aqi") || title.includes("air")) {
    return {
      category: "Atmospheric Air Quality",
      threat: "Elevated particulate pollution (PM2.5 / PM10 / Smog).",
      guidance: "Air quality index in hazardous zone with heightened risk of respiratory and ocular irritation.",
      action: "Wear N95 respirators outdoors, avoid outdoor exertion, and keep indoor air purifiers operational.",
    };
  }
  if (k === "seismic" || title.includes("earthquake") || title.includes("quake")) {
    return {
      category: "Seismological Event",
      threat: "Crustal tectonic ground motion.",
      guidance: "Ground tremor recorded in seismic zone with potential localized aftershocks.",
      action: "Follow 'Drop, Cover, and Hold On'. Check utility gas lines and structural walls before re-entering buildings.",
    };
  }
  if (k === "tsunami" || title.includes("tsunami")) {
    return {
      category: "Oceanic Tsunami Watch",
      threat: "Oceanic seismic disturbance and potential wave anomaly.",
      guidance: "Hazardous coastal sea-level fluctuations and strong marine currents.",
      action: "Move away from sea beaches, harbors, and low-lying coastal fringes to higher inland terrain immediately.",
    };
  }
  if (k === "marine" || title.includes("marine") || title.includes("wave")) {
    return {
      category: "Marine Sea-State Advisory",
      threat: "High swell breakers and turbulent coastal surf.",
      guidance: "Dangerous navigational conditions for small craft and artisanal fishing vessels.",
      action: "Fishermen advised not to venture into open deep waters; port cautionary signals active.",
    };
  }
  if (k === "wind" || title.includes("wind")) {
    return {
      category: "Gale / High Wind Advisory",
      threat: "Strong wind gusts and turbulent squalls.",
      guidance: "Risk of broken tree limbs, dislodged signages, and temporary utility interruptions.",
      action: "Park vehicles clear of large trees and secure loose construction scaffolding.",
    };
  }
  if (k === "fog" || title.includes("fog")) {
    return {
      category: "Dense Fog Advisory",
      threat: "Low visibility from radiation or advection fog.",
      guidance: "Road, rail and flight delays; very dense fog is under 50 m visibility.",
      action: "Slow travel, use fog lamps, and allow extra time for morning commutes.",
    };
  }
  if (k === "uv" || k === "uv_heat" || title.includes("uv") || title.includes("radiation")) {
    return {
      category: "High-risk UV / Solar Radiation",
      threat: "WHO very high or extreme ultraviolet index.",
      guidance: "Unprotected skin can burn quickly around solar noon, worse with heat.",
      action: "Seek shade 11:00–15:30 IST, wear sleeves, hat and sunglasses.",
    };
  }
  if (k === "fire" || title.includes("forest fire") || title.includes("wildfire")) {
    return {
      category: "Forest Fire / Thermal Anomaly",
      threat: "Satellite hotspots from NASA FIRMS VIIRS.",
      guidance: "Smoke, crop-residue burns, or wildfire. Not a burned-area map.",
      action: "Avoid smoke, keep windows shut, do not light open fires.",
    };
  }
  if (k === "landslide" || title.includes("landslide") || title.includes("mudslide")) {
    return {
      category: "Landslide Watch",
      threat: "Steep slopes after heavy rain may fail.",
      guidance: "Hill roads, cuts and riverbeds are the first to go.",
      action: "Stay off steep cuts, avoid night travel on hill roads, move upslope of debris fans.",
    };
  }
  return {
    category: "Official Disaster Advisory",
    threat: "Severe meteorological or environmental advisory active.",
    guidance: "Elevated risk conditions evaluated for this administrative jurisdiction.",
    action: "Monitor verified government bulletins and follow local civil defense advisories.",
  };
}


export function openAlert(w: { url?: string | null; href_kind?: string | null; lat?: number | null; lon?: number | null; kind?: string | null }, onNavigateData?: (sub: string) => void, setTab?: (t: "map" | "analytics" | "model" | "data") => void, setMapFocus?: (c: [number, number]) => void) {
  if (w.url && (w.href_kind === "bulletin" || /^https?:/i.test(w.url))) {
    window.open(w.url, "_blank", "noopener,noreferrer");
    return;
  }
  if (w.lat != null && w.lon != null && setMapFocus && setTab && (w.href_kind === "map" || !w.href_kind)) {
    setMapFocus([Number(w.lat), Number(w.lon)]);
    setTab("map");
    return;
  }
  if (w.href_kind === "nowcast") {
    setTab?.("analytics");
    return;
  }
  if (w.href_kind === "predicted") {
    setTab?.("model");
    return;
  }
  if (w.href_kind === "map") {
    setTab?.("map");
    return;
  }
  onNavigateData?.(w.kind === "aqi" ? "environment" : w.kind === "seismic" || w.kind === "tsunami" ? "seismology" : "risks");
}


export function formatAlertWindow(w: { window_start?: string | null; window_end?: string | null; issued_at?: string | null; expires_at?: string | null; eta_min?: number | null }) {
  const fmt = (iso?: string | null) => {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso);
    return d.toLocaleString("en-IN", {
      timeZone: "Asia/Kolkata",
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  };
  const a = w.window_start || w.issued_at;
  const b = w.window_end || w.expires_at;
  if (a && b) return `Expected ${fmt(a)} – ${fmt(b)} IST`;
  if (a) return `From ${fmt(a)} IST`;
  if (b) return `Until ${fmt(b)} IST`;
  if (w.eta_min != null && Number.isFinite(Number(w.eta_min))) {
    const m = Math.max(0, Math.round(Number(w.eta_min)));
    return m <= 5 ? "Expected now" : `Expected in ${m} min`;
  }
  return "";
}


export function alertTimePhase(w: {
  window_start?: string | null;
  window_end?: string | null;
  issued_at?: string | null;
  expires_at?: string | null;
  valid_until?: string | null;
}): "past" | "active" | "future" {
  const now = Date.now();
  const parse = (iso?: string | null) => {
    if (!iso) return NaN;
    const t = Date.parse(iso);
    return Number.isNaN(t) ? NaN : t;
  };
  const start = parse(w.window_start);
  const end = parse(w.window_end || w.expires_at || w.valid_until);
  const issued = parse(w.issued_at);
  if (!Number.isNaN(end) && end < now - 15 * 60_000) return "past";
  if (!Number.isNaN(start) && start > now + 20 * 60_000) return "future";
  if (Number.isNaN(end) && !Number.isNaN(issued) && now - issued > 48 * 3600_000) return "past";
  return "active";
}

// Great-circle Haversine Distance (in km)

export function formatOfficialBulletin(body?: string | null, rawTitle?: string): {
  headline?: string;
  description: string;
  instructions?: string;
  areaDesc?: string;
  severity?: string;
  urgency?: string;
  isStructuredJson: boolean;
} {
  const text = (body || rawTitle || "").trim();
  if (!text) {
    return { description: "Official meteorological warning bulletin in effect for this region.", isStructuredJson: false };
  }

  // Attempt to parse JSON string or extract JSON block
  let parsed: Record<string, any> | null = null;
  if (text.startsWith("{") && text.endsWith("}")) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = null;
    }
  } else {
    const jsonMatch = text.match(/\{[\s\S]*"headline"[\s\S]*\}/) || text.match(/\{[\s\S]*"description"[\s\S]*\}/);
    if (jsonMatch) {
      try {
        parsed = JSON.parse(jsonMatch[0]);
      } catch {
        parsed = null;
      }
    }
  }

  if (parsed && typeof parsed === "object") {
    return {
      headline: parsed.headline || parsed.event || parsed.title || undefined,
      description: parsed.description || parsed.msg || parsed.summary || parsed.details || text,
      instructions: parsed.instruction || parsed.instructions || parsed.action || undefined,
      areaDesc: parsed.areaDesc || parsed.area || parsed.scope || undefined,
      severity: parsed.severity || parsed.level || undefined,
      urgency: parsed.urgency || undefined,
      isStructuredJson: true,
    };
  }

  // Clean XML tags, CAP markers, and clean whitespace
  const cleaned = text
    .replace(/<[^>]+>/g, " ")
    .replace(/\b(CAP-India|NDMA|IMD)\s*::\s*/gi, "")
    .replace(/\\n/g, "\n")
    .replace(/\s{2,}/g, " ")
    .trim();

  return {
    description: cleaned || "Official meteorological warning in effect.",
    isStructuredJson: false,
  };
}

