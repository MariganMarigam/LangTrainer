"""Chain Reaction: Multiple-choice with randomly flipping direction each round.

Direction flips randomly: foreign→native or native→foreign.
Three difficulty levels control the reverse probability:
- Easy:   10% reverse (mostly word → translation)
- Hard:   30% reverse (translation → word)
- Chaos:  50% reverse
"""
import random
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QComboBox
from ui.games.components.multiple_choice import MultipleChoicePanel, generate_options
from ui.games.game_base import BaseGame
from ui.styles import (
    Colors, Fonts, label_style, combo_box_style,
    progress_label_style, score_label_style, destructive_button_style,
)


class ChainReactionWidget(BaseGame):
    """Multiple-choice quiz with random direction flips per round.

    Each round randomly selects forward (word→translation) or reverse
    (translation→word) based on the current difficulty's reverse probability.
    """

    finished = Signal()

    DIFFICULTIES: dict[str, float] = {
        "easy": 0.1,
        "hard": 0.3,
        "chaos": 0.5,
    }

    def __init__(self, db_manager, parent=None):
        super().__init__(db_manager, parent)
        self._reverse_prob: float = 0.0
        self._current_direction: str = "forward"
        self._finished_emitted: bool = False
        self._last_word_id: int | None = None
        self._pending_timers: list[QTimer] = []
        self._layout.setContentsMargins(16, 8, 16, 8)
        self._layout.setSpacing(8)
        self._build_ui()

    # ── UI Construction ────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the chain reaction game interface."""
        # ── Difficulty picker ──
        diff_layout = QHBoxLayout()
        diff_label = QLabel("Difficulty:")
        diff_label.setStyleSheet(label_style(Fonts.CALLOUT, Colors.SECONDARY_LABEL))
        diff_layout.addWidget(diff_label)

        self._diff_combo = QComboBox()
        self._diff_combo.addItems(["Easy", "Hard", "Chaos"])
        self._diff_combo.setStyleSheet(combo_box_style())
        self._diff_combo.currentTextChanged.connect(self._on_difficulty_change)
        diff_layout.addWidget(self._diff_combo)
        diff_layout.addStretch()
        self._layout.addLayout(diff_layout)

        # ── Direction indicator ──
        self._direction_label = QLabel("Foreign \u2192 Native")
        self._direction_label.setStyleSheet(
            label_style(Fonts.TITLE_3, Colors.BLUE),
        )
        self._direction_label.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._direction_label)

        # ── Multiple-choice panel (word card + status + combo + options) ──
        self._panel = MultipleChoicePanel()
        self._panel.answered.connect(self._on_answer)
        self._layout.addWidget(self._panel)

        # ── Bottom bar: progress | score ──
        progress_layout = QHBoxLayout()
        progress_layout.setContentsMargins(0, 2, 0, 0)
        self._progress_label = QLabel("0 / 0")
        self._progress_label.setStyleSheet(progress_label_style())
        progress_layout.addWidget(self._progress_label)
        progress_layout.addStretch()
        self._score_label = QLabel("Score: 0%")
        self._score_label.setStyleSheet(score_label_style())
        progress_layout.addWidget(self._score_label)
        self._layout.addLayout(progress_layout)

        # ── Close button ──
        self._close_btn = QPushButton("\u2715  Close")
        self._close_btn.setStyleSheet(destructive_button_style())
        self._close_btn.clicked.connect(self.finished.emit)
        self._layout.addWidget(self._close_btn)

    # ── Game Lifecycle ─────────────────────────────────────────────────

    def setup_game(self, words) -> None:
        """Initialize game with a list of words.

        Args:
            words: List of WordRecord objects.
        """
        super().setup_game(words)
        self._finished_emitted = False
        self._cancel_pending_timers()
        self._reverse_prob = self.DIFFICULTIES[self._diff_combo.currentText().lower()]
        self._score_label.setText("Score: 0%")
        self._show_round()

    def _show_round(self) -> None:
        """Display the next word with randomly selected direction."""
        if self.is_finished:
            self._finish_game()
            return

        word = self._current_words[self._current_index]
        self._last_word_id = word.id

        # Pick direction randomly based on difficulty
        reverse = random.random() < self._reverse_prob
        self._current_direction = "reverse" if reverse else "forward"

        # Update direction indicator (prominent, color-coded)
        if reverse:
            self._direction_label.setText("Native \u2192 Foreign")
            self._direction_label.setStyleSheet(
                label_style(Fonts.TITLE_3, Colors.ORANGE),
            )
        else:
            self._direction_label.setText("Foreign \u2192 Native")
            self._direction_label.setStyleSheet(
                label_style(Fonts.TITLE_3, Colors.BLUE),
            )

        # Build prompt and options
        options, correct_index = generate_options(self.db, word, 4, self._current_direction)
        prompt = word.translation if reverse else word.word

        self._panel.set_question(prompt)
        self._panel.set_options(options, correct_index)
        self._panel.set_status("Choose the correct answer:")
        self._panel.reset_feedback()
        self._progress_label.setText(self.progress_text)

    def _on_answer(self, is_correct: bool) -> None:
        """Handle an answer: record stats, show status, advance after delay.

        Args:
            is_correct: True if the chosen option matched the correct answer.
        """
        word = self._current_words[self._current_index]
        self.record_answer(word.id, is_correct)
        self._score_label.setText(f"Score: {self.score_text}")

        if is_correct:
            self._panel.set_status("Correct!")
        else:
            # In forward mode (word→translation), correct answer is the translation.
            # In reverse mode (translation→word), correct answer is the word.
            answer_display = word.word if self._current_direction == "reverse" else word.translation
            self._panel.set_status(f"Wrong! Answer: {answer_display}")

        self._schedule(self._show_round, 700)

    def _finish_game(self) -> None:
        """Handle game completion — show final score, emit finished."""
        if self._finished_emitted:
            return
        self._finished_emitted = True
        self._direction_label.setText("Game Over")
        self._panel.set_status(f"Final score: {self.score_text}")
        self._panel.set_enabled(False)
        self._close_btn.setText("Finish")
        self.finished.emit()

    # ── Difficulty Change ──────────────────────────────────────────────

    def _on_difficulty_change(self, text: str) -> None:
        """Handle difficulty change — reset and restart if game is active."""
        self._reverse_prob = self.DIFFICULTIES[text.lower()]
        if self._current_words:
            self._cancel_pending_timers()
            self._current_index = 0
            self._correct_count = 0
            self._total_count = 0
            self._finished_emitted = False
            self._score_label.setText("Score: 0%")
            self._panel.reset_feedback()
            # Force a NEW word: skip the first word if it repeats the last
            # one shown (avoids an immediate repeat on difficulty change).
            if (
                len(self._current_words) > 1
                and self._current_words[0].id == self._last_word_id
            ):
                self._current_index = 1
            self._show_round()

    # ── Timer Management ───────────────────────────────────────────────

    def _schedule(self, callback, ms: int) -> None:
        """Schedule a delayed callback via the managed pending-timers list.

        Args:
            callback: Callable to invoke after *ms* milliseconds.
            ms: Delay in milliseconds.
        """
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(callback)
        timer.start(ms)
        self._pending_timers.append(timer)

    def _cancel_pending_timers(self) -> None:
        """Cancel and clean up all pending delayed callbacks."""
        for timer in self._pending_timers:
            try:
                timer.stop()
                timer.deleteLater()
            except RuntimeError:
                pass
        self._pending_timers.clear()

    def cleanup(self) -> None:
        """Clean up resources — cancel all pending timers."""
        self._cancel_pending_timers()
        self._panel.cleanup()
        super().cleanup()
