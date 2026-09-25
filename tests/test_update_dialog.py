"""Tests for the auto-update dialogs.

Verifies the safety property that matters most: closing either dialog leaves the
non-destructive default ("later"), so the app never restarts or nags behind the
user's back. Also checks the "never" opt-out is persisted and that the styling
reuses the existing ui.styles helpers rather than inventing new CSS.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication

import ui.update_dialog as update_dialog
from ui.styles import Colors, pill_button_style
from ui.update_dialog import (
    RestartConfirmDialog, UpdateAvailableDialog, _human_size,
)

app = QApplication.instance() or QApplication([])


def test_human_size_formats_bytes():
    assert _human_size(0) == "0 B"
    assert _human_size(512) == "512 B"
    assert _human_size(1536) == "1.5 KB"
    assert _human_size(45 * 1024 * 1024) == "45.0 MB"
    assert _human_size(None) == "0 B"
    print("test_human_size_formats_bytes: PASS")


def test_closing_available_dialog_leaves_later():
    dialog = UpdateAvailableDialog("v1.1.0", 45 * 1024 * 1024)
    assert dialog.choice == "later"
    dialog.show()
    app.processEvents()
    dialog.close()
    assert dialog.choice == "later"
    print("test_closing_available_dialog_leaves_later: PASS")


def test_never_persists_disabled_flag(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setattr(update_dialog, "LOGS_DIR", Path(tmp))
        dialog = UpdateAvailableDialog("v1.1.0", 1024)
        dialog._on_never()
        assert dialog.choice == "never"
        state = json.loads((Path(tmp) / "update-check.json").read_text(encoding="utf-8"))
        assert state["disabled"] is True
    print("test_never_persists_disabled_flag: PASS")


def test_download_button_reuses_green_pill_style():
    dialog = UpdateAvailableDialog("v1.1.0", 1024)
    assert dialog.download_btn.styleSheet() == pill_button_style(Colors.GREEN)
    print("test_download_button_reuses_green_pill_style: PASS")


def test_closing_restart_dialog_leaves_later():
    dialog = RestartConfirmDialog("v1.1.0")
    assert dialog.choice == "later"
    dialog.show()
    app.processEvents()
    dialog.close()
    assert dialog.choice == "later"
    print("test_closing_restart_dialog_leaves_later: PASS")


def test_restart_disabled_never_allows_restart():
    dialog = RestartConfirmDialog("v1.1.0", restart_enabled=False)
    assert dialog.restart_btn.isEnabled() is False
    # Even a direct call cannot produce a restart choice while a game is open.
    dialog._on_restart()
    assert dialog.choice == "later"
    print("test_restart_disabled_never_allows_restart: PASS")


def test_restart_enabled_allows_restart():
    dialog = RestartConfirmDialog("v1.1.0", restart_enabled=True)
    assert dialog.restart_btn.isEnabled() is True
    dialog._on_restart()
    assert dialog.choice == "restart"
    print("test_restart_enabled_allows_restart: PASS")
