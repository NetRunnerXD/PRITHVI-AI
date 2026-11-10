/** Normalize /api/ready ingest payloads so the Map satellite-progress UI never crashes. */

export type IngestSat = {
  id?: string;
  name?: string;
  status?: string;
  detail?: string;
  bytes_read?: number;
  bytes_total?: number;
  started_ms?: number;
  done_ms?: number;
};

export type IngestSnap = {
  phase?: string;
  ready?: boolean;
  stale?: boolean;
  message?: string;
  satellites: IngestSat[];
  started_ms?: number;
  updated_ms?: number;
  data_time?: string | null;
  age_s?: number | null;
  as_of?: string;
};

export function parseIngestSnap(raw: unknown): IngestSnap | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const o = raw as Record<string, unknown>;
  const satellites = Array.isArray(o.satellites)
    ? o.satellites.filter((s): s is IngestSat => !!s && typeof s === "object" && !Array.isArray(s))
    : [];
  return {
    phase: typeof o.phase === "string" ? o.phase : "idle",
    ready: Boolean(o.ready),
    stale: Boolean(o.stale),
    message: typeof o.message === "string" ? o.message : "",
    satellites,
    started_ms: typeof o.started_ms === "number" ? o.started_ms : undefined,
    updated_ms: typeof o.updated_ms === "number" ? o.updated_ms : undefined,
    data_time: typeof o.data_time === "string" ? o.data_time : o.data_time == null ? null : undefined,
    age_s: typeof o.age_s === "number" ? o.age_s : o.age_s == null ? null : undefined,
    as_of: typeof o.as_of === "string" ? o.as_of : undefined,
  };
}

/** Safe access for optional storm-map packs (null until /nowcast/storm-map returns). */
export function stormDataTime(storm: unknown): string | undefined {
  if (!storm || typeof storm !== "object") return undefined;
  const t = (storm as { ir_image_time?: unknown }).ir_image_time;
  return typeof t === "string" && t ? t : undefined;
}
