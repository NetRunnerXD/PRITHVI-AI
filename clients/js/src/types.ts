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

export type ChatMsg = {
  id: string;
  role: string;
  content: string;
  content_en?: string | null;
  locale?: string;
  tool_trace?: { name: string; status: string; ms: number }[];
  translation?: Record<string, unknown> | null;
};

export type ChatRequest = {
  message: string;
  locale_hint?: string;
  output_locale?: string;
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
