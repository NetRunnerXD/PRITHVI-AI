# Vercel (public dashboard, GitHub auto-deploy)

Hobby (free) Next.js host. The API stays on Render (`deploy/render.md`). Pushes to the connected branch that change `frontend/` rebuild the site.

`NEXT_PUBLIC_API_BASE` is baked in at **build** time. If it is missing, the client defaults to `http://127.0.0.1:8000` and the live UI will fail.

## One-time

1. Sign up at [vercel.com](https://vercel.com) with GitHub.
2. **Add New → Project** → import `NetRunnerXD/Rituchakra` (or this fork).
3. **Root Directory:** `frontend` (Edit → `frontend`).
4. Framework: **Next.js** (detected). Install `npm ci`, build `npm run build`.
5. Environment Variables — **Production** and **Preview**:
   - `NEXT_PUBLIC_API_BASE` = `https://<your-render-api>.onrender.com` (no trailing slash)
6. Deploy. URL: `https://<project>.vercel.app`.
7. Optional: Project Settings → Git → Production Branch `main`. PRs get preview URLs.

CORS on the API Blueprint is `*`. After you have the Vercel URL, you can set Render `CORS_ORIGINS` to that origin plus localhost.

## After the first deploy

Redeploy if you added `NEXT_PUBLIC_API_BASE` after the first build (Settings → Environment Variables → Redeploy).

Advisor and snapshot calls hit Render; a sleeping Free API can take up to a minute on the first request.
