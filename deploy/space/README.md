---
title: Rituchakra API
emoji: 🌧️
colorFrom: sky
colorTo: green
sdk: docker
app_port: 8000
pinned: false
license: mit
short_description: India-first environmental intelligence JSON API
---

# Rituchakra API

Standalone FastAPI origin. No web assets. The Next.js dashboard and the Expo app call this Space together.

| Path | Client |
|---|---|
| `/api` | Canonical (OpenAPI, local-compatible) |
| `/v1` | Versioned alias |
| `/web/v1` | Web frameworks |
| `/app/v1` | Expo / React Native |

- Health: `/api/health` · ready: `/api/ready` · docs: `/docs`
- Advisor LLM is **not** Ollama on this Space. Set Space secrets:
  - `OLLAMA_BASE_URL` — OpenAI-compatible, e.g. `https://api.groq.com/openai/v1`
  - `OLLAMA_API_KEY`
  - `OLLAMA_MODEL` — e.g. `llama-3.1-8b-instant`
  - `PUBLIC_BASE_URL` — this Space URL (`https://<user>-rituchakra-api.hf.space`)
  - `CORS_ORIGINS` — `*` or the website + Expo origins

Without those secrets the JSON snapshot routes still work; Advisor falls back to templates.
