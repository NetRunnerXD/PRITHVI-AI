# Rituchakra

India-first environmental intelligence for districts, towns, and farms.

Rituchakra is a live dashboard and advisor for weather, flood, drought, heat, air quality, marine state, seismic activity, tsunami watches, and mandi prices. It answers four questions from published data and local models — what is happening, why it is happening, what is likely next, and what to do now — then explains those numbers in English, Hindi, or Bengali.

The Advisor LLM never invents rainfall, risk scores, liters, AQI, or rupees. Forecasts and quantities come from providers and models. The model only orchestrates tools and writes prose.

Default focus: **Nadia, West Bengal**. Search covers Indian cities, towns, and districts (for example Haldia, Santiniketan, Pune).

---

## Overview

Rituchakra is a monorepo. **The backend is a standalone HTTP API** (no web assets). Any client can sit in its own folder.

| Path | Role |
| --- | --- |
| `backend/` | FastAPI API — publish this independently (`/docs`, `/openapi.json`) |
| `frontend/` | Optional Next.js dashboard. Talks to the API over HTTP + CORS. |
| `clients/` | Portable TypeScript client for a new web app or React Native |

The browser (or a phone) calls FastAPI directly. A snapshot object is built for the selected place and drives widgets and Advisor tools.

### Four lenses

1. **What is happening** — sky, rain this hour and today, wind rose, soil moisture, ET₀, CPCB / Open-Meteo AQI, nearest-coast marine state, flood discharge, recent quakes, tsunami bulletins.
2. **Why it is happening** — NASA POWER climatology anomalies and short diagnostic stories (not free-form speculation).
3. **What is likely next** — dual 7-day forecast (trusted Open-Meteo vs residual-blend), soil / water-balance outlook, multi-hazard flood / seismic / tsunami scores.
4. **What we should do** — rule-engine prescriptions with quantities (irrigation hold vs apply, flood / heat / AQI / seismic actions).

### Product surface

| Tab | What you get |
| --- | --- |
| **Overview** | Multi-hazard watch, sky and today’s rain, wind profile, why / do cards, collapsible live plots |
| **Map** | India place search, nearby districts, basemaps, Bhuvan geomorphology overlay via a WMS proxy |
| **Forecast** | Charts, 7-day outlook table, district compare |
| **Predicted** | Side-by-side trusted Open-Meteo vs Rituchakra residual-blend |
| **XAI Risks** | Explainable cards (flood, drought, heat, irrigation, air, seismic, tsunami) with factor contributions |
| **Market** | Agmarknet mandi prices (data.gov.in) |
| **Advisor** | Tool-using chat. Presets in English, Hindi, and Bengali. Reply-in language control |

The UI language (EN / HI / BN) also sets the Advisor reply language. You can override reply language independently. The dashboard refreshes quietly every 60 seconds.

---

## Advisor

Ask in any language. The translation layer:

1. Detects the question language (script first).
2. Translates inbound text to **English** for intent routing and the LLM.
3. Runs tools against live snapshot JSON only.
4. Writes an English draft.
5. Translates that draft back to Hindi, Bengali, or the detected / selected reply language.
6. Locks numbers and source names (IMD, CPCB, USGS, INCOIS, Open-Meteo, AQI, and similar) so they are not dropped or invented.

If online translation is unavailable, Hindi and Bengali fall back to structured Indic composition. English is shown if that is not possible. Turn on **English source** in the dock to read the model draft.

The Advisor can rank districts (for example West Bengal flood risk), list gazetteer districts, compare two places, pull mandi prices, and narrate irrigation / rain / AQI / hazard watches. Place names in the question (Haldia, Pune, …) retarget the dashboard.

A local OpenAI-compatible LLM (default **Ollama** `qwen2.5`) is optional. If it is down, templates and structured Indic still answer from the snapshot.

---

## Data sources

Called on a normal dashboard load (no paid keys required for the core path):

| Source | Role |
| --- | --- |
| Open-Meteo forecast, flood, air, marine, geocode | Weather, soil, ET₀, GloFAS discharge, CAMS AQI, waves, India place search |
| NASA POWER | Daily climatology for anomalies |
| IMD CAP RSS | Official meteorological warnings |
| data.gov.in CPCB NAQI | Station air quality (key recommended) |
| data.gov.in Agmarknet | Mandi prices (key recommended) |
| USGS FDSN | Earthquakes in an India–Indian Ocean box |
| INCOIS ITEWS | Tsunami / quake bulletins |
| OpenAQ | Historical PM2.5 |
| Bhuvan WMS | NRSC geomorphology overlay |
| NASA GIBS | Optional true-color tiles |

Honest source labels:

- Open-Meteo has **no** earthquake or tsunami products. Seismic = USGS. Tsunami = INCOIS.
- IMD REST (`api.imd.gov.in`) needs an IP whitelist; until then CAP is the official warning feed.
- NCS has no stable public JSON API.
- Inland marine views snap to the nearest Indian coast instead of showing an empty grid.

Optional keys (see `backend/.env.example`): `DATA_GOV_IN_API_KEY`, `IMD_API_KEY`, `AIKOSH_API_KEY`, MOSDAC / NASA Earthdata / OpenWeather.

Do not commit secrets. `backend/.env` is gitignored.

---

## Architecture

```
Any client (Next / other web / React Native)
    └─ HTTP + CORS  →  FastAPI :8000
                          ├─ /                 service card
                          ├─ /docs             Swagger
                          ├─ /openapi.json     contract
                          ├─ /api/dashboard    snapshot
                          ├─ /api/nowcast      0–6 h locked nowcast
                          ├─ /api/geo/*        India search + Bhuvan WMS proxy
                          ├─ /api/chat         SSE Advisor
                          └─ providers + ML + in-memory TTL cache
```

**Hard rules**

- India-only search and gazetteer by default.
- The LLM does not compute forecasts, risk %, liters, or mandi rupees.
- Indic replies are never built by splicing English fragments into Hindi or Bengali.

---

## Requirements

- Python 3.11+
- Node.js 18+
- Optional: [Ollama](https://ollama.com) with an OpenAI-compatible model (default `qwen2.5`) for Advisor prose

---

## Quick start

```powershell
# Backend
cd backend
python -m pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Frontend is optional (second terminal)
cd frontend
copy .env.example .env.local
npm install
npm run dev
```

API (no UI required): [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Dashboard: [http://localhost:3000](http://localhost:3000) — calls `NEXT_PUBLIC_API_BASE` (default `http://127.0.0.1:8000`).

Health: `GET http://127.0.0.1:8000/api/health`

Ollama (optional):

```text
ollama serve
ollama pull qwen2.5
```

The web app does not embed the API. Restart uvicorn after backend edits unless you pass `--reload`. Bind `--host 0.0.0.0` for a phone on the LAN. See `backend/README.md` and `clients/README.md`.

---

## Configuration

Copy `backend/.env.example` to `backend/.env`.

| Variable | Purpose |
| --- | --- |
| `OLLAMA_BASE_URL` | OpenAI-compatible base (default `http://127.0.0.1:11434/v1`) |
| `OLLAMA_MODEL` | Model name (default `qwen2.5`) |
| `TRANSLATE_ENABLED` | Inbound / outbound MT (default true; Google gtx + MyMemory, no key) |
| `DATA_GOV_IN_API_KEY` | CPCB NAQI + Agmarknet |
| `IMD_API_KEY` | Official IMD REST after whitelist |
| `AIKOSH_API_KEY` | AIKosh dataset search |
| `DEFAULT_LAT` / `DEFAULT_LON` / `DEFAULT_STATE` / `DEFAULT_DISTRICT` | Startup location |
| `CORS_ORIGINS` | Allowed browser / app origins (`*` = any) |
| `CORS_ORIGIN_REGEX` | Extra origins (LAN / Expo) |
| `PUBLIC_BASE_URL` | Absolute API origin in responses (WMS links) |

---

## API (selected)

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/` | Service card (JSON, not HTML) |
| `GET` | `/docs`, `/openapi.json` | Swagger + OpenAPI contract |
| `GET` | `/api` | Published route catalog |
| `GET` | `/api/health` | Process + Ollama ping |
| `GET` | `/api/dashboard` | Full snapshot (`district`, `place`, `lat`, `lon`) |
| `GET` | `/api/nowcast` | Locked 0–6 h nowcast |
| `GET` | `/api/forecast`, `/predictions`, `/outlook`, `/risks` | Slice endpoints |
| `GET` | `/api/scan`, `/compare`, `/states`, `/districts`, `/brief` | Rank, compare, gazetteer, text brief |
| `GET` | `/api/geo/search`, `/geo/reverse`, `/geo/nearby` | India places |
| `GET` | `/api/map/layers`, `/api/map/wms` | Basemap list + Bhuvan proxy (absolute WMS URL) |
| `POST` | `/api/chat` | SSE Advisor (`message`, `locale_hint`, `output_locale`, `location`, `history`) |

---

## Tests

Run from `backend/` (`pythonpath = .` in `pytest.ini`):

```powershell
cd backend
python -m pytest -q
```

---

## Example questions

English

> Which districts in West Bengal are more likely to get flooded? List them.

Hindi

> अगले तीन दिन बारिश कैसी रहेगी? क्या अभी सिंचाई करूँ?

Bengali

> আগামী তিন দিনে আমার এলাকায় বৃষ্টির সম্ভাবনা কেমন? এখন সেচ দেওয়া উচিত কি?

The dashboard follows the place in the question. Irrigation advice quotes model rain and a liter band from the prescription engine, not from the LLM.

---

## License

Use and extend for India-focused environmental decision support. Attribute upstream data providers (IMD, Open-Meteo, NASA, CPCB, Agmarknet, USGS, INCOIS, NRSC Bhuvan) in any public deployment.
