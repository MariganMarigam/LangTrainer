"""Reusable flip card button for word games."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton
from ui.styles import HIDDEN_CARD_STYLE, MATCHED_CARD_STYLE, SELECTED_CARD_STYLE


class FlipCard(QPushButton):
    """A card that flips between front and back text on click.

    Front uses HIDDEN_CARD_STYLE, back uses SELECTED_CARD_STYLE,
    and locked (matched/placed) cells use MATCHED_CARD_STYLE.
    """

    flipped = Signal(bool)  # True when showing the back

    def __init__(self, front_text: str = "", back_text: str = "", parent=None):
        super().__init__(parent)
        self._front_text = front_text
        self._back_text = back_text
        self._is_flipped = False
        self._locked = False
        self.setText(front_text)
        self._apply_style()
        self.clicked.connect(self._on_clicked)

    def set_faces(self, front: str, back: str) -> None:
        """Set the front and back texts (keeps current side visible)."""
        self._front_text = front
        self._back_text = back
        if not self._is_flipped:
            self.setText(front)

    def flip(self) -> None:
        """Swap front/back instantly; locked cards do not flip."""
        if self._locked:
            return
        self._is_flipped = not self._is_flipped
        self.setText(self._back_text if self._is_flipped else self._front_text)
        self._apply_style()
        self.flipped.emit(self._is_flipped)

    def is_flipped(self) -> bool:
        """Return True when the back is showing."""
        return self._is_flipped

    def set_locked(self, locked: bool) -> None:
        """Lock the card (matched/placed cells) so it cannot flip."""
        self._locked = locked
        self._apply_style()

    def _on_clicked(self) -> None:
        self.flip()

    def _apply_style(self) -> None:
        if self._locked:
            self.setStyleSheet(MATCHED_CARD_STYLE)
        elif self._is_flipped:
            self.setStyleSheet(SELECTED_CARD_STYLE)
        else:
            self.setStyleSheet(HIDDEN_CARD_STYLE)