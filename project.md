# RainFall — agent handoff

India-first environmental intelligence dashboard. Live weather, flood, air, marine, seismic, tsunami, mandi prices, and explainable risk — then an Advisor LLM that **only narrates tool JSON**.

Use this file to continue work in a new session or a different tool. Prefer this over the shorter `README.md`.

---

## 1. What it is

A monorepo:

| Path | Stack |
|---|---|
| `backend/` | FastAPI + Pydantic v2 + httpx + pytest |
| `frontend/` | Next.js 14 App Router + Tailwind + Zustand + Recharts + Leaflet |

**Product questions (four lenses)**

1. What is happening — current sky, rain, soil, AQI  
2. Why it is happening — NASA POWER anomalies + diagnostic stories  
3. What is likely next — dual forecast (trusted Open-Meteo vs residual-blend) + hazard outlook  
4. What we should do — rule-engine prescriptions (liters, flood/heat/AQI/seismic)

Default focus: **Nadia, West Bengal** (`23.471, 88.5565`).

---

## 2. Hard constraints (do not violate)

- **India-only UX.** Gazetteer + geocoding are India. Do not add global city search as default.
- **LLM never invents numbers.** Forecasts, risk %, liters, AQI, mandi rupees come from providers/ML/tools. The LLM orchestrates tools and writes prose.
- **Local Ollama only** (`qwen2.5` via OpenAI-compatible API). Do **not** pull Mixtral / Llama 3.1. Hardware target: **16 GB RAM + RTX 3060 6 GB**.
- **No IMD REST without IP whitelist.** `api.imd.gov.in` returns 401. Use **IMD CAP RSS** for official warnings.
- **Do not commit API keys.** `DATA_GOV_IN_API_KEY` and others live in `backend/.env` (gitignored).
- **Open-Meteo has no earthquake or tsunami products.** Seismic = USGS FDSN. Tsunami = INCOIS ITEWS. Label sources honestly.
- **NCS has no stable public JSON.** Do not pretend an NCS live API exists.
- **Indic replies:** never splice English fragments into Hindi/Bengali (that produced garbage like `জেলা —`). Inbound MT (any language → English) feeds the LLM. Outbound MT (English → reply language) displays the answer. Numbers and source acronyms are locked. If MT fails, `compose_indic` is the hi/bn fallback.
- **Comments:** short, factual; no step-by-step narration in code.
- **UI verification:** if you change visible web UI and browser tools exist, exercise the feature. This repo often has no browser MCP — then verify via `/api` + Next compile and say so.

---

## 3. How to run

Windows / PowerShell. `&&` is not reliable in some agent shells — use `;` or separate commands.

```powershell
# Backend (cwd must be backend/ for pytest and uvicorn)
cd D:\Project\Random\RainFall\backend
python -m pip install -r requirements.txt
# copy .env.example .env   if missing
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Frontend
cd D:\Project\Random\RainFall\frontend
npm install
npm run dev
# http://localhost:3000
```

Ollama (optional but needed for Advisor prose + Indic render):

```
ollama serve
# model already expected: qwen2.5
```

- Frontend calls the API origin in `NEXT_PUBLIC_API_BASE` (CORS). Optional empty base uses a Next rewrite.
- Health: `GET http://127.0.0.1:8000/api/health` — Swagger: `/docs`
- Tests: `cd backend; python -m pytest -q` (`pythonpath = .` in `pytest.ini`). Running pytest from repo root fails with `No module named 'app'`.
- Restart uvicorn after backend edits (Python does not hot-reload unless `--reload`). Killing `:8000` then starting again is the usual pattern; old processes exit with code 1 — that is expected.

---

## 4. Architecture

```
Any client (frontend/ or a new web / React Native folder)
    └─ HTTP + CORS → FastAPI (:8000)   no web assets, /docs + /openapi.json
                          ├─ /api/dashboard  → services.snapshot.build_snapshot
                          ├─ /api/nowcast
                          ├─ /api/geo/*      → location_svc + Bhuvan WMS proxy
                          ├─ /api/chat       → SSE ← agents.orchestrator.run_agent
                          └─ providers (httpx) + ml + cache (in-memory TTL)
```

The Next app uses `NEXT_PUBLIC_API_BASE` (default `http://127.0.0.1:8000`). Portable client: `clients/js`. Do not serve `frontend/` from uvicorn.

**Snapshot is the core object.** Almost every dashboard widget and most tools read a `DashboardSnapshot`. `gather_observations` fans out with `asyncio.gather`, then `extract` → risks / outlook / blend / warnings / live board.

```
Location
  → gather_observations (OM weather/flood/air/marine, NASA, IMD CAP, CPCB, Agmarknet,
                         USGS, INCOIS, OpenAQ, AIKosh)
  → ml.features.extract
  → ml.risk.all_risks
  → ml.outlook + ml.blend (dual predictions)
  → ml.anomaly (stories)
  → ml.prescribe
  → ml.hazards_outlook
  → DashboardSnapshot { descriptive, diagnostic, predictive, prescriptive,
                        risks, live, predictions, ogd, map, vegetation }
```

---

## 5. Backend map (`backend/app/`)

| Path | Role |
|---|---|
| `main.py` | FastAPI app, CORS, `/`, `/docs`, `/api/health` — no static UI |
| `config.py` | pydantic-settings; `backend/.env` |
| `cache.py` | In-memory TTL cache (do not slam Open-Meteo/CAP) |
| `api/dashboard.py` | `/dashboard`, `/forecast`, `/predictions`, `/outlook`, `/risks`, `/scan`, `/compare`, `/states`, `/districts`, `/brief` |
| `api/geo.py` | `/geo/search`, `/geo/reverse`, `/geo/nearby`, `/map/layers`, **`/map/wms` Bhuvan proxy** |
| `api/deps.py` | `loc_from_query(district, place, lat, lon)` |
| `api/chat.py` | `POST /chat` SSE (`data: {json}\n\n`) |
| `services/snapshot.py` | Observation gather, warning build, `LiveWatch`, `primary_reply` |
| `services/location_svc.py` | Resolve/search: **towns first**, then districts, then Open-Meteo geocode |
| `services/scan.py` | Rank districts in a state (semaphore 8, Open-Meteo) |
| `services/compare.py` | Two-district snapshot delta |
| `providers/open_meteo.py` | forecast (TTL 90s), flood, air (`past_days=7`), marine, geocode |
| `providers/imd.py` | CAP RSS + humanize_cap_title + official REST (usually 401) |
| `providers/datagov.py` | CPCB NAQI + Agmarknet |
| `providers/nasa_power.py` | Daily climatology |
| `providers/hazards.py` | USGS FDSN + INCOIS ITEWS JSON catalog |
| `providers/openaq.py` | Historical PM2.5 |
| `providers/aikosh.py` | Dataset search if key present |
| `providers/http.py` | Shared `httpx.AsyncClient` (25s timeout) |
| `ml/features.py` | Flatten OM/flood/air/marine into feature dict |
| `ml/risk.py` | Weighted-linear XAI cards: flood, drought, heat, irrigation, air, **seismic, tsunami** |
| `ml/blend.py` | Dual forecast; ours stays within ~±12% of trusted Open-Meteo |
| `ml/outlook.py` | 7-day soil bucket, irrigate/flood flags |
| `ml/prescribe.py` | Actions + why/when/who + liter bands |
| `ml/anomaly.py` | Drivers + `DiagnosticStory` |
| `ml/sky.py` | WMO code → sky; 16-point compass; wind rose bins |
| `ml/hazards_outlook.py` | Multi-factor flood/tsunami/seismic scores on `predictions.hazards` |
| `data/india_districts.py` | District gazetteer |
| `data/india_towns.py` | Cities/towns (Haldia, Santiniketan, …) |
| `data/india_coast.py` | Coast snap for marine |
| `i18n/templates.py` | Deterministic en/hi/bn strings with `{slots}` |
| `i18n/translate_reply.py` | `compose_indic` structured hi/bn (MT fallback) |
| `i18n/detect.py` | Script detect (any language) + `has_script` + `pick_output_locale` |
| `i18n/mt.py` | Online MT: Google gtx → MyMemory; inbound any→en, outbound en→reply |
| `i18n/number_lock.py` | Advisory extra-number scan (does **not** rewrite text) |
| `agents/intent_router.py` | Intent + required tools |
| `agents/orchestrator.py` | Tool loop + English draft + Indic render |
| `agents/prompts.py` | `SYSTEM` (English tool loop). Outbound is MT, not an Ollama rewrite. |
| `llm/ollama_client.py` | OpenAI client → Ollama; empty-choices safe; retry without tools |
| `tools/__init__.py` | LangChain-shaped registry (`build_registry(snap)`) |
| `rag/store.py` + `rag/knowledge/` | Tiny playbook retrieve |
| `schemas/` | `Location`, `DashboardSnapshot`, `EarlyWarning`, `LiveWatch`, `RiskCard`, `ChatRequest` |

### Important schema fields

`Location`: `id, label, state, district, lat, lon, place_kind, place_name, crop_hint, plot_m2, …`

`DashboardSnapshot.live`: sky, wind (rose + hourly), marine (`nearest_coast`, `coast_km`, `snapped`), flood, air (CPCB + OM + history), quakes, tsunami.

`predictions`: `{ trusted, ours, adjustments, inputs, hazards }`.

`EarlyWarning`: `hazard` = weather|flood|air|marine|seismic|tsunami; titles go through `imd.humanize_cap_title` (never leave “Heavy to very heavy with extremely heavy rainfall”).

---

## 6. Frontend map (`frontend/src/`)

| Path | Role |
|---|---|
| `app/page.tsx` | Shell: header search + live stamp; tab bodies |
| `app/globals.css` | Light rain/neumorphic theme (`.neo`, `.chip`, `.live-dot`) |
| `lib/store.ts` | Zustand: locale, **outputLocale**, tab, dashboard, chat, sidebarOpen, pendingAsk |
| `lib/api.ts` | `fetchDashboard`, `searchPlaces`, `streamChat` (SSE) |
| `types/dashboard.ts` | Mirrors backend snapshot (keep in sync when adding fields) |
| `i18n/copy.ts` | UI strings `en` / `hi` / `bn` — add **all three** when adding a key |
| `i18n/presets.ts` | Same Advisor questions in en / hi / bn (chips + dock) |
| `components/Sidebar.tsx` | Collapsible rail + Lucide-style SVGs (`Icons.tsx`) + locale ASK chips |
| `components/OverviewLive.tsx` | Sky left, rain/predictions right, wind below; `OverviewPlots` exported |
| `components/EarlyWarnings.tsx` | Collapsible multi-hazard watch |
| `components/LensGrid.tsx` | Overview uses `focus="why-do"` (diagnostic + prescriptive only) |
| `components/ChatDock.tsx` | Presets by locale; `Markdown` renderer for assistant |
| `components/Markdown.tsx` | Lightweight `**`, `#`, lists, links — no extra npm markdown lib |
| `components/SquareMap.tsx` + `MapView.tsx` | Leaflet; Bhuvan overlay via `/api/map/wms` |
| `components/Icons.tsx` | Inline Lucide SVGs (ISC) |

**Tabs:** `overview | map | forecast | predicted | risks | market | advisor`

**Overview order:** hazard watch → sky + today’s rain → wind → why/do → collapsible plots (default closed).

**Quiet refresh:** every 60s via `quietRefresh()` (no loading flash). Open-Meteo forecast cache is 90s.

**Language:** `setLocale` also sets `outputLocale`. Advisor “Reply in” can override. Sidebar chips call `setPendingAsk` + switch to advisor.

---

## 7. Advisor / LLM pipeline

`POST /api/chat` body (`ChatRequest`):

```
message, locale_hint, output_locale, location, history[], regenerate
```

`run_agent` (`orchestrator.py`):

1. **Inbound MT:** detect language (script first). Translate any non-English question to English via Google gtx (MyMemory fallback). Presets stay in en/hi/bn in the UI; the LLM only ever sees English.
2. **Reply language:** `pick_output_locale`. An explicit “Reply in” override (output_locale ≠ UI hint) wins. Otherwise a non-English question is answered in that language (so Bengali typed in an English UI comes back in Bengali).
3. Classify intent / extract place / state / metric on the **English** text (original kept as fallback).
4. Build snapshot; stream `widget_patch` so the dashboard follows the place.
5. Run required tools, then Ollama tool-calling (English `SYSTEM`) up to 3 rounds. History is translated to English first.
6. Force a no-tools final English draft.
7. `_ensure_ranking` if rank JSON was not mentioned.
8. `lock_and_note` (advisory).
9. **Outbound MT:** translate the English draft to the reply language (numbers + IMD/CPCB/USGS/… locked). If MT fails or lacks script: `compose_indic` for hi/bn, else English.

**Do not** concatenate English templates with Indic fragments. **Do not** use a second Ollama pass to “rewrite” Indic — that produced spliced garbage.

Intents include: `rank, list, irrigation, rain, flood, drought, heat, aqi, price, compare, outlook, crop, seismic, tsunami, marine, general`.

---

## 8. External APIs and datasets

### Called on a normal dashboard load

| Source | URL / id | Role |
|---|---|---|
| Open-Meteo forecast | `api.open-meteo.com/v1/forecast` | Weather, soil, ET₀, wind, sky |
| Open-Meteo flood | `flood-api.open-meteo.com/v1/flood` | GloFAS discharge |
| Open-Meteo air | `air-quality-api.open-meteo.com/v1/air-quality` | CAMS AQI (+ `past_days=7`) |
| Open-Meteo marine | `marine-api.open-meteo.com/v1/marine` | Waves; inland → nearest coast |
| Open-Meteo geocode | `geocoding-api.open-meteo.com/v1/search` | Extra city search (`countryCode=IN`) |
| NASA POWER | `power.larc.nasa.gov/api/temporal/daily/point` | Climatology |
| IMD CAP | `cap-sources.s3.amazonaws.com/in-imd-en/rss.xml` | Official warnings |
| data.gov.in CPCB | resource `3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69` | Realtime NAQI |
| data.gov.in Agmarknet | resource `9ef84268-d588-465a-a308-a864a43d0070` | Mandi prices |
| USGS FDSN | `earthquake.usgs.gov/fdsnws/event/1/query` | 7-day India–Indian Ocean box |
| INCOIS ITEWS | `tsunami.incois.gov.in/itews/DSSProducts/OPR/past90days.json` | Tsunami/quake bulletins (TLS verify disabled for this host) |
| OpenAQ v2 | `api.openaq.org/v2/measurements` | Historical PM2.5 |
| Bhuvan WMS | `bhuvan-vec3.nrsc.gov.in/bhuvan/ows` | `gw_wfs:WB_LGEOM` and other `*_LGEOM` |
| NASA GIBS | `gibs.earthdata.nasa.gov/wms/...` | Optional true-color overlay |

### Map basemaps (browser tiles)

CARTO Positron, OSM, Esri World Imagery, OpenTopoMap.

### Wired but often not live

| Source | Notes |
|---|---|
| IMD REST `api.imd.gov.in` | 401 without whitelist |
| AIKosh | `missing_key` without `AIKOSH_API_KEY` |
| MOSDAC / NASA Earthdata / OpenWeather | Settings only; not on snapshot path |

### Local data

`india_districts.py`, `india_towns.py`, `india_coast.py`, `rag/knowledge/*.md`.

**Bhuvan pitfall:** `geomorphology.wb_gm50k_0506_new` on vec2 does **not** work. Use the FastAPI proxy `GET /api/map/wms` with `gw_wfs:WB_LGEOM`. Leaflet `WMSTileLayer` url = `/api/map/wms`.

**Marine pitfall:** Open-Meteo has no grid over many deltas. Snap via `nearest_coast`; never show “Inland — no marine grid”.

---

## 9. Location resolution

Order in `search_places` / `resolve_location`:

1. Curated towns (`india_towns.py`) — **Haldia, West Bengal** must beat Open-Meteo’s Odisha hamlet  
2. District gazetteer  
3. Open-Meteo India geocode (deduped)

Dashboard query: `district`, `place`, `lat`, `lon`. Frontend sends `place_name` as `place`.

`place_kind`: `district | city | town | place`.

---

## 10. Tests

Run from `backend/`:

```
python -m pytest -q
```

Notable tests: `test_imd_title`, `test_warnings`, `test_sky`, `test_coast`, `test_blend` (ours close to trusted), `test_translate_reply` (no Indic splice), `test_mt_layer` (protect/restore + locale pick + mocked Google), `test_location` (Haldia / Santiniketan), `test_risk_xai` (contributions sum to score), `test_agent_tools`.

When changing `extract`, `all_risks` (new cards OK if they still sum), `compose_indic`, or CAP titles — update these tests.

---

## 11. Config / env

`backend/app/config.py` + `backend/.env`:

| Variable | Purpose |
|---|---|
| `OLLAMA_BASE_URL` | default `http://127.0.0.1:11434/v1` |
| `OLLAMA_MODEL` | `qwen2.5` |
| `TRANSLATE_ENABLED` | default true; Google gtx + MyMemory, no key |
| `DATA_GOV_IN_API_KEY` | CPCB + Agmarknet |
| `IMD_API_KEY` | unused until REST whitelist |
| `AIKOSH_API_KEY` | AIKosh search |
| `DEFAULT_LAT/LON/STATE/DISTRICT` | Nadia defaults |

---

## 12. Common bugs already fixed (do not reintroduce)

| Symptom | Cause / fix |
|---|---|
| IMD 401 | Use CAP, not REST |
| Advisor only templates | Empty Ollama choices; retry no-tools; keep LLM text |
| Haldia AQI cited Siliguri | `extract_place` + city-match CPCB + `is_local_station` |
| Bengali `জেলা — / ভিত্তি —` | Phrase splicing; use online MT + `compose_indic` fallback, never splice |
| Number-lock deleted good LLM text | Lock is advisory only (`lock_and_note`) |
| “Inland — no marine grid” | Coast snap + honest nearest-coast label |
| Garbled IMD title | `humanize_cap_title` |
| Bhuvan overlay blank | Wrong layer/host; proxy vec3 `WB_LGEOM` |
| Advisor shows `**` `#` | Render with `Markdown.tsx` |
| UI language ≠ reply language | `setLocale` also sets `outputLocale` |
| Pytest `No module named app` | Run from `backend/` |

---

## 13. How to add things (recipes)

**New live field on Overview**  
1. Fetch in `gather_observations`  
2. `features.extract`  
3. `CurrentConditions` / `LiveWatch` / series  
4. `frontend/src/types/dashboard.ts`  
5. `OverviewLive` or `EarlyWarnings`  
6. `copy.ts` all three locales  

**New Advisor tool**  
Register in `tools/__init__.py`; add to `intent_router.required_tools` if needed; compact large JSON in `_compact_tools`.

**New Indic sentence**  
Add to `templates.py` **and** `compose_indic` — do not regex-replace English.

**New town**  
Append `india_towns.py` (name, state, district, lat, lon, kind, aliases).

---

## 14. Ports and processes

| Port | Process |
|---|---|
| 3000 | Next.js |
| 8000 | uvicorn `app.main:app` |
| 11434 | Ollama |

Only one listener on 8000. After a restart, `/api/health` should be 200.

---

## 15. Suggested first reads in a new session

1. This file  
2. `backend/app/services/snapshot.py`  
3. `backend/app/agents/orchestrator.py`  
4. `frontend/src/app/page.tsx`  
5. `frontend/src/lib/store.ts`  
6. `backend/app/tools/__init__.py`

Then grep for the feature name (`compose_indic`, `humanize_cap_title`, `WB_LGEOM`, `quietRefresh`, …).
