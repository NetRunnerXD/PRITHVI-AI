from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException

from app.auth import db
from app.auth.schemas import ForgotIn, LocationPatch, LoginIn, ProfilePatch, RegisterIn, ResetIn
from app.auth.security import (
    check_password,
    hash_otp,
    hash_password,
    make_token,
    new_otp,
    normalize_phone,
    phone_ok,
    read_token,
)
from app.auth.sms import send_sms
from app.data.india_mask import in_india
from app.services.location_svc import resolve_location

router = APIRouter()


def _bearer(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "sign_in_required")
    payload = read_token(authorization.split(" ", 1)[1].strip())
    if not payload or not payload.get("sub"):
        raise HTTPException(401, "invalid_token")
    return payload


def _loc_payload(lat: float, lon: float, place: str | None, source: str) -> dict:
    if not in_india(lat, lon):
        raise HTTPException(400, "location_outside_india")
    loc = resolve_location(q=place, lat=lat, lon=lon)
    return {
        "lat": lat,
        "lon": lon,
        "place": loc.place_name or loc.district,
        "district": loc.district,
        "state": loc.state,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
    }


@router.post("/auth/register")
async def register(body: RegisterIn):
    phone = normalize_phone(body.phone)
    if not phone_ok(phone):
        raise HTTPException(400, "invalid_indian_mobile")
    if await db.find_by_phone(phone):
        raise HTTPException(409, "phone_taken")
    loc = None
    if body.lat is not None and body.lon is not None:
        loc = _loc_payload(body.lat, body.lon, body.place, "gps")
    name = (body.display_name or "").strip() or f"User {phone[-4:]}"
    email = (body.email or "").strip() or None
    if email == "":
        email = None
    doc = {
        "phone": phone,
        "password_hash": hash_password(body.password),
        "display_name": name,
        "email": email,
        "sms_opt_in": bool(body.sms_opt_in),
        "location": loc,
        "reset": None,
    }
    try:
        saved = await db.insert_user(doc)
    except ValueError:
        raise HTTPException(409, "phone_taken")
    token = make_token(saved["_id"], phone)
    return {"token": token, "user": db.public_user(saved)}


@router.post("/auth/login")
async def login(body: LoginIn):
    phone = normalize_phone(body.phone)
    user = await db.find_by_phone(phone)
    if not user or not check_password(body.password, user.get("password_hash") or ""):
        raise HTTPException(401, "bad_credentials")
    return {"token": make_token(user["_id"], phone), "user": db.public_user(user)}


@router.get("/auth/me")
async def me(tok: dict = Depends(_bearer)):
    user = await db.find_by_id(tok["sub"])
    if not user:
        raise HTTPException(401, "unknown_user")
    return {"user": db.public_user(user)}


@router.patch("/auth/me")
async def patch_me(body: ProfilePatch, tok: dict = Depends(_bearer)):
    patch: dict = {}
    if body.display_name is not None:
        name = body.display_name.strip()
        if not name:
            raise HTTPException(400, "display_name_required")
        patch["display_name"] = name
    if body.email is not None:
        patch["email"] = body.email.strip() or None
    if body.sms_opt_in is not None:
        patch["sms_opt_in"] = bool(body.sms_opt_in)
    user = await db.update_user(tok["sub"], patch)
    if not user:
        raise HTTPException(401, "unknown_user")
    return {"user": db.public_user(user)}


@router.patch("/auth/me/location")
async def patch_location(body: LocationPatch, tok: dict = Depends(_bearer)):
    loc = _loc_payload(body.lat, body.lon, body.place, body.source if body.source in {"gps", "manual"} else "manual")
    user = await db.update_user(tok["sub"], {"location": loc})
    if not user:
        raise HTTPException(401, "unknown_user")
    return {"user": db.public_user(user)}


@router.post("/auth/forgot")
async def forgot(body: ForgotIn):
    phone = normalize_phone(body.phone)
    user = await db.find_by_phone(phone)
    # Same response whether or not the phone exists.
    if user:
        otp = new_otp()
        expires = datetime.now(timezone.utc) + timedelta(minutes=10)
        await db.update_user(
            user["_id"],
            {"reset": {"otp_hash": hash_otp(otp), "expires_at": expires.isoformat()}},
        )
        await send_sms(phone, f"Rituchakra password reset code: {otp}. Valid 10 min.")
    return {"ok": True}


@router.post("/auth/reset")
async def reset(body: ResetIn):
    phone = normalize_phone(body.phone)
    user = await db.find_by_phone(phone)
    if not user or not user.get("reset"):
        raise HTTPException(400, "invalid_or_expired_otp")
    reset = user["reset"]
    try:
        exp = datetime.fromisoformat(reset["expires_at"])
    except (TypeError, ValueError, KeyError):
        raise HTTPException(400, "invalid_or_expired_otp")
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > exp:
        raise HTTPException(400, "invalid_or_expired_otp")
    if hash_otp(body.otp.strip()) != reset.get("otp_hash"):
        raise HTTPException(400, "invalid_or_expired_otp")
    updated = await db.update_user(
        user["_id"],
        {"password_hash": hash_password(body.password), "reset": None},
    )
    token = make_token(user["_id"], phone)
    return {"token": token, "user": db.public_user(updated or user)}


@router.post("/auth/logout")
async def logout(_: dict = Depends(_bearer)):
    return {"ok": True}
