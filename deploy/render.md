# Render (public API, native Python)

Hugging Face **Docker** Spaces are paid. This host is a **Free** Render web service: GitHub connected, no Docker image, no Fly card.

URL after the first deploy: `https://rituchakra-api.onrender.com` (Render may add a suffix).

## One-time

1. Sign up at [render.com](https://render.com) with GitHub (free web service; no card for the Free instance).
2. **New → Blueprint** and select `NetRunnerXD/Prithvi AI` (`render.yaml`), **or** **New → Web Service**:
   - Repo: `Prithvi AI`, branch `main`
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

## Satellite Ingestion on Single Free Instance (Cron Trigger)

To run the satellite cruncher without a 2nd instance or credit card:
1. The single `rituchakra-api` service exposes a cron trigger endpoint:
   `POST` / `GET` `https://<your-service>.onrender.com/api/ingest/trigger`
2. Configure **[cron-job.org](https://cron-job.org)** or **[UptimeRobot](https://uptimerobot.com)** (Free):
   - **URL**: `https://<your-service>.onrender.com/api/ingest/trigger` (or `/api/ready` to wake)
   - **Schedule**: Every 10 to 15 minutes
   - **Effect**:
     - Wakes up the Render free instance so it never goes into deep sleep.
     - Fetches the latest INSAT-3DS IR1 JPEG from IMD.
     - Runs convective cloud segmentation, nowcasting, and hazard models.
     - Upserts verified strokes and hazard incidents straight into MongoDB Atlas!

### Optional Security
Set `INGEST_CRON_SECRET=<your-secret>` in Render Environment Variables. When set, pass `?secret=<your-secret>` in the cron trigger URL.

## Clients

```
NEXT_PUBLIC_API_BASE=https://<your-service>.onrender.com
EXPO_PUBLIC_API_BASE=https://<your-service>.onrender.com
```

Local `uvicorn` on the laptop is unchanged.
