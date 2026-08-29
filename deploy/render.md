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
3. GitHub → **Settings → Secrets → Actions**: `RENDER_DEPLOY_HOOK` = the URL from Render → service → **Settings → Deploy Hook**.
4. Optional env on the service (Advisor):
   - `OLLAMA_BASE_URL=https://api.groq.com/openai/v1`
   - `OLLAMA_API_KEY=`
   - `OLLAMA_MODEL=llama-3.1-8b-instant`
   - `PUBLIC_BASE_URL=https://<your-service>.onrender.com`
   - `CORS_ORIGINS=*` is already in the Blueprint

Pushes to `main` / `master` that change `backend/` redeploy. Free instances sleep after ~15 minutes idle; the first request can take up to a minute.

## Clients

```
NEXT_PUBLIC_API_BASE=https://<your-service>.onrender.com
EXPO_PUBLIC_API_BASE=https://<your-service>.onrender.com
```

Local `uvicorn` on the laptop is unchanged.
