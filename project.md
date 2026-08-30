# Rituchakra — agent handoff

India-first environmental intelligence. Live weather, flood, drought, heat, air, marine, seismic, tsunami, mandi prices, explainable risk, and a 0–6 h decision nowcast — then a chat Advisor that **only quotes Rituchakra `data()` packs**. It never invents millimetres, AQI, rupees, or risk scores.

Use this file to continue work in a new session or a different tool. Prefer this over the shorter `README.md`.

Product name is **Rituchakra**. Repo folder may still be `RainFall`. GitHub: `https://github.com/NetRunnerXD/Rituchakra.git` (`main`).

---

## 1. What it is

A monorepo. **The backend is the product.** It is a standalone JSON API (no web assets). Any UI lives in its own folder.

| Path | Stack / role |
|---|---|
| `backend/` | FastAPI + Pydantic v2 + httpx + pytest. Publish independently (`/docs`, `/openapi.json`). |
| `frontend/` | Optional Next.js 14 App Router dashboard (Tailwind, Zustand, Recharts, Leaflet). HTTP client of the API. |
| `clients/` | Portable TypeScript client (`clients/js`) for a new web app or React Native. No React/Next/DOM. |

**Product questions (four lenses)**

1. What is happening — current sky, rain, soil, AQI, live multi-hazard board
2. Why it is happening — NASA POWER anomalies + diagnostic stories + science pack
3. What is likely next — 0–6 h nowcast + dual 7-day forecast (trusted Open-Meteo vs residual-blend) + named date-window rain (`get_rain_window`) + hazard outlook
4. What we should do — rule-engine prescriptions (liters, pump-set, field access, flood/heat/AQI)

Default focus: **Haldia, Purba Medinipur, West Bengal** (`22.0667, 88.0698`). Nadia remains in the gazetteer. Search is India-only (towns, then districts, then Open-Meteo `countryCode=IN`).

---

## 2. Hard constraints (do not violate)

- **India-only UX.** Gazetteer + geocoding are India. Do not add global city search as default.
- **LLM never invents numbers.** Forecasts, risk %, liters, AQI, mandi rupees, nowcast mm, and **date-window daily mm** come from providers/ML/tools. The LLM orchestrates tools and writes prose. For “rain in Haldia 23–28 August” the answer is `get_rain_window` rows (or the deterministic table built from them), never free-form millimetres.
- **Local Ollama only** (`qwen2.5` via OpenAI-compatible API). Do **not** pull Mixtral / Llama 3.1.
- **No IMD REST without IP whitelist.** `api.imd.gov.in` returns 401. Use **IMD CAP RSS** for official warnings.
- **Do not commit API keys.** `DATA_GOV_IN_API_KEY` and others live in `backend/.env` (gitignored).
- **Open-Meteo has no earthquake or tsunami products.** Seismic = USGS FDSN. Tsunami = INCOIS ITEWS. Label sources honestly.
- **NCS has no stable public JSON.** Do not pretend an NCS live API exists.
- **Indic replies:** never splice English fragments into Hindi/Bengali (that produced garbage like `জেলা —`). Inbound MT (any language → English) feeds the LLM. Outbound MT (English → reply language) displays the answer. Numbers and source acronyms are locked. If MT fails, `compose_indic` is the hi/bn fallback.
- **Speech and CAP do not write millimetres.** Vernacular tags and IMD CAP change category and timing only (`nowcast.fuse_speech`, `cap_prior`).
- **Open-Meteo past hours are not rain-gauges.** Nowcast labels them `observed` / `open-meteo-analysis`. Do not call them station observations in the UI.
- **Kalman scenes are not satellite.** Default knots are Open-Meteo hourly analysis (`source_kind: model-analysis`). MOSDAC HEM / IMERG Early stay settings stubs until a legal download is wired. Do not label the live/history graph “INSAT”.
- **Storm-map IR is a public JPEG, not HEM millimetres.** `imd_insat.py` georeferences IMD’s Asia-sector INSAT-3D/3DS IR1 JPEG. Adler–Negri rain-rate is a Tb proxy. Do not quote it as a rain-gauge or as MOSDAC HEM. Cells are clipped with `india_mask.in_india` — the 68–97.5°E rectangle includes Tibet/Yunnan.
- **Asiamer bounds are 40–110°E, 10°S–45°N** (IMD SATMET SOP), not the old Kalpana 50–130°E / 40°S–40°N box. Public JPEGs include title + colorbar; `crop_chrome` strips those pixels before sampling and before `GET /api/sat/imd-asia`. Leaflet must use the proxy URL (CORS). Do not overlay the raw IMD host JPEG.
- **Models-tab hourly VERA is a nowcast overlay, not ECMWF ENS.** Ensemble = IR rain-rate mix + Open-Meteo hour. Blend / moe = gated member mean. Do not score Open-Meteo against itself: `obs` is IMERG/HEM/`obs_hourly` only. Until then show **agreement vs website** MAE, not “skill”. Alert words: No alert / Possible / Warning (not quiet / outlook / watch).
- **Weatherbit lightning is observed flashes, not a model watch.** Current search is 75 km / 45 min; history costs 10 quota units per call. On 429, keep the last good cache; do not overwrite it with an empty list. Open-Meteo weather_code ≥ 95 at hubs is a thunder nowcast, not GPS strokes.
- **Hugli tide / CWC / pond-tank are physiography-gated.** `physiography.classify` (Leh = orographic before arid). Jaipur and Leh must not show Hooghly port or Hugli tide.
- **Daily “today” is the IST calendar date.** `features.extract` skips `past_days` rows before today. Do not use `daily[0]` after `past_days=1` — that is yesterday (this showed ~80 mm as “today’s rainfall” in Haldia).
- **Backend serves no frontend assets.** Do not mount `StaticFiles` from `frontend/`. Clients call HTTP + CORS.
- **Comments:** short, factual; no step-by-step narration in code.
- **UI verification:** if you change visible web UI and browser tools exist, exercise the feature. This repo often has no browser MCP — then verify via `/api` + Next `tsc` and say so.

---

## 3. How to run

Windows / PowerShell. `&&` is not reliable in some agent shells — use `;` or separate commands.

```powershell
# Both processes from the repo root
cd D:\Project\Random\RainFall
python main.py
# API http://127.0.0.1:8000/docs   dashboard http://localhost:3000
# python main.py --api-only     API only
# python main.py --host 0.0.0.0

# Backend only (cwd must be backend/ for pytest and uvicorn)
cd D:\Project\Random\RainFall\backend
python -m pip install -r requirements.txt
# copy .env.example .env   if missing
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# use --host 0.0.0.0 if a phone / other machine will call the API

# Frontend (optional)
cd D:\Project\Random\RainFall\frontend
copy .env.example .env.local
npm install
npm run dev
# http://localhost:3000
```

Ollama (optional; needed for Advisor prose):

```
ollama serve
# model already expected: qwen2.5
```

- The Next app calls `NEXT_PUBLIC_API_BASE` (default `http://127.0.0.1:8000`) over CORS. Empty base uses same-origin `/api` plus an optional Next rewrite.
- Health: `GET http://127.0.0.1:8000/api/health`
- Service card: `GET http://127.0.0.1:8000/`
- Swagger: `http://127.0.0.1:8000/docs` — OpenAPI: `/openapi.json` — route list: `/api`
- Tests: `cd backend; python -m pytest -q` (`pythonpath = .` in `pytest.ini`). Running pytest from repo root fails with `No module named 'app'`.
- Frontend typecheck: `cd frontend; .\node_modules\.bin\tsc --noEmit`
- Restart uvicorn after backend edits (Python does not hot-reload unless `--reload`). Killing `:8000` then starting again is the usual pattern; old processes exit with code 1 — that is expected.
- Export OpenAPI: `cd backend; python scripts/export_openapi.py`

---

## 4. Architecture

```
Any client (frontend/ or a new web / React Native folder using clients/js)
    └─ HTTP + CORS → FastAPI (:8000)   JSON only, no web assets
                          ├─ /                 service card
                          ├─ /docs             Swagger
                          ├─ /openapi.json     contract
                          ├─ /api              route catalog
                          ├─ /api/health
                          ├─ /api/dashboard    snapshot
                          ├─ /api/nowcast           locked 0–6 h object
                          ├─ /api/nowcast/live      1-min gap + 1 Hz playhead
                          ├─ /api/nowcast-live      alias (proxies that drop /live)
                          ├─ /api/live-nowcast      alias
                          ├─ /api/nowcast/sat       Kalman rain-rate between scenes (stride=1|60)
                          ├─ /api/nowcast-sat       alias
                          ├─ /api/nowcast/storm-map  state / All-India IR cells + lightning feed
                          ├─ /api/nowcast-storm-map  alias
                          ├─ /api/science
                          ├─ /api/sat/imd-asia CORS-safe cropped INSAT Asia JPEG
                          ├─ /api/geo/*        India search + Bhuvan WMS proxy
                          ├─ /api/chat         SSE ← agents.orchestrator.run_agent
                          └─ providers + ml + science + cache (in-memory TTL)
```

**Snapshot is the core object.** Almost every dashboard widget and most tools read a `DashboardSnapshot`.

```
Location
  → gather_observations (OM weather/flood/air/marine, NASA, IMD CAP, CPCB, Agmarknet,
                         USGS, INCOIS, OpenAQ, AIKosh, Sachet, Hooghly port signal)
  → ml.features.extract
  → science.enrich_features (hysteresis + phenology onto the feature dict)
  → nowcast.fetch_neighbors (≤6 gazetteer OM hours, cached 90s)
  → ml.risk.all_risks
  → science.build_science (regret, livelihood, atlas, bandit, vernacular,
                           blindspot, water-balance XAI, nowcast A–H,
                           monsoon clock, ledger, CWC station lookup)
  → Sachet CAP + Hooghly port signal attached onto science
  → ml.outlook + ml.blend (dual 7-day predictions)
  → ml.vera.build_vera (Models tab pack on `predictions.vera`)
  → ml.anomaly + science diagnostic stories
  → ml.prescribe + nowcast actions (pump hold / take cover / stay off)
  → ml.hazards_outlook
  → DashboardSnapshot { descriptive, diagnostic, predictive, prescriptive,
                        risks, live, predictions, ogd, map, vegetation, science }
```

`science.nowcast.locked` is the only **nowcast** JSON the LLM may quote (not Kalman `playhead_rate` / `pred_series`). Named-date rain is quoted from **`get_rain_window.days`** only.

---

## 5. Backend map (`backend/app/`)

| Path | Role |
|---|---|
| `main.py` | FastAPI app, CORS, `/`, `/docs`, `/api`, `/api/health` — **no static UI** |
| `config.py` | pydantic-settings; `backend/.env` |
| `http_urls.py` | Absolute API URLs (`PUBLIC_BASE_URL` or request host) |
| `cache.py` | In-memory TTL cache (do not slam Open-Meteo/CAP) |
| `api/dashboard.py` | `/dashboard`, `/forecast`, `/predictions`, `/outlook`, `/risks`, `/science`, `/nowcast`, `/nowcast/live`, `/nowcast-live`, `/live-nowcast`, `/nowcast/sat`, `/nowcast-sat`, `/nowcast/storm-map`, `/nowcast-storm-map`, **`/sat/imd-asia`**, `/insights`, `/scan`, `/compare`, `/states`, `/districts`, `/brief`, `/agent/tools` |
| `api/geo.py` | `/geo/search`, `/geo/reverse`, `/geo/nearby`, `/map/layers`, **`/map/wms` Bhuvan proxy** |
| `api/deps.py` | `loc_from_query(district, place, lat, lon)` |
| `api/chat.py` | `POST /chat` SSE (`data: {json}\n\n`) |
| `services/snapshot.py` | Observation gather, warning build, `LiveWatch`, `primary_reply`, science + nowcast actions |
| `services/location_svc.py` | Resolve/search: towns → districts → state capital → Open-Meteo India (`resolve_india_place`) |
| `services/scan.py` | Rank districts **in that state only**. A town name is `unknown_state` (empty), never all-India. |
| `services/locality.py` | Keep a bulletin on the pin: drop Sachet/CAP rows that name another state; Hooghly port only on the Hooghly belt |
| `services/compare.py` | Two-district snapshot delta |
| `providers/open_meteo.py` | forecast (TTL 90s, `past_days=1` for hourly history, extra CAPE/dew/gust/cloud layers), flood, air (`past_days=7`), marine, geocode, **`daily_window`** (forecast + archive by `start_date`/`end_date`) |
| `providers/imd.py` | CAP RSS + humanize_cap_title + official REST (usually 401) |
| `providers/datagov.py` | CPCB NAQI + Agmarknet |
| `providers/nasa_power.py` | Daily climatology |
| `providers/hazards.py` | USGS FDSN + INCOIS ITEWS JSON catalog |
| `providers/openaq.py` | Historical PM2.5 |
| `providers/aikosh.py` | Dataset search if key present |
| `providers/cwc.py` | Nearest CWC gauge lookup (static table, not a live hydrograph) |
| `providers/sachet.py` | NDMA Sachet CAP RSS (state + India) |
| `providers/port_signal.py` | IMD Hooghly / Haldia port signal (best-effort scrape) |
| `providers/http.py` | Shared `httpx.AsyncClient` (25s timeout) |
| `providers/imd_insat.py` | Public IMD INSAT-3D/3DS Asiamer IR JPEG; chrome crop; `ASIA_BOUNDS` 40–110°E, 10°S–45°N; India crop + Tb grid |
| `providers/gibs_ir.py` | NASA GIBS Himawari IR + IMERG rate at a pin |
| `providers/weatherbit_lightning.py` | Current + historical lightning (75 km cap; last-good cache on 429) |
| `providers/lightning_feed.py` | Optional bbox URL, else Weatherbit hubs + 6 h stroke memory |
| `providers/om_thunder.py` | Open-Meteo weather_code / CAPE thunder, including `past_hours=6` |
| `science/sat_cv.py` | IR connected-component cells, hull rings, 15/30/60 min advection |
| `science/cv_nowcast.py` | Two-frame cooling, block-match flow, P(lightning) / P(cloudburst) |
| `science/thunder_predict.py` | Per-cell lifetime, predicted strikes, confidence band, storm polygons |
| `science/storm_map.py` | State / All-India pack: past/live/predicted incidents (skips network under pytest) |
| `science/convective.py` | Pin-level cloudburst / downburst / lightning scores from live IR + strokes |
| `science/sat_live.py` | Assemble INSAT + GIBS + lightning for the nowcast pin |
| `data/india_mask.py` | Point-in-India (mainland + NE rings, Andaman, Lakshadweep) |
| `data/physiography.py` | hugli / orographic / arid / plateau / plains — gates tide, CWC, pond scale |
| `ml/features.py` | Flatten OM/flood/air/marine; **slice daily series from IST today** (`_start_today`); keep `precip_yesterday_mm` |
| `ml/risk.py` | Weighted-linear XAI cards: flood, drought, heat, irrigation, air, seismic, tsunami, livelihood |
| `ml/blend.py` | Dual 7-day forecast; ours stays within ~±12% of trusted Open-Meteo |
| `ml/vera/` | VERA-MoE Models pack: CV branch, gate, fusion, hourly mix, verify ledger, extremes |
| `ml/train/` | Optional gate / sat pretrain scripts (not live path) |
| `providers/gpm_imerg.py` | GIBS IMERG always; GES DISC when Earthdata token set |
| `providers/graphcast_run.py` | GraphCast/Pangu/FourCastNet slot status + member attach |
| `providers/imd_gridded.py` | IMD Pune 0.25° archive status / ingest |
| `ml/outlook.py` | 7-day soil bucket, irrigate/flood flags (hysteresis soil) |
| `ml/prescribe.py` | Daily actions + why/when/who + liter bands |
| `ml/anomaly.py` | Drivers + `DiagnosticStory` |
| `ml/sky.py` | WMO code → sky; 16-point compass; wind rose bins |
| `ml/hazards_outlook.py` | Multi-factor flood/tsunami/seismic scores on `predictions.hazards` |
| `science/__init__.py` | `enrich_features` + `build_science` |
| `science/nowcast.py` | 0–6 h decision nowcast (see §5.1) |
| `science/live.py` | 1-min PCHIP gap series + 1 Hz playhead; issue log under `backend/.cache/nowcast_issues.jsonl` |
| `science/sat_kalman.py` | Async EKF rain-rate between observation scenes; persist `.cache/sat_kalman.json` |
| `providers/sat_obs.py` | Scene adapter: OM hours as `model-analysis`; MOSDAC/IMERG stub until credentials + download are wired |
| `science/sat_phys.py` | Deterministic intra-hour shape (Byers–Braham pulses, advection, CAPE, moisture, cloud, diurnal). Server-only. |
| `science/monsoon.py` | District monsoon clock (pre / active / break / post) |
| `science/ledger.py` | 7-day plot water-budget ledger (conservation-closed) |
| `science/wbgt.py` | Wet-bulb globe proxy for labour window |
| `science/soil.py` | Extra soil helpers (used by hysteresis / ledger) |
| `science/hysteresis.py` | Dual-limb soil memory |
| `science/regret.py` | 3-day irrigate hold/apply/wait regret |
| `science/livelihood.py` | Compound closed-task days |
| `science/residual.py` | India regional residual atlas for Open-Meteo |
| `science/bandit.py` | Which source to act on today (policy, not a learned bandit yet) |
| `science/phenology.py` | Crop stage from calendar + mandi stress |
| `science/vernacular.py` | Indic speech tags — **never millimetres** |
| `science/blindspot.py` | Unobserved hydrology flag |
| `science/wb_xai.py` | 3-day P−ET−runoff−ΔS identity |
| `science/verify.py` | Skill proxy vs climatology (+ nowcast error if present) |
| `data/india_districts.py` | District gazetteer + aliases + `state_frame` (All India bbox is 68.1–97.4°E, 6.6–35.8°N) |
| `data/india_towns.py` | Cities/towns (Haldia, Cherrapunji, Santiniketan, …) + fuzzy `extract_town` |
| `data/india_coast.py` | Coast snap for marine |
| `data/cwc_wb.py` | Static Hugli / WB CWC station table |
| `i18n/templates.py` | Deterministic en/hi/bn strings with `{slots}` (includes nowcast templates) |
| `i18n/translate_reply.py` | `compose_indic` structured hi/bn (MT fallback) |
| `i18n/detect.py` | Script detect + `has_script` + `pick_output_locale` |
| `i18n/mt.py` | Online MT: Google gtx → MyMemory |
| `i18n/number_lock.py` | Digit scan used by claim-check (ungrounded figures become `—`) |
| `agents/intent_router.py` | Legacy intent labels + required-tool packs (tests / docs). Live chat uses `utterance.interpret`. |
| `agents/dates.py` | Parse “23 to 28th August” / ISO / next N days |
| `agents/utterance.py` | Classify any line: catalog / follow-up / refuse / `How about Malda` place-retarget / data needs |
| `agents/facts.py` | `source_gate`, `quote_facts` (incl. outlook days), `[temp_c]` fill, false-shrug strip, `is_dash_soup` |
| `agents/data_tool.py` | One `data()` function (`forecast`, `nowcast`, `rain_window`, `aqi`, `mandi`, `warnings`, `risks`, `rank`, `states_weather`, `capability`, …) |
| `agents/claims.py` | Span-level numeral lock against this-turn payloads |
| `agents/memory.py` | In-process conversation: last place, collected keys, last refuse, catalog flag |
| `agents/binder.py` / `views.py` / `dimensions.py` | Dump detection, nowcast compact, multi-axis hints |
| `services/rain_window.py` | Open-Meteo daily slice for a place + calendar window |
| `agents/orchestrator.py` | SSE chat: interpret → resolve India place → optional `data()` loop → quote/lock → MT |
| `agents/prompts.py` | English `SYSTEM`. Outbound is MT, not a second Ollama rewrite. |
| `llm/ollama_client.py` | OpenAI client → Ollama; empty-choices safe; retry without tools |
| `data/fuzzy.py` | Name fold + Damerau–Levenshtein (`Puruliya`→Purulia, never Puri) |
| `data/india_capitals.py` | Weather HQ for every state / UT (Delhi, Odisha→Bhubaneswar, …) |
| `data/blocked_places.py` | Fiction / foreign names that must never geocode |
| `tools/__init__.py` | LangChain-shaped registry for `/agent/tools` and older tests |
| `rag/store.py` + `rag/knowledge/` | Tiny playbook retrieve |
| `schemas/` | `Location`, `DashboardSnapshot`, `EarlyWarning`, `LiveWatch`, `RiskCard`, `ChatRequest` |
| `scripts/export_openapi.py` | Write `backend/openapi.json` |
| `scripts/ingest_imerg.py` / `ingest_mosdac.py` / `ingest_imd_gridded.py` | Optional archives under `.cache/` |
| `scripts/nightly_obs.py` | Observation ingest for the verify ledger |
| `scripts/verify_models_cities.py` | Playwright smoke of Models tab on five cities |

### 5.1 Nowcast (`science/nowcast.py`)

0–6 h **decision** nowcast. Not MetNet / radar / INSAT.

| Piece | What it does |
|---|---|
| Lead-time split | Hours 1–2 `nowcast`, 3–4 `blend`, 5–6 `nwp` |
| Regime persistence | monsoon / cell / squall / break / orographic |
| Gazetteer advection | Optical-flow-like (u, v) on ≤6 neighbor OM points |
| CAP prior | Engine weights + onset pull — **no extra mm** |
| Speech fuse | Category / Kal watch / P(interrupt) — **`mm_changed` is always false** |
| Pump-set | 90 min P(interrupt) + liters; hold only if rain ≥ 0.8 mm |
| Field access | 2 h, phenology-gated |
| Cost-loss | wasted liters vs stress-mm if wait 2 h |
| Ponding | 60 / 120 min × hysteresis limb |
| Hourly water balance | P − infil − pond, checksum |
| Tide × rain | Harmonic **proxy** (labelled); `drain_blocked` |
| Pluvial vs fluvial | Plot ponding ≠ GloFAS river |
| Kal Baisakhi | Instability **watch**, not lightning |
| Air 6 h | Open-Meteo US AQI hours |
| WBGT labour | `wbgt.py` in the 2 h field-access window |
| Gap series | 1-min PCHIP shape; **sum of minutes = locked hourly mm** |
| Playhead | 1 Hz clock: tide station, onset countdown, ponding — **no new rain total** |
| Between-scene Kalman | 3-state **asynchronous EKF** on `[ln(r+ε), bias, decay]` (`sat_kalman.py`). Intra-hour **curve** is `sat_phys` (pulses / advection / CAPE / moisture / cloud), computed **on the server**. UI plots `pred_series` + `history.series` — do not recompute pulses in the browser (that broke Recharts). Scenes = OM hours, **not INSAT**. Does **not** rewrite locked mm. |
| Error memory | +1 h vs next OM hour, by district + regime |
| Locked JSON | `science.nowcast.locked` — Advisor quotes only this |

`GET /api/nowcast` returns locked + hours + pump/access/kal/tide/actions + gap/playhead + compact `sat`.

`GET /api/nowcast/live` (aliases `/api/nowcast-live`, `/api/live-nowcast`) returns the live clock: 1-minute `gap` series + `playhead` + compact `sat`. The UI ticks every second; rain timing finest on the locked-shape graph is 1 minute. Not MinuteCast / radar.

`GET /api/nowcast/sat?stride=1|60` (alias `/api/nowcast-sat`) returns the Kalman pack: `formula` (`decay_bias_v1` envelope only), `obs_knots`, **server** `pred_series`, `history` (causal replay), `innovations`, `mae`, `last_error_mm_h`, `next_obs_eta_s`, `drivers`. Advisor must not quote these rates — only `locked`.

If Next or a proxy 404s the nested `/nowcast/live` path, the frontend tries the aliases and can rebuild a 1-min gap in `lib/nowcastGap.ts`. Same pattern for `/nowcast/sat`.

### 5.2 Live storm map (`science/storm_map.py`)

India-only convective nowcast for the Map (and Risks) tab. **Does not rewrite locked Open-Meteo millimetres.**

| Piece | What it does |
|---|---|
| INSAT IR1 JPEG | Public Asia-sector image, cropped with `in_india` (non-India pixels warmed to 300 K) |
| GIBS | Himawari IR + IMERG as map overlays, not HEM mm |
| CV cells | Connected components on Tb ≤ 248 K; convex hull `ring`; Adler–Negri `rain_ir_mm_h` |
| Two-frame CV | Persist last India grid; cooling; 8×8 block flow; lightning-jump / cloudburst heuristics |
| Lifetime | Per-cell minutes from size, Tb, cooling, P(ltn), rain, speed, trend — not a kind-only +45 min |
| Predicted strikes | Lagrangian 15/30/45/60 min, `P(t)=P0·exp(−t/τ)`, `confidence` + `confidence_band` |
| Polygons | Live hull + +30 min advected hull |
| Past lightning | Weatherbit current (hubs, 75 km / 45 min) + optional today history (2 hubs, 10 credits/call) + 6 h memory. 429 → last-good cache. If still empty, Open-Meteo past-hour thunder at hubs (labelled, not GPS). |
| Past storm | IR cells that dropped off the live set, kept ~4 h |
| India crop | `in_india` then `state_frame`. All-India map does **not** draw the Tibet-covering rectangle. |

`GET /api/nowcast/storm-map?state=India` (alias `/nowcast-storm-map`). Under `PYTEST_CURRENT_TEST` returns `test-skip` with no HTTP.

Incident `phase`: `past` | `live` | `predicted`. Feed and highlights toggle those separately. Predicted rows must show `confidence`. Cell/pin circles use geographic metres, then a zoom floor (~8 px) and a zoom-out cap (~18 px) so they stay visible without covering India.

Clicking an incident focuses the map only — it must **not** call `onPick` / change the forecast pin.

### Important schema fields

`Location`: `id, label, state, district, lat, lon, place_kind, place_name, crop_hint, plot_m2, …`

`DashboardSnapshot.live`: sky, wind (rose + hourly), marine (`nearest_coast`, `coast_km`, `snapped`), flood, air (CPCB + OM + history), quakes, tsunami.

`DashboardSnapshot.science`: hysteresis, regret, livelihood, residual, bandit, phenology, vernacular, blindspot, water_balance, verify, **nowcast**, monsoon, ledger, cwc, market_lock, port, sachet_n, provenance.

`predictions`: `{ trusted, ours, adjustments, inputs, hazards, hybrid, vera }`.

### 5.3 Models tab (`ml/vera/`)

Dashboard section **Models** (`tabPredicted`). Pack is `predictions.vera` from `ml.vera.pipeline.build_vera`.

| Piece | What it does |
|---|---|
| CV branch | Last INSAT frames → CNN / ConvLSTM / ViT-shaped numpy stack; Adler–Negri rain PNG |
| Gate | Softmax over NWP + AI members, Kalman-smoothed; plain-English `reasons` + `confidence` % + `family` (`nwp` / `ai`) |
| Temporal hourly | `sat_weight(lead) * IR_est + (1−w) * Open-Meteo hour` (ensemble). After 24 h, climatology pull |
| Hourly rows | `ensemble`, **`moe` (gated blend)**, `om`, `members`, `lead_h` for 48 h; UI shows **0–24 h** |
| Verify | Log `.cache/vera_hourly_log.jsonl` keyed `pin\|hour\|lead`. `obs` only from `imerg_hourly` / `hem_hourly` / `obs_hourly`. `agreement` = MAE vs Open-Meteo (always). Skill KPI hidden without independent obs |
| Extremes | Heat / wind / rain with labels **No alert / Possible / Warning**. `compare.hourly` = blend rain vs website (Open-Meteo) |
| Satellite lab | `SatProcessMap`: proxied IR overlay, GIBS IMERG WMS, IR rain PNG, cells, AMV line, gate RGB |
| Colours | Ensemble teal `#146b7a`, blend purple `#8e44ad`, AI orange `#d35400`, NWP blue `#2c7fb8`, Open-Meteo rust `#c45c26` |

Do not call walk-forward “k-fold”. MLOps MAE is last verified ensemble error when independent obs exist — not `abs(q50)*0.12`.

`EarlyWarning`: `hazard` = weather|flood|air|marine|seismic|tsunami; titles go through `imd.humanize_cap_title` (never leave “Heavy to very heavy with extremely heavy rainfall”).

---

## 6. Frontend map (`frontend/src/`)

This folder is **one optional web client**. Do not treat it as the API. New UIs should start from `clients/`.

| Path | Role |
|---|---|
| `app/page.tsx` | Shell: header search + live stamp; tab bodies |
| `app/globals.css` | CSS-variable themes (`.neo`, `.chip`, `.live-dot`) |
| `lib/config.ts` | `API_BASE` / `apiUrl()` from `NEXT_PUBLIC_API_BASE` |
| `lib/api.ts` | `fetchDashboard`, `fetchNowcastLive` (tries `/nowcast/live` then aliases), `fetchNowcastSat`, `fetchStormMap`, `fetchStates`, `searchPlaces`, `streamChat` |
| `lib/nowcastGap.ts` | Client 1-min gap if live endpoint 404s |
| `lib/satKalman.ts` | Envelope twin + `chartFromPredSeries` / `interpSeries` (plot **server** points; do not run `sat_phys` in the browser) |
| `lib/store.ts` | Zustand: locale, **outputLocale**, tab, dashboard, chat, settings, favorites, **`applySuggestion` (tab + `setLocation` + `mapFocus`)** |
| `lib/units.ts` | Metric / imperial display |
| `types/dashboard.ts` | Mirrors backend snapshot + `NowcastPack` (keep in sync) |
| `i18n/copy.ts` | UI strings `en` / `hi` / `bn` — add **all three** when adding a key |
| `i18n/presets.ts` | Same Advisor questions in en / hi / bn (includes “Next 2 hours?” and **Haldia 23–28 Aug**) |
| `components/Sidebar.tsx` | Collapsible rail + ASK chips |
| `components/OverviewLive.tsx` | Sky, rain, **engine-labelled nowcast hours**, wind; `OverviewPlots` |
| `components/NowcastLive.tsx` | Nowcasting tab: playhead, Hugli tide, countdown, 120-min bar, ponding |
| `components/NowcastSat.tsx` | Minute / Second live series from API, history vs scenes (pred / held / obs / offset bars), MAE / innovation |
| `app/api/nowcast/live/route.ts` | Next proxy to FastAPI `/api/nowcast/live` (same-origin fallback) |
| `app/api/nowcast/sat/route.ts` | Next proxy to FastAPI `/api/nowcast/sat` |
| `components/SciencePanel.tsx` | Decision-science + nowcast tiles (collapsed on Overview) |
| `components/EarlyWarnings.tsx` | Multi-hazard watch (Alerts tab) |
| `components/SettingsPanel.tsx` | Theme, units, language, refresh, **API origin** |
| `components/ChatDock.tsx` | Presets; `ChatBlocks`; suggestion chips call `applySuggestion` (no auto tab switch) |
| `components/ChatBlocks.tsx` | Always show prose + optional tables/metrics |
| `components/PredictionsPanel.tsx` | Models tab: hourly 24 h, satellite lab, blend + reasons, extremes vs website, compare toggles, performance (agreement MAE + hourly history) |
| `components/SatProcessMap.tsx` | Leaflet process map; IMD proxy overlay; IMERG WMS; IR rain / cells / motion / gate RGB |
| `components/SquareMap.tsx` + `MapView.tsx` + `StormFeed.tsx` | Leaflet storm map: state / All India, basemap vs weather layers (no duplicate View/Basemap satellite), past/predicted/live highlights, zoom-aware circles, Weatherbit past ⚡, predicted ✦ + confidence, storm polygons. Incident click focuses only. |
| `components/MapWrap.tsx` | Dynamic `MapView` (no SSR) |
| `components/ThemeBoot.tsx` | Applies `data-theme` from settings |

**Tabs:** `overview | nowcast | alerts | map | forecast | predicted | risks | market | advisor | settings`  
Keys `1–9` switch the first nine tabs. Predicted is labelled **Models**.

**Models tab:** Hourly (ensemble / blend / Open-Meteo, 24 h) → Satellite lab → Blend (weights, confidence, reasons) → Extremes (No alert / Possible / Warning + website compare) → Compare (toggles) → Performance (website MAE always; IMERG skill when wired) → Outlook (7-day dual series).

**Overview order:** decision chips (pump / field / Kal-ghat) → sky + today’s rain → engine-labelled 0–6 h nowcast → 7-day glance → wind → collapsed Decision science → collapsed plots.

**Nowcasting tab:** 1 Hz playhead, Hugli tide (only if `phys.show_tide`), onset countdown, between-scene Kalman (Minute / Second + **History vs scenes**), locked-shape sweep, 120-min bar, ponding tank. Hours stay locked. Advisor never quotes Kalman mm/h. History line is the server physical series, not a bar between two hours.

**Map tab:** All India by default. Highlights: past lightning, predicted lightning, past storm, predicted storm, live cells. Fit events / overlay opacity / past window 1–6 h / predicted confidence filter. Same map on Risks.

**Quiet refresh:** every `settings.refreshSec` (default 60s) via `quietRefresh()`. Open-Meteo forecast cache is 90s.

**Language:** `setLocale` also sets `outputLocale`. Advisor “Reply in” can override. Sidebar chips call `setPendingAsk` + switch to advisor.

**Themes:** `sand | monsoon | midnight | ocean | contrast`. Units: `metric | imperial`.

---

## 7. Clients (`clients/`)

Framework-free TypeScript:

```ts
import { createClient } from "./clients/js/src";
const api = createClient({ baseUrl: "http://127.0.0.1:8000" });
await api.dashboard({ district: "Purba Medinipur", place: "Haldia" });
await api.nowcastLive({ district: "Purba Medinipur", place: "Haldia" });
await api.nowcastSat({ district: "Purba Medinipur", place: "Haldia" }, 1);
await api.streamChat({ message: "Should I irrigate?" }, onEvent);
```

On a phone, `baseUrl` is the PC LAN IP and uvicorn must bind `0.0.0.0`. CORS: `CORS_ORIGINS` / `CORS_ORIGIN_REGEX`. Suggested new folders: `mobile/` (Expo/RN), `web/` (Vite/etc.). Do not import `frontend/` into those apps.

---

## 8. Advisor / LLM pipeline

Chat-first, not a preset XOR. One function: **`data(need=…)`**. The dashboard pin is not auto-switched; chips let the user open a tab **at the discussed place**.

`POST /api/chat` body (`ChatRequest`):

```
message, locale_hint, output_locale, location, history[], regenerate, conversation_id
```

`run_agent` (`orchestrator.py`):

1. **Inbound MT:** detect language. Translate any non-English question to English (Google gtx → MyMemory). The LLM only ever sees English.
2. **Reply language:** `pick_output_locale` (`output_locale` wins).
3. **`utterance.interpret`** on the English line: refuse (pets / tourism / fiction), catalog (“all metrics”), follow-up (`yes` / `all of them`), or named `data()` needs. Bare “Puruliya” is a forecast. **`How about Malda` / `what about Puri`** is a place retarget → `forecast` at that town. **`what about Kerala?`** after a rank stays a **state follow-up** (not a capital forecast).
4. **Resolve place:** `resolve_named_place` (towns → districts → state/UT capital) then, if needed, `resolve_india_place` (Open-Meteo `countryCode=IN`). Never fall back to Haldia for an unknown or fictitious name. `Puruliya` ≠ Puri. `Delhi` is the city, not a state ranking. `all of them` is not a place.
5. Follow-ups inherit the last **asked** town from `memory.TurnState`. After a refuse, `yes` / `still tell me` stays refused (no Haldia AQI).
6. Optional Ollama tool loop (`data()` only). Deterministic needs (bare place, **how-about place**, catalog, date window) are **prefetched** so qwen cannot shrug or invent a 7-day table.
7. **Grounding:** `check_claims` replaces unbound digits with `—`. `fill_slots` replaces `[temp_c]` / `[rain_mm]`. `drop_false_shrug` drops “couldn’t find weather” when a pack exists. If the draft is **dash-soup** (`August —` / `—%` / `— mm` four or more times), **replace it** with `quote_facts` (now includes `outlook_days`). Otherwise append `quote_facts` when the prose forgot numbers.
8. **Outbound MT** of the English draft. No second Ollama rewrite. If MT fails: `compose_indic` for hi/bn, else English.
9. Suggestions (`focus-map`, forecast, nowcast, alerts, risks) include `location` + `center`. The UI calls `applySuggestion` → `setLocation` + `mapFocus`. Do **not** auto-`setTab`.

**Catalog** (`CATALOG_NEEDS`): forecast, nowcast, aqi, warnings, risks, mandi, capability (holes: radar, INSAT, gauges, IMD REST, NCS). Quote missing mandi / AQI honestly — never AQI 0.

**Do not** concatenate English templates with Indic fragments. **Do not** invent nowcast millimetres — quote locked nowcast only. **Do not** invent date-window millimetres — quote `data(need=rain_window)` / `get_rain_window.days`. **Do not** quote Kalman / playhead rates in Advisor.

Legacy intent labels (`rank`, `irrigation`, `window`, …) still exist on `intent_router` / `dimensions` for tests and `/agent/tools`. Live `/api/chat` does not prefetch a full snapshot for hello / elephant / poems.

---

## 9. External APIs and datasets

### Called on a normal dashboard load

| Source | URL / id | Role |
|---|---|---|
| Open-Meteo forecast | `api.open-meteo.com/v1/forecast` | Weather, soil, ET₀, wind, sky, hourly precip; `past_days=1`; CAPE, dewpoint, gusts, cloud layers |
| Open-Meteo flood | `flood-api.open-meteo.com/v1/flood` | GloFAS discharge |
| Open-Meteo air | `air-quality-api.open-meteo.com/v1/air-quality` | CAMS AQI (+ `past_days=7`) |
| Open-Meteo marine | `marine-api.open-meteo.com/v1/marine` | Waves; inland → nearest coast |
| Open-Meteo geocode | `geocoding-api.open-meteo.com/v1/search` | Extra city search (`countryCode=IN`) |
| NASA POWER | `power.larc.nasa.gov/api/temporal/daily/point` | Climatology |
| IMD CAP | `cap-sources.s3.amazonaws.com/in-imd-en/rss.xml` | Official warnings + nowcast timing prior |
| data.gov.in CPCB | resource `3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69` | Realtime NAQI |
| data.gov.in Agmarknet | resource `9ef84268-d588-465a-a308-a864a43d0070` | Mandi prices |
| USGS FDSN | `earthquake.usgs.gov/fdsnws/event/1/query` | 7-day India–Indian Ocean box |
| INCOIS ITEWS | `tsunami.incois.gov.in/itews/DSSProducts/OPR/past90days.json` | Tsunami/quake bulletins (TLS verify disabled for this host) |
| OpenAQ v2 | `api.openaq.org/v2/measurements` | Historical PM2.5 |
| Bhuvan WMS | `bhuvan-vec3.nrsc.gov.in/bhuvan/ows` | `gw_wfs:WB_LGEOM` and other `*_LGEOM` |
| NASA GIBS | `gibs.earthdata.nasa.gov/wms/...` | Himawari IR + IMERG overlays; optional true-color |
| IMD INSAT IR1 JPEG | `mausam.imd.gov.in/Satellite/3Dasiasec_ir1.jpg` | Public Asia-sector IR for storm-map cells (not HEM) |
| Weatherbit lightning | `api.weatherbit.io/v2.0/current/lightning` (+ `/history/lightning`) | Observed flashes, 75 km cap |
| Open-Meteo thunder | same forecast API, `weather_code` + CAPE | Hub thunder nowcast / past 6 h |

Nowcast neighbor fetch reuses Open-Meteo forecast (same 90s cache) for up to 6 nearby gazetteer points.

`get_rain_window` / `daily_window` also hits forecast **and** `archive-api.open-meteo.com/v1/archive` when the span includes past IST days. Horizon ≈ today + 16 days; leftover dates go in `missing` (do not invent).

### Map basemaps (browser tiles)

CARTO Positron, OSM, Esri World Imagery, OpenTopoMap.

### Wired but often not live

| Source | Notes |
|---|---|
| IMD REST `api.imd.gov.in` | 401 without whitelist |
| AIKosh | `missing_key` without `AIKOSH_API_KEY` |
| MOSDAC / NASA Earthdata / EUMETSAT | Settings only. No HEM/IMR HDF. Public INSAT JPEG is a different path (`imd_insat`). |
| Weatherbit | `WEATHERBIT_API_KEY`. 429 after ~1500 calls/day; circuit-break and keep last-good strokes. |

### Local data

`india_districts.py`, `india_towns.py`, `india_capitals.py`, `india_coast.py`, `india_mask.py`, `physiography.py`, `fuzzy.py`, `blocked_places.py`, `rag/knowledge/*.md`.

**Bhuvan pitfall:** `geomorphology.wb_gm50k_0506_new` on vec2 does **not** work. Use `GET /api/map/wms` with `gw_wfs:WB_LGEOM`. Leaflet url = `apiUrl("/map/wms")` (absolute when `PUBLIC_BASE_URL` or request host is set). `/api/map/layers` returns both `url` (absolute) and `path` (`/api/map/wms`).

**Marine pitfall:** Open-Meteo has no grid over many deltas. Snap via `nearest_coast`; never show “Inland — no marine grid”.

---

## 10. Location resolution

Chat and search share the same pipeline (`resolve_named_place` then `resolve_india_place` / `search_places`):

1. **Fuzzy fold** (`data/fuzzy.py`) — `Puruliya`→`Purulia`; reject stems (`Puri`, `Pure`, `Calicut`≠`Calcutta`)
2. **Curated towns** (`india_towns.py`) — Haldia, Cherrapunji, Santiniketan, …
3. **District gazetteer** + aliases (`puruliya`, `calcutta`, `calicut`→Kozhikode)
4. **State / UT capital** (`india_capitals.py`) — bare `Delhi` / `Odisha` / `Goa` is a forecast at the HQ, not every district in the state. Label is never `Delhi, Delhi`.
5. **Open-Meteo India geocode** — any other real Indian town/district (Wardha, Munnar, Tezpur, …)
6. **Refuse** fiction / foreign (`blocked_places.py`: Atlantis, Hogwarts, Paris). No Haldia fallback.

`resolve_location()` with no query still defaults to Haldia. `data(place=…)` uses `resolve_india_place` and returns `unknown_place` instead of the pin.

**Pin isolation (every tab):** a Howrah dashboard / scan / alerts list must not quote Chhattisgarh (or any other state). `districts_in_state("Howrah")` is empty — a town is not a state, and must **not** fall back to all-India. `rank_districts` on an unknown state returns `{ranked: [], error: unknown_state}` and does not fetch. Sachet/CAP rows that name another state are dropped (`services/locality.py`). Hooghly port signal only attaches for Howrah / Haldia / Kolkata / adjacent Hugli districts — not Jaipur or Malda. Nearby map points must stay within a few degrees of the pin.

Dashboard query: `district`, `place`, `lat`, `lon`. Frontend sends `place_name` as `place`.

`place_kind`: `district | city | town | place`. Nowcast `place` is the resolved point, not a district mean.

---

## 11. Tests

Run from `backend/`:

```
python -m pytest -q
```

Notable tests: `test_imd_title`, `test_warnings`, `test_sky`, `test_coast`, `test_blend`, `test_translate_reply`, `test_mt_layer`, `test_location` (Haldia / Cherrapunji / Puruliya≠Puri), `test_risk_xai`, `test_science`, `test_nowcast`, `test_live`, `test_sat_kalman`, `test_sat_phys`, `test_features`, `test_dates`, `test_rain_window`, `test_agent_tools`, `test_intent`, `test_api`, `test_physiography` (Leh orographic, Jaipur no tide), `test_india_mask` (Kolkata in, Lhasa/Dhaka/Kathmandu out), `test_convective`, `test_cv_nowcast`, `test_thunder_predict` (distinct lifetimes + confidence), `test_storm_map` (pytest skips network).

Chat / place: `test_fuzzy`, `test_fuzzy_names`, `test_fuzzy_contradictions`, `test_fictitious_places`, `test_bare_place`, `test_utterance`, `test_place_resolution`, `test_unpopular_places`, `test_human_utterances`, `test_followup_catalog` (`yes` / `all of them` stay on Purulia; chips carry `location`), `test_orchestrator`, `test_facts` (incl. dash-soup), `test_claims`, `test_binder`, `test_llm_eval` + `tests/llm/cases.json` (`How about malda` → forecast). Scripts: `scripts/eval_chat.py`, `scripts/eval_chat_live.py`.

**Per-tab isolation** (`tests/tabs/`): each dashboard tab has a module plus a contradiction sibling. Howrah must not leak Raipur / Chhattisgarh; Malda must not be Haldia; a joke is not a forecast; `what about Kerala?` is not a capital forecast.

| Module | Tab | Isolation | Contradiction |
|---|---|---|---|
| `test_tab_overview.py` | Overview | Howrah pin is WB | Raipur is Chhattisgarh |
| `test_tab_alerts.py` | Alerts | CG Sachet dropped for Howrah | Raipur keeps CG; port only on Hooghly belt |
| `test_tab_forecast.py` | Forecast / scan | WB rank is only WB | `rank("Howrah")` is empty, not India |
| `test_tab_risks.py` | Risks | Howrah labels name no far state | Raipur cards don’t say Howrah |
| `test_tab_nowcast.py` | Nowcast | Howrah ≠ Raipur coords | Malda ≠ Haldia |
| `test_tab_predicted.py` | Predicted | Outlook from that pin | Wet vs dry series don’t copy |
| `test_tab_market.py` | Market | Howrah key is WB | Raipur key is not Howrah |
| `test_tab_map.py` | Map | Nearby has no Raipur/CG | Search Raipur is CG |
| `test_tab_advisor.py` | Advisor | `How about malda` fetches Malda numbers | Joke stays chat; Kerala follow-up stays rank |

When changing `extract`, `all_risks`, `compose_indic`, CAP titles, nowcast millimetre rules, date parsing, CORS, place fold, `interpret`, or `locality` — update these tests. Each pass should keep a contradiction sibling (Puruliya≠Puri, Howrah≠Hogwarts, Howrah≠Chhattisgarh, catalog≠single AQI). If a test fails, add the inverse case before “fixing” only the happy path.

---

## 12. Config / env

`backend/app/config.py` + `backend/.env`:

| Variable | Purpose |
|---|---|
| `OLLAMA_BASE_URL` | default `http://127.0.0.1:11434/v1` |
| `OLLAMA_MODEL` | `qwen2.5` |
| `TRANSLATE_ENABLED` | default true; Google gtx + MyMemory, no key |
| `DATA_GOV_IN_API_KEY` | CPCB + Agmarknet |
| `WEATHERBIT_API_KEY` | Current / historical lightning |
| `LIGHTNING_FEED_URL` / `LIGHTNING_FEED_KEY` | Optional bbox lightning (`{south}{west}{north}{east}{key}`) |
| `NASA_EARTHDATA_USER` / `PASS` | GIBS / future IMERG; not required for Himawari WMS tiles |
| `EUMETSAT_TOKEN` | Optional; not on the default storm-map path |
| `IMD_API_KEY` | unused until REST whitelist |
| `AIKOSH_API_KEY` | AIKosh search |
| `DEFAULT_LAT/LON/STATE/DISTRICT/PLACE` | Haldia / Purba Medinipur defaults |
| `PUBLIC_BASE_URL` | Absolute origin in WMS / published links; empty = request host |
| `CORS_ORIGINS` | Comma list, or `*` (disables credentials) |
| `CORS_ORIGIN_REGEX` | LAN / Expo / Metro origins |

Frontend `frontend/.env.local`:

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_BASE` | API origin, default `http://127.0.0.1:8000`. Empty = same-origin `/api` + rewrite. |

---

## 13. Common bugs already fixed (do not reintroduce)

| Symptom | Cause / fix |
|---|---|
| IMD 401 | Use CAP, not REST |
| Advisor only templates | Empty Ollama choices; retry no-tools; keep LLM text |
| Haldia AQI cited Siliguri | `extract_place` + city-match CPCB + `is_local_station` |
| Bengali `জেলা — / ভিত্তি —` | Phrase splicing; use online MT + `compose_indic` fallback, never splice |
| Number-lock deleted good LLM text | Lock is advisory only (`lock_and_note`) |
| “Inland — no marine grid” | Coast snap + honest nearest-coast label |
| Garbled IMD title | `humanize_cap_title` |
| Bhuvan overlay blank | Wrong layer/host; proxy vec3 `WB_LGEOM`; use `apiUrl("/map/wms")` |
| Advisor shows `**` `#` | Render with `Markdown.tsx` |
| UI language ≠ reply language | `setLocale` also sets `outputLocale` |
| Pytest `No module named app` | Run from `backend/` |
| Latin tokens `XLT…` in Hindi | Number lock uses `⟦N⟧`, not XLT placeholders |
| Speech / CAP invents rain mm | Fuse and CAP change category/weights only |
| Pump “hold” on 0.3 mm drizzle | Hold only if P≥0.45 **and** rain90 ≥ 0.8 mm |
| Nowcast advection always `no-mesh` | Snapshot must `await fetch_neighbors` into `pre["neighbors"]` |
| `/api/nowcast/live` 404 | Route lives on FastAPI. Frontend tries aliases + `app/api/nowcast/live/route.ts` + client gap. Restart uvicorn after adding the route. |
| Gap minutes invent extra rain | Each hour’s 1-min bins must **renormalize** to that hour’s locked mm |
| Next rewrite required for every client | Default is CORS + `NEXT_PUBLIC_API_BASE`; do not force rewrite |
| Serving the dashboard from uvicorn | Backend is JSON-only; keep `frontend/` separate |
| “Today’s rainfall” ~80 mm in Haldia | `past_days=1` put yesterday first; slice daily from IST today (`_start_today`) |
| Kalman graph blank / laggy | Do not give Recharts a second `Scatter` `data=` array; do not run 90 pulses × 360 points every second in the browser; plot server `pred_series` |
| “Haldia rain” used district centroid | `mentioned_place` must prefer `extract_town` |
| Advisor invents 23–28 Aug mm | Prefetch `data(need=rain_window)` + `quote_facts`; never free-form those days |
| `Puruliya` → “couldn’t find” / Puri | Fuzzy fold + joint town/district score; no `needle.startswith("puri")` |
| Bare `Delhi` → `[temp_c]` / `Delhi, Delhi` | State/UT → capital forecast; `fill_slots`; `compose_label` |
| `all of them` → gazetteer refuse | Follow-up / catalog, not a place; inherit last asked town |
| Map chip stays on Haldia | Suggestion includes `location`+`center`; `applySuggestion` calls `setLocation` + `mapFocus` |
| Elephant then “Still tell me” fetches AQI | Sticky `last_refuse`; do not prefetch weather |
| `How about malda` → `August —` / `—%` / `— mm` | Treat as place retarget + prefetch `forecast`; quote `outlook_days`; replace dash-soup with `quote_facts` |
| Howrah bulletin names Chhattisgarh | `locality.alert_belongs`; `districts_in_state` must not fall back to all-India; no Hooghly port on inland/far pins |

---

## 14. How to add things (recipes)

**New live field on Overview**  
1. Fetch in `gather_observations`  
2. `features.extract`  
3. `CurrentConditions` / `LiveWatch` / series  
4. `frontend/src/types/dashboard.ts`  
5. `OverviewLive` or `EarlyWarnings`  
6. `copy.ts` all three locales  

**New Advisor fact pack**  
Add a `need` on `data_tool.NEEDS` + `DataLib.call` + `quote_facts` / `suggestions_for`. Wire `utterance.interpret` (or `CATALOG_NEEDS`). Do not add a second LLM tool. Named dates still use `rain_window`. Nowcast quotes **locked** fields only.

**New date-range rain question**  
Extend `agents/dates.py`; keep `get_rain_window` + `services/rain_window.py`; add a test in `test_dates.py`. Do not extend snapshot `forecast_days` unless the dashboard table also needs that horizon.

**New nowcast predictand**  
Add a function in `science/nowcast.py`, attach it in `build()`, put the number on `locked()`. Never let speech or the LLM write the number. Add a unit test in `test_nowcast.py`.

**New Indic sentence**  
Add to `templates.py` **and** `compose_indic` — do not regex-replace English.

**New town**  
Append `india_towns.py` (name, state, district, lat, lon, kind, aliases). Unlisted real Indian places still resolve via Open-Meteo India geocode — do not add one-off ifs.

**New tab / bulletin field**  
Add a `tests/tabs/test_tab_*.py` isolation case **and** a contradiction (far state / other pin). Filter through `locality.py` if the field can name another state.

**New mobile / web client**  
Use `clients/js`. Do not fork `frontend/` unless you need that exact Next dashboard.

---

## 15. Ports and processes

| Port | Process |
|---|---|
| 3000 | Next.js (optional client) |
| 8000 | uvicorn `app.main:app` (the API) |
| 11434 | Ollama |
| 8081 / 19006 | Expo / RN defaults (CORS already allows these) |

Only one listener on 8000. After a restart, `/api/health` should be 200 and `/` should return JSON (`service: rituchakra-api`).

---

## 16. Suggested first reads in a new session

1. This file
2. `backend/app/services/snapshot.py`
3. `backend/app/science/nowcast.py` + `science/live.py` + `science/sat_kalman.py` + `science/sat_phys.py`
4. `backend/app/science/storm_map.py` + `thunder_predict.py` + `cv_nowcast.py` + `data/india_mask.py`
5. `backend/app/science/__init__.py`
6. `backend/app/agents/orchestrator.py` + `agents/dates.py` + `services/rain_window.py`
7. Repo `main.py` launcher + `backend/app/main.py` (standalone API + CORS)
8. `frontend/src/components/SquareMap.tsx` + `MapView.tsx` + `StormFeed.tsx`
9. `frontend/src/components/NowcastLive.tsx` + `NowcastSat.tsx` + `frontend/src/lib/config.ts`
10. `clients/js/src/index.ts`

Then grep for the feature name (`compose_indic`, `humanize_cap_title`, `WB_LGEOM`, `get_nowcast`, `get_rain_window`, `in_india`, `storm-map`, `apiUrl`, `quietRefresh`, …).
