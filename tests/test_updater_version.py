"""Tests for version parsing, comparison and the update-check throttle.

Covers services/updater.py: parse_version, is_newer, should_check, record_check
and update_disabled. No network access: every function tested here is pure or
filesystem-local.
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import services.updater as updater


def test_parse_version_strips_v_prefix():
    assert updater.parse_version("v1.2.3") == (1, 2, 3)
    assert updater.parse_version("V2.0.0") == (2, 0, 0)
    assert updater.parse_version("  v0.9.1  ") == (0, 9, 1)
    print("test_parse_version_strips_v_prefix: PASS")


def test_parse_version_handles_missing_minor_and_empty():
    assert updater.parse_version("1") == (1,)
    assert updater.parse_version("") == ()
    assert updater.parse_version("v") == ()
    assert updater.parse_version("   ") == ()
    # A trailing non-numeric part contributes its leading digits only.
    assert updater.parse_version("1.0.0rc1") == (1, 0, 0)
    print("test_parse_version_handles_missing_minor_and_empty: PASS")


def test_is_newer_true_for_higher_patch():
    assert updater.is_newer("1.0.1", "1.0.0") is True
    assert updater.is_newer("v1.1.0", "1.0.9") is True
    print("test_is_newer_true_for_higher_patch: PASS")


def test_is_newer_false_for_equal_after_padding():
    assert updater.is_newer("1.0.0", "1.0") is False
    assert updater.is_newer("1.0", "1.0.0") is False
    assert updater.is_newer("1.0.0", "1.0.0") is False
    print("test_is_newer_false_for_equal_after_padding: PASS")


def test_is_newer_false_for_lower_or_unparsable():
    assert updater.is_newer("1.0.0", "1.0.1") is False
    assert updater.is_newer("0.9.0", "1.0.0") is False
    # Either side unparsable is never "newer".
    assert updater.is_newer("", "1.0.0") is False
    assert updater.is_newer("1.0.0", "") is False
    print("test_is_newer_false_for_lower_or_unparsable: PASS")


def test_should_check_respects_24h_interval():
    with tempfile.TemporaryDirectory() as tmp:
        state = Path(tmp) / updater.STATE_FILENAME
        now = time.time()

        # Checked 100 s ago -> not yet.
        updater.record_check(state)
        assert updater.should_check(state, now=now + 100) is False

        # Checked 90 000 s ago (> 86 400) -> due again.
        assert updater.should_check(state, now=now + 90000) is True

        # No state at all -> due immediately.
        state.unlink()
        assert updater.should_check(state, now=now) is True
    print("test_should_check_respects_24h_interval: PASS")


def test_record_check_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        state = Path(tmp) / updater.STATE_FILENAME
        updater.record_check(state, disabled=True)
        data = json.loads(state.read_text(encoding="utf-8"))
        assert data["disabled"] is True
        assert data["last_check"] > 0
        assert updater.load_state(state) == data
    # An unreadable state file must not raise.
    assert updater.load_state(Path("/nonexistent-dir-xyz/state.json")) == {}
    print("test_record_check_roundtrip: PASS")


def test_update_disabled_detects_marker_file(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        exe_dir = Path(tmp)
        monkeypatch.delenv("LANGTRAINER_NO_SELF_UPDATE", raising=False)
        assert updater.update_disabled(exe_dir) is False
        (exe_dir / updater.NO_UPDATE_FILE).write_text("off", encoding="utf-8")
        assert updater.update_disabled(exe_dir) is True
    print("test_update_disabled_detects_marker_file: PASS")


def test_update_disabled_detects_env_var(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("LANGTRAINER_NO_SELF_UPDATE", "1")
        assert updater.update_disabled(Path(tmp)) is True
        monkeypatch.setenv("LANGTRAINER_NO_SELF_UPDATE", "0")
        assert updater.update_disabled(Path(tmp)) is False
    print("test_update_disabled_detects_env_var: PASS")
