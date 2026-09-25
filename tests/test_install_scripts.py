"""Tests for install.sh / uninstall.sh (no bats: plain sh against a fake $HOME).

The scripts are the "install LangTrainer into my system" path, so the two
properties that matter are:

* the menu entry works — an ABSOLUTE Exec=, never a bare ``AppRun``, which is
  resolved against the desktop file's own directory and therefore only works
  from inside the unmounted image;
* uninstalling is reversible — the user's vocabulary survives by default and is
  deleted only on an explicit ``--purge``.

No root, ever: neither script may mention it. The tests also assert that a run
against a fake $HOME writes nothing into the real one.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "install.sh"
UNINSTALL_SH = REPO_ROOT / "uninstall.sh"
REAL_HOME = Path(os.path.expanduser("~"))

#: A stand-in for the 55 MB AppImage. The scripts copy it; they never run it.
FAKE_APPIMAGE = "#!/bin/sh\necho LangTrainer\n"


def _sh(script: Path, *args, home: Path, expect_success: bool = True):
    """Run `script` with `sh`, HOME pointed at `home`, XDG vars cleared.

    Args:
        script: The script to run.
        args: Positional arguments for the script.
        home: The fake $HOME to run against.
        expect_success: Assert the exit code is 0 when True, non-zero when False.

    Returns:
        The completed process, with stdout/stderr captured as text.
    """
    env = {
        "HOME": str(home),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        # The scripts must fall back to their own $HOME-relative defaults, so
        # these are cleared rather than inherited from the real environment.
        "LC_ALL": "C",
    }
    result = subprocess.run(
        ["sh", str(script), *args],
        env=env, cwd=str(home), capture_output=True, text=True, timeout=120,
    )
    if expect_success:
        assert result.returncode == 0, (
            f"{script.name} failed ({result.returncode})\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    else:
        assert result.returncode != 0, f"{script.name} unexpectedly succeeded"
    return result


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """An empty directory used as $HOME, with the real XDG vars unset.

    Mirrors a repository checkout: the scripts plus the AppImage and the icon
    directory the scripts look for beside themselves.
    """
    for name in ("XDG_DATA_HOME", "XDG_BIN_DIR", "LANGTRAINER_ICON"):
        monkeypatch.delenv(name, raising=False)
    home = tmp_path / "home"
    home.mkdir()
    (home / "LangTrainer-1.0.2-linux-x86_64.AppImage").write_text(
        FAKE_APPIMAGE, encoding="utf-8",
    )
    shutil.copy(INSTALL_SH, home / "install.sh")
    shutil.copy(UNINSTALL_SH, home / "uninstall.sh")
    icons = home / "assets" / "icons"
    icons.mkdir(parents=True)
    shutil.copy(REPO_ROOT / "assets" / "icons" / "langtrainer.png",
                icons / "langtrainer.png")
    return home


def _install(home: Path) -> subprocess.CompletedProcess:
    """Run install.sh against `home` and return the process."""
    return _sh(home / "install.sh", home=home)


# ── syntax ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("script", [INSTALL_SH, UNINSTALL_SH])
def test_scripts_pass_sh_syntax_check(script):
    """`sh -n` is dash-compatible parsing: the scripts must not be bash-only."""
    result = subprocess.run(
        ["sh", "-n", str(script)], capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, f"{script.name}: {result.stderr}"


@pytest.mark.parametrize("script", [INSTALL_SH, UNINSTALL_SH])
def test_scripts_are_executable_bit_set(script):
    """The scripts ship with the exec bit, so ./install.sh works from a clone."""
    assert os.access(script, os.X_OK), f"{script.name} is not executable"


# ── no root, ever ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("script", [INSTALL_SH, UNINSTALL_SH])
def test_no_privilege_escalation_anywhere_in_the_scripts(script):
    """A user install must never need elevated rights, so the word is absent.

    Checked against the whole file, comments included: a commented-out example
    is still a signal that the script was once expected to need it.
    """
    text = script.read_text(encoding="utf-8")
    assert "sudo" not in text, f"{script.name} mentions sudo"
    assert "doas" not in text, f"{script.name} mentions doas"


# ── install ─────────────────────────────────────────────────────────────────

def test_install_creates_the_menu_entry_with_an_absolute_exec(fake_home):
    """A relative Exec= is the single most common hand-rolled integration bug."""
    _install(fake_home)

    data_home = fake_home / ".local" / "share"
    desktop = data_home / "applications" / "langtrainer.desktop"
    assert desktop.is_file(), "the .desktop file was not created"

    text = desktop.read_text(encoding="utf-8")
    assert text.startswith("[Desktop Entry]"), "missing the Desktop Entry group"

    exec_lines = [ln for ln in text.splitlines() if ln.startswith("Exec=")]
    assert len(exec_lines) == 1, f"expected exactly one Exec= line, got {exec_lines}"
    exec_value = exec_lines[0][len("Exec="):].strip().strip('"')

    assert os.path.isabs(exec_value), f"Exec={exec_value!r} is not absolute"
    assert "AppRun" not in exec_value, f"Exec={exec_value!r} is a bare AppRun"
    expected = fake_home / ".local" / "share" / "LangTrainer" / "langtrainer"
    assert exec_value == str(expected), f"Exec points at {exec_value}"
    assert Path(exec_value).is_file(), "Exec points at a file that does not exist"


def test_install_creates_the_expected_desktop_keys(fake_home):
    """The entry must carry the keys a desktop environment needs."""
    _install(fake_home)
    text = (fake_home / ".local/share/applications/langtrainer.desktop").read_text(
        encoding="utf-8"
    )
    for key, value in (
        ("Type=Application", "Type=Application"),
        ("Terminal=false", "Terminal=false"),
        ("Icon=langtrainer", "Icon=langtrainer"),
        ("Categories=", "Categories=Education;Language;"),
    ):
        assert value in text, f"missing {key!r} in the desktop entry:\n{text}"


def test_install_creates_a_resolving_symlink(fake_home):
    """`langtrainer` on the command line must resolve to the installed binary."""
    _install(fake_home)

    link = fake_home / ".local" / "bin" / "langtrainer"
    assert link.is_symlink(), "the command symlink was not created"

    target = Path(os.readlink(link))
    assert target.is_absolute(), f"symlink target {target} is relative"
    assert target.is_file(), f"symlink target {target} does not exist"


def test_install_copies_the_icon(fake_home):
    """The 1024 px PNG is installed where hicolor lookup will find it."""
    _install(fake_home)
    icon = fake_home / ".local/share/icons/hicolor/1024x1024/apps/langtrainer.png"
    assert icon.is_file(), "the icon was not installed"
    original = REPO_ROOT / "assets" / "icons" / "langtrainer.png"
    assert icon.read_bytes() == original.read_bytes(), "the icon was altered"


def test_install_without_an_icon_still_installs_and_says_so(fake_home):
    """A user who downloaded only the AppImage and the script still gets an app."""
    shutil.rmtree(fake_home / "assets")
    result = _install(fake_home)

    assert (fake_home / ".local/share/LangTrainer/langtrainer").is_file()
    assert (fake_home / ".local/share/applications/langtrainer.desktop").is_file()
    assert "no icon found" in result.stderr, "the missing icon was not reported"
    assert "LANGTRAINER_ICON" in result.stderr, "no way to supply an icon is offered"


def test_install_makes_the_binary_executable(fake_home):
    """No exec bit means the menu entry launches nothing at all."""
    _install(fake_home)
    binary = fake_home / ".local/share/LangTrainer/langtrainer"
    assert binary.is_file()
    assert os.access(binary, os.X_OK), f"{binary} is not executable"


def test_install_writes_nothing_into_the_real_home(fake_home):
    """HOME=tmp_path must contain the whole install — the real one stays clean."""
    # Snapshot the real home before the run so a stray write is detectable.
    real_local = REAL_HOME / ".local"
    before = sorted(str(p) for p in real_local.rglob("*")) if real_local.is_dir() else []

    _install(fake_home)

    after = sorted(str(p) for p in real_local.rglob("*")) if real_local.is_dir() else []
    assert before == after, (
        "the install wrote into the real $HOME:\n"
        + "\n".join(sorted(set(after) - set(before)))
    )


def test_install_reports_how_to_undo(fake_home):
    """The printed instructions must name the uninstall script and --purge."""
    result = _install(fake_home)
    out = result.stdout + result.stderr
    assert "uninstall.sh" in out, "install.sh does not say how to undo itself"
    assert "--purge" in out, "install.sh does not mention the --purge escape hatch"


def test_install_without_an_appimage_fails_cleanly(fake_home):
    """No AppImage anywhere: a clear message and a non-zero exit, not a traceback."""
    (fake_home / "LangTrainer-1.0.2-linux-x86_64.AppImage").unlink()
    result = _sh(fake_home / "install.sh", home=fake_home, expect_success=False)
    assert "AppImage" in (result.stdout + result.stderr)


# ── uninstall ───────────────────────────────────────────────────────────────

def test_uninstall_removes_the_app_but_keeps_the_data(fake_home):
    """The default path must not touch a single byte of the user's vocabulary."""
    _install(fake_home)
    data_dir = fake_home / ".local/share/LangTrainer/data"
    data_dir.mkdir(parents=True, exist_ok=True)
    database = data_dir / "lang_trainer.db"
    database.write_bytes(b"SQLite format 3\x00" + b"pretend progress")
    logs_dir = fake_home / ".local/share/LangTrainer/logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "langtrainer-crash.log").write_text("something", encoding="utf-8")

    _sh(fake_home / "uninstall.sh", home=fake_home)

    data_home = fake_home / ".local" / "share"
    assert not (data_home / "applications/langtrainer.desktop").exists()
    assert not (fake_home / ".local/bin/langtrainer").exists()
    assert not (data_home / "LangTrainer/langtrainer").exists()
    assert not (data_home / "icons/hicolor/1024x1024/apps/langtrainer.png").exists()

    assert data_dir.is_dir(), "uninstall deleted the data directory"
    assert database.is_file(), "uninstall deleted the database"
    assert database.read_bytes() == b"SQLite format 3\x00" + b"pretend progress"
    assert (logs_dir / "langtrainer-crash.log").is_file()


def test_uninstall_purge_removes_the_data(fake_home):
    """--purge is the explicit, documented way to lose everything on purpose."""
    _install(fake_home)
    data_dir = fake_home / ".local/share/LangTrainer/data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "lang_trainer.db").write_bytes(b"SQLite format 3\x00")

    result = _sh(fake_home / "uninstall.sh", "--purge", home=fake_home)

    assert not data_dir.exists(), "--purge left the data directory behind"
    assert not (fake_home / ".local/share/LangTrainer").exists()
    assert not (fake_home / ".local/share/applications/langtrainer.desktop").exists()
    assert not (fake_home / ".local/bin/langtrainer").exists()
    assert "PURGED" in result.stdout, "the purge was not announced"


def test_uninstall_usage_warns_about_the_data(fake_home):
    """--help must say out loud that the default keeps the vocabulary."""
    result = _sh(fake_home / "uninstall.sh", "--help", home=fake_home)
    out = (result.stdout + result.stderr).lower()
    assert "purge" in out
    assert "keep your words" in out or "not delete your vocabulary" in out


def test_uninstall_without_install_is_harmless(fake_home):
    """Running it twice, or on a clean machine, must not fail."""
    _install(fake_home)
    _sh(fake_home / "uninstall.sh", home=fake_home)
    _sh(fake_home / "uninstall.sh", home=fake_home)


def test_uninstall_rejects_an_unknown_option(fake_home):
    """A typo must not be silently treated as the default, which keeps data."""
    result = _sh(fake_home / "uninstall.sh", "--purgee", home=fake_home,
                 expect_success=False)
    assert "unknown option" in result.stderr.lower()


def test_uninstall_leaves_a_non_symlink_command_alone(fake_home):
    """If something else owns ~/.local/bin/langtrainer, it is not ours to delete."""
    _install(fake_home)
    link = fake_home / ".local/bin/langtrainer"
    link.unlink()
    link.write_text("someone else's program\n", encoding="utf-8")

    _sh(fake_home / "uninstall.sh", home=fake_home)

    assert link.is_file(), "uninstall deleted a file it did not create"
    assert link.read_text(encoding="utf-8") == "someone else's program\n"
