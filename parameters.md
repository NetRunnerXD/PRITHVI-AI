# Rituchakra parameters

Every quantity the platform **fetches** from a provider or **calculates** locally. Advisor chat never invents these numbers; it only quotes snapshot / `data()` packs.

**Legend**

| Kind | Meaning |
|---|---|
| Fetched | Live API or dataset at the pin (or nearest valid cell) |
| Calculated | Derived in `backend/app` from fetched series |
| Climatology | Seasonal / long-term table, not a live monitor |
| Optional | Only if a key or product is present |

A UI **—** means the field was not in the fetched sample (not a fake zero). A numeric **0** is a real measurement (for example wind-sea height 0.12 m).

Default pin: **Haldia, Purba Medinipur, West Bengal** (`22.0667, 88.0698`). Search is India-only.

---

## 1. Location

| Parameter | Unit | Kind | Source |
|---|---|---|---|
| `lat`, `lon` | ° | Fetched / gazetteer | Towns, districts, Open-Meteo geocode `countryCode=IN` |
| `state`, `district`, `place_name`, `label` | — | Gazetteer | `india_towns`, `india_districts` |
| `timezone` | — | Fixed | `Asia/Kolkata` |
| `crop_hint`, `season_hint` | — | Gazetteer | Crop calendar hint |
| `plot_m2` | m² | Default / settings | Plot area for litre maths (default 400) |
| `place_kind` | — | Calculated | town / district |
| Physiography class | — | Calculated | `hugli` / `orographic` / `arid` / `plateau` / `plains` |
| `coast_km`, nearest coast name | km | Calculated | `india_coast` |
| In-India mask | bool | Calculated | Mainland + NE, Andaman, Lakshadweep |

---

## 2. Atmosphere — current and daily (Open-Meteo forecast)

IST calendar “today”; `past_days=1` so yesterday is available but not labelled as today.

| Parameter | Unit | Kind | Notes |
|---|---|---|---|
| Temperature 2 m now / max / min / mean | °C | Fetched | Daily max/min/mean from IST today |
| Temperature 80 / 120 / 180 m | °C | Fetched | Hourly extra call |
| Apparent temperature now / max / min | °C | Fetched | Open-Meteo, not the UI heat-index fallback |
| Dew point 2 m now / max / min / mean | °C | Fetched | |
| Relative humidity 2 m now / max / min / mean | % | Fetched | |
| Precipitation (rain+showers+snow) now | mm | Fetched | Current hour |
| Rain / showers / snowfall now | mm | Fetched | Split components |
| Rain / showers / snowfall daily sum | mm | Fetched | |
| Precipitation probability now / daily max | % | Fetched | |
| Precipitation hours | h | Fetched | |
| Snow depth | m | Fetched | Often 0 in the plains |
| Weather code | WMO | Fetched | Mapped to `sky_label` / `sky_kind` |
| Sea-level pressure | hPa | Fetched | |
| Surface pressure | hPa | Fetched | |
| Cloud cover total / low / mid / high | % | Fetched | |
| Visibility | m (API), km (UI) | Fetched | |
| Wind speed 10 m now / max / mean | km/h | Fetched | `wind_now_ms` = ÷ 3.6 |
| Wind speed 80 / 120 / 180 m | km/h | Fetched | |
| Wind direction 10 / 80 / 120 / 180 m | ° | Fetched | 16-point compass + flow compass |
| Wind gusts 10 m | km/h | Fetched | |
| Evapotranspiration | mm | Fetched | Hourly |
| Reference ET₀ (FAO) today and daily | mm | Fetched | |
| Vapour pressure deficit | kPa | Fetched | |
| CAPE | J/kg | Fetched | Hourly; convective / thunder |
| Shortwave radiation sum | MJ/m² | Fetched | Daily |
| UV index now | index | Fetched | CAMS air API |
| UV index clear-sky now | index | Fetched | |
| UV index daily max / clear-sky max | index | Fetched | Forecast daily |
| Sunrise / sunset | IST | Fetched | |
| Daylight duration / sunshine duration | s | Fetched | UI shows hours |
| `is_day` | bool | Fetched | |

**Hourly series (window around now):** precip, soil 0–7 cm, temp, RH, dew, MSL pressure, wind, gust, cloud layers, weather code, CAPE, VPD, precip probability.

**7-day hourly forecast (`predictive.hourly`, `GET /api/forecast/hourly`):** IST hours for today through +6 calendar days. Yesterday (`past_days`) is dropped. Model hours, not gauges.

| Field | Unit | Kind |
|---|---|---|
| `t` | ISO local | Fetched timestamp |
| `date`, `hour` | IST calendar | Calculated split |
| `precip_mm` | mm | Fetched |
| `precip_prob_pct` | % | Fetched |
| `temp_c` | °C | Fetched |
| `wind_kmh`, `wind_gust_kmh`, `wind_dir_deg` | km/h, ° | Fetched |
| `rh_pct`, `cloud_pct` | % | Fetched |
| `weather_code`, `sky_label`, `sky_kind` | WMO / text | Fetched + mapped |
| `visibility_km` | km | Fetched (m → km) |

UI: Forecast / Predicted tab expands a day into `HourlyForecast` (table + rain/temp/wind charts). Filter one day with `?date=YYYY-MM-DD`.

**Daily series from IST today:** precip, ET₀, Tmax, Tmin, wind max, wind dir.

---

## 3. Soil

| Parameter | Unit | Kind | Source |
|---|---|---|---|
| Soil moisture 0–7 cm | m³/m³ | Fetched | Outlook / risk backbone |
| Soil moisture 0–1 / 1–3 / 3–9 / 9–27 / 27–81 cm | m³/m³ | Fetched | Quality catalog |
| Soil temperature 0 / 6 / 18 / 54 cm | °C | Fetched | |
| Hysteresis limb | wet/dry | Calculated | Dual-limb soil memory |
| Hysteresis memory | — | Calculated | |
| Runoff 3-day | mm | Calculated | Hysteresis |
| Outlook soil each of 7 days | m³/m³ | Calculated | `outlook.step_day` |

---

## 4. Sun and moon

| Parameter | Unit | Kind | Source |
|---|---|---|---|
| Sunrise, sunset, daylight, sunshine, shortwave, UV max | — | Fetched | Open-Meteo daily |
| Moonrise, moonset | IST | Calculated | Local Meeus-lite (`science/astro.py`) |
| Moon phase name | — | Calculated | Synodic month |
| Moon illumination | 0–1 | Calculated | |

Not WeatherAPI.

---

## 5. Air quality

| Parameter | Unit | Kind | Source |
|---|---|---|---|
| CPCB National AQI | 0–500 | Fetched | data.gov.in resource `3b01bcb8-…` |
| AQI category | Good…Severe | Calculated | CPCB bands |
| Dominant pollutant, station, city, updated | — | Fetched | CPCB |
| CPCB sub-indices (PM10, PM2.5, NO2, SO2, CO, O3, NH3, …) | as published | Fetched | `ogd.aqi.pollutants` |
| US AQI, European AQI | index | Fetched | Open-Meteo CAMS |
| PM10, PM2.5 | µg/m³ | Fetched | CAMS |
| CO, NO2, SO2, O3, NH3, dust | µg/m³ | Fetched | CAMS and/or CPCB (NH3 often CPCB) |
| CO2 | ppm | Fetched | CAMS |
| CH4 | ppb | Fetched | CAMS |
| OpenAQ history | µg/m³ | Fetched | PM2.5/PM10/NO2/SO2/O3/CO/NH3 near the pin |
| WAQI | — | Optional | `WAQI_TOKEN` |
| OpenWeather air | — | Optional | `OPENWEATHER_API_KEY` |
| Hourly US AQI, EU AQI, UV, dust, PM10 | — | Fetched | CAMS `past_days=7` |

**Pollen (grains/m³)**

| Type | Kind | Source |
|---|---|---|
| Grass, mugwort (Asteraceae analog), ragweed (Parthenium analog) | Climatology | WB/Kolkata Burkard seasons, scaled by rain/wind |
| Alder, birch | Climatology | Himalayan long-range analog |
| Olive | Climatology | Casuarina / *Olea ferruginea* analog (not European CAMS Olea) |
| CAMS alder/birch/grass/mugwort/olive/ragweed | Fetched | Europe domain only; overwrites climatology when non-null |

CAMS ammonia/pollen are Europe-only. Where CPCB has no NH3 (e.g. some Leh/Kochi/Andaman samples), the field stays **—**. Port Blair often has no CPCB station; UI can show CAMS US AQI instead.

---

## 6. Marine

Open-Meteo Marine. Inland pins snap to the nearest Indian coast; Hooghly/delta pins may use an offshore Bay of Bengal / Arabian Sea cell when the river-mouth grid is too small.

| Parameter | Unit | Kind |
|---|---|---|
| Wave height, direction, period, peak period | m, °, s | Fetched (peak may copy mean period if the grid omits peak) |
| Wind-wave height, direction, period, peak period | m, °, s | Fetched |
| Swell height, direction, period, peak period | m, °, s | Fetched |
| Secondary swell height, direction, period | m, °, s | Fetched |
| Tertiary swell height, direction, period | m, °, s | Calculated if WAM has no 3rd partition (residual energy / 0.42 × secondary) |
| Sea level height including tides | m MSL | Fetched |
| Sea surface temperature | °C | Fetched |
| Ocean current velocity, direction | m/s, ° | Fetched |
| `marine_inland`, `snapped`, `offshore`, coast name/km | — | Calculated |

Hugli port signal / harmonic tide is **physiography-gated** (not shown as Hooghly for Jaipur/Leh).

---

## 7. Hydrology and flood

| Parameter | Unit | Kind | Source |
|---|---|---|---|
| River discharge, mean, max (daily) | m³/s | Fetched | Open-Meteo GloFAS |
| Discharge trend | rising/falling/steady | Calculated | +8% / −8% day-to-day |
| Empty GloFAS cell | — | Fetched nearby | Offset lat/lon retry (islands/coast) |
| CWC station name, km | — | Table | Static lookup, **not** a live hydrograph |
| Pond / tank scale | — | Calculated | Physiography |
| Water balance 7 d | mm | Calculated | Σ precip − Σ ET₀ |
| Outlook runoff, irrigate flag, flood-watch flag | — | Calculated | Per day |
| Ledger 7-day plot water budget | mm / litres | Calculated | Conservation-closed |
| Water-balance XAI (P − ET − runoff − ΔS) | mm | Calculated | 3-day identity |
| Blindspot (unobserved hydrology) | — | Calculated | |

---

## 8. Climatology and anomaly

| Parameter | Unit | Kind | Source |
|---|---|---|---|
| NASA POWER daily precip climatology | mm | Fetched | `power.larc.nasa.gov` |
| `clim_daily_mm`, `clim_3d_mm` | mm | Calculated | Mean of NASA series |
| `precip_ratio`, `precip_z` | — | Calculated | Today vs climatology |
| Diagnostic anomalies | z-score | Calculated | NASA + drivers |
| Diagnostic stories | text | Calculated | Heat, flood, AQI, … |
| Residual atlas | — | Calculated | India regional Open-Meteo residual |
| Dual 7-day “ours” vs trusted | mm, °C | Calculated | Residual-blend within ~±12% of Open-Meteo |

---

## 9. Seismic

USGS FDSN **CSV** (not GeoJSON) for the India–Indian Ocean box. EMSC FDSN is merged but the quality table prefers a USGS earthquake with station counts.

| Parameter | Unit | Kind |
|---|---|---|
| Time, updated | ISO UTC | Fetched |
| Latitude, longitude | ° | Fetched |
| Depth | km | Fetched |
| Magnitude, magType | — | Fetched |
| nst, gap, dmin, rms | — | Fetched (CSV) |
| net, id, place, type, status | — | Fetched |
| locationSource, magSource | — | Fetched (CSV) |
| horizontalError, depthError, magError, magNst | — | Fetched (CSV) |
| distance_km from pin | km | Calculated |
| tsunami_flag | bool | Fetched (USGS) |

NCS has no public JSON (not scraped).

---

## 10. Tsunami, multi-hazard bulletins

| Parameter | Kind | Source |
|---|---|---|
| ITEWS title, body, threat, mag, region, origin, lat/lon | Fetched | INCOIS catalog / RSS |
| Default “no threat for India” text | Fetched | When the catalog is quiet |
| GDACS event type, name, alert, lat/lon | Fetched | Indian Ocean basin + India-affected |
| IMD CAP warnings | Fetched | CAP RSS (not IMD REST) |
| Sachet / NDMA CAP | Fetched | State + India RSS |
| Hooghly / Haldia port signal | Fetched | Best-effort scrape; hugli belt only |
| Ambee | — | Not wired (no public key) |

---

## 11. Vegetation, phenology, market

| Parameter | Kind | Source |
|---|---|---|
| Vegetation stress index 0–100 | Calculated | ET₀ + soil + 3-day rain (**not NDVI**) |
| Crop stage name / score | Calculated | Calendar + mandi stress |
| Mandi commodity, variety, market, min/max/modal ₹ | Fetched | Agmarknet |
| Mandi stress, arrivals | Calculated | Phenology |
| Market lock / sell_today / wait / open | Calculated | Rain × mandi |

True NDVI would need MOSDAC/Earthdata HEM; not live.

---

## 12. Risk cards (0–100%, XAI factors)

Calculated weighted-linear cards (`ml/risk.py`):

| Card id | Drivers (inputs) |
|---|---|
| Flood | 3-day rain, soil, GloFAS, elevation proxy, IMD CAP |
| Drought | Rain deficit vs climatology, soil, ET₀ |
| Heat | Tmax, RH, consecutive hot days |
| Irrigation need | Soil, ET₀, precip probability |
| Air quality | CPCB / CAMS AQI and pollutants |
| Livelihood | Compound closed-task days |
| Seismic | Nearby USGS magnitude / distance |
| Tsunami | ITEWS threat, coast_km, USGS tsunami flag |

Each card: `score_pct`, `severity`, `confidence_pct`, `horizon_hours`, `factors[]`, `inputs_used`, `missing_inputs`, `sources`.

**Hazard outlook** (`predictions.hazards`): flood / tsunami / seismic scores with drivers.

---

## 13. Nowcast (0–6 h decision object)

Not MetNet, radar, or INSAT millimetres. Hours 1–2 nowcast, 3–4 blend, 5–6 NWP. Past hours = Open-Meteo **model analysis**, not a rain-gauge.

| Parameter | Kind |
|---|---|
| Hourly mm, p_wet, engine (`observed`/`nowcast`/`blend`/`nwp`) | Calculated |
| Onset / cessation clock | Calculated (speech/CAP may shift **timing only**, never mm) |
| Regime name | Calculated |
| Advection, upstream/downstream, ETA | Calculated from ≤6 gazetteer neighbors |
| Kal Baisakhi / storm watch level | Calculated |
| Ponding 60 / 120 min mm | Calculated |
| Hourly water-balance (infil, runoff) | Calculated |
| Tide × rain, drain blocked, stay-off ghat | Calculated (hugli-gated) |
| Pluvial vs fluvial split | Calculated |
| Pump: action, p_interrupt_90m, litres at risk | Calculated |
| Cost/loss: wasted litres vs stress if wait 2 h | Calculated |
| Field access enterable, p_closed_2h, reasons | Calculated |
| Squall visibility watch | Calculated |
| Peak US AQI next hours | Fetched series |
| Labour window / WBGT proxy | Calculated (`science/wbgt.py`) |
| Convective lightning / cloudburst / downburst scores | Calculated from IR + strokes |
| Error memory / neighborhood skill | Calculated |

**Live 1-min gap / 1 Hz playhead:** interpolates locked hours; does not rewrite millimetres.

**Kalman rain-rate between scenes:** default knots are Open-Meteo hourly analysis (`source_kind: model-analysis`). MOSDAC HEM only if a file is cached (never invented mm). Public IMD INSAT IR JPEG is a Tb proxy, not HEM.

**Storm map:** INSAT-3D/3DS IR1 JPEG cells + Weatherbit lightning (75 km / 45 min) + Open-Meteo thunder codes.

---

## 14. Prescriptions

Rule engine (`ml/prescribe.py` + nowcast actions). Examples: irrigation hold/apply, flood prep, AQI protect, pump hold, take cover, stay off field/ghat. Slots include litre bands, AQI, dates. LLM does not compute litres.

---

## 15. Other science pack fields

| Pack | Parameters (summary) |
|---|---|
| Monsoon clock | pre / active / break / post for the district |
| Bandit / trust | Which source to act on today (policy, not a learned bandit) |
| Vernacular | Indic speech tags — category/timing only, **no millimetres** |
| Verify / skill | Skill vs climatology; nowcast error if logged |
| Live issue log | `.cache/nowcast_issues.jsonl` |
| Compare | Delta of rain 3 d, water balance, flood score, AQI between two pins |
| Rank | Districts **in one state** by flood/rain/drought/heat/irrigation |
| Rain window | Daily precip/Tmax/Tmin/weather for a date span (forecast + ERA5 archive) |
| 7-day hourly | `predictive.hourly` / `/forecast/hourly` — Open-Meteo hours, IST, skip yesterday |

---

## 16. Snapshot series keys (`descriptive.series`)

`precip_hourly`, `temp_hourly`, `soil_hourly`, `rh_hourly`, `wind_hourly`, `wind_dir_hourly`, `cloud_hourly`, `aqi_hourly`, `aqi_history`, `uv_hourly`, `dust_hourly`, `pm10_hourly`, `wave_hourly`, `sst_hourly`, `swell_hourly`, `precip_daily`, `et0_daily`, `tmax_daily`, `tmin_daily`, `discharge_daily`.

The 7-day hour table is **not** these series keys; it lives on `predictive.hourly` (and `/outlook` / `/forecast/hourly`).

Each point: `t`, `value`, `unit`, `source`.

---

## 17. Provider status

`provider_status` map: `ok` / `empty` / `error` / `stale` / `missing_key` / `unauthorized` per source (Open-Meteo, flood, air, marine, NASA, IMD CAP, CPCB, Agmarknet, USGS, INCOIS, OpenAQ, GDACS, WAQI, OpenWeather, MOSDAC, Sachet, port, …).

---

## 18. Advisor `data()` packs

`forecast`, `nowcast`, `rain_window`, `aqi`, `quality`, `mandi`, `warnings`, `risks`, `rank`, `states_weather`, `compare`, `place_search`, `capability`.

Capability holes (honest “not available”): radar, INSAT HEM, NCS, IMD REST, rain-gauges.

---

## Sources (normal dashboard load)

Open-Meteo forecast / flood / air / marine / geocode / archive · NASA POWER · IMD CAP RSS · CPCB NAQI · Agmarknet · USGS FDSN CSV · EMSC FDSN · INCOIS ITEWS · OpenAQ · GDACS · IMD public INSAT IR JPEG · NASA GIBS · Weatherbit lightning (if key) · Sachet CAP · Hooghly port (hugli) · local moon · India pollen climatology.

**Not live / not invented:** IMD REST, NCS JSON, MOSDAC HEM millimetres, Ambee, Google Flood Hub, WeatherAPI moon.
