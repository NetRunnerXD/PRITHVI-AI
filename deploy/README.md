# Deploy Rituchakra (web + mobile API)

The backend is a JSON API. The Next dashboard and the Expo app are clients.

## Local containers

```powershell
copy backend\.env.example backend\.env
docker compose up --build
```

- API: http://localhost:8000/docs  health: `/api/health`  ready: `/api/ready`
- Web: http://localhost:3000
- Ollama: pulls `qwen2.5` once (`ollama-pull` service)

Use **one uvicorn worker**. The SWR cache is in-process.

## Public HTTPS

1. Set `.env` from `.env.production.example` (`PUBLIC_BASE_URL`, `CORS_ORIGINS`, `NEXT_PUBLIC_API_BASE`).
2. Put Caddy in front (`deploy/Caddyfile`): `/` → Next, `/api` → FastAPI, `flush_interval -1` for Advisor SSE.
3. Rebuild web so `NEXT_PUBLIC_API_BASE` is baked in.
4. Point Expo `EXPO_PUBLIC_API_BASE` at the same API origin.

Same-origin option: leave `NEXT_PUBLIC_API_BASE` empty and set `API_INTERNAL_URL=http://api:8000` on the Next process; Caddy still terminates TLS.

## Mobile

See `mobile/README.md`. Production phones need HTTPS; Android blocks cleartext HTTP.

## Hugging Face Space (GitHub, no credit card)

Public HTTPS API for the website and Android: [`deploy/huggingface.md`](huggingface.md). Pushes to `master` / `main` that change `backend/` run `.github/workflows/deploy-api.yml` when `HF_TOKEN` is set.

Optional paid path: [`deploy/fly.md`](fly.md).
