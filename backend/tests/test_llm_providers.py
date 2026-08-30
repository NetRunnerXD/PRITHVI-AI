"""Provider registry: keys, resolve, request override. No live HTTP."""

from app.config import get_settings
from app.llm import providers as registry
from app.schemas.chat import ChatRequest


def setup_function():
    get_settings.cache_clear()


def teardown_function():
    get_settings.cache_clear()


def test_default_is_ollama():
    p = registry.resolve(None)
    assert p.id == "ollama"
    assert p.keyed


def test_gemini_without_key_is_not_available(monkeypatch):
    monkeypatch.setattr("app.llm.providers.get_settings", lambda: _s(gemini_api_key=""))
    s = _s(gemini_api_key=None)
    g = registry.spec("gemini", s)
    assert g is not None
    assert not g.keyed
    assert "gemini" not in {p.id for p in registry.available(s)}
    assert registry.resolve("gemini", s).id == "ollama"


def test_gemini_with_key_resolves(monkeypatch):
    s = _s(gemini_api_key="secret", llm_provider="ollama")
    g = registry.spec("gemini", s)
    assert g.keyed
    assert g.base_url.startswith("https://generativelanguage.googleapis.com")
    assert registry.resolve("gemini", s).id == "gemini"
    assert registry.resolve("gemini", s).model == "gemini-2.0-flash"


def test_groq_openrouter_xai_github_keyed():
    s = _s(
        groq_api_key="g",
        openrouter_api_key="o",
        xai_api_key="x",
        github_token="gh",
    )
    ids = {p.id for p in registry.available(s)}
    assert ids >= {"ollama", "groq", "openrouter", "xai", "github"}


def test_unknown_request_ignored():
    s = _s()
    assert registry.resolve("not-a-vendor", s).id == "ollama"


def test_chat_request_accepts_llm_field():
    req = ChatRequest(message="Hi", llm="gemini")
    assert req.llm == "gemini"


def test_fallback_skips_empty_keys():
    s = _s(llm_fallback="groq,gemini", groq_api_key=None, gemini_api_key="k")
    assert registry.fallback_ids(s) == ["gemini"]


def _s(**over):
    from app.config import Settings

    base = Settings()
    return base.model_copy(update=over)
