# PRITHVI-AI (Rituchakra)

**PRITHVI-AI: An Open-LLM Powered Multilingual Environmental Intelligence & Climate Resilience Platform for India**

India-first live dashboard and advisor for weather, flood, drought, heat, air quality, marine state, seismic activity, tsunami watches, mandi prices, and convective nowcast (lightning / storm cells). It answers four questions from published data and local models — what is happening, why it is happening, what is likely next, and what to do now — then explains those numbers in English, Hindi, or Bengali.

The Advisor is a **local open LLM** (Ollama `qwen2.5` by default). It never invents rainfall, risk scores, liters, AQI, or rupees. Chat calls one `data()` library and quotes those packs. Bare names (`Puruliya`, `Delhi`) resolve through the India gazetteer or Open-Meteo India geocode.

Default focus: **Haldia, Purba Medinipur, West Bengal**. GitHub: [NetRunnerXD/Rituchakra](https://github.com/NetRunnerXD/Rituchakra).

Long-form proposal: [`full.md`](full.md). Engineering handoff: [`project.md`](project.md).

---

## Overview

Monorepo. **The backend is a standalone HTTP API** (no web assets).

| Path | Role |
| --- | --- |
| `backend/` | FastAPI API — publish independently (`/docs`, `/openapi.json`) |
| `frontend/` | Optional Next.js dashboard (HTTP + CORS) |
| `clients/` | Portable TypeScript client for a new web app or React Native |
| `main.py` | Starts API `:8000` and dashboard `:3000` |

### Four lenses

1. **What is happening** — sky, rain this hour and today, wind rose, soil, CPCB / Open-Meteo AQI, nearest-coast marine, flood discharge, quakes, tsunami bulletins, live IR storm cells.
2. **Why it is happening** — NASA POWER climatology anomalies and short diagnostic stories.
3. **What is likely next** — 0–6 h locked nowcast, dual 7-day forecast (Open-Meteo vs residual-blend), convective 15–60 min strike windows, multi-hazard scores.
4. **What we should do** — rule-engine prescriptions (irrigation hold vs apply, flood / heat / AQI / storm actions).

### Product surface

| Tab | What you get |
| --- | --- |
| **Overview** | Decision chips, sky, today’s rain, engine-labelled 0–6 h hours, 7-day glance, wind |
| **Nowcasting** | 1 Hz playhead, physiography-gated Hugli tide, Kalman between-scene rate, ponding |
| **Alerts** | IMD CAP + CPCB + INCOIS + USGS + local pump / field / storm actions |
| **Map** | All-India / state storm map: past lightning (Weatherbit), predicted lightning/storm + confidence, IR cells, polygons, GIBS IR/IMERG |
| **Forecast** | Charts, 7-day outlook, district compare |
| **Predicted / Models** | Trusted Open-Meteo vs VERA-MoE hybrid blend, 24 h hourly, satellite lab |
| **Risks** | Explainable cards + the same live storm map |
| **Market** | Agmarknet mandi prices |
| **Advisor** | Open-LLM chat; presets EN/HI/BN; reply-in language |

---

## Advisor (open LLM)

Ask in any language. Pipeline:

1. Detect language; translate inbound to **English**.
2. `utterance.interpret` → place resolve (India only) → one `data()` tool.
3. LLM writes English prose that **quotes packs**. Unbound digits become `—`. Dash-soup drafts are replaced with `quote_facts`.
4. Translate outbound to Hindi, Bengali, or the selected reply language. Numbers and source names stay locked.

If Ollama is down, templates and structured Indic still answer from the snapshot. The LLM does not compute millimetres.

---

## Data sources

| Source | Role |
| --- | --- |
| Open-Meteo forecast, flood, air, marine, geocode | Weather, soil, ET₀, GloFAS, CAMS AQI, waves, India search. On 429, last-good file or ERA5 archive fallback (labelled stale). |
| NASA POWER | Climatology anomalies |
| IMD CAP RSS | Official warnings |
| IMD INSAT-3D/3DS IR1 JPEG | Public Asia-sector IR for storm cells (not HEM mm) |
| NASA GIBS | Himawari IR + IMERG overlays |
| Weatherbit lightning | Observed flashes (75 km; last-good on 429) |
| data.gov.in CPCB / Agmarknet | AQI and mandi (key recommended) |
| USGS FDSN / INCOIS ITEWS | Earthquakes / tsunami |
| Bhuvan WMS | NRSC geomorphology |

Honest labels: Open-Meteo has no quake/tsunami products. IMD REST needs IP whitelist. NCS has no public JSON. Storm-map IR is a JPEG, not a rain-gauge. Hugli tide and CWC only where physiography says so.

Do not commit secrets. `backend/.env` is gitignored.

---

## Quick start

```powershell
cd D:\Project\Random\RainFall
python main.py
# API http://127.0.0.1:8000/docs
# Dashboard http://localhost:3000
```

Or separately:

```powershell
cd backend
python -m pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

cd frontend
npm install
npm run dev
```

Health: `GET http://127.0.0.1:8000/api/health`

Ollama (optional, for Advisor prose):

```text
ollama serve
ollama pull qwen2.5
```

If port 8000 is already taken, `main.py` exits with a clear error. Tests: `cd backend; python -m pytest -q`.

### Home Ollama for a deployed API

The cloud host cannot open a port on your PC. A small worker on this machine connects **out** and runs inference locally.

1. Set the same `LLM_WORKER_TOKEN` on the deployed API and in `backend/.env`.
2. Keep `ollama serve` running here (`ollama pull qwen2.5:3b`).
3. Point the worker at the public API:

```powershell
cd backend
$env:LLM_WORKER_TOKEN="your-shared-secret"
$env:PRITHVI_API="https://your-api.example"
python scripts/ollama_worker.py
```

`GET /api/health` then shows `ollama.home.online: true` and `detail: home-online:…`. When this process stops, chat uses `LLM_FALLBACK` (e.g. Groq) if configured.

---

## Configuration

See `backend/.env.example`. Important: `OLLAMA_*`, `DATA_GOV_IN_API_KEY`, `WEATHERBIT_API_KEY`, `LIGHTNING_FEED_URL`, `NASA_EARTHDATA_*`, `CORS_ORIGINS`, `PUBLIC_BASE_URL`.

## Deploy (web + phones)

The API does not serve the dashboard. Publish FastAPI, then point Next and Expo at it.

```powershell
copy backend\.env.example backend\.env
docker compose up --build
```

HTTPS, CORS, Caddy SSE notes, and the Expo app: [`deploy/README.md`](deploy/README.md) and [`mobile/README.md`](mobile/README.md). Set `PUBLIC_BASE_URL` and `CORS_ORIGINS` to your real HTTPS origins. Use one API worker (in-process cache).

The web app is installable (PWA manifest + shell service worker). Live `/api` responses are not cached.

---

## API (selected)

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/`, `/docs`, `/openapi.json`, `/api/health` | Service card, Swagger, health |
| `GET` | `/api/dashboard` | Full snapshot |
| `GET` | `/api/nowcast`, `/nowcast/live`, `/nowcast/sat` | Locked nowcast, playhead, Kalman |
| `GET` | `/api/nowcast/storm-map` | State / All-India IR cells + lightning (`?state=India`) |
| `GET` | `/api/forecast`, `/predictions`, `/outlook`, `/risks` | Slices |
| `GET` | `/api/geo/search`, `/map/wms` | India places, Bhuvan proxy |
| `POST` | `/api/chat` | SSE Advisor |

---

## License

Use and extend for India-focused environmental decision support. Attribute IMD, Open-Meteo, NASA, CPCB, Agmarknet, USGS, INCOIS, NRSC Bhuvan, Weatherbit where used.
