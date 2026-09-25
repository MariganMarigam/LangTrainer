"""Tests for the writable-primary / XDG-fallback data directory (v1.0.2).

An AppImage type-2 is a read-only SquashFS mount. Before this change
``config._get_app_root()`` returned ``sys.executable.parent`` unconditionally
and ``DB_PATH``/``DICS_DIR``/``LOGS_DIR`` were derived from it, so an AppImage
started, created nothing, and exited 0 — a running app with no database and no
error.

The portable path stays PRIMARY. XDG is only reached when the directory next to
the executable genuinely cannot be written, or when ``APPIMAGE`` is set (which
is the read-only mount by definition, so it is not even probed).

Each test re-imports ``config`` with a synthetic runtime because ``BASE_DIR``
and the fallback flags are computed at import time.
"""
import importlib
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import config

#: The database file the app creates next to the executable in portable mode.
PORTABLE_DB = Path("data") / "lang_trainer.db"


@pytest.fixture(autouse=True)
def _restore_config():
    """Re-import config with the real environment after every test."""
    yield
    importlib.reload(config)


def _load_config(monkeypatch, *, exe_dir, frozen=True, appimage=None,
                 xdg_data_home=None, home=None, writable=None):
    """Re-import config under a synthetic runtime and return the module.

    Args:
        monkeypatch: pytest monkeypatch fixture; every patch is undone by the
            autouse _restore_config reload plus monkeypatch's own teardown.
        exe_dir: Directory the (synthetic) executable lives in.
        frozen: False to simulate a development checkout.
        appimage: Value for the ``APPIMAGE`` env var, or None to leave it unset.
        xdg_data_home: Value for ``XDG_DATA_HOME``, or None to leave it unset.
        home: Value returned by ``Path.home()``, or None to leave it alone.
        writable: When not None, force ``config._dir_is_writable`` to this
            value and re-derive BASE_DIR. The value is applied AFTER the
            reload because reloading rebuilds the module globals, so a patch
            installed before it would be overwritten.

    Returns:
        The reloaded config module.
    """
    exe_dir = Path(exe_dir)
    exe_dir.mkdir(parents=True, exist_ok=True)
    bundle_dir = exe_dir / "_internal"
    bundle_dir.mkdir(exist_ok=True)

    monkeypatch.setattr(sys, "frozen", frozen, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle_dir), raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_dir / "LangTrainer"))

    monkeypatch.delenv("APPIMAGE", raising=False)
    if appimage is not None:
        monkeypatch.setenv("APPIMAGE", appimage)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    if xdg_data_home is not None:
        monkeypatch.setenv("XDG_DATA_HOME", str(xdg_data_home))
    if home is not None:
        monkeypatch.setattr(Path, "home", staticmethod(lambda: Path(home)))

    importlib.reload(config)

    if writable is not None:
        monkeypatch.setattr(config, "_dir_is_writable", lambda path: writable)
        # _get_app_root() reads module globals at call time, so re-running it
        # reproduces exactly what the import did.
        config.BASE_DIR = config._get_app_root()
    return config


# ── 1. the portable contract is unchanged ──────────────────────────────────

def test_not_frozen_uses_source_dir(monkeypatch, tmp_path):
    """A development checkout keeps using the directory holding config.py."""
    mod = _load_config(monkeypatch, exe_dir=tmp_path / "app", frozen=False)

    assert mod.BASE_DIR == Path(mod.__file__).parent
    assert mod.FALLBACK_DATA_DIR is None


def test_frozen_writable_non_appimage_uses_exe_dir(monkeypatch, tmp_path):
    """The normal frozen case is byte-identical to v1.0.1: data next to the exe."""
    exe_dir = tmp_path / "app"
    mod = _load_config(monkeypatch, exe_dir=exe_dir, writable=True)

    assert mod.BASE_DIR == exe_dir
    assert mod.FALLBACK_DATA_DIR is None
    assert mod.PORTABLE_DATA_EXISTS is False


def test_portable_case_derives_data_dirs_from_exe_dir(monkeypatch, tmp_path):
    """DB_PATH / DICS_DIR / LOGS_DIR still hang off the portable BASE_DIR."""
    exe_dir = tmp_path / "app"
    mod = _load_config(monkeypatch, exe_dir=exe_dir, writable=True)

    assert mod.DB_PATH == exe_dir / "data" / "lang_trainer.db"
    assert mod.DICS_DIR == exe_dir / "dics"
    assert mod.LOGS_DIR == exe_dir / "logs"


# ── 2. the fallback ────────────────────────────────────────────────────────

def test_frozen_unwritable_falls_back_to_xdg(monkeypatch, tmp_path):
    """An unwritable exe dir is the only frozen reason to leave the portable path."""
    exe_dir = tmp_path / "app"
    xdg = tmp_path / "xdgdata"
    mod = _load_config(
        monkeypatch, exe_dir=exe_dir, xdg_data_home=xdg, writable=False,
    )

    assert mod.BASE_DIR == xdg / "LangTrainer"
    assert mod.FALLBACK_DATA_DIR == xdg / "LangTrainer"
    assert mod.FALLBACK_DATA_DIR == mod.BASE_DIR


def test_appimage_uses_xdg_even_when_exe_dir_looks_writable(monkeypatch, tmp_path):
    """APPIMAGE is a read-only mount by definition, so it is not probed at all."""
    exe_dir = tmp_path / "app"
    xdg = tmp_path / "xdgdata"
    mod = _load_config(
        monkeypatch, exe_dir=exe_dir, xdg_data_home=xdg, writable=True,
        appimage="/tmp/.mount_LangTrainer/LangTrainer.AppImage",
    )

    assert mod.BASE_DIR == xdg / "LangTrainer"
    assert mod.FALLBACK_DATA_DIR == xdg / "LangTrainer"


def test_xdg_data_home_unset_uses_local_share(monkeypatch, tmp_path):
    """With no XDG_DATA_HOME the fallback is ~/.local/share/LangTrainer."""
    mod = _load_config(
        monkeypatch, exe_dir=tmp_path / "app", home=tmp_path / "home",
        writable=False,
    )

    assert mod.BASE_DIR == tmp_path / "home" / ".local" / "share" / "LangTrainer"


def test_empty_xdg_data_home_is_treated_as_unset(monkeypatch, tmp_path):
    """An exported-but-empty XDG_DATA_HOME must not produce a relative path."""
    mod = _load_config(
        monkeypatch, exe_dir=tmp_path / "app", home=tmp_path / "home",
        xdg_data_home="", writable=False,
    )

    assert mod.BASE_DIR == tmp_path / "home" / ".local" / "share" / "LangTrainer"


# ── 3. the silent-data-loss guard ───────────────────────────────────────────

def test_portable_data_exists_flag_when_db_is_already_there(monkeypatch, tmp_path):
    """A database at the old path must be reported, never silently ignored."""
    exe_dir = tmp_path / "app"
    (exe_dir / "data").mkdir(parents=True)
    (exe_dir / "data" / "lang_trainer.db").write_bytes(b"SQLite format 3\x00")
    xdg = tmp_path / "xdgdata"

    mod = _load_config(monkeypatch, exe_dir=exe_dir, xdg_data_home=xdg, writable=False)

    assert mod.PORTABLE_DATA_EXISTS is True
    assert mod.FALLBACK_DATA_DIR == xdg / "LangTrainer"


def test_portable_data_exists_is_false_without_a_db(monkeypatch, tmp_path):
    """A fresh AppImage install has nothing at the portable path to warn about."""
    mod = _load_config(
        monkeypatch, exe_dir=tmp_path / "app", xdg_data_home=tmp_path / "xdg",
        writable=False, appimage="/tmp/.mount_x/LangTrainer.AppImage",
    )

    assert mod.PORTABLE_DATA_EXISTS is False


def test_dics_still_extract_into_the_xdg_dir(monkeypatch, tmp_path):
    """ensure_dics_extracted() reads DICS_DIR at call time, so the XDG path works."""
    exe_dir = tmp_path / "app"
    xdg = tmp_path / "xdgdata"
    mod = _load_config(
        monkeypatch, exe_dir=exe_dir, xdg_data_home=xdg, writable=False,
        appimage="/tmp/.mount_x/LangTrainer.AppImage",
    )

    src = mod.BUNDLE_DIR / mod.DICS_BUNDLE_SUBDIR
    src.mkdir(parents=True, exist_ok=True)
    (src / "en-ru.txt").write_text("hello\tпривет\n", encoding="utf-8")

    ok, path = mod.ensure_dics_extracted()

    assert (ok, path) == (True, str(mod.DICS_DIR))
    assert mod.DICS_DIR == xdg / "LangTrainer" / "dics"
    assert (mod.DICS_DIR / "en-ru.txt").read_text(encoding="utf-8").startswith("hello")
    assert (mod.DICS_DIR / ".dics-installed").read_text(encoding="utf-8") == mod.APP_VERSION


# ── 4. _is_appimage / _dir_is_writable ─────────────────────────────────────

def test_is_appimage_reads_the_env_var(monkeypatch, tmp_path):
    monkeypatch.delenv("APPIMAGE", raising=False)
    assert config._is_appimage() is False
    monkeypatch.setenv("APPIMAGE", "/tmp/.mount_x/LangTrainer.AppImage")
    assert config._is_appimage() is True


def test_dir_is_writable_true_for_a_real_directory(tmp_path):
    assert config._dir_is_writable(tmp_path) is True


def test_dir_is_writable_false_under_a_file(tmp_path):
    """A path whose parent is a regular file cannot be created at all."""
    blocker = tmp_path / "a-file"
    blocker.write_text("not a directory", encoding="utf-8")

    assert config._dir_is_writable(blocker / "sub") is False


def test_dir_is_writable_leaves_no_probe_file(tmp_path):
    """The write probe must clean up after itself."""
    target = tmp_path / "probe-target"
    target.mkdir()

    assert config._dir_is_writable(target) is True
    assert list(target.iterdir()) == []
