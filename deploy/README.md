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
- Optional Indic STT/TTS: [`deploy/voice.md`](voice.md) (`docker compose --profile voice`)

Use **one uvicorn worker**. The SWR cache is in-process.

Home Ollama: set `LLM_WORKER_TOKEN` on the API, run `python backend/scripts/ollama_worker.py --api https://your-api` on the PC that has Ollama. See the README “Home Ollama” section.

## Public HTTPS (split hosts)

- **Dashboard:** Vercel Hobby, GitHub-connected — [`deploy/vercel.md`](vercel.md). Root directory `frontend`. Set `NEXT_PUBLIC_API_BASE` to the Render API origin.
- **API:** Render Free — [`deploy/render.md`](render.md).

Same-origin Caddy (optional, self-host): set `.env` from `.env.production.example`, put Caddy in front (`deploy/Caddyfile`), rebuild web so `NEXT_PUBLIC_API_BASE` is baked in. Leave `NEXT_PUBLIC_API_BASE` empty and set `API_INTERNAL_URL=http://api:8000` for Next rewrites.

Point Expo `EXPO_PUBLIC_API_BASE` at the same API origin.

## Mobile

See `mobile/README.md`. Production phones need HTTPS; Android blocks cleartext HTTP.

## Render (GitHub, native Python, no Docker)

Public HTTPS API: [`deploy/render.md`](render.md). Hugging Face Docker Spaces are paid; this path is a Free Render web service. Pushes that change `backend/` redeploy when the repo is connected and `RENDER_DEPLOY_HOOK` is set.

Optional paid path: [`deploy/fly.md`](fly.md). Hugging Face Docker notes: [`huggingface.md`](huggingface.md).
