"""Application configuration."""
import shutil
import sys
from pathlib import Path

APP_NAME = "LangTrainer"
APP_VERSION = "1.0.0"


def _is_frozen() -> bool:
    """Return True when running inside a PyInstaller bundle (onefile or onedir)."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def _get_app_root() -> Path:
    """Get the application root directory, handling PyInstaller frozen mode.

    In development: returns directory of this file (__file__.parent).
    In PyInstaller onefile/onedir (frozen): returns directory of the executable
    (sys.executable.parent) so persistent data (like the SQLite DB) is stored
    next to the executable and survives between runs.
    """
    if _is_frozen():
        # PyInstaller frozen mode (onefile/onedir) - store data next to exe
        return Path(sys.executable).parent
    return Path(__file__).parent


def _get_bundle_dir() -> Path:
    """Get the read-only bundle directory shipped inside the executable.

    onefile: sys._MEIPASS is a temp dir PyInstaller unpacks to.
    onedir:  sys._MEIPASS is the _internal folder next to the executable.
    Development: the source tree itself.
    """
    if _is_frozen():
        return Path(sys._MEIPASS)
    return Path(__file__).parent


BASE_DIR = _get_app_root()
DB_PATH = BASE_DIR / "data" / "lang_trainer.db"
BUNDLE_DIR = _get_bundle_dir()
DICS_DIR = BASE_DIR / "dics"
LOGS_DIR = BASE_DIR / "logs"
DICS_BUNDLE_SUBDIR = "dics"


def ensure_dics_extracted() -> tuple[bool, str]:
    """Copy the bundled dictionaries next to the executable on first frozen launch.

    Returns (ok, path) where path is the directory that should hold the
    dictionaries: DICS_DIR on success, or the source directory that was
    missing/unusable on failure.

    The DICS_DIR/".dics-installed" marker short-circuits every later launch, so a
    dictionary added in a *newer app version* is NOT installed into an existing
    installation. That is intentional: dictionaries ship with a new app version,
    never through the updater. It also preserves user edits to the .txt files —
    a destination file of identical size is left untouched.

    Never raises: every failure path returns (False, ...).
    """
    if not _is_frozen():
        return True, str(DICS_DIR)

    src = BUNDLE_DIR / DICS_BUNDLE_SUBDIR
    if not src.is_dir():
        return False, str(src)

    try:
        DICS_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False, str(src)

    marker = DICS_DIR / ".dics-installed"
    if marker.exists():
        return True, str(DICS_DIR)

    try:
        for src_file in src.glob("*.txt"):
            dest_file = DICS_DIR / src_file.name
            # Identical size == already installed (or user-edited): leave it alone.
            if dest_file.exists() and dest_file.stat().st_size == src_file.stat().st_size:
                continue
            shutil.copy2(src_file, dest_file)
    except OSError:
        # No marker: the next launch retries the copy.
        return False, str(DICS_DIR)

    try:
        marker.write_text(APP_VERSION, encoding="utf-8")
    except OSError:
        return False, str(DICS_DIR)

    return True, str(DICS_DIR)

TIMER_MIN = 1
TIMER_MAX = 30
TIMER_DEFAULT = 3

WORDS_PER_POPUP = 1
TRANSLATION_OPTIONS = 3
DEFAULT_WORDS_PER_GAME = 10
