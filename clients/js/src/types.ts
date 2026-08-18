/** Wire types for Rituchakra API. Safe to copy into a React Native or web app. */

export type Location = {
  id: string;
  label: string;
  country?: string;
  state: string;
  district: string;
  lat: number;
  lon: number;
  timezone?: string;
  crop_hint?: string;
  plot_m2?: number;
  place_kind?: string;
  place_name?: string | null;
};

export type LocQuery = {
  district?: string;
  place?: string;
  lat?: number;
  lon?: number;
};

export type ChatBlock = {
  type: string;
  text?: string;
  items?: { label?: string; cite?: string; unit?: string; value?: unknown }[];
  columns?: string[];
  rows?: Record<string, unknown>[];
  from?: string;
  action?: string;
  why?: unknown;
};

export type ChatMsg = {
  id: string;
  role: string;
  content: string;
  content_en?: string | null;
  locale?: string;
  blocks?: ChatBlock[];
  suggestions?: {
    id: string;
    label: string;
    tab?: string;
    window?: Record<string, unknown>;
    location?: Location;
    center?: number[];
    zoom?: number;
  }[];
  tool_trace?: { name: string; status: string; ms: number }[];
  citations?: { tool?: string; field?: string; value?: unknown }[];
  ui?: Record<string, unknown>[];
  translation?: Record<string, unknown> | null;
};

export type ChatRequest = {
  message: string;
  locale_hint?: string;
  output_locale?: string;
  conversation_id?: string;
  location?: Location | null;
  history?: ChatMsg[];
  regenerate?: boolean;
};

export type Health = {
  ok: boolean;
  service?: string;
  version?: string;
  docs?: string;
  default_location?: Location;
  ollama?: { ok: boolean; detail?: string; model?: string };
};

export type ServiceCard = {
  name: string;
  service: string;
  version: string;
  ok: boolean;
  docs: string;
  openapi: string;
  health: string;
  routes?: { methods: string[]; path: string }[];
};
