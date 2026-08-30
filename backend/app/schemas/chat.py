from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.location import Location


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = ""
    role: str = "user"
    content: str = ""
    content_en: str | None = None
    locale: str = "en"
    blocks: list[dict] = []
    suggestions: list[dict] = []
    tool_trace: list[dict] = []
    citations: list[dict] = []
    ui: list[dict] = []
    translation: dict | None = None

    @model_validator(mode="after")
    def _id(self):
        if not self.id:
            object.__setattr__(self, "id", f"m-{abs(hash((self.role, self.content))) % 10**10}")
        return self


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str = ""
    locale_hint: str | None = None
    output_locale: str | None = None
    conversation_id: str | None = None
    location: Location | None = None
    place: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)
    regenerate: bool = False
    stream: bool = True
    llm: str | None = None
    show_evidence: bool = False

    @model_validator(mode="before")
    @classmethod
    def _aliases(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        msg = str(data.get("message") or "").strip()
        if not msg:
            for k in ("query", "q", "text", "prompt", "question"):
                v = data.get(k)
                if v:
                    data["message"] = v
                    break
        loc = data.get("location")
        if isinstance(loc, str) and loc.strip():
            data["place"] = data.get("place") or loc.strip()
            data.pop("location", None)
        return data

    @field_validator("stream", "regenerate", "show_evidence", mode="before")
    @classmethod
    def _bool(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().lower() not in ("0", "false", "no", "")
        return v
