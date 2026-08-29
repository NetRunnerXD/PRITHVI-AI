# Hugging Face Space (retired for this repo)

Docker Spaces return **402 Payment Required** on create. Use **Render** instead: [`render.md`](render.md).

The notes below are only if you already have a paid Docker Space.

Free Docker Space. No credit card. GitHub Action on `master` / `main` uploads `backend/` when `HF_TOKEN` is set.

Public URL after first build:

`https://netrunnerxd-rituchakra-api.hf.space`

(Exact slug: `https://<user>-<space>.hf.space`.)

## One-time

1. Hugging Face account → [token](https://huggingface.co/settings/tokens): **classic write**, or fine-grained with **Repositories write** and **Spaces write**. The value starts with `hf_`.
2. GitHub repo **Settings → Secrets and variables → Actions → Repository secrets** (not an Environment, not Hugging Face Space secrets):
   - `HF_TOKEN` — that token
   - optional `HF_SPACE` — `your-hf-username/rituchakra-api` (defaults to whoever `whoami` returns)
3. Actions → **Deploy API (Hugging Face Space)** → Run workflow. The job prints `huggingface user=...` and the Space URL.
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
