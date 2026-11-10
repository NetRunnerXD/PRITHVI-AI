"""fetch_pn_models must not fail a Render build on HTTP / network errors."""
from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path
from unittest.mock import patch

import scripts.fetch_pn_models as fetch


class _Resp:
    def __init__(self, payload: dict):
        self._raw = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, n: int = -1):
        if n is None or n < 0:
            data, self._raw = self._raw, b""
            return data
        data, self._raw = self._raw[:n], self._raw[n:]
        return data


def test_http_401_returns_zero_and_skips(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PN_ENABLED", "1")
    monkeypatch.setenv("PN_MODEL_DOWNLOAD_TOKEN", "placeholder-token")
    monkeypatch.setenv("PN_MODEL_RELEASE_REPO", "owner/archive")
    monkeypatch.setenv("PN_MODEL_RELEASE_TAG", "pn-models-v7")
    monkeypatch.setenv("PN_V7_MODEL_PATH", str(tmp_path / "pn_nowcast_v7.onnx"))
    monkeypatch.setenv("PN_CORRECT_MODEL_PATH", str(tmp_path / "pn_correct_v6.onnx"))
    monkeypatch.setattr(fetch, "MODELS", tmp_path)
    monkeypatch.setattr(
        fetch,
        "ASSETS",
        (
            ("pn_nowcast_v7.onnx", str(tmp_path / "pn_nowcast_v7.onnx")),
            ("pn_correct_v6.onnx", str(tmp_path / "pn_correct_v6.onnx")),
            ("pn_net_v4.onnx", None),
            ("static_v4.npy", None),
        ),
    )

    def boom(*_a, **_k):
        raise urllib.error.HTTPError(
            "https://api.github.com/repos/owner/archive/releases/tags/pn-models-v7",
            401,
            "Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b""),
        )

    with patch("urllib.request.urlopen", side_effect=boom):
        assert fetch.main() == 0
    err = capsys.readouterr().err
    assert "HTTP 401" in err
    assert "Unauthorized" in err
    assert "placeholder-token" not in err
    assert not (tmp_path / "pn_nowcast_v7.onnx").exists()


def test_http_404_returns_zero(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PN_ENABLED", "1")
    monkeypatch.setenv("PN_MODEL_DOWNLOAD_TOKEN", "placeholder-token")
    monkeypatch.setenv("PN_V7_MODEL_PATH", str(tmp_path / "pn_nowcast_v7.onnx"))
    monkeypatch.setattr(fetch, "MODELS", tmp_path)
    monkeypatch.setattr(
        fetch,
        "ASSETS",
        (("pn_nowcast_v7.onnx", str(tmp_path / "pn_nowcast_v7.onnx")),),
    )

    def boom(*_a, **_k):
        raise urllib.error.HTTPError(
            "https://api.github.com/repos/owner/archive/releases/tags/pn-models-v7",
            404,
            "Not Found",
            hdrs=None,
            fp=io.BytesIO(b""),
        )

    with patch("urllib.request.urlopen", side_effect=boom):
        assert fetch.main() == 0
    err = capsys.readouterr().err
    assert "HTTP 404" in err
    assert "placeholder-token" not in err


def test_successful_download_writes_file(tmp_path, monkeypatch):
    dest = tmp_path / "pn_nowcast_v7.onnx"
    monkeypatch.setenv("PN_ENABLED", "1")
    monkeypatch.setenv("PN_MODEL_DOWNLOAD_TOKEN", "placeholder-token")
    monkeypatch.setenv("PN_V7_MODEL_PATH", str(dest))
    monkeypatch.setattr(fetch, "MODELS", tmp_path)
    monkeypatch.setattr(fetch, "ASSETS", (("pn_nowcast_v7.onnx", str(dest)),))

    payload = {"assets": [{"name": "pn_nowcast_v7.onnx", "url": "https://example.invalid/asset"}]}
    body = b"x" * 2048
    calls = {"n": 0}

    def fake_urlopen(req, timeout=0):
        calls["n"] += 1
        if "releases/tags" in getattr(req, "full_url", str(req)):
            return _Resp(payload)
        class Bin:
            def __enter__(self):
                self._data = body
                return self
            def __exit__(self, *exc):
                return False
            def read(self, n=-1):
                data, self._data = self._data, b""
                return data
        return Bin()

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        assert fetch.main() == 0
    assert dest.is_file() and dest.stat().st_size == 2048
    assert calls["n"] == 2


def test_skip_when_pn_disabled(monkeypatch, capsys):
    monkeypatch.setenv("PN_ENABLED", "0")
    monkeypatch.delenv("PN_MODEL_DOWNLOAD_TOKEN", raising=False)
    with patch("urllib.request.urlopen") as urlopen:
        assert fetch.main() == 0
        urlopen.assert_not_called()
    assert "PN_ENABLED not set; skip" in capsys.readouterr().out


def test_skip_when_pn_enabled_unset(monkeypatch, capsys):
    monkeypatch.delenv("PN_ENABLED", raising=False)
    with patch("urllib.request.urlopen") as urlopen:
        assert fetch.main() == 0
        urlopen.assert_not_called()
    assert "PN_ENABLED not set; skip" in capsys.readouterr().out
