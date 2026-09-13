# Render (public API, native Python)

Hugging Face **Docker** Spaces are paid. This host is a **Free** Render web service: GitHub connected, no Docker image, no Fly card.

URL after the first deploy: `https://rituchakra-api.onrender.com` (Render may add a suffix).

## One-time

1. Sign up at [render.com](https://render.com) with GitHub (free web service; no card for the Free instance).
2. **New → Blueprint** and select `NetRunnerXD/Rituchakra` (`render.yaml`), **or** **New → Web Service**:
   - Repo: `Rituchakra`, branch `main`
   - Runtime: **Python** (not Docker)
   - Root directory: `backend`
   - Build: `python -m pip install -r requirements.txt`
   - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1 --timeout-keep-alive 75`
   - Instance: **Free**
   - Health: `/api/ready`
3. Render deploys on every push that changes `backend/` (`autoDeploy: true`). You do **not** need a GitHub secret for that.
4. Optional: copy **Settings → Deploy Hook** to GitHub secret `RENDER_DEPLOY_HOOK` so Actions can poke a deploy. Skip this if you only use Blueprint auto-deploy.
5. Optional env on the service (Advisor):
   - `OLLAMA_BASE_URL=https://api.groq.com/openai/v1`
   - `OLLAMA_API_KEY=`
   - `OLLAMA_MODEL=llama-3.1-8b-instant`
   - `PUBLIC_BASE_URL=https://<your-service>.onrender.com`
   - `CORS_ORIGINS=*` is already in the Blueprint
   - `LLM_WORKER_TOKEN` — same secret you set on the home PC worker (`python scripts/ollama_worker.py`). Restart the service after adding it. Without this (and without a deploy that includes `/api/llm/worker`), the worker gets HTTP 403.

Also set `GROQ_API_KEY` (Advisor when the home Ollama worker is offline) and `LLM_FALLBACK=groq`. Snapshots rebuild every 10 minutes (`SNAPSHOT_TTL_S=600`).

Pushes to `main` / `master` that change `backend/` redeploy. Free instances sleep after ~15 minutes idle; the first request can take up to a minute.

Keep-warm: the web app pings `GET /api/ready` every 10 minutes while a tab is visible. For zero-user hours, point UptimeRobot or cron-job.org at `https://<service>.onrender.com/api/ready` every 10 minutes — **not** `/api/dashboard` (that would spend Open-Meteo quota).

`OM_SERVER_REFRESH` defaults off so Render does not rebuild snapshots from its shared IP. Browsers POST their Open-Meteo JSON to `/api/dashboard`.

A second service `prithvi-ai-ingest` (`APP_ROLE=ingest`) runs the satellite cycle. Both services are on the **Free** plan (no credit card needed).

### Setting up without a Credit Card (Manual Web Service):
If Render asks for a credit card when applying a multi-service Blueprint, create the service manually:
1. Go to **Dashboard → New + → Web Service**.
2. Select repository `NetRunnerXD/Rituchakra` (branch `main`).
3. Settings:
   - **Name**: `prithvi-ai-ingest`
   - **Root Directory**: `backend`
   - **Runtime**: `Python 3`
   - **Build Command**: `python -m pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1 --timeout-keep-alive 75`
   - **Instance Type**: `Free`
   - **Health Check Path**: `/api/ready`
4. Add Environment Variables:
   - `APP_ROLE` = `ingest`
   - `MONGODB_URI` = `<your-mongodb-uri>`
   - `MONGODB_DB` = `rituchakra`
   - `MONGODB_SAT_URI` = `<your-mongodb-sat-uri>`
   - `MONGODB_SAT_DB` = `rituchakra_sat`
   - `OM_SERVER_REFRESH` = `false`
   - `CACHE_DIR` = `/tmp/rituchakra-cache`
   - *(Optional)* `MOSDAC_USER`, `MOSDAC_PASS`, `NASA_EARTHDATA_API`
5. Keep-warm: Ping `https://<prithvi-ai-ingest>.onrender.com/api/ready` every 10 minutes (via UptimeRobot or cron-job.org) so the Free tier does not sleep.

## Clients

```
NEXT_PUBLIC_API_BASE=https://<your-service>.onrender.com
EXPO_PUBLIC_API_BASE=https://<your-service>.onrender.com
```

Local `uvicorn` on the laptop is unchanged.
