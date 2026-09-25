#!/usr/bin/env python3
"""Render the LangTrainer application icon.

Generates assets/icons/langtrainer.png (1024x1024, ARGB32). The generated PNG is
COMMITTED so CI never needs a generation step; re-run this only when the mark
changes:

    QT_QPA_PLATFORM=offscreen .venv/bin/python tools/make_icon.py

Stdlib + PySide6 only. The "LT" glyph and the #007AFF family are shared with
ui/tray.py so the app has exactly one mark.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter, QPen,
)

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "assets" / "icons" / "langtrainer.png"
DEFAULT_SIZE = 1024
GRADIENT_TOP = QColor("#409CFF")
GRADIENT_BOTTOM = QColor("#007AFF")
GLYPH = "LT"


def render_icon(size: int = DEFAULT_SIZE) -> QImage:
    """Render the LangTrainer mark: blue gradient tile, white rounded frame, 'LT'.

    Args:
        size: Edge length in pixels (square image).

    Returns:
        A transparent ARGB32 QImage.
    """
    # QFont touches QFontDatabase, which requires a QGuiApplication to exist.
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])

    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)

    # Full-bleed gradient background
    gradient = QLinearGradient(QPointF(0.0, 0.0), QPointF(0.0, float(size)))
    gradient.setColorAt(0.0, GRADIENT_TOP)
    gradient.setColorAt(1.0, GRADIENT_BOTTOM)
    painter.fillRect(QRectF(0.0, 0.0, float(size), float(size)), gradient)

    # White rounded-rectangle outline
    margin = size * 0.10
    frame = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)
    pen = QPen(QColor("#FFFFFF"))
    pen.setWidthF(size * 0.045)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawRoundedRect(frame, size * 0.18, size * 0.18)

    # White bold 'LT' glyph, centred
    font = QFont()
    font.setBold(True)
    font.setPixelSize(int(size * 0.42))
    painter.setFont(font)
    painter.setPen(QPen(QColor("#FFFFFF")))
    painter.drawText(image.rect(), Qt.AlignCenter, GLYPH)

    painter.end()
    return image


def main() -> int:
    """Write the rendered icon to OUTPUT_PATH."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    image = render_icon()
    if not image.save(str(OUTPUT_PATH), "PNG"):
        print(f"Failed to write {OUTPUT_PATH}", file=sys.stderr)
        return 1
    print(f"Wrote {OUTPUT_PATH} ({DEFAULT_SIZE}x{DEFAULT_SIZE})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
