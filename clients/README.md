# Clients

The **backend is the product**. This folder is for any UI that is not `frontend/`.

| Path | Role |
| --- | --- |
| `js/` | TypeScript HTTP + SSE client. Browser, Node, React Native. |
| `../frontend/` | Existing Next.js dashboard (reference web client). |
| `../backend/` | Standalone FastAPI. No UI files. |

To migrate to another web stack or React Native:

1. Run `backend/` on a host the new app can reach.
2. Copy or depend on `clients/js`.
3. Set the API origin (`http://127.0.0.1:8000` locally, or a published URL).
4. Do not rewrite `/api` through a web framework unless you want to. CORS is enabled on the API.

Swagger: `http://127.0.0.1:8000/docs`
