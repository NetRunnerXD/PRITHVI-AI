# Deploy to Hugging Face Spaces (100% Free Gradio/Python SDK — No Docker, No Credit Card)

On Hugging Face, **Docker Spaces** require payment/credit card, but **Gradio (Python) Spaces** are **100% Free** (2 vCPU, 16 GB RAM) with **no credit card required**.

Because Gradio is built on top of FastAPI, a Gradio Space can run your entire backend API and 24/7 ingestion cruncher directly with native Python!

---

## Step 1: Create a Free Gradio Space on Hugging Face
1. Go to **[huggingface.co/new-space](https://huggingface.co/new-space)**.
2. Enter Space Name: `prithvi-ai-ingest` (or `rituchakra-api`).
3. Select **Space SDK**: **Gradio** *(Free Python runtime, NOT Docker)*.
4. Set visibility: **Public** (or Private).
5. Hardware: **CPU Basic (Free · 2 vCPU · 16 GB RAM)**.
6. Click **Create Space**.

---

## Step 2: Space File Structure
In your Space repo, you only need:
- `requirements.txt`
- `app/` (the entire `backend/app/` folder)
- `app.py` (entry point for Hugging Face Gradio runner)

### `app.py` (FastAPI Bridge for Hugging Face)
Create `app.py` in the root of your Hugging Face space:

```python
import gradio as gr
from app.main import app as fastapi_app

# Create a clean status landing UI for Hugging Face
with gr.Blocks(title="Prithvi AI / PRITHVI-AI Backend") as demo:
    gr.Markdown("# 🛰️ PRITHVI-AI Satellite Ingestion & Hazard Backend")
    gr.Markdown(
        "This space powers 24/7 autonomous satellite crunching, convective nowcasting, and hazard models."
    )
    gr.Markdown("- **Health Status:** [/api/health](/api/health)")
    gr.Markdown("- **API Route Catalog:** [/api](/api)")
    gr.Markdown("- **Storm Map Incident Feed:** [/api/nowcast/storm-map?state=India](/api/nowcast/storm-map?state=India)")

# Mount Gradio onto the existing FastAPI application
# This exposes ALL /api, /v1, and ingestion lifecycle routes seamlessly on port 7860!
app = gr.mount_gradio_app(fastapi_app, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(fastapi_app, host="0.0.0.0", port=7860)
```

---

## Step 3: `requirements.txt`
Ensure `gradio` is included along with your backend requirements:
```text
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
pydantic>=2.8.0
pydantic-settings>=2.4.0
httpx>=0.27.0
pillow>=10.4.0
numpy>=1.26.0
scipy>=1.13.0
motor>=3.5.0
pymongo>=4.8.0
gradio>=4.40.0
```

---

### Step 4: Configure Variables and Secrets on Hugging Face
Go to your Space → **Settings → Variables and secrets**:

#### For API Service (`rituchakra-api`):
| Name | Type | Value |
|---|---|---|
| `APP_ROLE` | Variable | `api` |
| `MONGODB_URI` | Secret | `mongodb+srv://...` |
| `MONGODB_SAT_URI` | Secret | `mongodb+srv://...` |
| `CORS_ORIGINS` | Variable | `*` |
| `PUBLIC_BASE_URL` | Variable | `https://<your-username>-<space-name>.hf.space` |
| `GROQ_API_KEY` | Secret | `<your-groq-key>` (optional) |
| `LLM_FALLBACK` | Variable | `groq` |

#### For 24/7 Ingestion Cruncher (`prithvi-ai-ingest`):
| Name | Type | Value |
|---|---|---|
| `APP_ROLE` | Variable | `ingest` |
| `MONGODB_URI` | Secret | `mongodb+srv://...` |
| `MONGODB_SAT_URI` | Secret | `mongodb+srv://...` |
| `OM_SERVER_REFRESH` | Variable | `false` |
| `MOSDAC_USER` | Secret | `<username>` (optional) |
| `MOSDAC_PASS` | Secret | `<password>` (optional) |
| `NASA_EARTHDATA_API`| Secret | `<token>` (optional) |

---

## Direct API Access from Frontend / Mobile

Your API endpoints will be accessible at:
```
https://<your-username>-<space-name>.hf.space/api/health
https://<your-username>-<space-name>.hf.space/api/ready
https://<your-username>-<space-name>.hf.space/api/nowcast/storm-map?state=India
```

Set in `frontend/.env.local`:
```
NEXT_PUBLIC_API_BASE=https://<your-username>-<space-name>.hf.space
```

---

## Keeping Space Awake
Free Spaces sleep after inactivity (typically 48 hours).
To ensure 24/7 ingestion:
- Set up a free ping on [cron-job.org](https://cron-job.org) or [UptimeRobot](https://uptimerobot.com) to hit:
  `https://<your-username>-<space-name>.hf.space/api/ready` every 15 minutes.
