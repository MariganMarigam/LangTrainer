"""Tests for config.ensure_dics_extracted() (release plan step A3, A4).

Covers the five frozen-mode extraction cases plus the import-dialog start
directory. The module under test is reloaded per test with a synthetic frozen
environment (sys.frozen + sys._MEIPASS), which is what actually drives
_is_frozen() / BUNDLE_DIR / DICS_DIR.
"""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path

import pytest

import config


@pytest.fixture
def frozen_env(tmp_path, monkeypatch):
    """Reload config as if running from a PyInstaller bundle in tmp_path.

    Yields (bundle_dir, dics_dir). The reload recomputes _is_frozen(),
    BUNDLE_DIR (from sys._MEIPASS) and DICS_DIR (next to sys.executable).
    """
    bundle_dir = tmp_path / "_internal"
    bundle_dir.mkdir()
    exe_dir = tmp_path / "app"
    exe_dir.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle_dir), raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_dir / "LangTrainer"))

    importlib.reload(config)
    yield config.BUNDLE_DIR, config.DICS_DIR

    monkeypatch.undo()
    importlib.reload(config)


def _write_dics(bundle_dir: Path, names=("en-esp.txt", "en-ru.txt")) -> None:
    """Populate the bundled dics/ source folder."""
    src = bundle_dir / config.DICS_BUNDLE_SUBDIR
    src.mkdir(parents=True, exist_ok=True)
    for name in names:
        (src / name).write_text(f"hello\thola\nadios\tbye\n", encoding="utf-8")


def test_not_frozen_returns_true_without_copying(tmp_path):
    """In a dev checkout there is nothing to extract."""
    importlib.reload(config)
    ok, path = config.ensure_dics_extracted()
    assert ok is True
    assert path == str(config.DICS_DIR)


def test_marker_present_skips_copy(frozen_env):
    """An existing marker short-circuits: no copy, no rewriting the marker."""
    bundle_dir, dics_dir = frozen_env
    _write_dics(bundle_dir)
    dics_dir.mkdir(parents=True)
    marker = dics_dir / ".dics-installed"
    marker.write_text("0.0.1", encoding="utf-8")

    ok, path = config.ensure_dics_extracted()

    assert (ok, path) == (True, str(dics_dir))
    assert not list(dics_dir.glob("*.txt")), "copied despite the marker"
    assert marker.read_text(encoding="utf-8") == "0.0.1", "marker was rewritten"


def test_copies_txt_from_bundle_to_dics(frozen_env):
    """Every .txt is copied out of the bundle and the marker is written."""
    bundle_dir, dics_dir = frozen_env
    _write_dics(bundle_dir)

    ok, path = config.ensure_dics_extracted()

    assert (ok, path) == (True, str(dics_dir))
    for name in ("en-esp.txt", "en-ru.txt"):
        assert (dics_dir / name).is_file(), f"{name} was not extracted"
    assert (dics_dir / ".dics-installed").read_text(encoding="utf-8") == config.APP_VERSION


def test_second_call_is_a_noop(frozen_env):
    """A second launch copies nothing and leaves user edits intact."""
    bundle_dir, dics_dir = frozen_env
    _write_dics(bundle_dir)
    config.ensure_dics_extracted()

    # Simulate a user edit of a different size than the bundled original.
    edited = dics_dir / "en-esp.txt"
    edited.write_text("my own words\n", encoding="utf-8")
    before = edited.read_text(encoding="utf-8")
    mtimes = {p.name: p.stat().st_mtime_ns for p in dics_dir.glob("*.txt")}

    ok, path = config.ensure_dics_extracted()

    assert (ok, path) == (True, str(dics_dir))
    assert edited.read_text(encoding="utf-8") == before, "user edit was overwritten"
    assert {p.name: p.stat().st_mtime_ns for p in dics_dir.glob("*.txt")} == mtimes


def test_missing_source_returns_false(frozen_env):
    """A bundle without dics/ reports failure and points at the missing source."""
    _bundle_dir, dics_dir = frozen_env

    ok, path = config.ensure_dics_extracted()

    assert ok is False
    assert Path(path) == _bundle_dir / config.DICS_BUNDLE_SUBDIR
    assert not (dics_dir / ".dics-installed").exists()


def test_unwritable_dics_dir_returns_false_and_writes_no_marker(frozen_env, monkeypatch):
    """mkdir raising OSError -> (False, ...), and no marker, so the next launch retries."""
    bundle_dir, dics_dir = frozen_env
    _write_dics(bundle_dir)

    def boom(self, *args, **kwargs):
        raise OSError(13, "Permission denied")

    monkeypatch.setattr(Path, "mkdir", boom)
    try:
        ok, path = config.ensure_dics_extracted()
    finally:
        monkeypatch.undo()

    assert ok is False
    assert Path(path) == bundle_dir / config.DICS_BUNDLE_SUBDIR
    assert not (dics_dir / ".dics-installed").exists()


def test_identical_size_destination_is_not_overwritten(frozen_env):
    """Same-size destination is left alone, so user edits to same-length files survive."""
    bundle_dir, dics_dir = frozen_env
    _write_dics(bundle_dir)
    dics_dir.mkdir(parents=True)
    preexisting = dics_dir / "en-esp.txt"
    original = "hello\thola\nadios\tbye\n"
    preexisting.write_text(original.replace("hello", "HELLO"), encoding="utf-8")

    ok, _ = config.ensure_dics_extracted()

    assert ok is True
    assert preexisting.read_text(encoding="utf-8").startswith("HELLO")
    assert (dics_dir / "en-ru.txt").is_file(), "missing file was not extracted"


# ── A4: the import dialog start directory ──────────────────────────────────────

def test_add_dialog_start_dir_prefers_dics(tmp_path):
    """A dics/ folder holding .txt files wins; an empty one falls back to home."""
    from ui.add_words_dialog import _default_word_file_dir

    dics = tmp_path / "dics"
    dics.mkdir()
    assert _default_word_file_dir(dics) == Path.home(), "empty dics/ should fall back to home"

    (dics / "en-ru.txt").write_text("a\tb\n", encoding="utf-8")
    assert _default_word_file_dir(dics) == dics, "dics/ with .txt files should be preferred"
