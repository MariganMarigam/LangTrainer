"""Bomb: Countdown survival — answer correctly to add time, wrong subtracts.

Infinite survival mode: the game runs until the timer hits zero.
Correct answer: +1 s and combo+1.  Wrong answer: −1 s and combo reset.
Difficulty sets the starting time:
- Easy:   120 s
- Normal:  60 s
- Hard:    30 s
"""
import random
from PySide6.QtCore import Qt, Signal, QTimer, QElapsedTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QComboBox
from ui.games.components.multiple_choice import MultipleChoicePanel, generate_options
from ui.games.components.countdown_bar import CountdownBar
from ui.games.game_base import BaseGame
from ui.styles import (
    Colors, Fonts, label_style, combo_box_style,
    progress_label_style, score_label_style, destructive_button_style,
    pill_button_style,
)


class BombWidget(BaseGame):
    """Countdown survival MCQ — add or lose time per answer.

    The game runs indefinitely until the countdown timer reaches zero.
    """

    finished = Signal()

    DIFFICULTIES: dict[str, int] = {
        "easy": 120_000,
        "normal": 60_000,
        "hard": 30_000,
    }

    def __init__(self, db_manager, parent=None):
        super().__init__(db_manager, parent)
        self._remaining_ms: int = 120_000
        self._elapsed: QElapsedTimer = QElapsedTimer()
        self._tick_timer: QTimer | None = None
        self._combo: int = 0
        self._words_survived: int = 0
        self._current_word = None
        self._last_word_id: int | None = None
        self._pool: list = []
        self._pool_index: int = 0
        self._game_over_emitted: bool = False
        self._finished_emitted: bool = False
        self._hint_used: bool = False
        self._pending_timers: list[QTimer] = []
        self._layout.setContentsMargins(16, 8, 16, 8)
        self._layout.setSpacing(8)
        self._build_ui()

    # ── UI Construction ────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the bomb game interface."""
        # ── Difficulty picker ──
        diff_layout = QHBoxLayout()
        diff_label = QLabel("Difficulty:")
        diff_label.setStyleSheet(label_style(Fonts.CALLOUT, Colors.SECONDARY_LABEL))
        diff_layout.addWidget(diff_label)

        self._diff_combo = QComboBox()
        self._diff_combo.addItems(["Easy", "Normal", "Hard"])
        self._diff_combo.setStyleSheet(combo_box_style())
        self._diff_combo.currentTextChanged.connect(self._on_difficulty_change)
        diff_layout.addWidget(self._diff_combo)
        diff_layout.addStretch()

        self._best_label = QLabel("Best: 0")
        self._best_label.setStyleSheet(label_style(Fonts.CALLOUT, Colors.SECONDARY_LABEL))
        diff_layout.addWidget(self._best_label)
        self._layout.addLayout(diff_layout)

        # ── Countdown bar ──
        self._countdown = CountdownBar()
        self._countdown.set_max(120_000)
        self._layout.addWidget(self._countdown)

        # ── Multiple-choice panel (word card + status + combo + options) ──
        self._panel = MultipleChoicePanel()
        self._panel.answered.connect(self._on_answer)
        self._layout.addWidget(self._panel)

        # ── Hint row (1 use per word) ──
        hint_layout = QHBoxLayout()
        hint_layout.setContentsMargins(0, 0, 0, 0)
        self._hint_btn = QPushButton("\U0001f4a1 Hint")
        self._hint_btn.setStyleSheet(
            pill_button_style(
                Colors.CARD_BG_ALT, Colors.PRIMARY_LABEL,
                height="32px", font_size="13px",
            ),
        )
        self._hint_btn.clicked.connect(self._on_hint)
        hint_layout.addStretch()
        hint_layout.addWidget(self._hint_btn)
        self._layout.addLayout(hint_layout)

        # ── Bottom bar: progress | score ──
        progress_layout = QHBoxLayout()
        progress_layout.setContentsMargins(0, 2, 0, 0)
        self._progress_label = QLabel("Words: 0")
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
        self._game_over_emitted = False
        self._combo = 0
        self._words_survived = 0
        self._last_word_id = None
        self._cancel_pending_timers()

        diff_name = self._diff_combo.currentText().lower()
        self._remaining_ms = self.DIFFICULTIES[diff_name]

        self._countdown.set_max(self._remaining_ms)
        self._score_label.setText("Score: 0%")
        self._progress_label.setText("Words: 0")
        self._panel.set_combo_text("")

        self._update_best_label()

        # Shuffle word pool
        self._pool = list(self._current_words)
        random.shuffle(self._pool)
        self._pool_index = 0

        # Start elapsed timer and tick
        self._elapsed = QElapsedTimer()
        self._elapsed.start()
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(100)
        self._tick_timer.timeout.connect(self._on_tick)
        self._tick_timer.start()

        self._show_next_word()

    # ── Tick (100 ms) ──────────────────────────────────────────────────

    def _on_tick(self) -> None:
        """Update countdown display; end game when time runs out."""
        remaining = self._remaining_ms - self._elapsed.elapsed()
        if remaining <= 0:
            self._game_over()
            return
        self._countdown.set_remaining(int(remaining))
        self._countdown.set_danger(remaining < 3000)

    # ── Word Display ───────────────────────────────────────────────────

    def _pick_next_word(self):
        """Pick the next word from the pool, avoiding immediate repeats.

        Returns:
            The next WordRecord from the cycled pool.
        """
        if self._pool_index >= len(self._pool):
            random.shuffle(self._pool)
            self._pool_index = 0

        word = self._pool[self._pool_index]
        self._pool_index += 1

        # Avoid immediate repeat (skip if only 1 word, just return it)
        if len(self._pool) > 1 and word.id == self._last_word_id:
            if self._pool_index < len(self._pool):
                word = self._pool[self._pool_index]
                self._pool_index += 1

        self._last_word_id = word.id
        return word

    def _show_next_word(self) -> None:
        """Display the next word with multiple-choice options."""
        if self._game_over_emitted:
            return

        # Fresh hint available for the new word
        self._hint_used = False
        self._hint_btn.setEnabled(True)
        self._hint_btn.setText("\U0001f4a1 Hint")

        self._current_word = self._pick_next_word()
        options, correct_index = generate_options(
            self.db, self._current_word, 4, "forward",
        )

        self._panel.set_question(self._current_word.word.upper())
        self._panel.set_options(options, correct_index)
        self._panel._status_label.setStyleSheet(
            label_style(Fonts.BODY, Colors.SECONDARY_LABEL),
        )
        self._panel.set_status("Choose the correct translation:")
        self._panel.reset_feedback()
        self._progress_label.setText(self.progress_text)

    # ── Answer Handling ────────────────────────────────────────────────

    def _on_answer(self, is_correct: bool) -> None:
        """Handle an answer: adjust time, update combo, advance after delay.

        Args:
            is_correct: True if the chosen option matched the correct answer.
        """
        if self._game_over_emitted:
            return

        self.record_answer(self._current_word.id, is_correct)

        if is_correct:
            self._remaining_ms += 1000
            self._combo += 1
            self._words_survived += 1
            self._panel.set_status("Correct! +1s")
        else:
            self._remaining_ms -= 1000
            self._combo = 0
            self._panel.set_status(
                f"Wrong! Answer: {self._current_word.translation}",
            )

        self._score_label.setText(f"Score: {self.score_text}")

        # Update combo display
        if self._combo >= 3:
            self._panel.set_combo_text(f"\U0001f525 {self._combo}x")
        else:
            self._panel.set_combo_text("")

        self._schedule(self._show_next_word, 600)

    # ── Hint ────────────────────────────────────────────────────────────

    def _on_hint(self) -> None:
        """Reveal the current word's translation in the status label.

        The hint text is styled prominently (orange, semibold) so it stands
        out from the default gray status prompt. Limited to one use per
        word — the button stays disabled until the next word is shown.
        """
        if self._game_over_emitted or self._current_word is None or self._hint_used:
            return
        self._hint_used = True
        self._hint_btn.setEnabled(False)
        self._hint_btn.setText("\U0001f4a1 Hint used")
        self._panel._status_label.setStyleSheet(
            f"color: {Colors.ORANGE}; {Fonts.BODY} font-weight: semibold; padding: 4px;",
        )
        self._panel.set_status(f"\U0001f4a1 Hint: {self._current_word.translation}")

    # ── Game Over ──────────────────────────────────────────────────────

    def _game_over(self) -> None:
        """End the game: stop timers, show stats, emit finished."""
        if self._game_over_emitted:
            return
        self._game_over_emitted = True

        if self._tick_timer is not None:
            self._tick_timer.stop()
        self._cancel_pending_timers()

        diff_name = self._diff_combo.currentText().lower()
        self.db.record_game_result("bomb", diff_name, self._words_survived)
        best = self.db.get_game_best("bomb", diff_name)

        self._panel.set_enabled(False)
        self._hint_btn.setEnabled(False)
        self._panel.set_combo_text("")
        self._panel.set_status(
            f"\U0001f4a5  Best: {best} words | Accuracy: {self.score_text}",
        )
        self._countdown.set_remaining(0)
        self._close_btn.setText("Finish")
        self._update_best_label()

        if not self._finished_emitted:
            self._finished_emitted = True
            self.finished.emit()

    # ── Difficulty Change ──────────────────────────────────────────────

    def _on_difficulty_change(self, text: str) -> None:
        """Handle difficulty change — reset and restart if game is active."""
        if not self._current_words:
            return

        self._cancel_pending_timers()
        if self._tick_timer is not None:
            self._tick_timer.stop()

        diff_name = text.lower()
        self._remaining_ms = self.DIFFICULTIES[diff_name]
        self._combo = 0
        self._words_survived = 0
        # Keep the current word id so _pick_next_word skips it (no repeat).
        self._last_word_id = (
            self._current_word.id if self._current_word is not None else None
        )
        self._game_over_emitted = False
        self._finished_emitted = False

        self._correct_count = 0
        self._total_count = 0

        self._countdown.set_max(self._remaining_ms)
        self._score_label.setText("Score: 0%")
        self._progress_label.setText("Words: 0")
        self._panel.set_combo_text("")
        self._close_btn.setText("\u2715  Close")

        self._update_best_label()

        self._pool = list(self._current_words)
        random.shuffle(self._pool)
        self._pool_index = 0

        self._elapsed = QElapsedTimer()
        self._elapsed.start()
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(100)
        self._tick_timer.timeout.connect(self._on_tick)
        self._tick_timer.start()

        self._show_next_word()

    # ── Properties (overrides) ─────────────────────────────────────────

    @property
    def progress_text(self) -> str:
        """Show words survived (pool cycles indefinitely)."""
        return f"Words: {self._words_survived}"

    # ── Best Result Display ────────────────────────────────────────────

    def _update_best_label(self) -> None:
        """Refresh the header best-score label for the current difficulty."""
        diff_name = self._diff_combo.currentText().lower()
        best = self.db.get_game_best("bomb", diff_name)
        self._best_label.setText(f"Best: {best}")

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
        """Clean up resources — stop tick timer, cancel pending timers."""
        if self._tick_timer is not None:
            self._tick_timer.stop()
            self._tick_timer.deleteLater()
            self._tick_timer = None
        self._cancel_pending_timers()
        self._panel.cleanup()
        super().cleanup()
