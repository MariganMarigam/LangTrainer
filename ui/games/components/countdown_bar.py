"""Reusable countdown bar: horizontal progress bar + time label."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget
from ui.styles import Colors, Fonts, progress_bar_style


class CountdownBar(QWidget):
    """Shows remaining time as a progress bar plus a "08.42" seconds label."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._max_ms = 1
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._bar = QProgressBar()
        self._bar.setRange(0, 1000)
        self._bar.setValue(1000)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(10)
        self._bar.setStyleSheet(progress_bar_style())
        layout.addWidget(self._bar)

        self._time_label = QLabel("00.00")
        self._time_label.setStyleSheet(
            f"color: {Colors.SECONDARY_LABEL}; {Fonts.CAPTION_1} padding: 0;",
        )
        self._time_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._time_label)

    def set_max(self, ms: int) -> None:
        """Set the full countdown duration in milliseconds."""
        self._max_ms = max(1, ms)
        self.set_remaining(self._max_ms)

    def set_remaining(self, ms: int) -> None:
        """Update the bar and time label for the given remaining milliseconds."""
        remaining = max(0, ms)
        self._bar.setValue(int(remaining / self._max_ms * 1000))
        self._time_label.setText(f"{remaining / 1000.0:05.2f}")

    def set_danger(self, danger: bool) -> None:
        """Turn the bar red when time is running out."""
        self._bar.setStyleSheet(progress_bar_style(danger=danger))