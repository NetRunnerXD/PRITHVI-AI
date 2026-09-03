# Indic STT / TTS (optional)

Chat mic and “listen” use **browser Web Speech** unless these sidecars are running. The FastAPI process never loads the models.

| Role | Model | Languages |
|---|---|---|
| STT | AI4Bharat IndicConformer 600M via [VEXYL-STT](https://github.com/vexyl-ai/vexyl-stt) | 14 Indic |
| TTS | Indic Parler-TTS via [VEXYL-TTS](https://github.com/vexyl-ai/vexyl-tts) | 22 scheduled + Indian English |

STT is **gated** on Hugging Face: request access to `ai4bharat/indic-conformer-600m-multilingual`. TTS is not gated (~6 GB disk). TTS wants a GPU; CPU works but is slow.

## Local (Docker)

```powershell
# after HF access is approved
$env:HF_TOKEN="hf_..."
$env:VEXYL_STT_URL="http://vexyl-stt:8080"
$env:VEXYL_TTS_URL="http://vexyl-tts:8080"
docker compose --profile voice up --build
```

Or run the VEXYL servers on the host (Linux/WSL — their `setup.sh` is not PowerShell) and set in `backend/.env`:

```
VEXYL_STT_URL=http://127.0.0.1:8091
VEXYL_TTS_URL=http://127.0.0.1:8092
```

`GET /api/speech/status` reports whether each sidecar is up. Chat falls back to Web Speech when `stt`/`tts` are false.

Do **not** enable this on Render Free. Run sidecars on a GPU box or leave voice on the browser.
