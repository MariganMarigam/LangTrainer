"""Tests for the tray context-menu entries added in release plan step B4.

Verifies "Open Log Folder" and "Check for Updates" exist exactly once each and
that triggering them emits the matching signal. Phase C wires those signals to
the folder opener and the update flow.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication

from ui.tray import TrayManager

app = QApplication.instance() or QApplication([])


def _actions_containing(menu, needle: str) -> list:
    """Return every menu action whose text contains needle."""
    return [a for a in menu.actions() if needle in a.text()]


def test_open_logs_action_exists_exactly_once():
    """One 'Open Log Folder' entry — a duplicate would double-open the folder."""
    tray = TrayManager()
    tray.setup()
    try:
        assert len(_actions_containing(tray._menu, "Open Log Folder")) == 1
    finally:
        tray.cleanup()


def test_check_updates_action_exists_exactly_once():
    """One 'Check for Updates' entry."""
    tray = TrayManager()
    tray.setup()
    try:
        assert len(_actions_containing(tray._menu, "Check for Updates")) == 1
    finally:
        tray.cleanup()


def test_open_logs_action_emits_signal():
    """Triggering the action emits open_logs_requested exactly once."""
    tray = TrayManager()
    tray.setup()
    emitted = []
    tray.open_logs_requested.connect(lambda: emitted.append(True))
    try:
        _actions_containing(tray._menu, "Open Log Folder")[0].trigger()
        assert emitted == [True]
    finally:
        tray.cleanup()


def test_check_updates_action_emits_signal():
    """Triggering the action emits check_updates_requested exactly once."""
    tray = TrayManager()
    tray.setup()
    emitted = []
    tray.check_updates_requested.connect(lambda: emitted.append(True))
    try:
        _actions_containing(tray._menu, "Check for Updates")[0].trigger()
        assert emitted == [True]
    finally:
        tray.cleanup()


def test_pre_existing_actions_preserved():
    """The new entries must not displace the existing menu."""
    tray = TrayManager()
    tray.setup()
    try:
        for needle in ("Show Trainer", "Hide to Tray", "Clear Database", "Quit"):
            assert len(_actions_containing(tray._menu, needle)) == 1, needle
    finally:
        tray.cleanup()
