"""Tests for release-asset selection, digest verification and release lookup.

Every network call is routed through the `http_get_json` seam: no test imports
urllib, monkeypatches urllib.request, or opens a socket. `http_download` is
never exercised here — the digest tests work on a pre-written file.
"""
import hashlib
import inspect
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import services.updater as updater

_ASSETS = [
    {"name": "LangTrainer-1.1.0-linux-x86_64.tar.gz", "size": 10},
    {"name": "LangTrainer-1.1.0-windows-x64.exe", "size": 20},
    {"name": "LangTrainer-1.1.0-macos-arm64.tar.gz", "size": 30},
    {"name": "LangTrainer-1.1.0-checksums.txt", "size": 40},
    {"name": "Other-1.1.0-windows-x64.exe", "size": 50},
]

# Captured at import time, before any test monkeypatches the function away.
_HTTP_GET_JSON_TIMEOUT = inspect.signature(updater.http_get_json).parameters["timeout"].default


def _write_file(directory: Path, data: bytes) -> Path:
    """Create a file with the given bytes and return its path."""
    path = directory / "LangTrainer.exe"
    path.write_bytes(data)
    return path


def test_select_asset_matches_platform_key():
    chosen = updater.select_asset(_ASSETS, "windows-x64")
    assert chosen is not None
    assert chosen["name"] == "LangTrainer-1.1.0-windows-x64.exe"
    # First match wins, and the foreign-product asset is never selected.
    assert updater.select_asset(_ASSETS, "linux-x86_64")["size"] == 10
    assert updater.select_asset(_ASSETS, "macos-arm64")["size"] == 30
    print("test_select_asset_matches_platform_key: PASS")


def test_select_asset_returns_none_for_other_platform():
    assert updater.select_asset(_ASSETS, "windows-arm64") is None
    assert updater.select_asset([], "windows-x64") is None
    # A .txt asset is the manual-verification convenience file, never the
    # installable binary.
    assert updater.select_asset(
        [{"name": "LangTrainer-1.1.0-windows-x64-checksums.txt"}], "windows-x64"
    ) is None
    print("test_select_asset_returns_none_for_other_platform: PASS")


def test_verify_digest_accepts_matching_digest():
    with tempfile.TemporaryDirectory() as tmp:
        data = b"LangTrainer payload"
        path = _write_file(Path(tmp), data)
        digest = hashlib.sha256(data).hexdigest()
        ok, why = updater.verify_digest(path, {"digest": f"sha256:{digest}"})
        assert ok is True
        assert why == digest
    print("test_verify_digest_accepts_matching_digest: PASS")


def test_verify_digest_rejects_mismatch():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_file(Path(tmp), b"LangTrainer payload")
        ok, why = updater.verify_digest(path, {"digest": "sha256:" + "0" * 64})
        assert ok is False
        assert "mismatch" in why
    print("test_verify_digest_rejects_mismatch: PASS")


def test_verify_digest_fails_without_sha256_digest():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_file(Path(tmp), b"payload")
        for asset in ({}, {"digest": None}, {"digest": "md5:abc"}, {"digest": 123}):
            ok, why = updater.verify_digest(path, asset)
            assert ok is False
            assert why == "release asset has no sha256 digest"
    print("test_verify_digest_fails_without_sha256_digest: PASS")


def test_parse_checksums_handles_sha256sum_format():
    text = (
        "# a comment\n"
        "aaaa1111bbbb2222cccc3333dddd4444eeee5555ffff6666aabb7777cccc8888  LangTrainer.exe\n"
        "0000111122223333444455556666777788889999aaaabbbbccccddddeeeeffff *other.bin\n"
        "not-a-checksum-line\n"
    )
    parsed = updater.parse_checksums(text)
    assert parsed["LangTrainer.exe"].startswith("aaaa1111")
    assert parsed["other.bin"].startswith("00001111")
    assert len(parsed) == 2
    print("test_parse_checksums_handles_sha256sum_format: PASS")


def test_fetch_latest_release_returns_none_when_network_fails(monkeypatch):
    # http_get_json swallows every exception, including URLError and HTTPError.
    monkeypatch.setattr(updater, "http_get_json", lambda url, **kw: None)
    assert updater.fetch_latest_release("1.0.0") is None
    print("test_fetch_latest_release_returns_none_when_network_fails: PASS")


def test_fetch_latest_release_returns_none_on_404(monkeypatch):
    # A 404 (no releases published yet) is the normal Day-1 path: http_get_json
    # maps it to None, so the caller must treat None as "nothing to do" and
    # stay silent. That is exactly what this asserts.
    monkeypatch.setattr(updater, "http_get_json", lambda url, **kw: None)
    assert updater.fetch_latest_release("1.0.0") is None
    print("test_fetch_latest_release_returns_none_on_404: PASS")


def test_fetch_latest_release_returns_none_when_tag_not_newer(monkeypatch):
    monkeypatch.setattr(
        updater, "http_get_json",
        lambda url, **kw: {"tag_name": "v0.9.0", "assets": []},
    )
    assert updater.fetch_latest_release("1.0.0") is None
    # Same version is not an update either.
    monkeypatch.setattr(
        updater, "http_get_json",
        lambda url, **kw: {"tag_name": "1.0.0", "assets": []},
    )
    assert updater.fetch_latest_release("1.0.0") is None
    print("test_fetch_latest_release_returns_none_when_tag_not_newer: PASS")


def test_fetch_latest_release_returns_release_when_newer(monkeypatch):
    release = {"tag_name": "v1.1.0", "assets": _ASSETS}
    seen = {}

    def _fake_get(url, **kwargs):
        seen["url"] = url
        return release

    monkeypatch.setattr(updater, "http_get_json", _fake_get)
    assert updater.fetch_latest_release("1.0.0") is release
    assert seen["url"] == (
        "https://api.github.com/repos/MariganMarigam/LangTrainer/releases/latest"
    )
    # The check runs on the GUI thread, so the request must stay bounded even
    # though fetch_latest_release relies on the default rather than passing it.
    assert _HTTP_GET_JSON_TIMEOUT == updater.HTTP_TIMEOUT_SECONDS == 8
    print("test_fetch_latest_release_returns_release_when_newer: PASS")
