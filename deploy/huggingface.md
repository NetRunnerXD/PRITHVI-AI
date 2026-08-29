# Hugging Face Space (public API)

Free Docker Space. No credit card. GitHub Action on `master` / `main` uploads `backend/` when `HF_TOKEN` is set.

Public URL after first build:

`https://netrunnerxd-rituchakra-api.hf.space`

(Exact slug: `https://<user>-<space>.hf.space`.)

## One-time

1. Hugging Face account → [token](https://huggingface.co/settings/tokens) with **write**.
2. GitHub repo **Settings → Secrets and variables → Actions**:
   - `HF_TOKEN` — that token
   - optional `HF_SPACE` — default `NetRunnerXD/rituchakra-api`
3. Create the Space on first Action run (`create_repo` exist_ok).
4. Space **Settings → Variables and secrets** (Advisor + CORS):

```
PUBLIC_BASE_URL=https://netrunnerxd-rituchakra-api.hf.space
CORS_ORIGINS=*
OLLAMA_BASE_URL=https://api.groq.com/openai/v1
OLLAMA_API_KEY=<groq key, no credit card>
OLLAMA_MODEL=llama-3.1-8b-instant
```

Groq is optional. Snapshot, nowcast, geo, and market routes do not need it.

## Clients

```
NEXT_PUBLIC_API_BASE=https://netrunnerxd-rituchakra-api.hf.space
EXPO_PUBLIC_API_BASE=https://netrunnerxd-rituchakra-api.hf.space
```

Local `uvicorn` is unchanged (`http://127.0.0.1:8000`, Ollama on the laptop).

## Limits

CPU Space sleeps after long idle; first request can take a minute. One replica. Not Fly-style multi-region. Optional paid path: [`fly.md`](fly.md).
