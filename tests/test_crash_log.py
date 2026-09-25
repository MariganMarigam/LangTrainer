"""Tests for the crash hook and the guarded startup path (release plan B1, B2).

_importing this module imports `main`, which installs the crash hook as a side
effect. _bootstrap() itself is NEVER called here: it would take the real
single-instance lock and start the real QApplication. Each test calls the
helpers directly or monkeypatches main.main.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main
import pytest

from PySide6.QtWidgets import QApplication, QMessageBox

app = QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def preserve_excepthook():
    """Keep main's installed crash hook across tests that swap sys.excepthook."""
    saved = sys.excepthook
    yield
    sys.excepthook = saved


@pytest.fixture
def crash_log(tmp_path, monkeypatch):
    """Point main._append_crash_log's LOGS_DIR at a temp dir. Yields the log path."""
    logs = tmp_path / "logs"
    monkeypatch.setattr(main, "LOGS_DIR", logs)
    yield logs / "langtrainer-crash.log"


def _raise_boom():
    raise ValueError("boom")


def test_hook_writes_traceback(crash_log):
    """The hook logs the exception type, message and traceback."""
    main._install_crash_hook()
    try:
        _raise_boom()
    except ValueError:
        sys.excepthook(*sys.exc_info())

    text = crash_log.read_text(encoding="utf-8")
    assert "boom" in text
    assert "ValueError" in text
    assert "Traceback (most recent call last)" in text


def test_hook_delegates_to_previous_hook(crash_log):
    """The original excepthook is still called, so the native dialog appears."""
    seen = []
    previous = sys.excepthook  # main's installed hook, restored by the autouse fixture
    sys.excepthook = lambda *exc_info: seen.append(exc_info)
    main._install_crash_hook()
    installed = sys.excepthook
    try:
        _raise_boom()
    except ValueError:
        installed(*sys.exc_info())

    assert len(seen) == 1, "the sentinel excepthook was not called"
    assert seen[0][0] is ValueError
    assert "boom" in crash_log.read_text(encoding="utf-8")


def test_hook_survives_unwritable_logs_dir(tmp_path, monkeypatch):
    """An unwritable LOGS_DIR must never propagate out of the hook."""
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    monkeypatch.setattr(main, "LOGS_DIR", blocker / "logs")

    main._install_crash_hook()
    try:
        _raise_boom()
    except ValueError:
        sys.excepthook(*sys.exc_info())  # must not raise


def test_append_crash_log_truncates_oversized_file(tmp_path, monkeypatch):
    """Past 1 MiB only the last 256 KiB is kept, so a crash loop cannot fill the disk."""
    logs = tmp_path / "logs"
    monkeypatch.setattr(main, "LOGS_DIR", logs)
    log_path = logs / "langtrainer-crash.log"

    main._append_crash_log("HEAD" + "x" * (1024 * 1024))
    main._append_crash_log("TAIL-MARKER")

    assert log_path.stat().st_size <= 1024 * 1024 + len("TAIL-MARKER")
    assert "TAIL-MARKER" in log_path.read_text(encoding="utf-8", errors="replace")
    assert "HEAD" not in log_path.read_text(encoding="utf-8", errors="replace")


def test_bootstrap_reports_startup_failure(crash_log, monkeypatch):
    """A crash in main() is logged AND surfaced in a QMessageBox, then exits 1."""
    def boom():
        raise RuntimeError("nope")

    monkeypatch.setattr(main, "main", boom)
    monkeypatch.setattr(main, "_acquire_single_instance", lambda: object())
    monkeypatch.setattr(sys, "argv", ["LangTrainer"])

    shown = []
    monkeypatch.setattr(
        QMessageBox, "critical",
        staticmethod(lambda parent, title, text: shown.append((title, text))),
    )

    with pytest.raises(SystemExit) as excinfo:
        main._bootstrap()

    assert excinfo.value.code == 1
    assert len(shown) == 1, "no QMessageBox was shown"
    title, text = shown[0]
    assert title == f"{main.APP_NAME} could not start"
    assert "nope" in text, "the RuntimeError text did not reach the dialog"
    assert "langtrainer-crash.log" in text

    logged = crash_log.read_text(encoding="utf-8")
    assert "RuntimeError" in logged and "nope" in logged


def test_bootstrap_reraises_systemexit(crash_log, monkeypatch):
    """A clean sys.exit(0) from main() must not become a crash dialog."""
    def clean_exit():
        raise SystemExit(0)

    monkeypatch.setattr(main, "main", clean_exit)
    monkeypatch.setattr(main, "_acquire_single_instance", lambda: object())
    monkeypatch.setattr(sys, "argv", ["LangTrainer"])

    shown = []
    monkeypatch.setattr(
        QMessageBox, "critical",
        staticmethod(lambda parent, title, text: shown.append((title, text))),
    )

    with pytest.raises(SystemExit) as excinfo:
        main._bootstrap()

    assert excinfo.value.code == 0
    assert shown == [], "a clean exit was reported as a crash"


def test_bootstrap_returns_when_lock_is_taken(crash_log, monkeypatch):
    """A second instance logs and returns without starting main()."""
    monkeypatch.setattr(main, "_acquire_single_instance", lambda: None)
    monkeypatch.setattr(sys, "argv", ["LangTrainer"])
    monkeypatch.setattr(main, "main", lambda: pytest.fail("main() must not run"))

    main._bootstrap()  # no SystemExit

    assert "already running" in crash_log.read_text(encoding="utf-8")
