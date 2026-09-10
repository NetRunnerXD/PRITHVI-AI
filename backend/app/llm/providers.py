"""OpenAI-compatible LLM registry. Narration only — millimetres stay in data()."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings, get_settings

GROQ_URL = "https://api.groq.com/openai/v1"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
OPENROUTER_URL = "https://openrouter.ai/api/v1"
XAI_URL = "https://api.x.ai/v1"
GITHUB_URL = "https://models.inference.ai.azure.com"
IDS = ("local", "worker", "ollama", "groq", "gemini", "github", "openrouter", "xai")
SETTINGS_IDS = ("local", "worker", "groq", "gemini")


@dataclass(frozen=True)
class Provider:
    id: str
    model: str
    base_url: str
    api_key: str
    keyed: bool


def _key(raw: str | None) -> str:
    return (raw or "").strip()


def spec(pid: str, s: Settings | None = None) -> Provider | None:
    s = s or get_settings()
    name = (pid or "").strip().lower()
    if name in ("ollama", "local"):
        return Provider(
            id=name,
            model=s.ollama_model,
            base_url=s.ollama_base_url,
            api_key=s.ollama_api_key or "ollama",
            keyed=True,
        )
    if name == "worker":
        token = (s.llm_worker_token or "").strip()
        return Provider(
            id="worker",
            model=s.ollama_model,
            base_url=s.ollama_base_url,
            api_key=s.ollama_api_key or "ollama",
            keyed=bool(token),
        )
    if name == "groq":
        k = _key(s.groq_api_key)
        return Provider("groq", s.groq_model, GROQ_URL, k, bool(k))
    if name == "gemini":
        k = _key(s.gemini_api_key)
        return Provider("gemini", s.gemini_model, GEMINI_URL, k, bool(k))
    if name == "openrouter":
        k = _key(s.openrouter_api_key)
        return Provider("openrouter", s.openrouter_model, OPENROUTER_URL, k, bool(k))
    if name == "xai":
        k = _key(s.xai_api_key)
        return Provider("xai", s.xai_model, XAI_URL, k, bool(k))
    if name == "github":
        k = _key(s.github_token)
        return Provider("github", s.github_model, GITHUB_URL, k, bool(k))
    return None


def available(s: Settings | None = None) -> list[Provider]:
    s = s or get_settings()
    out: list[Provider] = []
    for pid in IDS:
        p = spec(pid, s)
        if p and p.keyed:
            out.append(p)
    return out


def resolve(requested: str | None = None, s: Settings | None = None) -> Provider:
    s = s or get_settings()
    want = (requested or "").strip().lower()
    if want:
        p = spec(want, s)
        if p and p.keyed:
            return p
    env = spec(s.llm_provider, s)
    if env and env.keyed:
        return env
    ollama = spec("ollama", s)
    assert ollama is not None
    return ollama


def select_narrator(payload, settings: Settings | None = None, *, insight_turn: bool) -> str | None:
    """Return provider id to use_provider, or None to keep resolve() default.

    Never treats providers.available() as liveness. Does not switch all chat.
    """
    s = settings or get_settings()
    want = (getattr(payload, "llm", None) or "").strip().lower()
    if want:
        return want
    if insight_turn and _key(s.xai_api_key):
        return "xai"
    return None


def fallback_ids(s: Settings | None = None) -> list[str]:
    s = s or get_settings()
    raw = [x.strip().lower() for x in (s.llm_fallback or "").split(",") if x.strip()]
    out = [x for x in raw if spec(x, s) and spec(x, s).keyed]
    groq = spec("groq", s)
    if groq and groq.keyed and "groq" not in out:
        out.append("groq")
    return out
