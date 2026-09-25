"""Application configuration."""
import os
import shutil
import sys
from pathlib import Path

APP_NAME = "LangTrainer"
APP_VERSION = "1.0.0"

#: Sub-path of the portable data root that holds the SQLite database.
DATA_SUBDIR = "data"
#: File name of the vocabulary database inside DATA_SUBDIR.
DB_FILENAME = "lang_trainer.db"
#: Marker written into LOGS_DIR once the "your data moved" tray balloon has been
#: shown, so it appears once per install instead of on every launch.
DATA_DIR_NOTICE_MARKER = "data-dir-notice-shown.txt"


def _is_frozen() -> bool:
    """Return True when running inside a PyInstaller bundle (onefile or onedir)."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def _is_appimage() -> bool:
    """Return True when running from an AppImage mount (read-only SquashFS)."""
    return bool(os.environ.get("APPIMAGE"))


def _dir_is_writable(path: Path) -> bool:
    """Return True when `path` exists (or can be created) and accepts new files.

    Must do a real write, not os.access: os.access lies for root and for full
    read-only mounts.

    Args:
        path: Directory to probe. It is created if it does not exist.

    Returns:
        True if a probe file could be created and removed, False on any
        OSError (read-only mount, missing parent, permission denied, path
        under a regular file).
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".lt-write-probe"
        probe.touch()
        probe.unlink()
        return True
    except OSError:
        return False


def _xdg_data_dir() -> Path:
    """Return the XDG user data directory for this app.

    Honours XDG_DATA_HOME when it is set to a non-empty value, which is what
    the XDG Base Directory specification requires; otherwise falls back to
    ~/.local/share.

    Returns:
        ``$XDG_DATA_HOME/LangTrainer`` or ``~/.local/share/LangTrainer``.
    """
    base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / APP_NAME


#: Set by _get_app_root() when BASE_DIR is NOT the portable directory next to
#: the executable, i.e. the app fell back to the XDG data directory. Equals
#: BASE_DIR when set, and is None in the normal portable case so that nothing
#: about a writable install changes.
FALLBACK_DATA_DIR: Path | None = None
#: Set by _get_app_root() when a database is already present at the portable
#: location. The UI must warn about it: falling back silently would show an
#: empty word list and look exactly like losing every word.
PORTABLE_DATA_EXISTS: bool = False


def _get_app_root() -> Path:
    """Get the application root directory, handling PyInstaller frozen mode.

    In development: returns directory of this file (__file__.parent).
    In PyInstaller onefile/onedir (frozen): returns directory of the executable
    (sys.executable.parent) so persistent data (like the SQLite DB) is stored
    next to the executable and survives between runs. This portable contract is
    PRIMARY and is byte-identical to earlier releases whenever the directory
    next to the executable is writable.
    Otherwise (read-only location, or an AppImage mount which is read-only by
    definition): returns the XDG data directory. An AppImage type-2 is a
    SquashFS mount — writing there creates nothing, so the app would start with
    no database and no error at all.

    Side effect: assigns FALLBACK_DATA_DIR and PORTABLE_DATA_EXISTS (see their
    declarations). Both are read by main.py to decide whether to tell the user
    where the data ended up.

    Returns:
        The directory that BASE_DIR, DB_PATH, DICS_DIR and LOGS_DIR derive from.
    """
    global FALLBACK_DATA_DIR, PORTABLE_DATA_EXISTS

    if not _is_frozen():
        PORTABLE_DATA_EXISTS = (Path(__file__).parent / DATA_SUBDIR / DB_FILENAME).is_file()
        return Path(__file__).parent

    exe_dir = Path(sys.executable).parent
    PORTABLE_DATA_EXISTS = (exe_dir / DATA_SUBDIR / DB_FILENAME).is_file()

    # APPIMAGE is checked first and short-circuits the probe: the mount is
    # read-only, so there is no point creating a directory inside it.
    if not _is_appimage() and _dir_is_writable(exe_dir):
        return exe_dir

    FALLBACK_DATA_DIR = _xdg_data_dir()
    return FALLBACK_DATA_DIR


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
DB_PATH = BASE_DIR / DATA_SUBDIR / DB_FILENAME
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
