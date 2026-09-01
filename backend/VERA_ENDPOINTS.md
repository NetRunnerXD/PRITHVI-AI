# VERA / Models APIs and parameters

Canonical prefix: `/api`. Same handlers also exist at `/v1`, `/web/v1`, `/app/v1`.
Query location: `lat`, `lon`, and/or `place` / `q` (see `loc_from_query`).

## Endpoints that carry the 12-parameter pack

| Method | Path | Role |
|---|---|---|
| GET | `/api/dashboard` | Full snapshot. Models pack at `predictions.vera.parameters` |
| GET | `/api/predictions` | Dual ours/trusted + `vera` when `source=both` |
| GET | `/api/vera/parameters` | 12 heads only + fusion q50/q95/q99 + train status |
| GET | `/api/vera/train` | EQRN / Swin weight status (device, last pinball, path) |
| POST | `/api/vera/train?epochs=20` | Train EQRN (pinball) and tiny Swin-UNet (GPU if CUDA) |
| GET | `/api/nowcast` | CAPE / convective context used by lightning head |
| GET | `/api/nowcast/live` | Live IR + strokes when Weatherbit/feed is set |
| GET | `/api/sat/imd-asia` | INSAT JPEG for CV / Swin patches |
| GET | `/docs` | OpenAPI |

## Snapshot feeds the heads already use (no extra key)

| Head | Source | Open-Meteo / other field |
|---|---|---|
| rainfall | fusion EQMN | member `precipitation_sum` |
| temperature | fusion EQMN | `temperature_2m_max` |
| heat_wave | extremes | `temperature_2m_max` vs climatology |
| wind | fusion EQMN | `wind_speed_10m_max` |
| gusts | features | `wind_gusts_10m` |
| hub_wind | features | `wind_speed_80m/120m/180m` else 10 m power-law |
| solar | features | `shortwave_radiation`, `shortwave_radiation_sum` |
| fog | features | `visibility`, `relative_humidity_2m`, `weather_code` 45–48, `is_day` |
| waves | marine API | `wave_height` (Open-Meteo marine = INCOIS-class Hs) |
| aqi | air-quality API | CAMS `us_aqi`, `pm10` |
| lightning | features + live sat | `cape` + stroke count |
| tropical_cyclone | GDACS | `eventtype=TC` in India box |

## Env / API keys (optional unless noted)

| Env | Used for |
|---|---|
| (none) | Open-Meteo forecast, marine, CAMS air, GDACS, NASA POWER |
| `MOSDAC_USER` `MOSDAC_PASS` `MOSDAC_BASE_URL` | Native INSAT L1B for CV/Swin |
| `NASA_EARTHDATA_API` or user/pass | IMERG granules (GIBS WMS works without) |
| `WEATHERBIT_API_KEY` or `LIGHTNING_FEED_URL` | Damini-class strokes |
| `WAQI_TOKEN` | Station AQI overlay |
| `OPENWEATHER_API_KEY` | Extra air |
| `CDS_API_KEY` | Native ERA5 |
| `GRAPHCAST_WEIGHTS_DIR` | Local AI member checkpoints |
| `IMD_API_KEY` | Official IMD REST (IP whitelist) |
| CUDA + `pip install torch` | GPU EQRN + Swin (`POST /api/vera/train`) |

Weights land in `backend/.cache/mlflow/eqrn.pt` and `swin_unet.pt`. Fusion uses EQRN quantiles when that file exists.

Member EQMN (gate weights) is applied to rainfall, temperature (+ diurnal amp), wind, gusts, hub-height (log-law), solar shortwave, and visibility/fog when those series exist on Open-Meteo blend members. Waves and AQI are single-source (marine CAMS / CPCB), not multi-model blends.

## Blocked on this host (cannot implement here)

| Need | Blocker |
|---|---|
| CUDA EQRN / SwinNowcast | No NVIDIA GPU; torch is CPU |
| Damini-2.0 | IITM app, no public JSON |
| MOSDAC night-microphysics fog | Needs MOSDAC login + HDF5 |
| INCOIS WW3 NetCDF | Portal download, not lat/lon REST |
| SAFAR-Air | Four-city research net, no REST |
| IMD cyclone_track / cone / lightning REST | IP whitelist + `IMD_API_KEY` |

## Train locally

```
pip install torch
cd backend
python -m app.ml.train.eqrn
python -m app.ml.train.swin_unet
# or
curl -X POST "http://127.0.0.1:8000/api/vera/train?epochs=20"
```
