#!/usr/bin/env python3
"""
LangTrainer — Build Script (PyInstaller)

Usage:
    python build.py                # Default release build (--onefile, single executable)
    python build.py --onedir       # Directory distribution (faster startup, bigger)
    python build.py --clean        # Clean build cache first

Requirements:
    pip install -r requirements-build.txt

UPX compression is intentionally DISABLED: it is the strongest Defender/SmartScreen
heuristic and costs ~10 MB. See the release plan, decision table section 0.
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path

# Force UTF-8 console output: on cp1251-locale Windows (e.g. Russian),
# emoji in print() raises UnicodeEncodeError and aborts the build.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

APP_NAME = "LangTrainer"
ROOT_DIR = Path(__file__).parent.resolve()
BUILD_DIR = ROOT_DIR / "build"
DIST_DIR = ROOT_DIR / "dist"
DICS_SRC = ROOT_DIR / "dics"
ICON_SRC = ROOT_DIR / "assets" / "icons" / "langtrainer.png"


def parse_args():
    parser = argparse.ArgumentParser(description="Build LangTrainer with PyInstaller")
    parser.add_argument("--onedir", action="store_true",
                        help="Build a directory distribution (default: --onefile)")
    parser.add_argument("--clean", action="store_true",
                        help="Clean build cache before building")
    return parser.parse_args()


def _add_data_arg(src: Path, dest: str) -> list[str]:
    """Build a PyInstaller --add-data argument with the platform-correct separator."""
    sep = ";" if sys.platform == "win32" else ":"
    return ["--add-data", f"{src}{sep}{dest}"]


def _icon_args(icon: Path) -> list[str]:
    """Return --icon arguments, or [] when the icon file is absent.

    A missing icon is cosmetic: warn and continue, never fail the build.
    """
    if icon.exists():
        return ["--icon", str(icon)]
    print(f"⚠️  Icon not found at {icon} — building without one")
    return []


def clean():
    """Remove previous build artifacts."""
    for d in [BUILD_DIR, DIST_DIR]:
        if d.exists():
            print(f"🧹  Cleaning {d}...")
            shutil.rmtree(d)
    
    # Also clean __pycache__ and .pyc files
    for pycache in ROOT_DIR.rglob("__pycache__"):
        shutil.rmtree(pycache)
    for pyc in ROOT_DIR.rglob("*.pyc"):
        pyc.unlink()


def build(args):
    """Run PyInstaller with optimized settings."""
    
    # ── PyInstaller command ─────────────────────────────────────────────
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--noconfirm",           # Overwrite output without asking
        "--log-level", "WARN",   # Less verbose
    ]
    
    # Windowed mode (no console window on Windows/macOS).
    # Without --windowed the macOS job produces a console binary, not a .app.
    if sys.platform in ("win32", "darwin"):
        cmd.append("--windowed")

    # Output mode: onefile by default (single .exe, per release plan section 0)
    cmd.append("--onedir" if args.onedir else "--onefile")

    # UPX is disabled by decision (release plan section 0): it is the strongest
    # Defender/SmartScreen heuristic and only saves ~10 MB.

    # ── Explicitly EXCLUDE unused Qt modules (~400 MB saving) ──────────
    # We ONLY need: QtCore, QtGui, QtWidgets
    QT_UNUSED_MODULES = [
        "PySide6.Qt3DAnimation", "PySide6.Qt3DCore", "PySide6.Qt3DExtras",
        "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DRender",
        "PySide6.QtBluetooth", "PySide6.QtCharts", "PySide6.QtChartsQml",
        "PySide6.QtDataVisualization", "PySide6.QtDesigner",
        "PySide6.QtGraphs", "PySide6.QtHelp", "PySide6.QtHttpServer",
        "PySide6.QtLocation", "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets", "PySide6.QtNetwork",
        "PySide6.QtNetworkAuth", "PySide6.QtNfc",
        "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets",
        "PySide6.QtPdf", "PySide6.QtPdfWidgets",
        "PySide6.QtPositioning", "PySide6.QtPrintSupport",
        "PySide6.QtQml", "PySide6.QtQmlModels", "PySide6.QtQuick",
        "PySide6.QtQuick3D", "PySide6.QtQuickControls2",
        "PySide6.QtQuickWidgets", "PySide6.QtRemoteObjects",
        "PySide6.QtSensors", "PySide6.QtSerialBus",
        "PySide6.QtSerialPort", "PySide6.QtSpatialAudio",
        "PySide6.QtSql", "PySide6.QtStateMachine",
        "PySide6.QtSvg", "PySide6.QtSvgWidgets",
        "PySide6.QtTest", "PySide6.QtTextToSpeech",
        "PySide6.QtUiTools", "PySide6.QtWebChannel",
        "PySide6.QtWebEngine", "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineQuick", "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebSockets", "PySide6.QtXml",
    ]
    
    for mod in QT_UNUSED_MODULES:
        cmd.extend(["--exclude-module", mod])
    
    # ── Hidden imports (things PyInstaller might miss) ──────────────────
    cmd.extend(["--hidden-import", "PySide6.QtCore"])
    cmd.extend(["--hidden-import", "PySide6.QtGui"])
    cmd.extend(["--hidden-import", "PySide6.QtWidgets"])
    
    # ── Data files to include ───────────────────────────────────────────
    # Dictionaries. Destination is exactly "dics" — a relative dest resolves
    # against sys._MEIPASS, so config.ensure_dics_extracted() finds them there.
    # (data/ is NOT included — the DB is created at runtime next to the exe)
    if not DICS_SRC.is_dir():
        print(f"❌  Dictionary folder not found: {DICS_SRC}")
        print("   The build cannot proceed without it.")
        sys.exit(1)
    cmd.extend(_add_data_arg(DICS_SRC, "dics"))

    # ── Icon (cosmetic — a missing icon must never fail the build) ───────
    cmd.extend(_icon_args(ICON_SRC))

    # ── Entry point ─────────────────────────────────────────────────────
    cmd.append(str(ROOT_DIR / "main.py"))

    # ── Execute ─────────────────────────────────────────────────────────
    mode = "onedir" if args.onedir else "onefile"
    # --distpath keeps the two modes from colliding on dist/<name>/ and makes
    # the mode visible in the artifact name.
    out_root = DIST_DIR / f"{APP_NAME}_{mode}"
    cmd.extend(["--distpath", str(out_root)])

    print(f"\n{'='*60}")
    print(f"🔨  Building {APP_NAME}...")
    print(f"📁  Mode: {mode}")
    print(f"{'='*60}\n")

    result = subprocess.run(cmd, cwd=ROOT_DIR)

    if result.returncode != 0:
        print(f"\n❌  Build failed with code {result.returncode}")
        sys.exit(1)

    # ── Report ──────────────────────────────────────────────────────────
    if sys.platform == "win32":
        inner = f"{APP_NAME}.exe"
    elif sys.platform == "darwin":
        inner = f"{APP_NAME}.app"
    else:
        inner = APP_NAME
    # onefile -> a single file; onedir -> the application folder.
    output = out_root / APP_NAME if args.onedir else out_root / inner
    
    print(f"\n{'='*60}")
    print(f"✅  Build complete!")
    print(f"📂  Output: {output}")
    
    # Show size
    if output.exists():
        if output.is_dir():
            total_size = sum(f.stat().st_size for f in output.rglob("*") if f.is_file())
        else:
            total_size = output.stat().st_size
        print(f"📦  Size: {total_size / 1024 / 1024:.1f} MB")
    
    print(f"{'='*60}\n")

    return output


def main():
    args = parse_args()

    # Check PyInstaller availability
    try:
        import PyInstaller
    except ImportError:
        print("❌  PyInstaller not found. Install it:")
        print("   pip install -r requirements-build.txt")
        sys.exit(1)

    if args.clean:
        clean()

    output = build(args)

    print("\n💡  Next steps:")
    print(f"   - Run the build:  {output}")
    print("   - UPX is disabled by design; do not add --upx-dir.")


if __name__ == "__main__":
    main()
