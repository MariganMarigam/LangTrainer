"""Tests for the single-instance guard (release plan C2, used by _bootstrap step 4).

A second LangTrainer launch must refuse to start rather than becoming an
invisible duplicate: two tray icons, two popup timers, two writers on one
SQLite file (which is what makes bug B5 reachable).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QLockFile

import main

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


def _acquire(path) -> QLockFile | None:
    """Acquire a QLockFile the same way main._acquire_single_instance() does."""
    lock = QLockFile(str(path))
    lock.setStaleLockTime(0)
    return lock if lock.tryLock(0) else None


def test_second_acquire_is_refused(tmp_path):
    """The first holder wins; a second acquire against the same file returns None."""
    lock_path = tmp_path / "langtrainer.lock"
    first = _acquire(lock_path)
    assert first is not None, "the first acquire must succeed"
    second = _acquire(lock_path)
    assert second is None, "a second instance acquired the lock"


def test_lock_is_reclaimed_after_unlink(tmp_path):
    """A lock file left behind by a power cut is reclaimed once it is removed.

    The first QLockFile is kept alive on purpose: it would otherwise delete the
    lock file in __del__ and there would be nothing left to remove. Unlinking it
    from under the still-held handle reproduces a crashed process.
    """
    lock_path = tmp_path / "langtrainer.lock"
    stale = _acquire(lock_path)
    assert stale is not None
    assert lock_path.exists()

    lock_path.unlink()

    again = _acquire(lock_path)
    assert again is not None, "a stale lock was not reclaimed"


def test_acquire_single_instance_helper(tmp_path, monkeypatch):
    """main._acquire_single_instance honours the lock and honours logs/ location."""
    logs = tmp_path / "logs"
    monkeypatch.setattr(main, "LOGS_DIR", logs)
    logs.mkdir()

    first = main._acquire_single_instance()
    assert first is not None
    try:
        assert main._acquire_single_instance() is None
    finally:
        first.unlock()


def test_first_launch_creates_missing_logs_dir(tmp_path, monkeypatch):
    """On a clean install logs/ does not exist yet — the lock must still be taken.

    Regression: QLockFile cannot create its own parent directory, so without an
    explicit mkdir the very first launch failed the lock and exited silently.
    """
    logs = tmp_path / "does_not_exist_yet" / "logs"
    monkeypatch.setattr(main, "LOGS_DIR", logs)
    assert not logs.exists()

    lock = main._acquire_single_instance()

    assert lock is not None, "first launch on a clean install could not take the lock"
    assert logs.is_dir()
