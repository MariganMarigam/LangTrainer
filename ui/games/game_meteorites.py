"""Meteorites Game: Choose correct translation from options."""
import random
from PySide6.QtCore import Signal, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton
from ui.games.components.multiple_choice import MultipleChoicePanel, generate_options
from ui.games.game_base import BaseGame
from ui.styles import (
    destructive_button_style, progress_label_style, score_label_style,
)


class MeteoritesWidget(BaseGame):
    """Shows foreign word + 3-4 translation buttons.
    One correct, rest are random distractors.
    Tracks combo counter for consecutive correct answers.
    """

    finished = Signal()

    def __init__(self, db_manager, parent=None):
        super().__init__(db_manager, parent)
        self._current_word = None
        self._combo = 0
        self._max_combo = 0
        self._last_btn_count = 4
        self._finished_emitted = False
        self._pending_timers = []
        self._build_ui()

    def _build_ui(self):
        """Build the iOS-inspired game interface."""
        self._layout.setContentsMargins(16, 8, 16, 8)
        self._layout.setSpacing(12)

        # ── Multiple-choice panel (word card + status + combo + options) ──
        self._panel = MultipleChoicePanel()
        self._panel.answered.connect(self._on_answer)
        self._layout.addWidget(self._panel)

        # ── Bottom bar: progress | score ──────────────────────────────────
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

        # ── Close button ──────────────────────────────────────────────────
        self._close_btn = QPushButton("✕  Close")
        self._close_btn.setStyleSheet(destructive_button_style())
        self._close_btn.clicked.connect(self.finished.emit)
        self._layout.addWidget(self._close_btn)

    def setup_game(self, words):
        """Initialize game with words.

        Args:
            words: List of WordRecord objects.
        """
        super().setup_game(words)
        self._combo = 0
        self._max_combo = 0
        self._finished_emitted = False
        self._panel.set_combo_text("")
        self._score_label.setText("Score: 0%")
        self._show_next()

    def _show_next(self):
        """Show the next word with 3-4 option buttons."""
        if self.is_finished:
            self._finish_game()
            return

        self._current_word = self._current_words[self._current_index]
        self._panel.set_question(self._current_word.word.upper())
        self._progress_label.setText(self.progress_text)

        btn_count = random.choice([3, 4])
        self._last_btn_count = btn_count
        options, correct_index = generate_options(
            self.db, self._current_word, btn_count, "forward",
        )
        self._panel.set_options(options, correct_index)
        self._panel.set_status("Choose the correct translation:")

    def _on_answer(self, is_correct: bool):
        """Handle an answer: combo tracking, stats, status, advance."""
        if is_correct:
            self._combo += 1
            if self._combo > self._max_combo:
                self._max_combo = self._combo
            if self._combo >= 3:
                self._panel.set_combo_text(f"Fire {self._combo}x Combo!")
            else:
                self._panel.set_combo_text("")
        else:
            self._combo = 0
            self._panel.set_combo_text("")

        self.record_answer(self._current_word.id, is_correct)
        self._score_label.setText(f"Score: {self.score_text}")

        msg = (
            "Correct!"
            if is_correct
            else f"Wrong! Answer: {self._current_word.translation}"
        )
        self._panel.set_status(msg)

        self._schedule(self._show_next, 1200)

    def _schedule(self, callback, ms: int) -> None:
        """Schedule a delayed callback via the managed pending-timers list."""
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(callback)
        timer.start(ms)
        self._pending_timers.append(timer)

    def _cancel_pending_timers(self):
        """Cancel and clean up all pending delayed callbacks."""
        for timer in self._pending_timers:
            try:
                timer.stop()
                timer.deleteLater()
            except RuntimeError:
                pass
        self._pending_timers.clear()

    def cleanup(self):
        """Clean up resources — cancel all pending timers."""
        self._cancel_pending_timers()
        self._panel.cleanup()
        super().cleanup()

    def _finish_game(self):
        """Handle game completion."""
        if self._finished_emitted:
            return
        self._finished_emitted = True
        self._panel.set_question("Complete!")
        self._panel.set_status(
            f"Final: {self.score_text} | Best combo: {self._max_combo}",
        )
        self._panel.set_options(["--"] * self._last_btn_count, 0)
        self._panel.set_enabled(False)
        self._close_btn.setText("Finish")
        self.finished.emit()