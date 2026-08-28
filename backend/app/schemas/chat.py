from pydantic import BaseModel, Field

from app.schemas.location import Location


class ChatMessage(BaseModel):
    id: str
    role: str
    content: str
    content_en: str | None = None
    locale: str = "en"
    blocks: list[dict] = []
    suggestions: list[dict] = []
    tool_trace: list[dict] = []
    citations: list[dict] = []
    ui: list[dict] = []
    translation: dict | None = None


class ChatRequest(BaseModel):
    message: str
    locale_hint: str | None = None
    output_locale: str | None = None
    conversation_id: str | None = None
    location: Location | None = None
    history: list[ChatMessage] = Field(default_factory=list)
    regenerate: bool = False
    stream: bool = True
