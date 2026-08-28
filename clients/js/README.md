# @rituchakra/client

Framework-free TypeScript client for the Rituchakra HTTP API. No React, Next.js, or DOM.

Use this folder when you start a **new web app** or a **React Native / Expo** app. Do not import `frontend/` — that package is one Next.js dashboard, not the API.

## Point at a running API

```ts
import { createClient } from "./src";

const api = createClient({
  baseUrl: process.env.RITUCHAKRA_API || "http://127.0.0.1:8000",
});

const health = await api.health();
const dash = await api.dashboard({ district: "Nadia", lat: 23.471, lon: 88.5565 });
const places = await api.searchPlaces("Haldia");
const storms = await api.stormMap("India");
await api.streamChat({ message: "Should I irrigate?", locale_hint: "en" }, (ev) => {
  console.log(ev.type);
});
```

On a phone, `baseUrl` must be the machine that runs FastAPI (for example `http://192.168.1.20:8000`), and that process must allow your origin via `CORS_ORIGINS` / `CORS_ORIGIN_REGEX`.

## New app folders (suggested)

```text
mobile/          Expo app in this repo (imports this package via Metro)
web/             Vite / Remix / etc. — same client
frontend/        existing Next.js dashboard (already talks to the API)
backend/         FastAPI — run this first
```

The backend publishes `/docs` and `/openapi.json`. It does not ship web assets.
