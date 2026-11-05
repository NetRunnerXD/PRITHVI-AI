# Prithvi AI API

Standalone FastAPI service. **No frontend assets.** Publish this process and any web or React Native app can call it.

## Run

```powershell
cd backend
python -m pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- Service card: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- Health: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)
- Speech status: [http://127.0.0.1:8000/api/speech/status](http://127.0.0.1:8000/api/speech/status) (Indic STT/TTS sidecars; see `../deploy/voice.md`)
- Swagger: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- OpenAPI: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)
- Route catalog: [http://127.0.0.1:8000/api](http://127.0.0.1:8000/api)

Surfaces (same handlers; local `/api` is unchanged):

| Prefix | For |
|---|---|
| `/api` | Local dashboard, pytest, `clients/js` |
| `/v1` | Published versioned API |
| `/web/v1` | Website / other web frameworks |
| `/app/v1` | Expo / React Native |

Web origin (`localhost:3000`) and Expo (`localhost:8081`) may call this process at the same time. CORS lists both. Optional `X-Prithvi AI-Client: web|app`.

Bind `0.0.0.0` if a phone or another machine will call the API. Set `CORS_ORIGINS` / `CORS_ORIGIN_REGEX` and, when publishing, `PUBLIC_BASE_URL`.

Local clients (no frontend rebuild needed):

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# GET  http://127.0.0.1:8000/api/health
# GET  http://127.0.0.1:8000/api/bootstrap
# GET  http://127.0.0.1:8000/api/alerts
# GET  http://127.0.0.1:8000/api/market
# POST http://127.0.0.1:8000/api/chat   JSON body {"message":"...","stream":false}
```

Android / Expo: `EXPO_PUBLIC_API_BASE=http://<LAN-IP>:8000`. Prefer `stream: false` on chat if SSE is unavailable.

## PRITHVI-Nowcast v7 (local, optional)

R2 network + frozen PN-Blend as one ONNX file (6.7 MB, git-ignored) in `backend/models/pn_nowcast_v7.onnx`.
Test CSI (0.5°, rain ≥ 1 mm/h): 0.643 / 0.466 / 0.393 / 0.364 at 1 / 3 / 6 / 12 h.

```
pip install -r requirements-pn.txt
PN_ENABLED=1  PN_VERSION=v7  [PN_V7_MODEL_PATH=models/pn_nowcast_v7.onnx]  NASA_EARTHDATA_API=<token>
```

* Inputs: IMERG Early (6 h), GFS (NOMADS subset, run ≤ T−6 h), IFS open data (run ≤ T−8 h). INSAT is masked.
* `GET /api/research/pn-live?wait=true` — live pack (groups live/masked, NWP runs, leads, validation).
* `GET /api/research/pn-track?days=30` — live track record from `pn_runs` (Mongo or `.cache/pn_runs.json`).
* Fallbacks: IMERG gap/stale → persistence; `PN_VERSION=v4` → old PN-Net.
* Memory: one v7 run needs ~0.4 GB extra RAM at peak — too much for a 512 MB instance.
* Re-export: `python tools/pn_export_onnx_v7.py --weights best.pt --static static.npy --frozen frozen_v7.json --out models/pn_nowcast_v7.onnx`

### PN-Correct v6 (optional, `PN_CORRECT_ENABLED=1`, needs `PN_VERSION=v7`)

Separate "rain ≥ 1 mm/h within 25 km" layer at 6 / 9 / 12 h on the 0.25° GFS grid (`backend/models/pn_correct_v6.onnx`, 7.8 MB, git-ignored).
It never replaces the v7 field (hand-over weight fixed at 1.0). Cut-offs 0.30 / 0.28 / 0.26; test CSI (0.25°) 0.385 / 0.373 / 0.367.

* Inputs: primary GFS run ≤ T−6 h (f000 env + 6-h APCP), IFS 00/12 run ≤ T−8 h (tp 12–36 h, step-24 env + u/v200), IMERG T−1..T−3 on 331×351. INSAT masked (sat_ok = 0).
* Output: `pn_correct` in `/api/research/pn-live`; Science panel tile "Rain within 25 km" at the selected place.
* Cost: ~0.12 s per run (features + ONNX), +~11 MB peak RSS on top of v7.
* PN-Judge is not wired (failed its pre-registered test).

## Tests

```powershell
cd backend
python -m pytest -q
```

## Export OpenAPI

```powershell
cd backend
python scripts/export_openapi.py
```

Writes `openapi.json` next to this file.

## Clients

Do not serve `../frontend` from this process. Point a new app at this origin using `../clients/js`. Implementation guide: [`../docs/api.md`](../docs/api.md).

## Public host

GitHub deploys this folder to a **Render Free Python** web service (not Docker). See `../deploy/render.md`. Local `uvicorn` is unchanged. On Render, set `OLLAMA_BASE_URL` to Groq or GitHub Models if Advisor prose is needed.
