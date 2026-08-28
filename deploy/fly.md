# Fly.io + GitHub Actions

The public API (`https://rituchakra-api.fly.dev` after first deploy) is the origin for:

- Next.js: `NEXT_PUBLIC_API_BASE=https://rituchakra-api.fly.dev`
- Expo/Android: `EXPO_PUBLIC_API_BASE=https://rituchakra-api.fly.dev`

Later pushes to `main` that touch `backend/` run `.github/workflows/deploy-api.yml`.

## One-time Fly setup

```powershell
winget install Flyctl
fly auth login
fly apps create rituchakra-api --org personal
# optional persistent last-good cache:
# fly volumes create rituchakra_cache --region bom --size 1 --app rituchakra-api
fly secrets set PUBLIC_BASE_URL=https://rituchakra-api.fly.dev --app rituchakra-api
# CORS: local web + Expo + production web when you have it
fly secrets set CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:8081,http://localhost:19006 --app rituchakra-api
fly tokens create deploy -x 999999h --app rituchakra-api
```

Paste the token into GitHub → repo **Settings → Secrets and variables → Actions →** `FLY_API_TOKEN`.

First deploy (local or wait for the Action):

```powershell
cd backend
fly deploy --remote-only
curl https://rituchakra-api.fly.dev/api/ready
curl https://rituchakra-api.fly.dev/api/bootstrap
```

Ollama is not on this VM. Advisor uses templates until you point `OLLAMA_BASE_URL` at a GPU box.

## After the URL exists

Rebuild the website with `NEXT_PUBLIC_API_BASE` set. Restart Expo with `EXPO_PUBLIC_API_BASE` set. Android requires HTTPS (this URL is).
