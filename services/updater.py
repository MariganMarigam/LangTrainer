"""Auto-update support for LangTrainer — GitHub Releases, stdlib only.

This module MUST NOT import a third-party package. It is imported by
``main.py`` before ``QApplication`` exists (the ``--complete-update`` completer
path runs with no GUI at all), and any extra import would become a frozen
runtime dependency of the packaged app. That is why version parsing is
hand-rolled instead of using ``packaging``.

Scope (locked decision):

* **Windows** — download, verify the SHA-256 digest published in the GitHub
  release JSON, self-replace the executable, relaunch.
* **macOS / Linux** — notify and open the Releases page. No self-install:
  a macOS ``.app`` is a directory bundle that ``os.replace`` cannot replace,
  and ``sys.executable`` points *inside* the bundle.

The trust anchor is ``release["assets"][i]["digest"]`` (``"sha256:<hex>"``).
It ships in the same API response as the asset URL, so verifying against it
costs zero extra fetches and introduces no second trust domain.
``checksums.txt`` is a convenience asset for manual verification only and is
never a prerequisite for installing.

Every function here is written to never raise on the paths that run before the
GUI exists; the ones that report status do so through a return value.
"""
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Callable, Optional

# ── Constants ───────────────────────────────────────────────────────────────
GITHUB_API = "https://api.github.com"
# GitHub answers 403 to any request without a User-Agent.
USER_AGENT = "LangTrainer-UpdateCheck/1.0 (+https://github.com/MariganMarigam/LangTrainer)"
REPO_OWNER = "MariganMarigam"
REPO_NAME = "LangTrainer"

#: Minimum seconds between two automatic update checks (24 h).
CHECK_INTERVAL_SECONDS = 86400
#: Network timeout for the release check. Must be short: the check runs on the
#: GUI thread and the app stays fully usable meanwhile.
HTTP_TIMEOUT_SECONDS = 8

#: Drop this file next to the executable (or set LANGTRAINER_NO_SELF_UPDATE=1)
#: to suppress updates entirely.
NO_UPDATE_FILE = "NO_AUTOUPDATE"
#: Name of the throttle-state file inside logs/.
STATE_FILENAME = "update-check.json"

_CHUNK_SIZE = 64 * 1024
_LEADING_DIGITS = re.compile(r"\d+")

# Windows process constants, defined locally so this module needs no import
# that only exists on win32.
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_STILL_ACTIVE = 259
_ERROR_INVALID_PARAMETER = 87
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200


# ── Platform ────────────────────────────────────────────────────────────────
def exe_name() -> str:
    """Return the file name of the application executable on this platform."""
    return "LangTrainer.exe" if sys.platform == "win32" else "LangTrainer"


def platform_asset_key() -> str:
    """Return the release-asset key matching the running platform.

    Returns:
        ``"windows-x64"``, ``"macos-arm64"``, ``"macos-x86_64"`` (Intel Macs)
        or ``"linux-x86_64"``.
    """
    if sys.platform == "win32":
        return "windows-x64"
    if sys.platform == "darwin":
        machine = platform.machine().lower()
        if machine in ("arm64", "aarch64"):
            return "macos-arm64"
        return "macos-x86_64"
    return "linux-x86_64"


def self_install_supported() -> bool:
    """Return True when this platform may replace its own executable.

    Only Windows: on macOS the executable lives inside a ``.app`` directory
    bundle that ``os.replace`` cannot replace, and on Linux the executable may
    be owned by root while the data directory is user-writable.
    """
    return sys.platform == "win32"


def release_page_url() -> str:
    """Return the human-facing Releases page URL."""
    return f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/latest"


def update_disabled(exe_dir: Path) -> bool:
    """Return True when updates are disabled by marker file or env var.

    Args:
        exe_dir: Directory holding the executable.

    Returns:
        True if ``NO_AUTOUPDATE`` is present next to the executable, or the
        environment variable ``LANGTRAINER_NO_SELF_UPDATE`` equals ``"1"``.
    """
    try:
        if (Path(exe_dir) / NO_UPDATE_FILE).is_file():
            return True
    except OSError:
        pass
    return os.environ.get("LANGTRAINER_NO_SELF_UPDATE") == "1"


# ── Versions ────────────────────────────────────────────────────────────────
def parse_version(text: str) -> tuple[int, ...]:
    """Parse a version string into a tuple of integers.

    Strips a leading ``v``/``V``, keeps the leading digits of every
    ``.``-separated part and drops non-numeric parts.

    Args:
        text: Version string, e.g. ``"v1.2.3"``, ``"1.0"``, ``"1.0.0rc1"``.

    Returns:
        Tuple of ints. An empty input returns an empty tuple.

    Examples:
        >>> parse_version("v1.2.3")
        (1, 2, 3)
        >>> parse_version("")
        ()
    """
    if not isinstance(text, str):
        return ()
    cleaned = text.strip().lstrip("vV").strip()
    if not cleaned:
        return ()
    parts: list[int] = []
    for chunk in cleaned.split("."):
        match = _LEADING_DIGITS.match(chunk.strip())
        if match:
            parts.append(int(match.group(0)))
    return tuple(parts)


def is_newer(remote: str, local: str) -> bool:
    """Return True when ``remote`` is a strictly newer version than ``local``.

    Shorter versions are zero-padded, so ``"1.0.0"`` vs ``"1.0"`` is not newer.
    An unparsable version on either side is never newer.

    Args:
        remote: Version offered by the release.
        local: Version currently installed.

    Returns:
        True only when every component of ``remote`` is greater.
    """
    r = parse_version(remote)
    l = parse_version(local)
    if not r or not l:
        return False
    width = max(len(r), len(l))
    r_padded = r + (0,) * (width - len(r))
    l_padded = l + (0,) * (width - len(l))
    return r_padded > l_padded


# ── Network ─────────────────────────────────────────────────────────────────
def _open(url: str, timeout: int):
    """Open ``url`` with the mandatory GitHub headers, or return None.

    Args:
        url: Absolute URL to fetch.
        timeout: Socket timeout in seconds.

    Returns:
        An open response object, or None if anything at all went wrong.
    """
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except Exception:
        return None


def http_get_json(url: str, timeout: int = HTTP_TIMEOUT_SECONDS) -> Optional[dict]:
    """GET a URL and parse the body as a JSON object.

    Args:
        url: Absolute URL to fetch.
        timeout: Socket timeout in seconds.

    Returns:
        The decoded object, or None on any failure — including a 404, which is
        the normal Day-1 path while no release has been published yet.
    """
    response = _open(url, timeout)
    if response is None:
        return None
    try:
        with response:
            raw = response.read()
        data = json.loads(raw.decode("utf-8", errors="replace"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def http_get_text(url: str, timeout: int = HTTP_TIMEOUT_SECONDS) -> Optional[str]:
    """GET a URL and return the body as text.

    Args:
        url: Absolute URL to fetch.
        timeout: Socket timeout in seconds.

    Returns:
        The decoded body, or None on any failure.
    """
    response = _open(url, timeout)
    if response is None:
        return None
    try:
        with response:
            return response.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def http_download(url: str, dest: Path, timeout: int = 300,
                  progress: Optional[Callable[[int, int], None]] = None) -> bool:
    """Stream a URL to ``dest``.

    Args:
        url: Absolute URL to download.
        dest: Destination path. A partial file is removed on any failure.
        timeout: Socket timeout in seconds.
        progress: Optional callback ``progress(downloaded, total)``. ``total``
            is 0 when the server sends no Content-Length.

    Returns:
        True on success, False on any failure (with ``dest`` unlinked).
    """
    dest = Path(dest)
    downloaded = 0
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        response = _open(url, timeout)
        if response is None:
            raise OSError(f"could not open {url}")
        with response:
            total = 0
            try:
                total = int(response.headers.get("Content-Length") or 0)
            except (TypeError, ValueError):
                total = 0
            if progress is not None:
                progress(0, total)
            with open(dest, "wb") as handle:
                while True:
                    chunk = response.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if progress is not None:
                        progress(downloaded, total)
        # PyInstaller sets the exec bit in dist/ at BUILD time; nothing sets it
        # at DOWNLOAD time, so a file written with open(...,'wb') is 0644 and a
        # relaunched binary is not executable on POSIX (bug B1). Windows-only
        # self-install makes this unreachable for shipped users, but the helper
        # is still correct.
        if os.name != "nt":
            os.chmod(dest, 0o755)
        return True
    except Exception:
        try:
            if dest.exists():
                dest.unlink()
        except OSError:
            pass
        return False


# ── Release lookup ──────────────────────────────────────────────────────────
def fetch_latest_release(current_version: str) -> Optional[dict]:
    """Fetch the newest published release, if it is newer than ours.

    Args:
        current_version: The version running right now.

    Returns:
        The release object, or None when the network failed, no release is
        published yet (404), or the newest tag is not newer than ours.
    """
    url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
    data = http_get_json(url)
    if not data:
        return None
    tag = data.get("tag_name")
    if not isinstance(tag, str) or not is_newer(tag, current_version):
        return None
    return data


def select_asset(assets: list, key: str) -> Optional[dict]:
    """Pick the release asset matching this platform.

    Args:
        assets: The ``assets`` list of a GitHub release object.
        key: Platform key from :func:`platform_asset_key`.

    Returns:
        The first matching asset dict, or None. ``.txt`` assets are skipped:
        they are the optional manual-verification convenience file, never the
        installable binary.
    """
    if not isinstance(assets, list):
        return None
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = asset.get("name")
        if not isinstance(name, str):
            continue
        if name.endswith(".txt"):
            continue
        if name.startswith("LangTrainer-") and key in name:
            return asset
    return None


# ── Integrity ───────────────────────────────────────────────────────────────
def sha256_file(path: Path) -> str:
    """Return the lowercase hex SHA-256 digest of a file.

    Args:
        path: File to hash.

    Returns:
        64-character hex digest.

    Raises:
        OSError: If the file cannot be read.
    """
    digest = hashlib.sha256()
    with open(Path(path), "rb") as handle:
        while True:
            chunk = handle.read(_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def parse_checksums(text: str) -> dict:
    """Parse a ``sha256sum``-style checksum list.

    Used only for the optional ``checksums.txt`` convenience asset that a user
    may verify manually. It is never a prerequisite for installing.

    Args:
        text: Contents of a checksums file, lines of ``"<hex>  <name>"``.

    Returns:
        Mapping of file name to hex digest. Unparsable lines are skipped.
    """
    result: dict[str, str] = {}
    if not isinstance(text, str):
        return result
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # "digest *name" (binary marker) and "digest  name" both occur.
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        digest, name = parts[0].strip(), parts[1].strip()
        if name.startswith("*"):
            name = name[1:]
        if len(digest) == 64 and all(c in "0123456789abcdefABCDEF" for c in digest):
            result[name] = digest.lower()
    return result


def verify_digest(path: Path, asset: dict) -> tuple[bool, str]:
    """Verify a downloaded file against the asset's published digest.

    The digest ships in the same GitHub API response as the asset URL, so this
    check costs nothing and adds no second trust domain.

    Args:
        path: The downloaded file.
        asset: The asset dict from the release object.

    Returns:
        ``(True, <hex digest>)`` on a match, otherwise
        ``(False, <reason>)``. The reason is written for display verbatim in a
        user-facing dialog.
    """
    try:
        actual = sha256_file(path)
    except OSError as exc:
        return False, f"could not read downloaded file: {exc}"

    digest = asset.get("digest") if isinstance(asset, dict) else None
    if not isinstance(digest, str) or not digest.lower().startswith("sha256:"):
        return False, "release asset has no sha256 digest"
    expected = digest.split(":", 1)[1].strip().lower()
    if actual != expected:
        return False, f"checksum mismatch: expected {expected}, got {actual}"
    return True, actual


def download_asset(asset: dict, dest: Path,
                   progress: Optional[Callable[[int, int], None]] = None) -> tuple[bool, str]:
    """Download a release asset and verify it.

    Args:
        asset: Asset dict from the release object.
        dest: Destination path for the verified file.
        progress: Optional progress callback, see :func:`http_download`.

    Returns:
        ``(True, <hex digest>)`` on success, ``(False, <reason>)`` otherwise.
        A failed download never leaves a file behind.
    """
    url = asset.get("browser_download_url") if isinstance(asset, dict) else None
    if not isinstance(url, str) or not url:
        return False, "release asset has no download URL"
    if not http_download(url, Path(dest), progress=progress):
        return False, f"download of {asset.get('name', 'the update')} failed"
    return verify_digest(Path(dest), asset)


# ── Process liveness ────────────────────────────────────────────────────────
def process_is_alive(pid: int) -> bool:
    """Return True when a process with this PID exists.

    Args:
        pid: Process id to probe.

    Returns:
        False when the process is gone. On an inconclusive error the answer is
        True: waiting for a live process is safe, assuming a dead one is not.
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False

    if sys.platform == "win32":
        import ctypes  # win32-only; keeps the import out of the POSIX path
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            # ERROR_INVALID_PARAMETER means no such PID; anything else is
            # inconclusive and must be treated as alive.
            return kernel32.GetLastError() != _ERROR_INVALID_PARAMETER
        code = ctypes.c_ulong()
        ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        kernel32.CloseHandle(handle)
        if not ok:
            return True
        return code.value == _STILL_ACTIVE

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def wait_for_pid_exit(pid: int, timeout: float = 30.0) -> bool:
    """Wait until a process disappears.

    Args:
        pid: Process id to wait on.
        timeout: Maximum seconds to wait.

    Returns:
        True when the process is gone, False on timeout.
    """
    deadline = time.time() + timeout
    while True:
        if not process_is_alive(pid):
            return True
        if time.time() >= deadline:
            return False
        time.sleep(0.2)


# ── Crash recovery ──────────────────────────────────────────────────────────
def _exe_dir() -> Path:
    """Return the directory holding the running executable."""
    return Path(sys.executable).parent


def self_heal(exe_dir: Path) -> None:
    """Repair an installation left half-updated by a crashed swap.

    Runs at the top of every launch. Never raises, and never leaves a state
    where nothing is left to run: on every path at least one of
    ``{target, backup, newfile}`` survives.

    Args:
        exe_dir: Directory holding the executable.
    """
    exe_dir = Path(exe_dir)
    target = exe_dir / exe_name()
    backup = exe_dir / (exe_name() + ".old")
    newfile = exe_dir / (exe_name() + ".new")

    try:
        # 1. Healthy: the real executable is there.
        if target.is_file():
            return
        has_backup = backup.exists()
        has_new = newfile.exists()

        # 2. Backup only: the swap died between the two renames.
        if has_backup and not has_new:
            os.replace(backup, target)
            return

        # 3. Backup AND new file: the swap never completed.
        if has_backup and has_new:
            # The backup is the older known-good image; the .new file is the
            # fully downloaded and digest-verified one. Either survives if the
            # other rename fails, so nothing is ever left with nothing to run.
            try:
                backup.unlink()
            except OSError:
                pass
            os.replace(newfile, target)
            return

        # 4. Neither: nothing to recover, nothing to do.
        return
    except Exception:
        # Any remaining artifact is still on disk and is retried next launch.
        return


# ── Completer ───────────────────────────────────────────────────────────────
def complete_update(old_pid: int, nonce: str) -> int:
    """Replace this executable with the downloaded update and relaunch it.

    Runs as a fresh process (``--complete-update``) BEFORE ``QApplication``
    exists, so it never raises: every failure becomes a return code.

    Order matters (bug B3): the swap happens FIRST and the wait comes after.
    The running image is bound to the file identity now named ``.old``, so the
    real name is already free at t=0. Waiting first would inject up to 30 s
    during which ``LangTrainer.exe`` does not exist, long enough for Windows to
    silently drop a pinned taskbar icon, for no reason.

    The backup is deleted only after the swap AND after the old process is
    confirmed dead (bug B4): before that it cannot be told apart from a stale
    backup from an earlier attempt.

    Args:
        old_pid: PID of the process being replaced.
        nonce: Token written next to the ``.new`` file at download time.

    Returns:
        ``0`` success; ``2`` the old process is still alive; ``3`` nothing to
        install or the swap failed; ``4`` unexpected exception; ``5`` not
        Windows, nothing was touched; ``6`` the nonce is missing or mismatched,
        nothing was touched.
    """
    exe_dir = _exe_dir()
    target = exe_dir / exe_name()
    backup = exe_dir / (exe_name() + ".old")
    newfile = exe_dir / (exe_name() + ".new")
    nonce_file = exe_dir / (exe_name() + ".nonce")

    # 1. Windows only, BEFORE touching a single file. A macOS .app is a
    #    directory bundle that os.replace cannot replace, and on POSIX the
    #    executable may be owned by root.
    if not self_install_supported():
        return 5

    # 2. Nonce guard: a manually typed --complete-update must not be able to
    #    destroy a good install. The file is created at download time.
    try:
        if not nonce_file.is_file() or nonce_file.read_text(encoding="utf-8").strip() != (nonce or ""):
            return 6
    except OSError:
        return 6

    try:
        # 3. Nothing downloaded: nothing to do.
        if not newfile.exists():
            return 3

        # 4. Swap immediately. A transient Defender scan raises the SAME
        #    PermissionError as a genuine ACL denial, because CPython's
        #    path_error2 maps both ERROR_ACCESS_DENIED (5) and
        #    ERROR_SHARING_VIOLATION (32) to it — so retry rather than report.
        #    Never tell the user "you need admin rights" on PermissionError.
        for attempt in range(5):
            try:
                if target.exists():
                    os.replace(target, backup)
                os.replace(newfile, target)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.5)

        # 5. The swap must have produced the real executable.
        if not target.exists():
            return 3

        # 6. Only now is it safe to wait for the old image to be released.
        if not wait_for_pid_exit(old_pid, 30.0):
            return 2

        # 7. The parent is confirmed dead; the backup is now safe to drop.
        try:
            if backup.exists():
                backup.unlink()
        except OSError:
            pass

        # 8. Relaunch detached, so the completer can exit without killing it.
        subprocess.Popen(
            [str(target)],
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
        )
        return 0
    except Exception:
        return 4


def relaunch_for_update(old_pid: int, nonce: str) -> None:
    """Start the completer process and hard-exit this one.

    The caller must already have stopped the timer, cleaned up the tray,
    disconnected the database and called ``app.quit()``: the hard exit skips
    ``atexit``. This process holds a memory-mapped image of its own executable
    and must exit promptly for the swap to succeed.

    Args:
        old_pid: This process's PID, handed to the completer so it can wait.
        nonce: The token matching the ``.nonce`` file next to the ``.new`` file.

    Returns:
        Never returns.
    """
    subprocess.Popen(
        [
            sys.executable,
            "--complete-update",
            "--pid",
            str(old_pid),
            "--nonce",
            str(nonce or ""),
        ],
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
    )
    os._exit(0)


# ── Throttle state ──────────────────────────────────────────────────────────
def load_state(state_path: Path) -> dict:
    """Read the update-check state file.

    Args:
        state_path: Path of the JSON state file.

    Returns:
        The decoded object, or ``{}`` when it is absent or unreadable.
    """
    try:
        with open(Path(state_path), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def should_check(state_path: Path, now: Optional[float] = None) -> bool:
    """Return True when enough time has passed for another update check.

    Args:
        state_path: Path of the JSON state file.
        now: Current epoch seconds; defaults to ``time.time()``.

    Returns:
        True when no check is recorded yet, when the state is unreadable, or
        when ``CHECK_INTERVAL_SECONDS`` have elapsed.
    """
    if now is None:
        now = time.time()
    try:
        last = float(load_state(state_path).get("last_check", 0) or 0)
    except (TypeError, ValueError):
        last = 0.0
    return (now - last) >= CHECK_INTERVAL_SECONDS


def record_check(state_path: Path, disabled: bool = False) -> None:
    """Persist the time of this check and the "never" opt-out.

    Called even when the network is dead, so a user on a plane does not retry
    on every launch.

    Args:
        state_path: Path of the JSON state file.
        disabled: True to record the "never check again" opt-out.

    Returns:
        None. Never raises.
    """
    try:
        state_path = Path(state_path)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump({"last_check": time.time(), "disabled": bool(disabled)}, handle)
    except OSError:
        pass
