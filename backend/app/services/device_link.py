"""Find an ESP32 on the LAN by the code on its screen.

This process broadcasts `PRITHVI?` to UDP 3901. A box that is on the home
network answers `PRITHVI1 CODE IP`. The website then posts this computer's
own LAN address to the box. The box never accepts a server URL over UDP.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import time
from typing import Any

import httpx

log = logging.getLogger("prithvi.device")

PORT = 3901
SEEN_S = 30.0
_seen: dict[str, dict[str, Any]] = {}
_linked: dict[str, str] = {}


def _norm(code: str) -> str:
    return "".join(ch for ch in (code or "").upper() if ch.isalnum())[:8]


def _ipv4(text: str) -> bool:
    parts = (text or "").split(".")
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(part) <= 255 for part in parts)
    except ValueError:
        return False


def note_reply(text: str, fallback_ip: str) -> bool:
    parts = (text or "").split()
    if len(parts) < 2 or parts[0] != "PRITHVI1":
        return False
    ip = parts[2] if len(parts) >= 3 and _ipv4(parts[2]) else fallback_ip
    note_seen(parts[1], ip)
    return bool(_norm(parts[1]) and ip)


def note_seen(code: str, ip: str) -> None:
    key = _norm(code)
    if len(key) < 4 or not ip:
        return
    _seen[key] = {"code": key, "ip": ip, "seen": time.time()}


def seen_devices() -> list[dict[str, Any]]:
    now = time.time()
    rows = []
    for row in _seen.values():
        ago = now - float(row["seen"])
        if ago > SEEN_S:
            continue
        rows.append({"code": row["code"], "ip": row["ip"], "ago_s": int(ago)})
    rows.sort(key=lambda r: r["ago_s"])
    return rows


def lan_ipv4s() -> list[str]:
    found: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.add(str(info[4][0]))
    except OSError:
        pass
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        found.add(str(sock.getsockname()[0]))
    except OSError:
        pass
    finally:
        sock.close()
    return sorted(ip for ip in found if ip and not ip.startswith("127.") and not ip.startswith("169.254."))


def _directed_broadcast(ip: str) -> str:
    parts = ip.split(".")
    if len(parts) != 4:
        return "255.255.255.255"
    parts[3] = "255"
    return ".".join(parts)


def local_ip_toward(peer: str) -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect((peer, 9))
        return str(sock.getsockname()[0])
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def linked_base() -> str:
    return _linked.get("base") or ""


def linked_code() -> str:
    return _linked.get("code") or ""


async def _status(base: str, timeout: float = 2.5) -> dict[str, Any] | None:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=min(1.2, timeout))) as client:
            response = await client.get(f"{base}/api/status")
        if response.status_code != 200:
            return None
        body = response.json()
        if isinstance(body, dict):
            return body
    except Exception:
        return None
    return None


async def probe_setup() -> dict[str, Any] | None:
    body = await _status("http://192.168.4.1")
    if not body:
        return None
    code = _norm(str(body.get("code") or ""))
    if not code:
        return None
    note_seen(code, "192.168.4.1")
    return body


def _remember_status(body: dict[str, Any] | None, fallback_ip: str) -> None:
    if not body:
        return
    code = _norm(str(body.get("code") or ""))
    live = str(body.get("live_ip") or fallback_ip)
    if code and (_ipv4(live) or live == "192.168.4.1"):
        note_seen(code, live)


async def probe_mdns() -> dict[str, Any] | None:
    body = await _status("http://prithvi.local", timeout=0.8)
    _remember_status(body, "")
    return body


async def probe_subnet(code: str) -> None:
    if any(row["code"] == code for row in seen_devices()):
        return
    targets: list[str] = []
    for local in lan_ipv4s():
        pieces = local.split(".")
        if len(pieces) != 4:
            continue
        prefix = ".".join(pieces[:3])
        targets.extend(f"{prefix}.{n}" for n in range(1, 255) if f"{prefix}.{n}" != local)
    if not targets:
        return
    found = asyncio.Event()
    sem = asyncio.Semaphore(48)

    async def hit(ip: str) -> None:
        if found.is_set():
            return
        async with sem:
            if found.is_set():
                return
            body = await _status(f"http://{ip}", timeout=0.4)
        if not body:
            return
        _remember_status(body, ip)
        if _norm(str(body.get("code") or "")) == code:
            found.set()

    await asyncio.gather(*(hit(ip) for ip in targets))


async def link_code(code: str) -> dict[str, Any]:
    key = _norm(code)
    if len(key) < 4:
        raise ValueError("code")
    await probe_setup()
    await probe_mdns()
    if not any(row["code"] == key for row in seen_devices()) and not os.environ.get("PYTEST_CURRENT_TEST"):
        await probe_subnet(key)
    match = next((row for row in seen_devices() if row["code"] == key), None)
    if match is None:
        raise LookupError("code")
    base = "http://192.168.4.1" if match["ip"] == "192.168.4.1" else f"http://{match['ip']}"
    body = await _status(base)
    heard = _norm(str((body or {}).get("code") or ""))
    if body is not None and heard and heard != key:
        raise LookupError("code")
    _linked["code"] = key
    _linked["base"] = base
    mine = local_ip_toward(match["ip"])
    if mine.startswith("192.168.4.") or mine == "127.0.0.1":
        log.info("linked %s at %s without saving a setup address", key, base)
    else:
        await push_host(mine)
    return {"ok": True, "code": key, "base": base, "status": body}


async def push_host(host: str, port: int = 8000) -> dict[str, Any]:
    if not host or host.startswith("192.168.4.") or host == "127.0.0.1":
        raise RuntimeError("host")
    if port < 1 or port > 65535:
        raise RuntimeError("port")
    return await _post("/api/server", {"host": host, "port": port})


async def box_status() -> dict[str, Any]:
    base = linked_base()
    if not base:
        raise LookupError("link")
    body = await _status(base)
    if body is None:
        # Bluetooth can stall Wi-Fi for a moment. One retry keeps that off the Device tab.
        await asyncio.sleep(0.6)
        body = await _status(base, timeout=4.0)
    if body is None:
        raise ConnectionError(base)
    return body


async def _get(path: str, timeout: float = 8.0) -> dict[str, Any]:
    base = linked_base()
    if not base:
        raise LookupError("link")
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=1.5)) as client:
        response = await client.get(f"{base}{path}")
    try:
        body = response.json()
    except Exception:
        body = {}
    if response.status_code >= 400:
        detail = body.get("error") if isinstance(body, dict) else ""
        raise RuntimeError(str(detail or response.status_code))
    return body if isinstance(body, dict) else {}


def _bt_view(raw: dict[str, Any]) -> dict[str, Any]:
    devices = raw.get("devices")
    return {
        "ok": True,
        "paired": bool(raw.get("paired")),
        "linked": bool(raw.get("linked")),
        "name": str(raw.get("name") or ""),
        "devices": devices if isinstance(devices, list) else [],
    }


async def box_bt(body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Scan speakers, save one by address or typed name, or forget the saved one."""
    if not body or not body.get("action"):
        return _bt_view(await _get("/api/bt", timeout=8))
    action = str(body.get("action") or "")
    if action not in {"scan", "pair", "forget", "tone"}:
        raise RuntimeError("action")
    raw = await _post(
        "/api/bt",
        {
            "action": action,
            "bda": str(body.get("bda") or "")[:24],
            "name": str(body.get("name") or "")[:31],
        },
        timeout=50,
    )
    if action == "pair":
        current = await box_status()
        if current.get("audio_mode") == "i2s":
            await _post(
                "/api/audio",
                {
                    "audio_mode": "both",
                    "volume": int(current.get("volume") or 80),
                    "save": True,
                },
            )
    return _bt_view(raw)


async def box_wifi() -> dict[str, Any]:
    base = linked_base()
    if not base:
        raise LookupError("link")
    async with httpx.AsyncClient(timeout=httpx.Timeout(12.0, connect=1.5)) as client:
        response = await client.get(f"{base}/api/scan")
    response.raise_for_status()
    body = response.json()
    return body if isinstance(body, dict) else {"ok": False, "aps": []}


async def _post(path: str, payload: dict[str, Any], timeout: float = 8.0) -> dict[str, Any]:
    base = linked_base()
    if not base:
        raise LookupError("link")
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=1.5)) as client:
        response = await client.post(f"{base}{path}", json=payload)
    try:
        body = response.json()
    except Exception:
        body = {}
    if response.status_code >= 400:
        detail = body.get("error") if isinstance(body, dict) else ""
        raise RuntimeError(str(detail or response.status_code))
    return body if isinstance(body, dict) else {}


async def push_box(body: dict[str, Any]) -> dict[str, Any]:
    current = await box_status()
    saved: list[str] = []
    card = None
    if "place" in body:
        has_geo = bool(body.get("has_geo")) and body.get("lat") is not None and body.get("lon") is not None
        lat = float(body.get("lat") or 0)
        lon = float(body.get("lon") or 0)
        same_place = str(body.get("place") or "") == str(current.get("place") or "")
        if not has_geo and same_place and current.get("has_geo"):
            has_geo = True
            lat = float(current.get("lat") or 0)
            lon = float(current.get("lon") or 0)
        place_body = await _post(
            "/api/place",
            {
                "place": str(body.get("place") or ""),
                "has_geo": has_geo,
                "lat": lat,
                "lon": lon,
                "save": True,
                "preview": True,
            },
            timeout=25.0,
        )
        if isinstance(place_body.get("card"), dict):
            card = place_body["card"]
        saved.append("place")
    if body.get("audio_mode") or body.get("volume") is not None or body.get("rec_sec") is not None:
        await _post(
            "/api/audio",
            {
                "audio_mode": body.get("audio_mode") or current.get("audio_mode") or "i2s",
                "volume": int(body.get("volume") if body.get("volume") is not None else current.get("volume") or 80),
                "rec_sec": int(body.get("rec_sec") if body.get("rec_sec") is not None else current.get("rec_sec") or 6),
                "save": True,
            },
        )
        saved.append("audio")
    display_keys = ("contrast", "poll_min", "show_aqi", "show_rain", "alert_takeover")
    if any(key in body for key in display_keys):
        await _post(
            "/api/display",
            {
                "contrast": int(body.get("contrast") if body.get("contrast") is not None else current.get("contrast") or 200),
                "poll_min": int(body.get("poll_min") if body.get("poll_min") is not None else current.get("poll_min") or 10),
                "show_aqi": bool(body["show_aqi"]) if "show_aqi" in body else bool(current.get("show_aqi", True)),
                "show_rain": bool(body["show_rain"]) if "show_rain" in body else bool(current.get("show_rain", True)),
                "alert_takeover": bool(body["alert_takeover"]) if "alert_takeover" in body else bool(current.get("alert_takeover", True)),
            },
        )
        saved.append("display")
    alert_keys = ("heat", "rain", "flood", "storm", "air", "quake", "tsunami", "quiet_start", "quiet_end")
    if any(key in body for key in alert_keys):
        payload = {key: body[key] for key in alert_keys if key in body}
        await _post("/api/alerts", payload)
        saved.append("alerts")
    if body.get("ssid"):
        net = {
            "ssid": str(body.get("ssid") or "")[:32],
            "hostname": current.get("hostname") or "prithvi",
            "dhcp": True,
            "scheme": current.get("scheme") or "http",
            "host": current.get("host") or "",
            "port": int(current.get("port") or 8000),
            "prefix": current.get("prefix") or "",
            "ap_ssid": current.get("ap_ssid") or "PRITHVI-SETUP",
            "ap_open": not bool(current.get("ap_pass_set")),
            "ap_ip": current.get("ap_ip") or "192.168.4.1",
            "ap_mask": current.get("ap_mask") or "255.255.255.0",
            "ap_channel": int(current.get("ap_channel") or 6),
            "captive": bool(current.get("captive", True)),
            "connect_s": int(current.get("connect_s") or 8),
            "request_s": int(current.get("request_s") or 120),
        }
        if body.get("pass"):
            net["pass"] = str(body["pass"])
        await _post("/api/net", net)
        saved.append("wifi")
    result: dict[str, Any] = {"ok": True, "saved": saved}
    if card is not None:
        result["card"] = card
    return result


class _Beacon(asyncio.DatagramProtocol):
    def datagram_received(self, data: bytes, addr) -> None:  # noqa: ANN001
        text = data.decode("utf-8", "replace").strip()
        note_reply(text, str(addr[0]))


async def beacon_loop() -> None:
    loop = asyncio.get_running_loop()
    binds = lan_ipv4s() or ["0.0.0.0"]
    transports: list[tuple[str, asyncio.BaseTransport]] = []
    for ip in binds:
        try:
            transport, _protocol = await loop.create_datagram_endpoint(
                _Beacon,
                local_addr=(ip, PORT),
                allow_broadcast=True,
            )
        except OSError as exc:
            log.warning("device beacon %s:%s unavailable: %s", ip, PORT, exc)
            continue
        transports.append((ip, transport))
    if not transports:
        return

    async def solicit() -> None:
        while True:
            for ip, transport in transports:
                dests = ["255.255.255.255"]
                if ip != "0.0.0.0":
                    dests.insert(0, _directed_broadcast(ip))
                for dest in dests:
                    try:
                        transport.sendto(b"PRITHVI?", (dest, PORT))
                    except OSError:
                        pass
            await asyncio.sleep(2)

    task = asyncio.create_task(solicit())
    try:
        await asyncio.Future()
    finally:
        task.cancel()
        for _ip, transport in transports:
            transport.close()
