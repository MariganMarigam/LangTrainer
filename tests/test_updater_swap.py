"""Tests for the self-update swap: process liveness, crash recovery, guards.

The two guards that protect a user's installation are tested hardest:
`complete_update` must refuse on a non-Windows platform and must refuse a
mismatched nonce WITHOUT touching a single file. A macOS `.app` is a directory
bundle `os.replace` cannot replace, and a manually typed `--complete-update`
must not be able to destroy a good install.
"""
import hashlib
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import services.updater as updater

_EXE = "LangTrainer.exe"  # updater.exe_name() with sys.platform forced to win32


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
