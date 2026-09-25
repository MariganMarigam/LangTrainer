"""Regression tests for main._run_update_flow.

The auto-update flow runs from a one-shot ``QTimer.singleShot(1500, ...)``
callback, so a NameError on its hot path does not surface at start-up: the app
launches, creates its database, looks healthy, and only then logs a traceback
into logs/langtrainer-crash.log. In a frozen build that means the defect reaches
real users with a green test suite, which is exactly what happened --
``main.py`` read a bare ``APP_VERSION`` that line 90 never imported, so every
launch whose 24 h throttle had expired died in the updater instead of checking
for an update. It shipped in v1.0.0, v1.0.1 and v1.0.2.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import main
from config import APP_VERSION


def _stub_update_flow(tmp_path, monkeypatch, *, release, should_check=True,
                      disabled=False, version_dir_disabled=False):
    """Drive _run_update_flow with the network and the UI stubbed out.

    Returns the dict that records what the flow asked the updater for.
    """
    state = tmp_path / "updater-state.json"
    seen: dict[str, object] = {}

    monkeypatch.setattr(main, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(main.updater, "STATE_FILENAME", "updater-state.json")
    monkeypatch.setattr(main.updater, "load_state", lambda _p: {"disabled": disabled})
    monkeypatch.setattr(
        main.updater, "update_disabled", lambda _p: version_dir_disabled,
    )
    monkeypatch.setattr(
        main.updater, "should_check", lambda _p: should_check,
    )

    def _fake_fetch(current_version):
        seen["current_version"] = current_version
        return release

    monkeypatch.setattr(main.updater, "fetch_latest_release", _fake_fetch)
    monkeypatch.setattr(
        main.updater, "select_asset", lambda assets, key: assets[0] if assets else None,
    )
    monkeypatch.setattr(main.updater, "platform_asset_key", lambda: "linux-x86_64")
    monkeypatch.setattr(main.updater, "record_check", lambda _p: None)

    offered: dict[str, object] = {}
    monkeypatch.setattr(
        main, "_offer_update",
        lambda app, db, tray, win, timer, rel, asset, force: offered.update(
            {"release": rel, "asset": asset, "force": force},
        ),
    )

    main._run_update_flow(
        app=None, db=None, tray=None, main_window=None, timer_service=None,
        force=False,
    )
    seen["state_file"] = state
    seen["offered"] = offered
    return seen


def test_update_flow_passes_the_app_version_not_an_undefined_name(
    tmp_path, monkeypatch
):
    """The version must reach fetch_latest_release as a real string.

    A bare `APP_VERSION` in main's namespace raises NameError here instead.
    """
    seen = _stub_update_flow(
        tmp_path, monkeypatch,
        release={"tag_name": "v9.9.9", "assets": [{"name": "app"}]},
    )
    assert seen["current_version"] == APP_VERSION
    assert isinstance(seen["current_version"], str)
    assert seen["current_version"], "the running version must not be empty"


def test_update_flow_offers_the_asset_when_a_newer_release_exists(
    tmp_path, monkeypatch
):
    """End to end through the stubbed network: the update is offered."""
    release = {"tag_name": "v9.9.9", "assets": [{"name": "LangTrainer-linux-x86_64.AppImage"}]}
    seen = _stub_update_flow(tmp_path, monkeypatch, release=release)
    assert seen["offered"]["release"] is release
    assert seen["offered"]["asset"]["name"].endswith(".AppImage")
    assert seen["offered"]["force"] is False


def test_update_flow_stays_silent_when_throttled(tmp_path, monkeypatch):
    """A throttled install must not even ask GitHub."""
    seen = _stub_update_flow(
        tmp_path, monkeypatch,
        release={"tag_name": "v9.9.9", "assets": [{"name": "app"}]},
        should_check=False,
    )
    assert "current_version" not in seen
    assert seen["offered"] == {}


def test_update_flow_stays_silent_when_opted_out(tmp_path, monkeypatch):
    """`disabled` in the state file wins unless the user forces the check."""
    seen = _stub_update_flow(
        tmp_path, monkeypatch,
        release={"tag_name": "v9.9.9", "assets": [{"name": "app"}]},
        disabled=True,
    )
    assert "current_version" not in seen
    assert seen["offered"] == {}


def test_main_module_exposes_no_bare_app_version_reference():
    """Guard the mistake itself, not just this one call site.

    main.py imports APP_NAME/LOGS_DIR from config by name, so a future edit
    that reaches for the bare APP_VERSION again would compile and pass every
    other test. The only names main may use are the ones it actually imports.
    """
    assert not hasattr(main, "APP_VERSION"), (
        "main must not gain a bare APP_VERSION name: the module does not import "
        "it, and reading it bare raises NameError at runtime. Use "
        "config.APP_VERSION instead."
    )
    assert main.config.APP_VERSION == APP_VERSION


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
