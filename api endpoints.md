# API endpoints

Source: live OpenAPI at `http://127.0.0.1:8000/openapi.json` (Swagger UI: `http://127.0.0.1:8000/docs`).

**Rituchakra API** v0.4.0

India-first environmental intelligence HTTP API. JSON only — no web assets. Canonical routes live under /api (local dashboard and tests). The same handlers are also served at /v1, /web/v1, and /app/v1 so a website and a phone app can call this process together. The Advisor LLM never invents millimetres, litres, AQI, or rupees; those come from providers and models.

Base URL (local): `http://127.0.0.1:8000`

Canonical prefix is `/api`. The same handlers are also mounted at `/v1`, `/web/v1`, and `/app/v1` (aliases omitted from this OpenAPI).

---

## Index

| Method | Path | Summary | Tag |
|---|---|---|---|
| `GET` | `/` | Service card | meta |
| `GET` | `/api` | Published route catalog | meta |
| `GET` | `/api/bootstrap` | Client boot pack | meta |
| `GET` | `/api/health` | Liveness | meta |
| `HEAD` | `/api/health` | Liveness probe | meta |
| `GET` | `/api/ready` | Readiness | meta |
| `GET` | `/api/agent/tools` | List Tools | snapshot |
| `GET` | `/api/alerts` | Alerts Api | snapshot |
| `GET` | `/api/blend` | Blend Weights | snapshot |
| `GET` | `/api/blend/hazards` | Blend Hazards | snapshot |
| `GET` | `/api/blend/weights` | Blend Weights | snapshot |
| `POST` | `/api/brief` | Brief | snapshot |
| `GET` | `/api/compare` | Compare Api | snapshot |
| `GET` | `/api/dashboard` | Dashboard | snapshot |
| `GET` | `/api/districts` | Districts Api | snapshot |
| `GET` | `/api/forecast` | Forecast | snapshot |
| `GET` | `/api/forecast/hourly` | Forecast Hourly | snapshot |
| `GET` | `/api/insights` | Insights | snapshot |
| `GET` | `/api/live-nowcast` | Nowcast Live Alias | snapshot |
| `GET` | `/api/market` | Market Api | snapshot |
| `GET` | `/api/nowcast` | Nowcast Api | snapshot |
| `GET` | `/api/nowcast-live` | Nowcast Live Api | snapshot |
| `GET` | `/api/nowcast-sat` | Nowcast Sat Api | snapshot |
| `GET` | `/api/nowcast-storm-map` | Storm Map Api | snapshot |
| `GET` | `/api/nowcast/live` | Nowcast Live Api | snapshot |
| `GET` | `/api/nowcast/sat` | Nowcast Sat Api | snapshot |
| `GET` | `/api/nowcast/storm-map` | Storm Map Api | snapshot |
| `GET` | `/api/outlook` | Outlook | snapshot |
| `GET` | `/api/predictions` | Predictions | snapshot |
| `GET` | `/api/risks` | Risks | snapshot |
| `GET` | `/api/sat/imd-asia` | Imd Asia Jpeg | snapshot |
| `GET` | `/api/scan` | Scan Api | snapshot |
| `GET` | `/api/science` | Science Api | snapshot |
| `GET` | `/api/states` | States Api | snapshot |
| `POST` | `/api/chat` | Chat | advisor |
| `GET` | `/api/geo/nearby` | Geo Nearby | geo |
| `GET` | `/api/geo/reverse` | Geo Reverse | geo |
| `GET` | `/api/geo/search` | Geo Search | geo |
| `GET` | `/api/map/layers` | Map Layers | geo |
| `GET` | `/api/map/radar` | Map Radar | geo |
| `GET` | `/api/map/weather-grid` | Map Weather Grid | geo |
| `GET` | `/api/map/wms` | Bhuvan Wms Proxy | geo |
| `HEAD` | `/api/map/wms` | Bhuvan Wms Proxy | geo |

---

## meta

### `GET` `/`

Service card

Operation ID: `root__get`

**Responses**
- `200` — Successful Response

### `GET` `/api`

Published route catalog

Operation ID: `api_catalog_api_get`

**Responses**
- `200` — Successful Response

### `GET` `/api/bootstrap`

Client boot pack

First request for web or Android: pin, locales, flags, and route map.

Operation ID: `bootstrap_api_bootstrap_get`

**Responses**
- `200` — Successful Response

### `GET` `/api/health`

Liveness

Operation ID: `health_api_health_get`

**Responses**
- `200` — Successful Response

### `HEAD` `/api/health`

Liveness probe

Operation ID: `health_head_api_health_head`

**Responses**
- `200` — Successful Response

### `GET` `/api/ready`

Readiness

Operation ID: `ready_api_ready_get`

**Responses**
- `200` — Successful Response

---

## snapshot

### `GET` `/api/agent/tools`

List Tools

Operation ID: `list_tools_api_agent_tools_get`

**Parameters**

- `district` (query, optional, string | null)
- `place` (query, optional, string | null)
- `lat` (query, optional, number | null)
- `lon` (query, optional, number | null)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/alerts`

Alerts Api

Warnings, actions, and live hazard lists without the full dashboard.

Operation ID: `alerts_api_api_alerts_get`

**Parameters**

- `district` (query, optional, string | null)
- `place` (query, optional, string | null)
- `lat` (query, optional, number | null)
- `lon` (query, optional, number | null)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/blend`

Blend Weights

Operation ID: `blend_weights_api_blend_get`

**Parameters**

- `district` (query, optional, string | null)
- `place` (query, optional, string | null)
- `lat` (query, optional, number | null)
- `lon` (query, optional, number | null)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/blend/hazards`

Blend Hazards

Operation ID: `blend_hazards_api_blend_hazards_get`

**Parameters**

- `district` (query, optional, string | null)
- `place` (query, optional, string | null)
- `lat` (query, optional, number | null)
- `lon` (query, optional, number | null)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/blend/weights`

Blend Weights

Operation ID: `blend_weights_api_blend_weights_get`

**Parameters**

- `district` (query, optional, string | null)
- `place` (query, optional, string | null)
- `lat` (query, optional, number | null)
- `lon` (query, optional, number | null)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `POST` `/api/brief`

Brief

Operation ID: `brief_api_brief_post`

**Parameters**

- `locale` (query, optional, string) default `"en"`
- `district` (query, optional, string | null)
- `place` (query, optional, string | null)
- `lat` (query, optional, number | null)
- `lon` (query, optional, number | null)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/compare`

Compare Api

Operation ID: `compare_api_api_compare_get`

**Parameters**

- `a` (query, required, string)
- `b` (query, required, string)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/dashboard`

Dashboard

Operation ID: `dashboard_api_dashboard_get`

**Parameters**

- `locale` (query, optional, string) default `"en"`
- `district` (query, optional, string | null)
- `place` (query, optional, string | null)
- `lat` (query, optional, number | null)
- `lon` (query, optional, number | null)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/districts`

Districts Api

Operation ID: `districts_api_api_districts_get`

**Parameters**

- `state` (query, optional, string | null)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/forecast`

Forecast

Operation ID: `forecast_api_forecast_get`

**Parameters**

- `district` (query, optional, string | null)
- `place` (query, optional, string | null)
- `lat` (query, optional, number | null)
- `lon` (query, optional, number | null)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/forecast/hourly`

Forecast Hourly

Operation ID: `forecast_hourly_api_forecast_hourly_get`

**Parameters**

- `date` (query, optional, string | null) — YYYY-MM-DD IST
- `district` (query, optional, string | null)
- `place` (query, optional, string | null)
- `lat` (query, optional, number | null)
- `lon` (query, optional, number | null)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/insights`

Insights

Operation ID: `insights_api_insights_get`

**Parameters**

- `district` (query, optional, string | null)
- `place` (query, optional, string | null)
- `lat` (query, optional, number | null)
- `lon` (query, optional, number | null)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/live-nowcast`

Nowcast Live Alias

Alias so older proxies that drop a nested /live segment still work.

Operation ID: `nowcast_live_alias_api_live_nowcast_get`

**Parameters**

- `district` (query, optional, string | null)
- `place` (query, optional, string | null)
- `lat` (query, optional, number | null)
- `lon` (query, optional, number | null)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/market`

Market Api

Agmarknet / OGD mandi slice.

Operation ID: `market_api_api_market_get`

**Parameters**

- `district` (query, optional, string | null)
- `place` (query, optional, string | null)
- `lat` (query, optional, number | null)
- `lon` (query, optional, number | null)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/nowcast`

Nowcast Api

Operation ID: `nowcast_api_api_nowcast_get`

**Parameters**

- `district` (query, optional, string | null)
- `place` (query, optional, string | null)
- `lat` (query, optional, number | null)
- `lon` (query, optional, number | null)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/nowcast-live`

Nowcast Live Api

Operation ID: `nowcast_live_api_api_nowcast_live_get`

**Parameters**

- `district` (query, optional, string | null)
- `place` (query, optional, string | null)
- `lat` (query, optional, number | null)
- `lon` (query, optional, number | null)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/nowcast-sat`

Nowcast Sat Api

Live Kalman rain-rate between observation scenes. stride=1 or 60.

Operation ID: `nowcast_sat_api_api_nowcast_sat_get`

**Parameters**

- `stride` (query, optional, integer) default `60`
- `district` (query, optional, string | null)
- `place` (query, optional, string | null)
- `lat` (query, optional, number | null)
- `lon` (query, optional, number | null)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/nowcast-storm-map`

Storm Map Api

Operation ID: `storm_map_api_api_nowcast_storm_map_get`

**Parameters**

- `state` (query, required, string)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/nowcast/live`

Nowcast Live Api

Operation ID: `nowcast_live_api_api_nowcast_live_get`

**Parameters**

- `district` (query, optional, string | null)
- `place` (query, optional, string | null)
- `lat` (query, optional, number | null)
- `lon` (query, optional, number | null)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/nowcast/sat`

Nowcast Sat Api

Live Kalman rain-rate between observation scenes. stride=1 or 60.

Operation ID: `nowcast_sat_api_api_nowcast_sat_get`

**Parameters**

- `stride` (query, optional, integer) default `60`
- `district` (query, optional, string | null)
- `place` (query, optional, string | null)
- `lat` (query, optional, number | null)
- `lon` (query, optional, number | null)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/nowcast/storm-map`

Storm Map Api

Operation ID: `storm_map_api_api_nowcast_storm_map_get`

**Parameters**

- `state` (query, required, string)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/outlook`

Outlook

Operation ID: `outlook_api_outlook_get`

**Parameters**

- `district` (query, optional, string | null)
- `place` (query, optional, string | null)
- `lat` (query, optional, number | null)
- `lon` (query, optional, number | null)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/predictions`

Predictions

Operation ID: `predictions_api_predictions_get`

**Parameters**

- `source` (query, optional, string) default `"both"`
- `district` (query, optional, string | null)
- `place` (query, optional, string | null)
- `lat` (query, optional, number | null)
- `lon` (query, optional, number | null)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/risks`

Risks

Operation ID: `risks_api_risks_get`

**Parameters**

- `district` (query, optional, string | null)
- `place` (query, optional, string | null)
- `lat` (query, optional, number | null)
- `lon` (query, optional, number | null)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/sat/imd-asia`

Imd Asia Jpeg

Same-origin INSAT Asia-sector JPEG so Leaflet ImageOverlay is not blocked by CORS.

Operation ID: `imd_asia_jpeg_api_sat_imd_asia_get`

**Responses**
- `200` — Successful Response

### `GET` `/api/scan`

Scan Api

Operation ID: `scan_api_api_scan_get`

**Parameters**

- `state` (query, required, string)
- `metric` (query, optional, string) default `"flood"`
- `limit` (query, optional, integer) default `30`

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/science`

Science Api

Operation ID: `science_api_api_science_get`

**Parameters**

- `district` (query, optional, string | null)
- `place` (query, optional, string | null)
- `lat` (query, optional, number | null)
- `lon` (query, optional, number | null)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/states`

States Api

Operation ID: `states_api_api_states_get`

**Responses**
- `200` — Successful Response

---

## advisor

### `POST` `/api/chat`

Chat

Operation ID: `chat_api_chat_post`

**Request body** (required)
- Content-Type: `application/json`
- Schema: `ChatRequest — object{message, locale_hint, output_locale, conversation_id, location, history, regenerate, stream, llm, show_evidence}`

| Field | Type | Required | Description |
|---|---|---|---|
| `message` | string | yes |  |
| `locale_hint` | string | null | no |  |
| `output_locale` | string | null | no |  |
| `conversation_id` | string | null | no |  |
| `location` | Location — object{id, label, country, state, district, imd_district_id, imd_station_id, imd_subdivision, lat, lon, timezone, crop_hint +4} | null | no |  |
| `history` | array[ChatMessage — object{id, role, content, content_en, locale, blocks, suggestions, tool_trace, citations, ui, translation}] | no |  |
| `regenerate` | boolean | no |  |
| `stream` | boolean | no |  |
| `llm` | string | null | no |  |
| `show_evidence` | boolean | no |  |

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

---

## geo

### `GET` `/api/geo/nearby`

Geo Nearby

Operation ID: `geo_nearby_api_geo_nearby_get`

**Parameters**

- `lat` (query, required, number)
- `lon` (query, required, number)
- `limit` (query, optional, integer) default `8`

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/geo/reverse`

Geo Reverse

Operation ID: `geo_reverse_api_geo_reverse_get`

**Parameters**

- `lat` (query, required, number)
- `lon` (query, required, number)

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/geo/search`

Geo Search

Operation ID: `geo_search_api_geo_search_get`

**Parameters**

- `q` (query, required, string)
- `limit` (query, optional, integer) default `8`

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/map/layers`

Map Layers

Operation ID: `map_layers_api_map_layers_get`

**Responses**
- `200` — Successful Response

### `GET` `/api/map/radar`

Map Radar

RainViewer frame list (public). Tiles are loaded in the browser.

Operation ID: `map_radar_api_map_radar_get`

**Responses**
- `200` — Successful Response

### `GET` `/api/map/weather-grid`

Map Weather Grid

Global Open-Meteo sample grid. Storm / pin stay India-only.

Operation ID: `map_weather_grid_api_map_weather_grid_get`

**Parameters**

- `hour` (query, optional, integer) default `0`

**Responses**
- `200` — Successful Response
- `422` — Validation Error
  - `application/json`: `HTTPValidationError — object{detail}`

### `GET` `/api/map/wms`

Bhuvan Wms Proxy

Browser-safe proxy. Bhuvan TLS/CORS often blocks direct Leaflet WMS.

Operation ID: `bhuvan_wms_proxy_api_map_wms_head`

**Responses**
- `200` — Successful Response

### `HEAD` `/api/map/wms`

Bhuvan Wms Proxy

Browser-safe proxy. Bhuvan TLS/CORS often blocks direct Leaflet WMS.

Operation ID: `bhuvan_wms_proxy_api_map_wms_head`

**Responses**
- `200` — Successful Response

---

## Schemas

### `ChatMessage`

Type: `object`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes |  |
| `role` | string | yes |  |
| `content` | string | yes |  |
| `content_en` | string | null | no |  |
| `locale` | string | no |  |
| `blocks` | array[object] | no |  |
| `suggestions` | array[object] | no |  |
| `tool_trace` | array[object] | no |  |
| `citations` | array[object] | no |  |
| `ui` | array[object] | no |  |
| `translation` | object | null | no |  |

### `ChatRequest`

Type: `object`

| Field | Type | Required | Description |
|---|---|---|---|
| `message` | string | yes |  |
| `locale_hint` | string | null | no |  |
| `output_locale` | string | null | no |  |
| `conversation_id` | string | null | no |  |
| `location` | Location — object{id, label, country, state, district, imd_district_id, imd_station_id, imd_subdivision, lat, lon, timezone, crop_hint +4} | null | no |  |
| `history` | array[ChatMessage — object{id, role, content, content_en, locale, blocks, suggestions, tool_trace, citations, ui, translation}] | no |  |
| `regenerate` | boolean | no |  |
| `stream` | boolean | no |  |
| `llm` | string | null | no |  |
| `show_evidence` | boolean | no |  |

### `HTTPValidationError`

Type: `object`

| Field | Type | Required | Description |
|---|---|---|---|
| `detail` | array[ValidationError — object{loc, msg, type}] | no |  |

### `Location`

Type: `object`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes |  |
| `label` | string | yes |  |
| `country` | string | no |  |
| `state` | string | yes |  |
| `district` | string | yes |  |
| `imd_district_id` | string | null | no |  |
| `imd_station_id` | string | null | no |  |
| `imd_subdivision` | string | null | no |  |
| `lat` | number | yes |  |
| `lon` | number | yes |  |
| `timezone` | string | no |  |
| `crop_hint` | string | no |  |
| `season_hint` | string | no |  |
| `plot_m2` | number | no | Assumed smallholder plot |
| `place_kind` | string | no |  |
| `place_name` | string | null | no |  |

### `ValidationError`

Type: `object`

| Field | Type | Required | Description |
|---|---|---|---|
| `loc` | array[string | integer] | yes |  |
| `msg` | string | yes |  |
| `type` | string | yes |  |
