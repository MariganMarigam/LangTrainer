"""Tests for bug B5 — the SRS column migration must not swallow a locked database.

`DatabaseManager._migrate_srs_columns()` used a bare `except sqlite3.OperationalError:
pass`, so a "database is locked" (a second instance holding the file) silently
skipped the migration. The failure only surfaced much later as
"no such column: ease_factor" deep inside the SRS game, far from the cause.

Only "duplicate column name" is benign. Everything else must propagate.
"""
import os
import sqlite3
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DatabaseManager


class _RaisingCursor:
    """Cursor stand-in whose execute() always raises the configured error."""

    def __init__(self, error: sqlite3.OperationalError) -> None:
        self._error = error
        self.calls: list[str] = []

    def execute(self, sql: str):
        self.calls.append(sql)
        raise self._error


def _manager_with_failing_cursor(message: str) -> DatabaseManager:
    """Return a connected DatabaseManager whose cursor always raises."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = DatabaseManager(path)
    db.connect()
    db.cursor = _RaisingCursor(sqlite3.OperationalError(message))
    return db


def test_duplicate_column_does_not_propagate():
    """The benign case: every column already exists, so the loop just continues."""
    db = _manager_with_failing_cursor("duplicate column name: ease_factor")
    try:
        db._migrate_srs_columns()  # must NOT raise
        # All four SRS columns were attempted, not aborted after the first.
        assert len(db.cursor.calls) == 4, db.cursor.calls
    finally:
        db.disconnect()
        os.unlink(db.db_path)
    print("test_duplicate_column_does_not_propagate: PASS")


def test_locked_database_propagates():
    """The dangerous case: a lock means the migration did NOT happen — raise."""
    db = _manager_with_failing_cursor("database is locked")
    try:
        with pytest.raises(sqlite3.OperationalError) as excinfo:
            db._migrate_srs_columns()
        assert "database is locked" in str(excinfo.value)
    finally:
        db.disconnect()
        os.unlink(db.db_path)
    print("test_locked_database_propagates: PASS")
