# Agent handoff — THIS SESSION ONLY

**Date:** 2026-09-13  
**Repo:** Prithvi AI (`D:\Project\Random\RainFall`), branch `main` → `origin/main`  
**Remote:** `https://github.com/NetRunnerXD/Prithvi AI.git`

This file is the handoff for **convective nowcast accuracy, INSAT, fog/heat/UV, map events, FIRMS fire, landslide, alert Live/Archive**. Ignore older i18n/chat/SMS notes. The working tree also has **unrelated uncommitted files** (agents, i18n, pin SMS, risk_mesh, etc.) — do not mix those into this task unless the user asks.

**Product rules:** `project.md`. Locked Open-Meteo millimetres are never rewritten. Public INSAT JPEG is not MOSDAC HEM. Weatherbit = observed flashes, not Damini. Open-Meteo thunder = model analysis, not GPS. Official CAP still suppresses model duplicates.

**Do not commit:** `backend/.env`, `frontend/.env.local`, `backend/test_5_niche.py`.

**Do not restart** uvicorn/Next the user just killed unless they ask for new verification.

**Reverted (2026-09-13):** later architecture after this build is **out**. Removed Mongo nowcast ledger, ingest role / second Render host, keep-warm, `POST /internal/ingest`, hazard_ledger, risk_mesh, pin SMS, Sarvam/SMS-auto extras, mobile/client ingest docs. Storm-map **always fetches INSAT JPEG** again (no skip-on-ledger). Predicted strike floor is **0.12** including cloud. Working tree should only show this science/map/alerts delta plus `continue.md` / map screenshots / `test_5_niche.py`.

---

## Status: implementation done, uncommitted

User flow in this session:

1. Predictions often disagreed with trusted live/forecast; add fog, high-risk UV, heatwave with **expected start–end**; use INSAT if unused.
2. Map-tab event representation; forest fire + landslide; Alerts = active/future only, past → Archive.
3. Follow-up: predicted storm/lightning **accurate but too few**; past lightning empty; no landslide / downburst / cold cloud on the map.

All three are implemented. Last live quote (All-India storm-map): `past_lightning: 2`, `predicted: ~193`, `cloud: 3`, `landslide: 27`, `fire: ~57`, `downburst: 0` (needs two IR frames).

Nothing from this session is committed. User has **not** asked to commit.

---

## Split of the dirty tree

### In scope for this handoff (science / map / alerts)

| Path | Why |
|---|---|
| `backend/app/providers/imd_insat.py` | Fail-cache 45 s |
| `backend/app/science/sat_live.py` | Timeout 6 s (was 1.2 s); cache success 180 / fail 45 |
| `backend/app/science/sat_cv.py` | 235 K cores + 248 K anvil; HE-lite; ForTraCC overlap |
| `backend/app/science/cv_nowcast.py` | Schultz, LightningCast-lite, kinds including `cloud` / downburst |
| `backend/app/science/thunder_predict.py` | `agreement_gate`; predicted floor ~0.12; first-lead rescue |
| `backend/app/science/storm_map.py` | Map keeps unverified predicted; OM past thunder; landslides pack |
| `backend/app/science/convective.py` | Shared convective helpers |
| `backend/app/science/env_hazards.py` **new** | Fog, IMD heatwave, WHO UV |
| `backend/app/science/landslide.py` **new** | Pin warning vs map orographic watch |
| `backend/app/providers/firms.py` **new** | VIIRS South-Asia 24 h clusters |
| `backend/app/providers/om_thunder.py` | Past model thunder for map |
| `backend/app/services/alerts.py` | Windows; env hazards; gate still on alert rail |
| `backend/app/services/snapshot.py` | `firms_fires`; skip under pytest |
| `backend/app/schemas/dashboard.py` | `window_start` / `window_end` |
| `frontend/src/components/MapView.tsx` | Glyphs, landslides like fires, OM popup |
| `frontend/src/components/SquareMap.tsx` | Default highlights include past ⚡, cloud, downburst, fire, landslide |
| `frontend/src/components/StormFeed.tsx` | Extra kinds + slides |
| `frontend/src/components/OverviewLive.tsx` | `alertTimePhase` Live vs Archive |
| `frontend/src/components/EarlyWarnings.tsx` | Expected window copy |
| Tests: `test_cv_nowcast.py`, `test_thunder_predict.py`, `test_convective.py`, `test_alert_model.py`, `test_env_hazards.py`, `test_firms_landslide.py` | |

### Out of scope (same dirty tree — leave alone)

Agents (`facts.py`, `orchestrator.py`, …), i18n/mt, ChatDock, speech, pin SMS (`sms_pin.py`, `pin_sms.py`), `hazard_ledger.py`, `risk_mesh.py`, `store/`, `india_*_simplified.json`, map PNGs, deleted root `package-lock.json`, `backend/test_5_niche.py`.

If asked to commit **this** work, split PRs/commits:

1. INSAT timeout + convective + env alerts + windows  
2. FIRMS / landslide / map glyphs / Archive  
3. Past-lightning + predicted coverage restore (gate stays on alerts)

---

## Design that must not regress

| Surface | Rule |
|---|---|
| **Alerts** | Lightning needs `agreement_gate`. IR-only → **no** `assemble_warnings` row. Test: `test_ir_only_lightning_does_not_alert`. |
| **Map** | Unverified predicted lightning **stays**. `confidence_band: low` + honest note. Do **not** set phase to unverified-and-drop. |
| **Past lightning** | Open-Meteo past thunder: `engine: open-meteo-thunder`, popup **“Model thunder (not GPS)”**. Expired IR lightning cells kept as past. Do not skip `past_cells` for expired IR lightning. Default highlight **on**. |
| **Cold cloud** | 248 K anvil halo `layer: anvil` → kind `cloud`. Predicted strikes include cloud; p0 floor **0.12** so 15 min lead is not dropped. |
| **Downburst** | Collapsing **or** warming top (`d_tb_k ≥ 2`), even if `p_lightning` is low. Needs **two** IR frames. Do not call disk `track()` when cells already have `trend` (pollutes tests via `ir_frames.json`). |
| **Landslide** | Pin **warning** only if orographic + heavy 3-day rain. Map list: orographic/hill cells with `rain_ir ≥ 8` **or** `p_cloudburst ≥ 0.28`. Not GSI. Keep parens in hill expression. |
| **FIRMS** | Thermal hotspot, not burned area. Skip isolated FRP &lt; 8 MW. India-scope if n≥8 or FRP≥40; else ≤40 km from pin. |
| **INSAT** | `sat_live` timeout **≥ 6 s**, not 1.2 s. Fail cache **45 s**, not 900 s. JPEG ≠ HEM/gauges. MOSDAC still needs creds (not wired this session). |
| **Heat / fog / UV** | IMD plains 40 / coast 37 / hills 30 +4.5 °C / 2 days, or Tmax ≥45/47; WBGT; WHO UVI ≥8/11. Windows typically 09:00–18:00 IST for heat. |
| **CAP** | Official IMD/Sachet still suppress same kind+state model duplicates. |
| **mm** | Never rewrite locked Open-Meteo hourly millimetres. |

---

## Known leftover issues (not fixed)

- Leaflet duplicate key `c18` on map (noted, not fully fixed).
- Browser Open-Meteo **429** after debug traffic is expected. Backend snapshot can still serve. `OM_SERVER_REFRESH=false` on Render.
- `downburst` count **0** on first IR frame is expected.
- Past lightning ~0 if Weatherbit 429 **and** no OM hub with `lead_h < 0` thunder **and** no expired IR lightning yet.
- `test_om_thunder.py` does not exist.
- pytest `vera_hourly` had 3 failures in a shared verify log — treated as **pre-existing**, not this session.
- Damini/ILLN: no public JSON. MOSDAC L1B/HEM: not started.

---

## Tests last green

```
cd backend
python -m pytest tests/test_cv_nowcast.py tests/test_thunder_predict.py tests/test_convective.py tests/test_alert_model.py tests/test_env_hazards.py tests/test_firms_landslide.py -q
```

Convective/map set: **32 passed**. FIRMS/landslide/IR-only extras also passed.

If `test_enhance_tags_downburst_and_cloud` fails: trend was overwritten by disk `track()`. If `test_predicted_strikes_include_weaker_cloud` is empty: floor/lead rescue dropped below 0.16.

---

## How to run (only if user wants verification)

```
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

cd frontend
npm run dev
```

`frontend/.env.local`: `NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000`  
First start from **repo root fails** (no `app`, no frontend `package.json`). Use `backend/` and `frontend/`.

Sanity: `GET http://127.0.0.1:8000/api/nowcast/storm-map?state=India` — inspect `counts` (`past_lightning`, `predicted`, `cloud`, `landslide`, `fire`, `downburst`). `counts.downburst` must be a **single** key (duplicate key was removed).

Manual Map/Alerts check if asked: All India, Past lightning on, predicted volume high but popups distinguish confirmed vs IR-only, FIRMS clusters, landslide in Ghats/Himalaya, Highlights Cold cloud / Downburst, Alerts Live vs Archive.

---

## Suggested next (this scope only — wait for user)

1. Commit in-scope files when asked (split as above). Do not include out-of-scope dirty files.
2. Manual Map + Alerts pass.
3. Optional later (not started): MOSDAC L1B/HEM if `MOSDAC_USER`/`MOSDAC_PASS`; Damini if a feed URL appears; reliability diagram from `.cache/lightning_verify.jsonl`; Leaflet `c18` key.

Do **not** start those extras unprompted.
