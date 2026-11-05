import pytest

from app.services import device_link


def test_link_requires_a_heard_code(monkeypatch):
    device_link._seen.clear()
    device_link._linked.clear()

    async def no_setup():
        return None

    async def no_push(host, port=8000):
        return {"ok": True, "host": host, "port": port}

    monkeypatch.setattr(device_link, "probe_setup", no_setup)
    monkeypatch.setattr(device_link, "push_host", no_push)
    device_link.note_seen("K7M4QP", "192.168.1.40")
    with pytest.raises(LookupError):
        import asyncio

        asyncio.run(device_link.link_code("ZZZZZZ"))


def test_link_uses_the_heard_address(monkeypatch):
    device_link._seen.clear()
    device_link._linked.clear()

    async def no_setup():
        return None

    async def no_mdns():
        return None

    async def status(base):
        assert base == "http://192.168.1.40"
        return {"code": "K7M4QP", "ssid": ""}

    async def no_push(host, port=8000):
        return {"ok": True}

    monkeypatch.setattr(device_link, "probe_setup", no_setup)
    monkeypatch.setattr(device_link, "probe_mdns", no_mdns)
    monkeypatch.setattr(device_link, "_status", status)
    monkeypatch.setattr(device_link, "push_host", no_push)
    monkeypatch.setattr(device_link, "local_ip_toward", lambda ip: "192.168.1.20")
    device_link.note_seen("k7m4qp", "192.168.1.40")
    import asyncio

    linked = asyncio.run(device_link.link_code("K7M4QP"))
    assert linked["base"] == "http://192.168.1.40"
    assert device_link.linked_code() == "K7M4QP"


def test_mdns_status_is_enough_to_link(monkeypatch):
    device_link._seen.clear()
    device_link._linked.clear()

    async def no_setup():
        return None

    async def mdns():
        device_link.note_seen("P9V9ZN", "192.168.0.108")
        return {"code": "P9V9ZN", "live_ip": "192.168.0.108"}

    async def status(base):
        assert base == "http://192.168.0.108"
        return {"code": "P9V9ZN"}

    async def push(host, port=8000):
        return {"ok": True, "host": host, "port": port}

    monkeypatch.setattr(device_link, "probe_setup", no_setup)
    monkeypatch.setattr(device_link, "probe_mdns", mdns)
    monkeypatch.setattr(device_link, "_status", status)
    monkeypatch.setattr(device_link, "push_host", push)
    monkeypatch.setattr(device_link, "local_ip_toward", lambda ip: "192.168.0.20")
    import asyncio

    linked = asyncio.run(device_link.link_code("P9V9ZN"))
    assert linked["base"] == "http://192.168.0.108"


def test_reply_keeps_the_address_from_the_box():
    device_link._seen.clear()
    assert device_link.note_reply("PRITHVI1 P9V9ZN 192.168.0.108", "10.0.0.1")
    rows = device_link.seen_devices()
    assert rows[0]["code"] == "P9V9ZN"
    assert rows[0]["ip"] == "192.168.0.108"
    assert not device_link.note_reply("PRITHVI P9V9ZN http://192.168.0.20:8000", "10.0.0.1")


def test_link_tells_the_box_this_computer(monkeypatch):
    device_link._seen.clear()
    device_link._linked.clear()
    pushed = {}

    async def no_setup():
        return None

    async def no_mdns():
        return None

    async def status(base):
        return {"code": "P9V9ZN"}

    async def push(host, port=8000):
        pushed["host"] = host
        pushed["port"] = port
        return {"ok": True}

    monkeypatch.setattr(device_link, "probe_setup", no_setup)
    monkeypatch.setattr(device_link, "probe_mdns", no_mdns)
    monkeypatch.setattr(device_link, "_status", status)
    monkeypatch.setattr(device_link, "push_host", push)
    monkeypatch.setattr(device_link, "local_ip_toward", lambda ip: "192.168.0.20")
    device_link.note_seen("P9V9ZN", "192.168.0.108")
    import asyncio

    asyncio.run(device_link.link_code("P9V9ZN"))
    assert pushed == {"host": "192.168.0.20", "port": 8000}


def test_link_skips_a_setup_subnet_address(monkeypatch):
    device_link._seen.clear()
    device_link._linked.clear()
    pushed = {}

    async def no_setup():
        return None

    async def no_mdns():
        return None

    async def status(base):
        return {"code": "P9V9ZN"}

    async def push(host, port=8000):
        pushed["host"] = host
        return {"ok": True}

    monkeypatch.setattr(device_link, "probe_setup", no_setup)
    monkeypatch.setattr(device_link, "probe_mdns", no_mdns)
    monkeypatch.setattr(device_link, "_status", status)
    monkeypatch.setattr(device_link, "push_host", push)
    monkeypatch.setattr(device_link, "local_ip_toward", lambda ip: "192.168.4.2")
    device_link.note_seen("P9V9ZN", "192.168.0.108")
    import asyncio

    asyncio.run(device_link.link_code("P9V9ZN"))
    assert pushed == {}


def test_push_host_rejects_the_setup_subnet():
    device_link._linked["base"] = "http://192.168.0.108"
    import asyncio

    with pytest.raises(RuntimeError):
        asyncio.run(device_link.push_host("192.168.4.2"))
