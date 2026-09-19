# CODEMAP — where to change what (Prithvi AI)

Agents: read this first, then `docs/codegraph.json`. Product rules: `project.md` §2. Refresh the graph with `python backend/scripts/codebase_graph.py`.

## Entrypoints

| Surface | Path |
|---|---|
| API process | `backend/app/main.py` — FastAPI, snapshot loop, SMS loop |
| HTTP routes | `backend/app/api/` (`dashboard.py`, `chat.py`, `geo.py`, `meta.py`, `speech.py`) |
| Auth / pin SMS | `backend/app/auth/` |
| Dashboard UI | `frontend/src/app/page.tsx` + `frontend/src/components/` |
| Client SDK | `clients/js/src/index.ts` |
| Expo app | `mobile/App.tsx` |

## Where to change X

| Want to change | Start here | Also touch |
|---|---|---|
| Dashboard JSON for a pin | `backend/app/services/snapshot.py` | `snapshot_obs.py`, `snapshot_assemble.py`, `snapshot_live.py`, `schemas/dashboard.py` |
| Official / model alerts | `backend/app/services/alerts.py` | `science/env_hazards.py`, `science/thunder_predict.py` |
| Storm map cells / lightning / fire | `backend/app/science/storm_map.py` | `providers/imd_insat.py`, `providers/firms.py`, `science/cv_nowcast.py` |
| Open-Meteo millimetres | `backend/app/providers/open_meteo.py` | never rewrite in LLM/agents |
| Advisor chat / SSE | `backend/app/agents/orchestrator.py` | `agents/data_tool.py`, `agents/facts.py`, `api/chat.py` |
| Tool `data()` packs | `backend/app/tools/__init__.py` | `agents/data_tool.py` |
| Place search (India-only) | `backend/app/services/location_svc.py` | `data/india_towns.py`, `data/india_districts.py` |
| Home tab UI | `frontend/src/components/OverviewLive.tsx` (barrel) → `components/overview/` |
| Map tab glyphs | `frontend/src/components/MapView.tsx`, `SquareMap.tsx` |
| Models / VERA tab | `frontend/src/components/PredictionsPanel.tsx` | `backend/app/ml/vera/` |
| Copy / locale strings | `frontend/src/i18n/copy.ts` | `backend/app/i18n/` |
| Zustand client state | `frontend/src/lib/store.ts` | `lib/api.ts` |

## Layers (backend)

```
api / agents  →  services  →  science / ml  →  providers  →  HTTP
                     ↓
                 schemas, cache, config
```

LLM narrates only. Numbers come from providers / ML / tools.

## Hard constraints (do not violate)

See `project.md` §2. Short list: India-only search; no invented mm/AQI/₹; no IMD REST; Indic MT must not splice English; daily “today” is IST; backend serves no frontend assets.

## Graph files

- `docs/codegraph.json` — nodes (path, lines, exports) + import edges
- `docs/codegraph.md` — largest files + collapsed package mermaid
