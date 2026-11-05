"""IndicTrans2 distilled sidecar. The API process must not import this file.

English ↔ the 22 scheduled languages. One sentence per request. The API in
``app.i18n.mt`` splits documents and falls back to Google when this process
is down.

  pip install -r requirements-mt.txt
  # Accept both model pages while logged in, then put the read token in
  # backend/.env as HF_TOKEN=hf_... (a shell $env:HF_TOKEN wins over .env).
  python scripts/mt_sidecar.py

Listens on http://127.0.0.1:8093. Point the API at it with MT_SIDECAR_URL.
MT_BEAMS defaults to 5 (the model card). Set MT_BEAMS=1 if CPU is too slow.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from typing import Any
from urllib.parse import urlparse

EN_INDIC = "ai4bharat/indictrans2-en-indic-dist-200M"
INDIC_EN = "ai4bharat/indictrans2-indic-en-dist-200M"
ENGINE = "indictrans2-dist-200m"

# Same tags as app.i18n.mt._FLORES. Kept here so this process does not import the API.
_TAGS = {
    "asm_Beng",
    "ben_Beng",
    "brx_Deva",
    "doi_Deva",
    "eng_Latn",
    "guj_Gujr",
    "hin_Deva",
    "kan_Knda",
    "kas_Arab",
    "gom_Deva",
    "mai_Deva",
    "mal_Mlym",
    "mni_Mtei",
    "mar_Deva",
    "npi_Deva",
    "ory_Orya",
    "pan_Guru",
    "san_Deva",
    "sat_Olck",
    "snd_Arab",
    "tam_Taml",
    "tel_Telu",
    "urd_Arab",
}

DEVICE = "cpu"
BEAMS = 5
MODELS: dict[str, tuple[Any, Any]] = {}
PROCESSOR: Any = None
LOCK = Lock()


def _processor() -> Any:
    # Local port: the PyPI package compiles a Cython extension and needs MSVC.
    from it2_processor import IndicProcessor

    return IndicProcessor(inference=True)


def _direction(src: str, tgt: str) -> str:
    if src not in _TAGS or tgt not in _TAGS:
        raise ValueError("lang")
    if src == "eng_Latn" and tgt != "eng_Latn":
        return "en-indic"
    if tgt == "eng_Latn" and src != "eng_Latn":
        return "indic-en"
    raise ValueError("pair")


def translate_text(text: str, src: str, tgt: str) -> str:
    """One sentence. The lock is held across preprocess and postprocess.

    IndicProcessor keeps entity maps on the instance. A failed generate must
    not leave that queue for the next sentence, so the processor is replaced.
    """
    global PROCESSOR
    import torch

    key = _direction(src, tgt)
    tokenizer, model = MODELS[key]
    with LOCK:
        try:
            batch = PROCESSOR.preprocess_batch([text], src_lang=src, tgt_lang=tgt)
            inputs = tokenizer(
                batch,
                truncation=True,
                padding="longest",
                return_tensors="pt",
                return_attention_mask=True,
            )
            if DEVICE == "cuda":
                inputs = inputs.to(DEVICE)
            with torch.inference_mode():
                generated = model.generate(
                    **inputs,
                    use_cache=True,
                    min_length=0,
                    max_length=256,
                    num_beams=BEAMS,
                    num_return_sequences=1,
                )
            decoded = tokenizer.batch_decode(
                generated,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=True,
            )
            out = PROCESSOR.postprocess_batch(decoded, lang=tgt)
        except Exception:
            PROCESSOR = _processor()
            raise
    piece = out[0] if out else ""
    return (piece or "").strip()


def _apply_dotenv_token() -> None:
    """Use HF_TOKEN from backend/.env when the shell did not set one."""
    if (os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN") or "").strip():
        return
    path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return
    for line in lines:
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, val = raw.split("=", 1)
        if key.strip() not in {"HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"}:
            continue
        val = val.strip().strip('"').strip("'")
        if not val:
            continue
        os.environ["HF_TOKEN"] = val
        os.environ.setdefault("HUGGING_FACE_HUB_TOKEN", val)
        return


def _shim_transformers_onnx() -> None:
    """IndicTrans2 remote code imports transformers.onnx, which transformers 5 removed.

    That import only builds an ONNX export helper. Inference never calls it.
    """
    import sys
    import types

    try:
        import transformers.onnx  # noqa: F401

        return
    except ImportError:
        pass
    onnx = types.ModuleType("transformers.onnx")
    utils = types.ModuleType("transformers.onnx.utils")

    class OnnxConfig:
        default_fixed_batch = 2
        default_fixed_sequence = 8

    class OnnxSeq2SeqConfigWithPast(OnnxConfig):
        pass

    def compute_effective_axis_dimension(dimension, fixed_dimension, num_token_to_add=0):
        if dimension == -1:
            return fixed_dimension + num_token_to_add
        return dimension

    onnx.OnnxConfig = OnnxConfig
    onnx.OnnxSeq2SeqConfigWithPast = OnnxSeq2SeqConfigWithPast
    utils.compute_effective_axis_dimension = compute_effective_axis_dimension
    onnx.utils = utils
    sys.modules["transformers.onnx"] = onnx
    sys.modules["transformers.onnx.utils"] = utils
    import transformers

    transformers.onnx = onnx


def _legacy_kv_cache(model: Any) -> None:
    """Keep IndicTrans2 on its tuple cache.

    transformers 4.57 wraps every encoder-decoder ``past_key_values`` in
    ``EncoderDecoderCache`` unless the model opts out. IndicTrans2 indexes
    ``past_key_values[0][0]`` and crashes on that wrapper.
    """

    @classmethod
    def _supports_default_dynamic_cache(cls) -> bool:
        return False

    model.__class__._supports_default_dynamic_cache = _supports_default_dynamic_cache


def _gated_download(exc: BaseException) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    return "gated" in text or "401" in text or "403" in text or "unauthorized" in text


def _load() -> None:
    global DEVICE, MODELS, PROCESSOR, BEAMS
    _apply_dotenv_token()
    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    except ImportError:
        print("Install sidecar deps: pip install -r requirements-mt.txt", file=sys.stderr)
        raise SystemExit(1)
    _shim_transformers_onnx()
    try:
        BEAMS = max(1, min(5, int(os.environ.get("MT_BEAMS", "5"))))
    except ValueError:
        BEAMS = 5
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    kwargs: dict[str, Any] = {"trust_remote_code": True}
    if DEVICE == "cuda":
        kwargs["torch_dtype"] = torch.float16
        try:
            import flash_attn  # noqa: F401

            kwargs["attn_implementation"] = "flash_attention_2"
        except Exception:
            pass
    else:
        kwargs["torch_dtype"] = torch.float32
    loaded: dict[str, tuple[Any, Any]] = {}
    for key, name in (("en-indic", EN_INDIC), ("indic-en", INDIC_EN)):
        print(f"loading {name} on {DEVICE}", flush=True)
        try:
            tokenizer = AutoTokenizer.from_pretrained(name, trust_remote_code=True)
            model = AutoModelForSeq2SeqLM.from_pretrained(name, **kwargs).to(DEVICE)
        except Exception as exc:
            if not _gated_download(exc):
                raise
            print(
                "Hugging Face refused the download.\n"
                "Log in and accept the terms on both pages, then set a read token:\n"
                "  https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M\n"
                "  https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M\n"
                "Put HF_TOKEN=hf_... in backend/.env, or in this shell as $env:HF_TOKEN.\n"
                "The shell value wins over .env. A token from an account that has not "
                "accepted the terms still gets 401 or 403.",
                file=sys.stderr,
            )
            raise SystemExit(1) from exc
        model.eval()
        _legacy_kv_cache(model)
        loaded[key] = (tokenizer, model)
    MODELS = loaded
    PROCESSOR = _processor()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if urlparse(self.path).path == "/health":
            self._json(200, {"ok": True, "engine": ENGINE})
            return
        self._json(404, {"ok": False})

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/translate":
            self._json(404, {"ok": False})
            return
        try:
            n = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            n = 0
        if n <= 0 or n > 65536:
            self._json(400, {"error": "body"})
            return
        try:
            payload = json.loads(self.rfile.read(n).decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            self._json(400, {"error": "json"})
            return
        if not isinstance(payload, dict):
            self._json(400, {"error": "fields"})
            return
        text = payload.get("text")
        src = payload.get("src")
        tgt = payload.get("tgt")
        if not isinstance(text, str) or not text.strip():
            self._json(400, {"error": "fields"})
            return
        if not isinstance(src, str) or not isinstance(tgt, str):
            self._json(400, {"error": "fields"})
            return
        try:
            body = translate_text(text.strip(), src.strip(), tgt.strip())
        except ValueError:
            self._json(400, {"error": "pair"})
            return
        except Exception:
            traceback.print_exc()
            self._json(500, {"error": "translate"})
            return
        if not body:
            self._json(502, {"error": "empty"})
            return
        self._json(200, {"text": body})

    def _json(self, code: int, obj: dict) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} {fmt % args}", flush=True)


def _reexec_in_venv() -> None:
    """IndicTrans2 needs transformers 4.x. This machine's default Python stays on 5.x for Gradio."""
    try:
        import transformers

        major = int(str(transformers.__version__).split(".", 1)[0])
    except Exception:
        major = 0
    if major == 4:
        return
    venv_py = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".venv", "Scripts", "python.exe"))
    if os.path.isfile(venv_py) and os.path.normcase(sys.executable) != os.path.normcase(venv_py):
        # os.execv splits this path on the space in "PRITHVI-AI Main" on Windows.
        cmd = [venv_py, os.path.abspath(__file__), *sys.argv[1:]]
        raise SystemExit(subprocess.call(cmd))
    print(
        "IndicTrans2 needs transformers 4.x. Create backend/.venv and install requirements-mt.txt there.\n"
        "The default Python is left on transformers 5 so other tools keep working.",
        file=sys.stderr,
    )
    raise SystemExit(1)


def main() -> None:
    _reexec_in_venv()
    _load()
    host = os.environ.get("MT_SIDECAR_HOST", "127.0.0.1")
    port = int(os.environ.get("MT_SIDECAR_PORT", "8093"))
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"indictrans2 sidecar on http://{host}:{port} beams={BEAMS}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("stopping", flush=True)
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
