"""Tests for the self-update swap: process liveness, crash recovery, guards.

The two guards that protect a user's installation are tested hardest:
`complete_update` must refuse on a non-Windows platform and must refuse a
mismatched nonce WITHOUT touching a single file. A macOS `.app` is a directory
bundle `os.replace` cannot replace, and a manually typed `--complete-update`
must not be able to destroy a good install.
"""
import ctypes
import hashlib
import os
import sys
import tempfile
import time
import types
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import services.updater as updater

_EXE = "LangTrainer.exe"  # updater.exe_name() with sys.platform forced to win32
_VERSIONED = "LangTrainer-1.0.0-windows-x64.exe"  # the name the release publishes


class _DeadProcessKernel32:
    """Stand-in for ctypes.windll.kernel32 on Linux, where it does not exist.

    Forcing sys.platform="win32" sends process_is_alive down the win32 branch.
    Every PID is reported dead via ERROR_INVALID_PARAMETER, so
    wait_for_pid_exit returns immediately instead of sleeping 30 s.
    """

    def OpenProcess(self, access, inherit, pid):  # noqa: N802 - win32 name
        return 0

    def GetLastError(self):  # noqa: N802 - win32 name
        return updater._ERROR_INVALID_PARAMETER

    def GetExitCodeProcess(self, handle, ptr):  # noqa: N802 - win32 name
        return 1

    def CloseHandle(self, handle):  # noqa: N802 - win32 name
        return 1


def _frozen_as(monkeypatch, exe_path):
    """Make the process look like the published binary at `exe_path`."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_path))
    monkeypatch.setattr(sys, "platform", "win32")


def _digest_tree(directory: Path) -> dict:
    """Map every file in `directory` to its sha256, for byte-identity proofs."""
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(directory.iterdir())
        if p.is_file()
    }


def _scratch(tmp: str) -> Path:
    """Build a scratch install dir: a live exe, a staged .new and a backup."""
    exe_dir = Path(tmp)
    (exe_dir / _EXE).write_bytes(b"old-image")
    (exe_dir / (_EXE + ".new")).write_bytes(b"new-image")
    (exe_dir / (_EXE + ".old")).write_bytes(b"older-image")
    (exe_dir / (_EXE + ".nonce")).write_text("tok3n", encoding="utf-8")
    return exe_dir


def test_process_is_alive_for_current_pid():
    assert updater.process_is_alive(os.getpid()) is True
    assert updater.process_is_alive(0) is False
    assert updater.process_is_alive(-1) is False
    print("test_process_is_alive_for_current_pid: PASS")


def test_wait_for_pid_exit_returns_promptly_for_dead_pid():
    # PID 0x7FFFFFF0 is above every default pid_max on Linux.
    started = time.time()
    assert updater.wait_for_pid_exit(0x7FFFFFF0, timeout=5.0) is True
    elapsed = time.time() - started
    assert elapsed < 1.0, f"waited {elapsed:.2f}s for an already-dead pid"
    print("test_wait_for_pid_exit_returns_promptly_for_dead_pid: PASS")


def test_self_heal_healthy_install_is_untouched(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    with tempfile.TemporaryDirectory() as tmp:
        exe_dir = _scratch(tmp)
        before = _digest_tree(exe_dir)
        updater.self_heal(exe_dir)
        assert _digest_tree(exe_dir) == before
    print("test_self_heal_healthy_install_is_untouched: PASS")


def test_self_heal_restores_backup_only(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    with tempfile.TemporaryDirectory() as tmp:
        exe_dir = _scratch(tmp)
        (exe_dir / _EXE).unlink()
        (exe_dir / (_EXE + ".new")).unlink()
        updater.self_heal(exe_dir)
        assert (exe_dir / _EXE).is_file()
        assert (exe_dir / _EXE).read_bytes() == b"older-image"
        assert not (exe_dir / (_EXE + ".old")).exists()
    print("test_self_heal_restores_backup_only: PASS")


def test_self_heal_prefers_new_when_both_present(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    with tempfile.TemporaryDirectory() as tmp:
        exe_dir = _scratch(tmp)
        (exe_dir / _EXE).unlink()
        updater.self_heal(exe_dir)
        assert (exe_dir / _EXE).is_file()
        assert (exe_dir / _EXE).read_bytes() == b"new-image"
        assert not (exe_dir / (_EXE + ".old")).exists()
    print("test_self_heal_prefers_new_when_both_present: PASS")


def test_self_heal_does_not_raise_with_nothing_to_recover(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    with tempfile.TemporaryDirectory() as tmp:
        exe_dir = Path(tmp)
        updater.self_heal(exe_dir)  # must not raise
        assert list(exe_dir.iterdir()) == []
    print("test_self_heal_does_not_raise_with_nothing_to_recover: PASS")


def test_complete_update_returns_5_on_non_windows_without_touching_files(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    with tempfile.TemporaryDirectory() as tmp:
        exe_dir = _scratch(tmp)
        monkeypatch.setattr(updater, "_exe_dir", lambda: exe_dir)
        before = _digest_tree(exe_dir)

        assert updater.complete_update(os.getpid(), "tok3n") == 5

        assert _digest_tree(exe_dir) == before, "refusal must not touch any file"
        assert (exe_dir / _EXE).read_bytes() == b"old-image"
        assert (exe_dir / (_EXE + ".new")).read_bytes() == b"new-image"
    print("test_complete_update_returns_5_on_non_windows_without_touching_files: PASS")


def test_complete_update_returns_6_on_nonce_mismatch_without_touching_files(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    with tempfile.TemporaryDirectory() as tmp:
        exe_dir = _scratch(tmp)
        monkeypatch.setattr(updater, "_exe_dir", lambda: exe_dir)
        before = _digest_tree(exe_dir)

        assert updater.complete_update(os.getpid(), "wrong-nonce") == 6

        assert _digest_tree(exe_dir) == before, "refusal must not touch any file"
        assert (exe_dir / _EXE).read_bytes() == b"old-image"
        assert (exe_dir / (_EXE + ".new")).read_bytes() == b"new-image"
    print("test_complete_update_returns_6_on_nonce_mismatch_without_touching_files: PASS")


def test_complete_update_returns_6_when_nonce_file_missing(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    with tempfile.TemporaryDirectory() as tmp:
        exe_dir = _scratch(tmp)
        (exe_dir / (_EXE + ".nonce")).unlink()
        monkeypatch.setattr(updater, "_exe_dir", lambda: exe_dir)
        before = _digest_tree(exe_dir)
        assert updater.complete_update(os.getpid(), "tok3n") == 6
        assert _digest_tree(exe_dir) == before
    print("test_complete_update_returns_6_when_nonce_file_missing: PASS")


def test_complete_update_returns_3_when_nothing_staged(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    with tempfile.TemporaryDirectory() as tmp:
        exe_dir = _scratch(tmp)
        (exe_dir / (_EXE + ".new")).unlink()
        monkeypatch.setattr(updater, "_exe_dir", lambda: exe_dir)
        assert updater.complete_update(os.getpid(), "tok3n") == 3
        assert (exe_dir / _EXE).read_bytes() == b"old-image"
    print("test_complete_update_returns_3_when_nothing_staged: PASS")


# ── The real released file name (v1.0.1 fix) ────────────────────────────────
# The release publishes LangTrainer-1.0.0-windows-x64.exe, so exe_name() must
# resolve to whatever the user actually launched. A hardcoded name made the
# swap install a second LangTrainer.exe beside the running binary.


def test_exe_name_returns_real_filename_when_frozen(monkeypatch):
    launched = Path("/tmp/does-not-matter") / _VERSIONED
    _frozen_as(monkeypatch, launched)
    assert updater.exe_name() == _VERSIONED
    assert updater.exe_name() == launched.name
    print("test_exe_name_returns_real_filename_when_frozen: PASS")


def test_exe_name_falls_back_when_not_frozen(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    assert updater.exe_name() == "LangTrainer.exe"
    monkeypatch.setattr(sys, "platform", "linux")
    assert updater.exe_name() == "LangTrainer"
    print("test_exe_name_falls_back_when_not_frozen: PASS")


def test_exe_name_ignores_empty_executable(monkeypatch):
    # A frozen process whose sys.executable is empty must not yield "".
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "")
    monkeypatch.setattr(sys, "platform", "win32")
    assert updater.exe_name() == "LangTrainer.exe"
    monkeypatch.setattr(sys, "platform", "linux")
    assert updater.exe_name() == "LangTrainer"
    print("test_exe_name_ignores_empty_executable: PASS")


def test_self_heal_is_noop_for_versioned_executable(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        exe_dir = Path(tmp)
        (exe_dir / _VERSIONED).write_bytes(b"live-image")
        _frozen_as(monkeypatch, exe_dir / _VERSIONED)
        before = sorted(p.name for p in exe_dir.iterdir())
        before_digests = _digest_tree(exe_dir)

        updater.self_heal(exe_dir)

        assert sorted(p.name for p in exe_dir.iterdir()) == before
        assert _digest_tree(exe_dir) == before_digests
        assert before == [_VERSIONED], "scratch dir must hold only the versioned exe"
        assert (exe_dir / "LangTrainer.exe").exists() is False
    print("test_self_heal_is_noop_for_versioned_executable: PASS")


def test_complete_update_under_versioned_name_leaves_single_binary(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        exe_dir = Path(tmp)
        (exe_dir / _VERSIONED).write_bytes(b"old-image")
        (exe_dir / (_VERSIONED + ".new")).write_bytes(b"new-image")
        (exe_dir / (_VERSIONED + ".nonce")).write_text("tok3n", encoding="utf-8")
        _frozen_as(monkeypatch, exe_dir / _VERSIONED)
        monkeypatch.setattr(
            ctypes, "windll", types.SimpleNamespace(kernel32=_DeadProcessKernel32()),
            raising=False,
        )
        relaunched = []
        monkeypatch.setattr(
            updater.subprocess, "Popen", lambda *a, **k: relaunched.append(a[0])
        )

        assert updater.complete_update(0x7FFFFFF0, "tok3n") == 0

        names = sorted(p.name for p in exe_dir.iterdir())
        exes = [n for n in names if n.endswith(".exe")]
        assert exes == [_VERSIONED], f"expected one versioned exe, got {exes}"
        assert "LangTrainer.exe" not in names
        assert not any(n.endswith(".old") for n in names), f"stale backup: {names}"
        assert (exe_dir / _VERSIONED).read_bytes() == b"new-image"
        assert relaunched == [[str(exe_dir / _VERSIONED)]]
    print("test_complete_update_under_versioned_name_leaves_single_binary: PASS")
