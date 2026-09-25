"""Tests for the build.py CLI surface (release plan step A1, A2, A6).

Covers the decisions locked in section 0 of the plan: onefile is the DEFAULT,
--onedir is opt-in, UPX is gone entirely, and the --add-data / --icon helpers
emit the platform-correct arguments.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path

import pytest

import build


def test_onedir_is_not_the_default():
    """Onefile is the default packaging mode (section 0)."""
    argv = sys.argv
    try:
        sys.argv = ["build.py"]
        assert build.parse_args().onedir is False
    finally:
        sys.argv = argv


def test_onedir_flag_sets_it():
    """--onedir opts into a directory distribution."""
    argv = sys.argv
    try:
        sys.argv = ["build.py", "--onedir"]
        assert build.parse_args().onedir is True
    finally:
        sys.argv = argv


def test_upx_argument_is_gone():
    """UPX is disabled by decision — the flag must not come back."""
    argv = sys.argv
    try:
        sys.argv = ["build.py", "--upx", "/usr/bin/upx"]
        with pytest.raises(SystemExit):
            build.parse_args()
    finally:
        sys.argv = argv


@pytest.mark.parametrize(
    "platform_value, separator",
    [("win32", ";"), ("linux", ":"), ("darwin", ":")],
)
def test_add_data_arg_uses_platform_separator(monkeypatch, platform_value, separator, tmp_path):
    """--add-data joins source and destination with ';' on Windows, ':' elsewhere."""
    monkeypatch.setattr(build.sys, "platform", platform_value)
    src = tmp_path / "dics"
    assert build._add_data_arg(src, "dics") == ["--add-data", f"{src}{separator}dics"]


def test_add_data_arg_destination_is_bare_dics(monkeypatch, tmp_path):
    """Destination must be exactly 'dics' — 'dics/dics' would nest the folder."""
    monkeypatch.setattr(build.sys, "platform", "linux")
    src = tmp_path / "dics"
    assert build._add_data_arg(src, "dics")[1].endswith(":dics")


def test_icon_args_empty_for_missing_file(tmp_path):
    """A missing icon is cosmetic: warn and continue, never fail the build."""
    assert build._icon_args(tmp_path / "nope.png") == []


def test_icon_args_for_real_file(tmp_path):
    """An existing icon yields --icon <path>."""
    icon = tmp_path / "langtrainer.png"
    icon.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert build._icon_args(icon) == ["--icon", str(icon)]


def test_committed_icon_exists_and_is_a_real_png():
    """The committed icon must be present so CI needs no generation step."""
    icon = build.ICON_SRC
    assert icon.exists(), f"{icon} is missing"
    assert icon.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", "not a real PNG"


def test_dics_source_dir_exists():
    """build() exits 1 when dics/ is absent; it must exist in the repo."""
    assert build.DICS_SRC.is_dir()
    assert list(build.DICS_SRC.glob("*.txt")), "dics/ contains no .txt files"
