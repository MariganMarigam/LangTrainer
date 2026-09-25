"""Dialogs for the auto-update flow, styled to match the rest of the app.

Two surfaces live here:

* :class:`UpdateAvailableDialog` — "version X is ready, download it?"
* :class:`RestartConfirmDialog` — "download is done, restart now?"

Both default their ``choice`` to ``"later"`` in ``__init__`` BEFORE any button
exists, so closing the dialog with the window button or Esc always leaves a
safe, non-destructive answer. The app never restarts itself behind the user's
back.
"""
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

import services.updater as updater
from config import LOGS_DIR
from ui.styles import Colors, Fonts, label_style, pill_button_style

#: Suffix of the secondary button style, matching ui/add_words_dialog.py.
_SECONDARY_BORDER = f"1px solid {Colors.SEPARATOR}"


def _human_size(n: int) -> str:
    """Format a byte count for display.

    Args:
        n: Size in bytes.

    Returns:
        A short human string, e.g. ``"42.7 MB"`` or ``"0 B"``.
    """
    try:
        size = float(n)
    except (TypeError, ValueError):
        return "0 B"
    if size < 1024:
        return f"{int(size)} B"
    for unit in ("KB", "MB", "GB"):
        size /= 1024.0
        if size < 1024.0:
            return f"{size:.1f} {unit}"
    return f"{size / 1024.0:.1f} TB"


class UpdateAvailableDialog(QDialog):
    """Ask the user whether to download an available update.

    Attributes:
        choice: ``"download"``, ``"later"`` or ``"never"``. Defaults to
            ``"later"``, which is also what a plain window close leaves behind.
    """

    def __init__(self, version: str, size_bytes: int = 0, parent=None):
        super().__init__(parent)
        # Before the buttons exist: closing the dialog must be non-destructive.
        self.choice: str = "later"
        self._set_window_flags()
        self._build_ui(version, size_bytes)

    def _set_window_flags(self) -> None:
        """Setup window flags — override title bar."""
        self.setWindowTitle("Update Available")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

    def _build_ui(self, version: str, size_bytes: int) -> None:
        """Build the dialog interface with iOS-inspired styling."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        title = QLabel(f"LangTrainer {version} is available")
        title.setStyleSheet(f"color: {Colors.BLUE}; {Fonts.TITLE_2} padding: 4px;")
        layout.addWidget(title)

        body = QLabel(
            f"Download size: {_human_size(size_bytes)}.\n"
            "The update is verified against the checksum published with the "
            "release, then installed and relaunched for you."
        )
        body.setStyleSheet(label_style(Fonts.FOOTNOTE, Colors.SECONDARY_LABEL))
        body.setWordWrap(True)
        layout.addWidget(body)

        action_layout = QHBoxLayout()
        action_layout.addStretch()

        self.never_btn = QPushButton("Never")
        self.never_btn.setStyleSheet(pill_button_style(Colors.RED))
        self.never_btn.clicked.connect(self._on_never)
        action_layout.addWidget(self.never_btn)

        self.later_btn = QPushButton("Later")
        self.later_btn.setStyleSheet(
            pill_button_style(Colors.CARD_BG_ALT, border=_SECONDARY_BORDER)
        )
        self.later_btn.clicked.connect(self.reject)
        action_layout.addWidget(self.later_btn)

        self.download_btn = QPushButton("Download")
        self.download_btn.setStyleSheet(pill_button_style(Colors.GREEN))
        self.download_btn.clicked.connect(self._on_download)
        action_layout.addWidget(self.download_btn)

        layout.addLayout(action_layout)

    def _on_download(self) -> None:
        """Record the intent to download and close."""
        self.choice = "download"
        self.accept()

    def _on_never(self) -> None:
        """Persist the opt-out so the check stops nagging, then close."""
        self.choice = "never"
        try:
            updater.record_check(Path(LOGS_DIR) / updater.STATE_FILENAME, disabled=True)
        except Exception:
            pass
        self.reject()


class RestartConfirmDialog(QDialog):
    """Ask whether to restart now that the update is downloaded and verified.

    Attributes:
        choice: ``"restart"`` or ``"later"``. Defaults to ``"later"``, which is
            also what a plain window close leaves behind.
    """

    def __init__(self, version: str, restart_enabled: bool = True, parent=None):
        super().__init__(parent)
        # Before the buttons exist: closing the dialog must not restart the app.
        self.choice: str = "later"
        self._restart_enabled = bool(restart_enabled)
        self._set_window_flags()
        self._build_ui(version)

    def _set_window_flags(self) -> None:
        """Setup window flags — override title bar."""
        self.setWindowTitle("Restart to Update")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

    def _build_ui(self, version: str) -> None:
        """Build the dialog interface with iOS-inspired styling."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        title = QLabel("Update ready")
        title.setStyleSheet(f"color: {Colors.BLUE}; {Fonts.TITLE_2} padding: 4px;")
        layout.addWidget(title)

        if self._restart_enabled:
            body_text = (
                f"LangTrainer {version} has been downloaded and verified.\n"
                "Restart now to finish installing it?"
            )
        else:
            body_text = (
                f"LangTrainer {version} has been downloaded and verified.\n\n"
                "A game is in progress, so restarting now would end it. "
                "Finish or close the game, then check for updates again — "
                "the downloaded file stays ready for the next attempt."
            )
        body = QLabel(body_text)
        body.setStyleSheet(label_style(Fonts.FOOTNOTE, Colors.SECONDARY_LABEL))
        body.setWordWrap(True)
        layout.addWidget(body)

        action_layout = QHBoxLayout()
        action_layout.addStretch()

        self.later_btn = QPushButton("Later")
        self.later_btn.setStyleSheet(
            pill_button_style(Colors.CARD_BG_ALT, border=_SECONDARY_BORDER)
        )
        self.later_btn.clicked.connect(self.reject)
        action_layout.addWidget(self.later_btn)

        self.restart_btn = QPushButton("Restart Now")
        self.restart_btn.setStyleSheet(pill_button_style(Colors.GREEN))
        if self._restart_enabled:
            self.restart_btn.clicked.connect(self._on_restart)
        else:
            # A restart loses the in-flight game run, so the action is taken
            # away rather than left to fail.
            self.restart_btn.setEnabled(False)
            self.restart_btn.setVisible(False)
        action_layout.addWidget(self.restart_btn)

        layout.addLayout(action_layout)

    def _on_restart(self) -> None:
        """Record the intent to restart and close."""
        if not self._restart_enabled:
            self.choice = "later"
            self.reject()
            return
        self.choice = "restart"
        self.accept()
