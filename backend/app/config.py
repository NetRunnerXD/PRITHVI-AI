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
    ollama_model: str = "qwen2.5"
    ollama_api_key: str = "ollama"

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
    openweather_api_key: str | None = None
    weatherbit_api_key: str | None = None
    eumetsat_token: str | None = None
    lightning_feed_url: str | None = None
    lightning_feed_key: str | None = None

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
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8081,http://localhost:19006"
    # LAN / Expo / Metro. Used when a phone hits this machine's API.
    cors_origin_regex: str = r"https?://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+)(:\d+)?"

    user_agent: str = "Rituchakra/0.3 (India environmental intelligence; local-dev)"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def cors_allow_all(self) -> bool:
        return "*" in self.cors_origin_list


@lru_cache
def get_settings() -> Settings:
    return Settings()
