from pydantic import BaseModel, Field

from app.schemas.location import Location
from app.schemas.risk import Prescription, RiskCard, TimePoint


class EarlyWarning(BaseModel):
    id: str
    severity: str
    title: str
    body: str = ""
    lenses: list[str] = ["predictive"]
    valid_until: str | None = None
    linked_risk_id: str | None = None
    linked_prescription_ids: list[str] = []
    source: str = "imd-cap"
    hazard: str = "weather"
    issued_at: str | None = None
    distance_km: float | None = None


class CurrentConditions(BaseModel):
    temp_c: float | None = None
    precip_1h_mm: float | None = None
    humidity_pct: float | None = None
    wind_ms: float | None = None
    wind_dir_deg: float | None = None
    wind_compass: str | None = None
    soil_moisture_m3m3: float | None = None
    et0_mm: float | None = None
    weather_code: int | None = None
    cloud_cover_pct: float | None = None
    visibility_km: float | None = None
    is_day: bool | None = None
    sky_label: str | None = None
    sky_kind: str | None = None
    aqi: int | None = None
    aqi_category: str | None = None
    aqi_station: str | None = None
    aqi_pollutant: str | None = None
    wave_height_m: float | None = None
    wave_period_s: float | None = None
    wave_dir_deg: float | None = None
    wave_compass: str | None = None
    om_us_aqi: int | None = None
    om_eu_aqi: int | None = None
    om_pm25: float | None = None
    apparent_temp_c: float | None = None
    dew_point_c: float | None = None
    pressure_msl_hpa: float | None = None
    uv_index: float | None = None
    sst_c: float | None = None
    swell_height_m: float | None = None


class Anomaly(BaseModel):
    variable: str
    z_score: float
    label: str
    source: str = "nasa-power"


class Descriptive(BaseModel):
    current: CurrentConditions
    series: dict[str, list[TimePoint]] = {}


class DiagnosticStory(BaseModel):
    id: str
    title: str
    why: str
    evidence: str
    implication: str = ""


class Diagnostic(BaseModel):
    anomalies: list[Anomaly] = []
    drivers: list[str] = []
    stories: list[DiagnosticStory] = []


class Predictive(BaseModel):
    precip_next_3d_mm: float = 0.0
    precip_7d_mm: float = 0.0
    precip_probability_pct: list[int] = []
    temp_max_c: list[float] = []
    temp_min_c: list[float] = []
    flood_discharge_trend: str = "steady"
    river_discharge: list[float] = []
    water_balance_7d_mm: float = 0.0
    et0_7d_mm: float = 0.0
    irrigate_dates: list[str] = []
    flood_watch_dates: list[str] = []
    outlook_days: list[dict] = []
    model: str = "open-meteo:best_match"


class Prescriptive(BaseModel):
    warnings: list[EarlyWarning] = []
    actions: list[Prescription] = []


class MapState(BaseModel):
    center: list[float]
    zoom: int = 8
    layers: list[dict] = []


class LiveWatch(BaseModel):
    generated_at: str = ""
    refresh_s: int = 300
    sky: dict = {}
    wind: dict = {}
    marine: dict = {}
    flood: dict = {}
    air: dict = {}
    quakes: list[dict] = []
    tsunami: list[dict] = []
    source_notes: list[str] = []


class DashboardSnapshot(BaseModel):
    location: Location
    generated_at: str
    sources: list[str]
    descriptive: Descriptive
    diagnostic: Diagnostic
    predictive: Predictive
    prescriptive: Prescriptive
    risks: list[RiskCard]
    map: MapState
    vegetation: dict = {}
    provider_status: dict[str, str] = {}
    ogd: dict = {}
    predictions: dict = {}
    live: LiveWatch = Field(default_factory=LiveWatch)
    science: dict = {}
    quality: dict = {}
