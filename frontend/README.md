# Rituchakra web client

Next.js dashboard. It is **one** UI for the API in `../backend`. It does not contain the product logic and is not required to publish the API.

For a new web stack or React Native app, start from `../clients` instead of forking this folder.

## Run (API must be up first)

```powershell
cd ../backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# this folder
cd ../frontend
copy .env.example .env.local
npm install
npm run dev
```

`NEXT_PUBLIC_API_BASE` (default `http://127.0.0.1:8000`) is the FastAPI origin. The browser calls that host directly. CORS is configured on the API.

Same-origin proxy (optional): set `NEXT_PUBLIC_API_BASE=` empty so fetches use `/api` and Next rewrites to `:8000`.

## Production (Vercel)

Connect the GitHub repo at [vercel.com](https://vercel.com). Root directory: this folder. Set `NEXT_PUBLIC_API_BASE` to the public FastAPI origin (Render). Details: [`../deploy/vercel.md`](../deploy/vercel.md).
