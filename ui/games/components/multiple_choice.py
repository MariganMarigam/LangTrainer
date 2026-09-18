"""Reusable multiple-choice question panel for games."""
import random
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from ui.styles import Colors, Fonts, card_style, label_style, pill_button_style


class MultipleChoicePanel(QWidget):
    """Word card + status + combo labels + up to 6 option buttons.

    Emits ``answered(bool)`` after feedback is shown so games can record
    the answer and advance to the next round.

    Options are stacked in a single column by default (``columns=1``).
    Pass ``columns=2`` for a compact two-column grid with smaller buttons
    (used by Domination for up to 6 options).
    """

    answered = Signal(bool)  # True if the chosen option was correct

    def __init__(self, parent=None, columns: int = 1):
        super().__init__(parent)
        self._columns = max(1, columns)
        self._correct_index = -1
        self._pending_timers = []
        self._build_ui()

    # ── Sizing helpers ─────────────────────────────────────────────────

    def _button_height(self) -> int:
        """Return the option button height in pixels for the column mode."""
        return 36 if self._columns > 1 else 44

    def _normal_style(self) -> str:
        """Return the normal (unanswered) pill style for option buttons."""
        height = f"{self._button_height()}px"
        font_size = "13px" if self._columns > 1 else "15px"
        return pill_button_style(
            Colors.CARD_BG_ALT, height=height, font_size=font_size,
        )

    def _feedback_style(self, bg: str) -> str:
        """Return a feedback pill style that keeps its color when disabled."""
        height = self._button_height()
        font_size = "13px" if self._columns > 1 else "15px"
        return (
            f"QPushButton {{ background-color: {bg}; color: white; "
            f"border: none; border-radius: {height // 2}px; padding: 4px 12px; "
            f"font-size: {font_size}; font-weight: semibold; "
            f"min-height: {height}px; }}"
            f"QPushButton:disabled {{ background-color: {bg}; color: white; }}"
        )

    def _dimmed_style(self) -> str:
        """Return the dimmed (non-chosen, non-correct) feedback style."""
        height = self._button_height()
        font_size = "13px" if self._columns > 1 else "15px"
        return (
            f"QPushButton {{ background-color: {Colors.CARD_BG}; "
            f"color: {Colors.TERTIARY_LABEL}; border: none; "
            f"border-radius: {height // 2}px; padding: 4px 12px; "
            f"font-size: {font_size}; font-weight: semibold; "
            f"min-height: {height}px; }}"
            f"QPushButton:disabled {{ background-color: {Colors.CARD_BG}; "
            f"color: {Colors.TERTIARY_LABEL}; }}"
        )

    def _build_ui(self) -> None:
        """Build the word card, status/combo labels and option buttons."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # ── Word card ─────────────────────────────────────────────────────
        word_card = QFrame()
        word_card.setStyleSheet(card_style())
        word_layout = QVBoxLayout(word_card)
        if self._columns > 1:
            word_layout.setContentsMargins(12, 12, 12, 12)
            word_font = Fonts.TITLE_2
        else:
            word_layout.setContentsMargins(16, 24, 16, 24)
            word_font = Fonts.TITLE_1
        self._word_label = QLabel("Word")
        self._word_label.setStyleSheet(
            f"color: {Colors.PRIMARY_LABEL}; {word_font} "
            "background: transparent; padding: 0;",
        )
        self._word_label.setAlignment(Qt.AlignCenter)
        word_layout.addWidget(self._word_label)
        layout.addWidget(word_card)

        # ── Status label ──────────────────────────────────────────────────
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(
            label_style(Fonts.BODY, Colors.SECONDARY_LABEL),
        )
        self._status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._status_label)

        # ── Combo label ───────────────────────────────────────────────────
        self._combo_label = QLabel("")
        self._combo_label.setStyleSheet(
            label_style(Fonts.HEADLINE, Colors.ORANGE),
        )
        self._combo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._combo_label)

        # ── Option buttons (1 or 2 columns, up to 6) ──────────────────────
        self._option_buttons = []
        if self._columns > 1:
            options_layout = QGridLayout()
            options_layout.setSpacing(8)
        else:
            options_layout = QVBoxLayout()
            options_layout.setSpacing(8)
        normal_style = self._normal_style()
        for i in range(6):
            btn = QPushButton(f"Option {i + 1}")
            btn.setStyleSheet(normal_style)
            btn.setMinimumHeight(self._button_height())
            btn.clicked.connect(
                lambda checked, idx=i: self._on_option_clicked(idx),
            )
            self._option_buttons.append(btn)
            if self._columns > 1:
                options_layout.addWidget(
                    btn, i // self._columns, i % self._columns,
                )
            else:
                options_layout.addWidget(btn)
        layout.addLayout(options_layout)

    def set_question(self, prompt: str) -> None:
        """Show the prompt (big word label)."""
        self._word_label.setText(prompt)

    def set_options(self, options: list[str], correct_index: int) -> None:
        """Show one button per option (hides extras) and store the correct index."""
        self._correct_index = correct_index
        normal_style = self._normal_style()
        for i, btn in enumerate(self._option_buttons):
            if i < len(options):
                btn.show()
                btn.setText(options[i])
                btn.setEnabled(True)
                btn.setStyleSheet(normal_style)
            else:
                btn.hide()

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable all visible option buttons."""
        for btn in self._option_buttons:
            if not btn.isHidden():
                btn.setEnabled(enabled)

    def show_feedback(self, chosen_index: int) -> None:
        """Apply green/red/dim feedback styles and disable all buttons."""
        correct_feedback = self._feedback_style(Colors.GREEN)
        wrong_feedback = self._feedback_style(Colors.RED)
        dimmed_feedback = self._dimmed_style()

        for i, btn in enumerate(self._option_buttons):
            if btn.isHidden():
                continue
            btn.setEnabled(False)
            if i == self._correct_index:
                btn.setStyleSheet(correct_feedback)
            elif i == chosen_index:
                btn.setStyleSheet(wrong_feedback)
            else:
                btn.setStyleSheet(dimmed_feedback)

    def reset_feedback(self) -> None:
        """Restore normal pill styles and re-enable all visible buttons."""
        normal_style = self._normal_style()
        for btn in self._option_buttons:
            if not btn.isHidden():
                btn.setEnabled(True)
                btn.setStyleSheet(normal_style)

    def set_combo_text(self, text: str) -> None:
        """Set the orange combo label (empty string hides it)."""
        self._combo_label.setText(text)

    def set_status(self, text: str) -> None:
        """Set the secondary status label."""
        self._status_label.setText(text)

    def _on_option_clicked(self, index: int) -> None:
        """Show feedback, then emit answered with the correctness result."""
        self.show_feedback(index)
        self.answered.emit(index == self._correct_index)

    def _schedule(self, callback, ms: int) -> None:
        """Schedule a delayed callback via the managed pending-timers list."""
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(callback)
        timer.start(ms)
        self._pending_timers.append(timer)

    def cleanup(self) -> None:
        """Cancel all pending timers (call on game exit)."""
        for timer in self._pending_timers:
            try:
                timer.stop()
                timer.deleteLater()
            except RuntimeError:
                pass
        self._pending_timers.clear()


def generate_options(db, word, count: int, direction: str = "forward") -> tuple[list[str], int]:
    """Generate (options, correct_index) for a multiple-choice question.

    Args:
        db: DatabaseManager instance.
        word: WordRecord — the question word.
        count: Number of options to generate.
        direction: "forward" → prompt is word.word, options are translations;
            "reverse" → prompt is word.translation, options are words.

    Returns:
        Tuple of (shuffled options list, index of the correct option).
    """
    correct_value = word.translation if direction == "forward" else word.word
    options = [correct_value]
    distractors = [w for w in db.get_random_words(count - 1) if w.id != word.id]
    for w in distractors[: count - 1]:
        options.append(w.translation if direction == "forward" else w.word)
    while len(options) < count:
        options.append("---")

    order = list(range(len(options)))
    random.shuffle(order)
    shuffled = [options[i] for i in order]
    return shuffled, order.index(0)
