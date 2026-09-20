"""Provider registry: keys, resolve, request override. No live HTTP."""

import pytest

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


def test_local_and_worker_specs():
    s = _s(llm_worker_token="tok")
    loc = registry.spec("local", s)
    assert loc is not None and loc.keyed and loc.id == "local"
    w = registry.spec("worker", s)
    assert w is not None and w.keyed
    s2 = _s(llm_worker_token="")
    w2 = registry.spec("worker", s2)
    assert w2 is not None and not w2.keyed
    assert registry.resolve("local", s).id == "local"


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
    assert registry.resolve("gemini", s).model.startswith("gemini-")


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


def test_chat_request_aliases_and_loose_location():
    a = ChatRequest.model_validate({"prompt": "Rain in Haldia?", "stream": "false"})
    assert a.message == "Rain in Haldia?"
    assert a.stream is False
    b = ChatRequest.model_validate({"query": "AQI?", "location": "Pune"})
    assert b.message == "AQI?"
    assert b.place == "Pune"
    assert b.location is None
    c = ChatRequest.model_validate({"text": "hi", "history": [{"role": "user", "content": "yo"}]})
    assert c.history[0].id
    assert c.history[0].content == "yo"


def test_select_narrator_insight_xai():
    s = _s(xai_api_key="x", llm_provider="ollama")
    req = ChatRequest(message="AQI?")
    assert registry.select_narrator(req, s, insight_turn=True) == "xai"
    assert registry.select_narrator(req, s, insight_turn=False) is None
    req2 = ChatRequest(message="AQI?", llm="groq")
    assert registry.select_narrator(req2, s, insight_turn=True) == "groq"
    s2 = _s(xai_api_key="", llm_provider="ollama")
    assert registry.select_narrator(req, s2, insight_turn=True) is None


def test_exc_kind_404_is_missing():
    from app.llm.ollama_client import _exc_kind

    class _NotFound(Exception):
        status_code = 404

        def __str__(self) -> str:
            return "Error code: 404 - The model `llama-3.1-8b-instant` does not exist or you do not have access to it"

    assert _exc_kind(_NotFound()) == "missing"


def test_default_groq_model_is_current():
    s = _s()
    g = registry.spec("groq", s)
    assert g is not None
    assert g.model == "openai/gpt-oss-20b"


@pytest.mark.asyncio
async def test_groq_404_does_not_claim_gemini_dropped_tools(monkeypatch):
    from app.llm import ollama_client
    from app.agents.data_tool import SCHEMA

    class _NotFound(Exception):
        status_code = 404

        def __str__(self) -> str:
            return "Error code: 404 - The model `llama-3.1-8b-instant` does not exist"

    class _Completions:
        async def create(self, **kwargs):
            raise _NotFound()

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    s = _s(groq_api_key="gsk", gemini_api_key="", llm_provider="groq", llm_fallback="groq")
    monkeypatch.setattr(ollama_client, "client", lambda: _Client())
    monkeypatch.setattr("app.llm.ollama_client.get_settings", lambda: s)
    monkeypatch.setattr("app.llm.providers.get_settings", lambda: s)
    tok = ollama_client.use_provider("groq")
    try:
        out = await ollama_client.chat([{"role": "user", "content": "rain?"}], tools=[SCHEMA])
    finally:
        ollama_client.reset_provider(tok)
    assert out.get("tools_stripped") is False
    assert out.get("provider") == "groq"
    assert "404" in str(out.get("error") or "")


def test_fallback_skips_empty_keys():
    s = _s(llm_fallback="groq,gemini", groq_api_key=None, gemini_api_key="k")
    assert registry.fallback_ids(s) == ["gemini"]


@pytest.mark.asyncio
async def test_chat_uses_local_ollama_even_with_worker_token_and_groq(monkeypatch):
    """Cloud worker token + Groq key must not skip a live local Ollama GPU."""
    from app.llm import ollama_client

    called = {"n": 0}

    class _Msg:
        content = "local GPU"
        tool_calls = None

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    class _Completions:
        async def create(self, **kwargs):
            called["n"] += 1
            return _Resp()

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    monkeypatch.setattr(ollama_client, "client", lambda: _Client())
    s = _s(groq_api_key="gsk", llm_worker_token="secret", llm_provider="ollama")
    monkeypatch.setattr("app.llm.ollama_client.get_settings", lambda: s)
    monkeypatch.setattr("app.llm.providers.get_settings", lambda: s)
    out = await ollama_client.chat([{"role": "user", "content": "rain?"}])
    assert called["n"] >= 1
    assert out.get("provider") == "ollama"
    assert "GPU" in out["content"]


@pytest.mark.asyncio
async def test_chat_uses_local_ollama_even_if_groq_keyed(monkeypatch):
    """A Groq key must not skip the local GPU when no home-worker token is set."""
    from app.llm import ollama_client

    called = {"n": 0}

    class _Msg:
        content = "GPU reply about rain."
        tool_calls = None

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    class _Completions:
        async def create(self, **kwargs):
            called["n"] += 1
            return _Resp()

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    monkeypatch.setattr(ollama_client, "client", lambda: _Client())
    monkeypatch.setattr(
        "app.llm.ollama_client.get_settings",
        lambda: _s(groq_api_key="gsk", llm_worker_token="", llm_provider="ollama"),
    )
    monkeypatch.setattr(
        "app.llm.providers.get_settings",
        lambda: _s(groq_api_key="gsk", llm_worker_token="", llm_provider="ollama"),
    )
    out = await ollama_client.chat([{"role": "user", "content": "rain?"}])
    assert called["n"] == 1
    assert "GPU reply" in out["content"]
    assert out.get("provider") == "ollama"


def test_default_fallback_gemini_then_groq():
    s = _s(llm_fallback="", groq_api_key="gsk", gemini_api_key="gk")
    assert registry.fallback_ids(s) == ["gemini", "groq"]


def test_default_fallback_skips_missing_gemini():
    s = _s(llm_fallback="", groq_api_key="gsk", gemini_api_key="")
    assert registry.fallback_ids(s) == ["groq"]


@pytest.mark.asyncio
async def test_gemini_chat_never_sends_tools(monkeypatch):
    from app.agents.data_tool import SCHEMA
    from app.llm import ollama_client

    seen = {}

    async def _fake_gen(**kwargs):
        seen.update(kwargs)
        return {"content": "Humid at Haldia with 12.2 mm from the pack.", "tool_calls": []}

    monkeypatch.setattr("app.llm.gemini_native.generate", _fake_gen)
    s = _s(gemini_api_key="gk", groq_api_key="", llm_provider="gemini", llm_fallback="gemini")
    monkeypatch.setattr("app.llm.ollama_client.get_settings", lambda: s)
    monkeypatch.setattr("app.llm.providers.get_settings", lambda: s)
    tok = ollama_client.use_provider("gemini")
    try:
        out = await ollama_client.chat([{"role": "user", "content": "rain?"}], tools=[SCHEMA])
    finally:
        ollama_client.reset_provider(tok)
    assert seen.get("tools") is None
    assert "12.2" in out["content"]
    assert out.get("provider") == "gemini" or out.get("content")


def test_gemini_tools_are_not_strict_json_schema():
    from app.agents.data_tool import SCHEMA
    from app.llm.ollama_client import sanitize_tools

    gem = sanitize_tools([SCHEMA], strict=False)
    params = gem[0]["function"]["parameters"]
    assert "additionalProperties" not in params
    groq = sanitize_tools([SCHEMA], strict=True)
    assert groq[0]["function"]["parameters"]["additionalProperties"] is False


def test_skip_loopback_ollama_on_public_host():
    assert not registry.skip_loopback_ollama(_s(public_base_url="", ollama_base_url="http://127.0.0.1:11434/v1"))
    assert registry.skip_loopback_ollama(
        _s(public_base_url="https://rituchakra-api.onrender.com", ollama_base_url="http://127.0.0.1:11434/v1")
    )


class _ToolUseFailed(Exception):
    status_code = 400
    body: dict | None = None

    def __init__(self, generation: str | None = None):
        self.body = None
        if generation:
            self.body = {
                "error": {
                    "message": "Failed to call a function. Please adjust your prompt.",
                    "code": "tool_use_failed",
                    "failed_generation": generation,
                }
            }

    def __str__(self) -> str:
        return "Error code: 400 - Failed to call a function. tool_use_failed"


class _Schema400(Exception):
    status_code = 400

    def __str__(self) -> str:
        return "invalid_request_error: JSON schema validation failed"


@pytest.mark.asyncio
async def test_groq_tool_use_failed_retries_with_tools(monkeypatch):
    from app.llm import ollama_client
    from app.agents.data_tool import SCHEMA

    n = {"i": 0}

    class _Fn:
        name = "data"
        arguments = '{"need":"forecast"}'

    class _Call:
        id = "c1"
        function = _Fn()

    class _Msg:
        content = ""
        tool_calls = [_Call()]

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    class _Completions:
        async def create(self, **kwargs):
            n["i"] += 1
            if n["i"] == 1:
                raise _ToolUseFailed()
            assert kwargs.get("tools")
            return _Resp()

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    s = _s(groq_api_key="gsk", llm_provider="groq", llm_fallback="")
    monkeypatch.setattr(ollama_client, "client", lambda: _Client())
    monkeypatch.setattr("app.llm.ollama_client.get_settings", lambda: s)
    monkeypatch.setattr("app.llm.providers.get_settings", lambda: s)
    tok = ollama_client.use_provider("groq")
    try:
        out = await ollama_client.chat([{"role": "user", "content": "rain?"}], tools=[SCHEMA])
    finally:
        ollama_client.reset_provider(tok)
    assert n["i"] == 2
    assert out.get("tools_stripped") is False
    assert out.get("provider") == "groq"
    assert out["tool_calls"][0]["name"] == "data"


@pytest.mark.asyncio
async def test_groq_salvages_xml_failed_generation(monkeypatch):
    from app.llm import ollama_client
    from app.agents.data_tool import SCHEMA, parse_xml_tool_calls

    xml = '<function=data{"need": "forecast", "place": "Haldia"}>'
    assert parse_xml_tool_calls(xml)[0]["name"] == "data"

    class _Completions:
        async def create(self, **kwargs):
            raise _ToolUseFailed(xml)

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    s = _s(groq_api_key="gsk", llm_provider="groq", llm_fallback="")
    monkeypatch.setattr(ollama_client, "client", lambda: _Client())
    monkeypatch.setattr("app.llm.ollama_client.get_settings", lambda: s)
    monkeypatch.setattr("app.llm.providers.get_settings", lambda: s)
    tok = ollama_client.use_provider("groq")
    try:
        out = await ollama_client.chat([{"role": "user", "content": "rain?"}], tools=[SCHEMA])
    finally:
        ollama_client.reset_provider(tok)
    assert out.get("tools_stripped") is False
    assert out.get("via") == "failed-generation"
    assert out["tool_calls"][0]["name"] == "data"
    assert "forecast" in out["tool_calls"][0]["arguments"]


@pytest.mark.asyncio
async def test_groq_schema_error_strips_tools(monkeypatch):
    from app.llm import ollama_client
    from app.agents.data_tool import SCHEMA

    n = {"i": 0}

    class _Msg:
        content = "data(need=forecast, place=Haldia)"
        tool_calls = None

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    class _Completions:
        async def create(self, **kwargs):
            n["i"] += 1
            if kwargs.get("tools"):
                raise _Schema400()
            return _Resp()

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    s = _s(groq_api_key="gsk", llm_provider="groq", llm_fallback="")
    monkeypatch.setattr(ollama_client, "client", lambda: _Client())
    monkeypatch.setattr("app.llm.ollama_client.get_settings", lambda: s)
    monkeypatch.setattr("app.llm.providers.get_settings", lambda: s)
    tok = ollama_client.use_provider("groq")
    try:
        out = await ollama_client.chat([{"role": "user", "content": "rain?"}], tools=[SCHEMA])
    finally:
        ollama_client.reset_provider(tok)
    assert out.get("tools_stripped") is True
    assert out.get("provider") == "groq"
    assert out.get("error")


def _s(**over):
    from app.config import Settings

    base = Settings()
    return base.model_copy(update=over)
