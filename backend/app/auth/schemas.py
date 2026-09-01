from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    phone: str
    password: str = Field(min_length=6, max_length=128)
    display_name: str | None = Field(default=None, max_length=80)
    sms_opt_in: bool = False
    lat: float | None = None
    lon: float | None = None
    place: str | None = None
    email: str | None = None


class LoginIn(BaseModel):
    phone: str
    password: str


class ProfilePatch(BaseModel):
    display_name: str | None = Field(default=None, max_length=80)
    email: str | None = None
    sms_opt_in: bool | None = None


class LocationPatch(BaseModel):
    lat: float
    lon: float
    place: str | None = None
    source: str = "manual"


class ForgotIn(BaseModel):
    phone: str


class ResetIn(BaseModel):
    phone: str
    otp: str
    password: str = Field(min_length=6, max_length=128)
