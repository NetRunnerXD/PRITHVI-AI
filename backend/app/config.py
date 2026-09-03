from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ollama_base_url: str = "http://127.0.0.1:11434/v1"
    ollama_model: str = "qwen2.5:3b"
    ollama_triage_model: str = "qwen2.5:0.5b"
    ollama_api_key: str = "ollama"
    # Home PC reverse-connects with this token; cloud then dispatches Ollama jobs.
    llm_worker_token: str = ""
    llm_worker_timeout_s: float = 120.0
    snapshot_ttl_s: float = 600.0
    snapshot_swr_s: float = 3600.0

    # Hosted OpenAI-compat narrators. Keys stay on the server.
    llm_provider: str = "ollama"
    llm_fallback: str = ""
    groq_api_key: str | None = None
    groq_model: str = "llama-3.1-8b-instant"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    openrouter_api_key: str | None = None
    openrouter_model: str = "meta-llama/llama-3.1-8b-instruct:free"
    xai_api_key: str | None = None
    xai_model: str = "grok-4.5"
    github_token: str | None = None
    github_model: str = "meta-llama/Llama-3.1-8B-Instruct"

    imd_api_key: str | None = None
    imd_api_base: str = "https://api.imd.gov.in/api/v1"

    aikosh_api_key: str | None = None
    aikosh_api_base: str = "https://aikosh.indiaai.gov.in/api"

    data_gov_in_api_key: str | None = None

    mosdac_user: str | None = None
    mosdac_pass: str | None = None
    mosdac_base_url: str | None = None
    nasa_earthdata_user: str | None = None
    nasa_earthdata_pass: str | None = None
    nasa_earthdata_api: str | None = None
    openweather_api_key: str | None = None
    waqi_token: str | None = None
    weatherbit_api_key: str | None = None
    eumetsat_token: str | None = None
    lightning_feed_url: str | None = None
    lightning_feed_key: str | None = None
    cds_api_key: str | None = None
    graphcast_weights_dir: str | None = None

    # Google gtx + MyMemory, no key. Off = skip inbound/outbound MT.
    translate_enabled: bool = True

    default_lat: float = 22.0667
    default_lon: float = 88.0698
    default_state: str = "West Bengal"
    default_district: str = "Purba Medinipur"
    default_place: str = "Haldia"

    cache_dir: str = str(ROOT / ".cache")
    # Empty = derive from the incoming request. Set when publishing behind a public host.
    public_base_url: str = ""
    api_version: str = "0.4.0"
    # Comma list, or * for any browser / React Native origin.
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:8081,http://127.0.0.1:8081,"
        "https://localhost:8081,https://127.0.0.1:8081,"
        "http://localhost:19006,http://127.0.0.1:19006"
    )
    # LAN / Expo / Metro. Used when a phone hits this machine's API.
    cors_origin_regex: str = (
        r"https?://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|"
        r"172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+)(:\d+)?"
    )

    user_agent: str = "Rituchakra/0.4 (India environmental intelligence; local-dev)"

    # Optional accounts (MongoDB Atlas M0). Empty URI = in-process store.
    mongodb_uri: str = ""
    mongodb_db: str = "rituchakra"
    jwt_secret: str = ""
    fast2sms_api_key: str = ""
    sms_dry_run: bool = True
    sms_alert_interval_s: float = 900.0

    # Optional VEXYL Indic STT/TTS sidecars (empty = off; chat falls back to Web Speech).
    vexyl_stt_url: str = ""
    vexyl_tts_url: str = ""
    vexyl_api_key: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def cors_allow_all(self) -> bool:
        return "*" in self.cors_origin_list


@lru_cache
def get_settings() -> Settings:
    return Settings()
