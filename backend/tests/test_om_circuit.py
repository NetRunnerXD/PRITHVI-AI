import asyncio

from app.providers import open_meteo
from app.providers.om_hub import hub


def setup_function():
    open_meteo.reset_circuit()
    hub.reset()


def teardown_function():
    open_meteo.reset_circuit()
    hub.reset()


def test_circuit_trips_and_skips_http(monkeypatch):
    calls = []

    class Boom:
        async def get(self, *a, **k):
            calls.append(1)
            class R:
                status_code = 429

                def raise_for_status(self):
                    raise RuntimeError("429")

                def json(self):
                    return {}

            return R()

    monkeypatch.setattr(open_meteo, "client", lambda: Boom())

    async def run():
        try:
            await open_meteo.om_json("forecast", {"latitude": 22.0, "longitude": 88.0})
        except RuntimeError:
            pass
        assert open_meteo.circuit_open()
        n = len(calls)
        try:
            await open_meteo.om_json("forecast", {"latitude": 22.0, "longitude": 88.0})
        except RuntimeError:
            pass
        assert len(calls) == n

    asyncio.run(run())


def test_fallback_ids_auto_groq():
    from app.llm import providers as registry
    from app.config import Settings

    s = Settings().model_copy(update={"llm_fallback": "", "groq_api_key": "gsk_test"})
    assert "groq" in registry.fallback_ids(s)
