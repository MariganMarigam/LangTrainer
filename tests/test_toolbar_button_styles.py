"""Tests for toolbar action-button styling consistency.

Verifies that the 'Add Words' and 'Statistics' buttons share the exact
geometry of the 'Clear' button (border-radius, padding, font, min-height)
while keeping their own accent colors — red stays exclusive to Clear.
"""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication

from database.db_manager import DatabaseManager
from ui.main_window import MainWindow
from ui.styles import Colors, action_button_style, destructive_button_style

app = QApplication.instance() or QApplication([])

_GEOMETRY_PROPS = ("border-radius", "padding", "font-size", "font-weight", "min-height")


def _geometry(stylesheet: str) -> dict:
    """Extract geometry-defining properties from a QPushButton stylesheet."""
    props = {}
    for prop in _GEOMETRY_PROPS:
        match = re.search(rf"{prop}:\s*([^;]+);", stylesheet)
        assert match, f"missing {prop} in stylesheet"
        props[prop] = match.group(1).strip()
    return props


def test_action_button_style_matches_destructive_geometry():
    assert _geometry(action_button_style()) == _geometry(destructive_button_style())
    print("test_action_button_style_matches_destructive_geometry: PASS")


def test_destructive_red_stays_exclusive_to_clear():
    assert Colors.RED in destructive_button_style()
    assert Colors.RED not in action_button_style(Colors.BLUE)
    print("test_destructive_red_stays_exclusive_to_clear: PASS")


def test_toolbar_buttons_share_clear_geometry():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = DatabaseManager(path)
    db.connect()
    window = MainWindow(db)
    window.show()
    app.processEvents()
    clear_geo = _geometry(window._clear_btn.styleSheet())
    assert _geometry(window._add_btn.styleSheet()) == clear_geo
    assert _geometry(window._stats_btn.styleSheet()) == clear_geo
    heights = {window._add_btn.height(), window._stats_btn.height(), window._clear_btn.height()}
    assert len(heights) == 1, f"buttons render at different heights: {heights}"
    window.close()
    db.disconnect()
    os.unlink(path)
    print("test_toolbar_buttons_share_clear_geometry: PASS")