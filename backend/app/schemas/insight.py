from __future__ import annotations

from pydantic import BaseModel, Field


class Band(BaseModel):
    key: str
    scale: str | None = None
    category: str
    band: str
    significance: str | None = None
    meaning: str
    raw_cite: str | None = None
    missing: bool = False


class InsightPacket(BaseModel):
    locus: str
    generated_at: str
    pack_fingerprint: str
    sentiment: str = "inquisitive"
    tone: str = "curious"
    domain: str = "general"
    intent: str = "forecast"
    bands: list[Band] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    cites: list[str] = Field(default_factory=list)
    needs_extra: list[str] = Field(default_factory=list)
    playbook: str | None = None


class InsightReply(BaseModel):
    meaning: str
    suggestion: str
    extra: str | None = None
    used_band_keys: list[str] = Field(default_factory=list)
