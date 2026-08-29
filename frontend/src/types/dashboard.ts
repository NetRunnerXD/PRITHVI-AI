export type Location = {
  id: string;
  label: string;
  country: string;
  state: string;
  district: string;
  imd_subdivision?: string | null;
  lat: number;
  lon: number;
  timezone: string;
  crop_hint: string;
  season_hint?: string;
  plot_m2?: number;
  place_kind?: string;
  place_name?: string | null;
};

export type Factor = { id: string; label: string; contribution_pct: number };

export type RiskCard = {
  id: string;
  label: string;
  severity: string;
  score_pct: number;
  confidence_pct: number;
  horizon_hours: number;
  factors: Factor[];
  method: string;
  inputs_used: string[];
  missing_inputs: string[];
  sources: string[];
  updated_at: string;
};

export type TimePoint = { t: string; value: number; unit: string; source: string };

export type EarlyWarning = {
  id: string;
  severity: string;
  title: string;
  body: string;
  lenses: string[];
  source: string;
  hazard?: string;
  issued_at?: string | null;
  distance_km?: number | null;
  linked_risk_id?: string | null;
};

export type WindHour = {
  t: string;
  dir: number;
  speed: number;
  compass: string;
  flow: string;
};

export type LiveWatch = {
  generated_at: string;
  refresh_s: number;
  sky: {
    label?: string;
    kind?: string;
    weather_code?: number | null;
    is_day?: boolean | null;
    cloud_cover_pct?: number | null;
    visibility_km?: number | null;
    temp_c?: number | null;
    humidity_pct?: number | null;
    precip_1h_mm?: number | null;
    place?: string;
  };
  wind: {
    speed_kmh?: number | null;
    speed_ms?: number | null;
    direction_deg?: number | null;
    compass?: string;
    flow_compass?: string;
    flow_deg?: number | null;
    hourly?: WindHour[];
    rose?: { dir: string; count: number; avg_speed: number }[];
  };
  marine: {
    inland?: boolean;
    wave_height_m?: number | null;
    wave_period_s?: number | null;
    wave_dir_deg?: number | null;
    wave_compass?: string | null;
    nearest_coast?: string | null;
    coast_km?: number | null;
    snapped?: boolean;
    source?: string;
    wave_peak_period_s?: number | null;
    wind_wave_height_m?: number | null;
    swell_height_m?: number | null;
    swell_period_s?: number | null;
    sst_c?: number | null;
    sea_level_m?: number | null;
    ocean_current_ms?: number | null;
    ocean_current_dir?: number | null;
  };
  flood: {
    discharge?: number[];
    trend?: string;
    score_pct?: number;
    source?: string;
  };
  air: {
    cpcb?: {
      value?: number;
      category?: string;
      station?: string;
      dominant_pollutant?: string;
    } | null;
    open_meteo?: {
      us_aqi?: number | null;
      european_aqi?: number | null;
      pm2_5?: number | null;
      pm10?: number | null;
      no2?: number | null;
      so2?: number | null;
      co?: number | null;
      co2?: number | null;
      o3?: number | null;
      nh3?: number | null;
      ch4?: number | null;
      dust?: number | null;
      uv_index?: number | null;
      uv_index_clear_sky?: number | null;
      pollen?: Record<string, number | null>;
    };
    waqi?: Record<string, unknown> | null;
    openweather?: Record<string, unknown> | null;
    sources?: string[];
    history?: { t?: string; value?: number }[];
    history_source?: string;
  };
  quakes: {
    mag?: number | null;
    place?: string | null;
    distance_km?: number | null;
    time_iso?: string | null;
    tsunami_flag?: boolean;
  }[];
  tsunami: { title?: string; body?: string; source?: string }[];
  source_notes?: string[];
};

export type Prescription = {
  id: string;
  priority: number;
  action: string;
  rationale_codes: string[];
  quant: {
    water_saved_liters_min?: number | null;
    water_saved_liters_max?: number | null;
    method?: string | null;
    assumptions?: Record<string, unknown>;
  };
  template_id?: string | null;
  slots?: Record<string, unknown>;
  confidence_pct: number;
  why?: string;
  when?: string;
  who?: string;
};

export type OutlookDay = {
  date: string;
  precip_mm: number;
  precip_prob_pct: number;
  temp_max_c?: number | null;
  temp_min_c?: number | null;
  et0_mm: number;
  soil_m3m3: number;
  water_balance_mm: number;
  irrigate: boolean;
  flood_watch: boolean;
};

export type DashboardSnapshot = {
  location: Location;
  generated_at: string;
  sources: string[];
  descriptive: {
    current: {
      temp_c?: number | null;
      precip_1h_mm?: number | null;
      humidity_pct?: number | null;
      wind_ms?: number | null;
      wind_dir_deg?: number | null;
      wind_compass?: string | null;
      soil_moisture_m3m3?: number | null;
      et0_mm?: number | null;
      aqi?: number | null;
      aqi_category?: string | null;
      aqi_station?: string | null;
      aqi_pollutant?: string | null;
      sky_label?: string | null;
      sky_kind?: string | null;
      cloud_cover_pct?: number | null;
      visibility_km?: number | null;
      is_day?: boolean | null;
      wave_height_m?: number | null;
      om_us_aqi?: number | null;
      om_pm25?: number | null;
      apparent_temp_c?: number | null;
      dew_point_c?: number | null;
      pressure_msl_hpa?: number | null;
      uv_index?: number | null;
      sst_c?: number | null;
      swell_height_m?: number | null;
    };
    series: Record<string, TimePoint[]>;
  };
  diagnostic: {
    anomalies: { variable: string; z_score: number; label: string }[];
    drivers: string[];
    stories?: { id: string; title: string; why: string; evidence: string; implication?: string }[];
  };
  predictive: {
    precip_next_3d_mm: number;
    precip_7d_mm?: number;
    precip_probability_pct: number[];
    temp_max_c: number[];
    temp_min_c: number[];
    flood_discharge_trend: string;
    river_discharge: number[];
    water_balance_7d_mm?: number;
    et0_7d_mm?: number;
    irrigate_dates?: string[];
    flood_watch_dates?: string[];
    outlook_days?: OutlookDay[];
    model: string;
  };
  prescriptive: { warnings: EarlyWarning[]; actions: Prescription[] };
  risks: RiskCard[];
  map: { center: number[]; zoom: number; layers: { id: string; visible?: boolean }[] };
  vegetation: { index?: number; label?: string; kind?: string; note?: string };
  provider_status: Record<string, string>;
  ogd?: {
    aqi?: {
      value?: number;
      category?: string;
      station?: string;
      city?: string;
      dominant_pollutant?: string;
      pollutants?: Record<string, number>;
      updated?: string;
    } | null;
    mandi?: {
      commodity?: string;
      variety?: string;
      market?: string;
      modal_price?: number;
      min_price?: number | null;
      max_price?: number | null;
      date?: string;
      unit?: string;
    }[];
    nearby?: Location[];
    quakes?: Record<string, unknown>[];
    tsunami?: Record<string, unknown>[];
    gdacs?: Record<string, unknown>[];
    mosdac?: Record<string, unknown>;
    moon?: Record<string, unknown>;
  };
  quality?: {
    air?: Record<string, unknown>;
    climate?: Record<string, unknown>;
    moon?: Record<string, unknown>;
    marine?: Record<string, unknown>;
    seismic?: Record<string, unknown>[];
    tsunami?: Record<string, unknown>[];
    flood?: Record<string, unknown>;
    gdacs?: Record<string, unknown>[];
    mosdac?: Record<string, unknown>;
  };
  predictions?: {
    trusted?: PredictionPack;
    ours?: PredictionPack;
    adjustments?: string[];
    inputs?: Record<string, number>;
    hazards?: {
      flood?: { score_pct?: number; level?: string; days?: string[]; drivers?: string[]; method?: string; source?: string };
      tsunami?: { score_pct?: number; level?: string; threat?: boolean; latest_title?: string; coast_km?: number; method?: string };
      seismic?: { score_pct?: number; level?: string; nearest_mag?: number | null; nearest_km?: number | null; nearest_place?: string; method?: string };
    };
  };
  live?: LiveWatch;
  science?: {
    hysteresis?: {
      limb?: string;
      memory?: number;
      soil_now?: number;
      runoff_3d_mm?: number;
      runoff_7d_mm?: number;
      flip?: string;
      method?: string;
    };
    regret?: {
      action?: string;
      regret_hold_mm?: number;
      regret_apply_mm?: number;
      chosen_regret_mm?: number;
      liters_at_risk_min?: number;
      liters_at_risk_max?: number;
      method?: string;
    };
    livelihood?: {
      score_pct?: number;
      level?: string;
      task?: string;
      closed_days?: string[];
      drivers?: string[];
      method?: string;
    };
    residual?: { id?: string; frac?: number; regime?: string; identified?: boolean; method?: string; note?: string };
    bandit?: { source?: string; trust_ours_pct?: number; reason?: string; method?: string };
    phenology?: { family?: string; stage?: string; stage_score?: number; mandi_stress?: number; method?: string };
    vernacular?: { named?: { tag?: string; en?: string; hi?: string; bn?: string }; heard?: { tags?: string[] } };
    blindspot?: { score_pct?: number; level?: string; drivers?: string[]; note?: string; method?: string };
    water_balance?: {
      identity?: string;
      parts?: Record<string, number>;
      checksum_mm?: number;
      method?: string;
    };
    verify?: { method?: string; note?: string; abs_vs_clim_mm?: number; nowcast?: { last_error_mm?: number | null; frac?: number } };
    nowcast?: NowcastPack;
    provenance?: Record<string, string>;
    monsoon?: { label?: string; regime?: string };
    cwc?: { name?: string; km?: number; river?: string; relevant?: boolean };
    port?: { active?: boolean; signal?: string | null; relevant?: boolean };
    phys?: { kind?: string; label?: string; pond_scale?: number; hugli?: boolean; show_tide?: boolean };
    market_lock?: { advice?: string; lock?: boolean };
    ledger?: { days?: { date?: string; precip_mm?: number }[] };
  };
};

export type NowcastHour = {
  t: string;
  lead_h?: number;
  mm: number;
  p_wet?: number;
  engine: string;
  nwp_mm?: number;
  persist_mm?: number;
  source?: string;
};

export type NowcastPack = {
  method?: string;
  hours?: NowcastHour[];
  observed?: NowcastHour[];
  gap?: { dt_s?: number; series?: { t: string; mm: number; mm_h?: number; p_wet?: number }[]; note?: string };
  playhead?: Record<string, unknown>;
  regime?: { name?: string; daily?: string; last_mm?: number; method?: string };
  clock?: { t_start?: string | null; t_stop?: string | null };
  ponding?: { mm_60?: number; mm_120?: number; factor?: number; phys?: string };
  pump?: { p_interrupt_90m?: number; liters_at_risk?: number; rain_90m_mm?: number; action?: string };
  access?: { enterable?: boolean; p_closed_2h?: number; reasons?: string[]; stage?: string };
  kal?: { score_pct?: number; level?: string; kal_belt?: boolean };
  tide?: { drain_blocked?: boolean; coastal?: boolean; rain_3h_mm?: number; stay_off_ghat?: boolean; relevant?: boolean };
  phys?: { kind?: string; label?: string; pond_scale?: number; hugli?: boolean; show_tide?: boolean };
  cost?: { wasted_liters_if_apply?: number; stress_mm_if_wait_2h?: number; prefer?: string };
  air?: { peak_us_aqi?: number | null; hours?: { t?: string; us_aqi?: number }[] };
  labour?: { closed_2h?: boolean; peak_us_aqi?: number };
  squall?: { watch?: boolean; visibility_km?: number | null };
  split?: { pluvial?: boolean; fluvial?: boolean };
  stream?: { upstream?: { district?: string; mm?: number | null; km?: number } | null; eta_h?: number | null };
  neighbor_storm?: { flag?: boolean; wet_neighbors?: number; home_mm?: number };
  locked?: Record<string, unknown>;
  actions?: { id?: string; action?: string; verb?: string; when?: string }[];
  sat?: SatKalmanPack;
  convective?: ConvectivePack;
  sat_live?: SatLivePack;
};

export type ConvectivePack = {
  lightning?: { level?: string; score_pct?: number; n_strokes?: number; nearest_km?: number | null; detected?: boolean; nowcast?: { eta_min?: number | null } };
  cloudburst?: { level?: string; score_pct?: number; eta_min?: number | null; rain_sat_mm_h?: number; rain_ir_mm_h?: number };
  downburst?: { level?: string; score_pct?: number; eta_min?: number | null; gust_env_kmh?: number; cape_jkg?: number };
  cell?: { id?: string; lat?: number; lon?: number; min_tb_k?: number; rain_ir_mm_h?: number; trend?: string; speed_kmh?: number };
  n_cells?: number;
  sensors?: Record<string, boolean>;
};

export type SatLivePack = {
  ok?: boolean;
  as_of?: string;
  insat?: { ok?: boolean; source?: string; tb_k?: number | null };
  ir?: { ok?: boolean; source?: string; tb_k?: number | null };
  imerg?: { ok?: boolean; mm_h?: number | null; source?: string };
  lightning?: { ok?: boolean; n?: number; nearest_km?: number | null; strokes?: { lat: number; lon: number; distance_km: number; t?: string | null }[] };
  cells?: ConvectivePack["cell"][];
};

export type SatKalmanPack = {
  engine?: string;
  source?: string;
  source_kind?: string;
  obs_knots?: { t: string; mm?: number; mm_h?: number }[];
  pred_series?: { t: string; mm_h: number; mm?: number; lead_s?: number; engine?: string }[];
  playhead_rate?: number;
  last_error_mm_h?: number | null;
  mae?: number | null;
  n_updates?: number;
  kalman_gain?: number[];
  next_obs_eta_s?: number | null;
  stride_s?: number;
  note?: string;
  method?: string;
  formula?: {
    kind?: string;
    eps?: number;
    adv_mm_h?: number;
    x?: number[];
    last_obs_t?: string | null;
    last_obs_mm_h?: number | null;
    pulses?: { c?: string; s?: number; a?: number; kind?: string }[];
    drivers?: Record<string, unknown>;
  };
  innovations?: { t: string; y: number; obs: number; pred: number }[];
  history?: SatHistoryPack;
  rewrites_locked?: boolean;
  error?: string;
};

export type SatHistoryPoint = {
  t: string;
  pred?: number | null;
  held?: number | null;
  obs?: number | null;
  y?: number | null;
  after?: number | null;
  scene?: boolean;
};

export type SatHistoryPack = {
  series?: SatHistoryPoint[];
  scenes?: { t: string; obs: number; pred: number; y: number; after?: number | null }[];
  mae?: number | null;
  n?: number;
  stride_s?: number;
  note?: string;
  engine?: string;
};

export type ChatTranslation = {
  engine?: string;
  src?: string;
  tgt?: string;
  inbound?: { src?: string; tgt?: string; engine?: string; ok?: boolean };
  outbound?: { src?: string; tgt?: string; engine?: string; ok?: boolean };
};

export type ChatBlock = {
  type: string;
  text?: string;
  title?: string;
  items?: { label?: string; cite?: string; unit?: string; value?: unknown }[];
  columns?: string[];
  rows?: Record<string, unknown>[];
  from?: string;
  action?: string;
  why?: unknown;
};

export type UiAction = {
  op: string;
  tab?: string;
  path?: string;
  value?: unknown;
  target?: string;
  center?: number[];
  zoom?: number;
  location?: Location;
  highlight?: string;
};

export type ChatSuggestion = {
  id: string;
  label: string;
  tab?: string;
  window?: Record<string, unknown>;
  location?: Location;
  center?: number[];
  zoom?: number;
};

export type ChatMsg = {
  id: string;
  role: "user" | "assistant";
  content: string;
  content_en?: string | null;
  locale?: string;
  blocks?: ChatBlock[];
  suggestions?: ChatSuggestion[];
  tool_trace?: { name: string; status: string; ms: number }[];
  citations?: { tool?: string; field?: string; value?: unknown }[];
  ui?: UiAction[];
  translation?: ChatTranslation;
};

export type TabId =
  | "overview"
  | "nowcast"
  | "alerts"
  | "map"
  | "forecast"
  | "predicted"
  | "risks"
  | "market"
  | "advisor"
  | "settings";

export type ThemeId = "sand" | "monsoon" | "midnight" | "ocean" | "contrast";
export type UnitSys = "metric" | "imperial";
export type Density = "comfortable" | "compact";

export type PredDay = OutlookDay & { confidence_pct?: number; adjustment?: string };

export type PredictionPack = {
  source: string;
  method: string;
  days: PredDay[];
  precip_3d_mm: number;
  precip_7d_mm: number;
  et0_7d_mm: number;
  water_balance_7d_mm: number;
  irrigate_dates: string[];
  flood_watch_dates: string[];
};
