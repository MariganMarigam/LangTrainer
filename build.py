#!/usr/bin/env python3
"""
LangTrainer — Build Script (PyInstaller + UPX)

Usage:
    python build.py                # Default release build (--onedir)
    python build.py --onefile      # Single executable (slower startup, smaller zip)
    python build.py --clean        # Clean build cache first
    python build.py --upx /path/to/upx  # Specify UPX executable

Requirements:
    pip install pyinstaller
    (optional) Install UPX: https://upx.github.io/
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path

APP_NAME = "LangTrainer"
ROOT_DIR = Path(__file__).parent.resolve()
BUILD_DIR = ROOT_DIR / "build"
DIST_DIR = ROOT_DIR / "dist"


def parse_args():
    parser = argparse.ArgumentParser(description="Build LangTrainer with PyInstaller")
    parser.add_argument("--onefile", action="store_true",
                        help="Build single executable (default: --onedir)")
    parser.add_argument("--clean", action="store_true",
                        help="Clean build cache before building")
    parser.add_argument("--upx", type=str, default=None,
                        help="Path to UPX executable (e.g., /usr/bin/upx)")
    return parser.parse_args()


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
    
    # Windowed mode (no console window on Windows)
    if sys.platform == "win32":
        cmd.append("--windowed")
    
    # Output mode
    if args.onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")
    
    # UPX compression
    if args.upx:
        upx_path = Path(args.upx)
        if upx_path.exists():
            cmd.append("--upx-dir")
            cmd.append(str(upx_path.parent))
            print(f"📦  Using UPX from: {upx_path}")
        else:
            print(f"⚠️  UPX not found at {upx_path}, skipping compression")
    
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
    # assets/ is empty, but include the directory structure
    # (data/ is NOT included — DB is created at runtime)
    
    # ── Entry point ─────────────────────────────────────────────────────
    cmd.append(str(ROOT_DIR / "main.py"))
    
    # ── Execute ─────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"🔨  Building {APP_NAME}...")
    print(f"📁  Mode: {'onefile' if args.onefile else 'onedir'}")
    print(f"{'='*60}\n")
    
    result = subprocess.run(cmd, cwd=ROOT_DIR)
    
    if result.returncode != 0:
        print(f"\n❌  Build failed with code {result.returncode}")
        sys.exit(1)
    
    # ── Report ──────────────────────────────────────────────────────────
    if args.onefile:
        output = DIST_DIR / APP_NAME / f"{APP_NAME}.exe" if sys.platform == "win32" else DIST_DIR / APP_NAME / APP_NAME
    else:
        output = DIST_DIR / APP_NAME
    
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


def main():
    args = parse_args()
    
    # Check PyInstaller availability
    try:
        import PyInstaller
    except ImportError:
        print("❌  PyInstaller not found. Install it:")
        print("   pip install pyinstaller")
        sys.exit(1)
    
    if args.clean:
        clean()
    
    build(args)
    
    print("\n💡  Next steps:")
    print("   - Run the build:  dist/LangTrainer/LangTrainer")
    if args.onefile:
        print("   - Single file:   dist/LangTrainer.exe")
    print("   - To reduce further: install UPX and run with --upx /path/to/upx")


if __name__ == "__main__":
    main()
