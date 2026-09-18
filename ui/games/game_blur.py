"""Blur: Word shown blurred — type it before time runs out.

A word is displayed with a QGraphicsBlurEffect. The player must type
the exact word. Hint (1 use per word) toggles the word's translation:
first click replaces the blurred word with the translation (input
hidden), second click restores the word and exhausts the hint.

Blur starts at 70% of the word label's font size (blurry but readable)
and decreases smoothly (piecewise linear) to 0% as the countdown runs.
Duration depends on difficulty: Easy 30 s, Normal 20 s, Hard 15 s.
"""
import random
import re
from PySide6.QtCore import (
    Qt, Signal, QTimer, QElapsedTimer,
)
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QGraphicsBlurEffect,
)
from ui.games.game_base import BaseGame
from ui.styles import (
    Colors, Fonts, label_style, combo_box_style, input_field_style,
    progress_label_style, score_label_style, destructive_button_style,
)


class BlurWidget(BaseGame):
    """Display a blurred word — type it to score.

    Difficulty-based countdown (Easy 30 s, Normal 20 s, Hard 15 s).
    Hint (1 use per word) toggles translation visibility.  10 words per
    game.  Piecewise blur: 70% → 40% → 25% → 0% across three time
    segments (see ``BLUR_SCHEDULES``).
    """

    finished = Signal()

    # Start blur = 70% of the word label's font size.  QGraphicsBlurEffect
    # .blurRadius is in pixels, so the radius is scaled to the rendered
    # word size: 28px font → 19px start (with max(8, …) floor).
    BLUR_START_FRACTION: float = 0.70
    _FONT_SIZE_FALLBACK_PX: int = 28  # Fonts.TITLE_1

    # Piecewise blur schedule: (start_ms, end_ms, start_frac, end_frac).
    # Blur fraction is linearly interpolated within each segment.
    BLUR_SCHEDULES: dict[str, list[tuple[int, int, float, float]]] = {
        "easy": [
            (0, 10_000, 0.70, 0.40),
            (10_000, 20_000, 0.40, 0.25),
            (20_000, 30_000, 0.25, 0.00),
        ],
        "normal": [
            (0, 7_000, 0.70, 0.40),
            (7_000, 14_000, 0.40, 0.25),
            (14_000, 20_000, 0.25, 0.00),
        ],
        "hard": [
            (0, 6_000, 0.70, 0.40),
            (6_000, 10_000, 0.40, 0.25),
            (10_000, 15_000, 0.25, 0.00),
        ],
    }

    WORDS_PER_GAME: int = 10
    _DURATIONS: dict[str, int] = {
        "easy": 30_000,
        "normal": 20_000,
        "hard": 15_000,
    }
    TICK_MS: int = 100

    def __init__(self, db_manager, parent=None):
        super().__init__(db_manager, parent)
        # Timers
        self._tick_timer: QTimer | None = None
        self._elapsed: QElapsedTimer = QElapsedTimer()
        self._remaining_ms: int = self._DURATIONS["easy"]
        self._pending_timers: list[QTimer] = []

        # Pool
        self._pool: list = []
        self._pool_index: int = 0
        self._last_word_id: int | None = None
        self._current_word = None

        # Hint state
        self._hint_used: bool = False
        self._hint_active: bool = False

        # Blur effect (created once, reused); label is empty at construction
        self._blur_effect = QGraphicsBlurEffect()
        self._blur_effect.setBlurRadius(0)

        # Finished guard
        self._finished_emitted: bool = False

        self._layout.setContentsMargins(16, 8, 16, 8)
        self._layout.setSpacing(8)
        self._build_ui()

        # Duration based on difficulty combo (combo built in _build_ui)
        self._duration_ms: int = self._DURATIONS[self._difficulty_key()]
        self._diff_combo.currentTextChanged.connect(self._on_difficulty_changed)

    # ── UI Construction ────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the blur game interface."""
        # ── Difficulty picker ──
        diff_layout = QHBoxLayout()
        diff_label = QLabel("Difficulty:")
        diff_label.setStyleSheet(label_style(Fonts.CALLOUT, Colors.SECONDARY_LABEL))
        diff_layout.addWidget(diff_label)

        self._diff_combo = QComboBox()
        self._diff_combo.addItems(["Easy", "Normal", "Hard"])
        self._diff_combo.setStyleSheet(combo_box_style())
        diff_layout.addWidget(self._diff_combo)
        diff_layout.addStretch()
        self._layout.addLayout(diff_layout)

        # ── Blurred word label (centered, big) ──
        self._word_label = QLabel("")
        self._word_label.setStyleSheet(
            label_style(Fonts.TITLE_1, Colors.PRIMARY_LABEL)
        )
        self._word_label.setAlignment(Qt.AlignCenter)
        self._word_label.setGraphicsEffect(self._blur_effect)
        self._layout.addWidget(self._word_label)

        # ── Timer label ──
        self._timer_label = QLabel("\u23f1 30.0s")
        self._timer_label.setStyleSheet(
            label_style(Fonts.CALLOUT, Colors.SECONDARY_LABEL)
        )
        self._timer_label.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._timer_label)

        # ── Input field ──
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type the word here...")
        self._input.setStyleSheet(input_field_style())
        self._input.returnPressed.connect(self._on_submit)
        self._layout.addWidget(self._input)

        # ── Hint button ──
        self._hint_btn = QLabel("\U0001f4a1 Hint (1 left)")
        self._hint_btn.setStyleSheet(
            label_style(Fonts.CALLOUT, Colors.ORANGE)
        )
        self._hint_btn.setAlignment(Qt.AlignCenter)
        self._hint_btn.setCursor(Qt.PointingHandCursor)
        self._hint_btn.mousePressEvent = lambda _: self._on_hint()
        self._layout.addWidget(self._hint_btn)

        # ── Status label ──
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(
            label_style(Fonts.CALLOUT, Colors.SECONDARY_LABEL)
        )
        self._status_label.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._status_label)

        # ── Bottom bar: progress + score ──
        progress_layout = QHBoxLayout()
        progress_layout.setContentsMargins(0, 2, 0, 0)
        self._progress_label = QLabel("Words: 0/10")
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

        self._layout.addStretch()

    # ── Difficulty helpers ────────────────────────────────────────────────

    def _difficulty_key(self) -> str:
        """Return the lowercase difficulty key from the combo box."""
        return self._diff_combo.currentText().strip().lower()

    def _on_difficulty_changed(self, _text: str) -> None:
        """Handle difficulty change — reset the game and show a new word.

        Mirrors the game_bomb reset pattern: guard on active words, update
        the duration, cancel timers, reset counters, then show a fresh word
        (``_pick_next_word`` skips the current word id, so no repeat).
        """
        if not self._current_words:
            return

        self._duration_ms = self._DURATIONS[self._difficulty_key()]
        self._cancel_pending_timers()
        if self._tick_timer is not None:
            self._tick_timer.stop()

        self._current_index = 0
        self._correct_count = 0
        self._total_count = 0
        self._finished_emitted = False
        self._hint_used = False
        self._hint_active = False

        self._pool = list(self._current_words)
        random.shuffle(self._pool)
        self._pool_index = 0

        self._score_label.setText("Score: 0%")
        self._progress_label.setText(f"Words: 0/{len(self._current_words)}")
        self._close_btn.setText("\u2715  Close")
        self._word_label.setStyleSheet(
            label_style(Fonts.TITLE_1, Colors.PRIMARY_LABEL)
        )
        self._input.setStyleSheet(input_field_style())

        self._show_word()

    # ── Game Lifecycle ─────────────────────────────────────────────────

    def setup_game(self, words) -> None:
        """Initialize game with words.

        Args:
            words: List of WordRecord objects.
        """
        super().setup_game(words)
        self._finished_emitted = False
        self._hint_used = False
        self._last_word_id = None
        self._cancel_pending_timers()
        self._duration_ms = self._DURATIONS[self._difficulty_key()]

        # Limit to WORDS_PER_GAME
        game_words = self._current_words[: self.WORDS_PER_GAME]
        self._current_words = game_words
        self._current_index = 0
        self._correct_count = 0
        self._total_count = 0

        # Pool
        self._pool = list(game_words)
        random.shuffle(self._pool)
        self._pool_index = 0

        self._score_label.setText("Score: 0%")
        self._progress_label.setText(f"Words: 0/{len(game_words)}")
        self._close_btn.setText("\u2715  Close")

        self._show_word()

    def cleanup(self) -> None:
        """Clean up resources — stop tick timer, cancel pending timers."""
        self._cancel_pending_timers()
        if self._tick_timer is not None:
            self._tick_timer.stop()
            self._tick_timer.deleteLater()
            self._tick_timer = None
        super().cleanup()

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

        if len(self._pool) > 1 and word.id == self._last_word_id:
            if self._pool_index < len(self._pool):
                word = self._pool[self._pool_index]
                self._pool_index += 1

        self._last_word_id = word.id
        return word

    def _show_word(self) -> None:
        """Display the next blurred word with a fresh countdown."""
        if self.is_finished:
            self._finish_game()
            return

        self._current_word = self._pick_next_word()

        # Reset state
        self._hint_used = False
        self._hint_active = False
        self._word_label.setVisible(True)
        self._input.setVisible(True)
        self._hint_btn.setVisible(True)
        self._hint_btn.setText("\U0001f4a1 Hint (1 left)")
        self._hint_btn.setStyleSheet(
            label_style(Fonts.CALLOUT, Colors.ORANGE)
        )

        # Set blurred word — start at 70% of the font size; the 100ms tick
        # drives the piecewise blur down to 0 as the countdown runs.
        self._blur_effect.setBlurRadius(
            self._blur_radius(self.BLUR_START_FRACTION)
        )
        self._word_label.setText(self._current_word.word)
        self._word_label.setVisible(True)

        # Clear input
        self._input.clear()
        self._input.setStyleSheet(input_field_style())
        self._input.setEnabled(True)
        self._input.setFocus()

        # Status
        self._status_label.setText("Type the word!")
        self._status_label.setStyleSheet(
            label_style(Fonts.CALLOUT, Colors.SECONDARY_LABEL)
        )

        # Start countdown
        self._remaining_ms = self._duration_ms
        self._elapsed = QElapsedTimer()
        self._elapsed.start()

        if self._tick_timer is None:
            self._tick_timer = QTimer(self)
            self._tick_timer.setInterval(self.TICK_MS)
            self._tick_timer.timeout.connect(self._on_tick)
        self._tick_timer.start()

    def _word_font_size_px(self) -> int:
        """Return the word label's rendered font size in pixels.

        The label's font is set via stylesheet (Fonts.TITLE_1), so parse
        the ``font-size`` rule from the stylesheet rather than relying on
        QFont (which is not polished in headless tests).

        Returns:
            Font size in pixels; falls back to Fonts.TITLE_1 (28px) if
            the stylesheet has no explicit ``font-size`` rule.
        """
        match = re.search(r"font-size:\s*(\d+)px", self._word_label.styleSheet())
        if match is None:
            return self._FONT_SIZE_FALLBACK_PX
        return int(match.group(1))

    def _blur_fraction(self, elapsed_ms: int) -> float:
        """Return the blur fraction (0.0-0.70) for the given elapsed time.

        Piecewise linear per difficulty: each segment interpolates from its
        start fraction to its end fraction over its time span.  Past the
        last segment the fraction is 0.0 (fully clear).

        Args:
            elapsed_ms: Milliseconds elapsed since the word was shown.

        Returns:
            Blur fraction in [0.0, 0.70].
        """
        schedule = self.BLUR_SCHEDULES[self._difficulty_key()]
        for start_ms, end_ms, start_frac, end_frac in schedule:
            if elapsed_ms <= end_ms:
                span = end_ms - start_ms
                if span <= 0:
                    return start_frac
                t = (elapsed_ms - start_ms) / span
                return start_frac + (end_frac - start_frac) * t
        return 0.0

    def _blur_radius(self, fraction: float) -> float:
        """Convert a blur fraction to a pixel radius.

        The start value keeps the historical ``max(8, …)`` floor; all other
        values are ``font_px * fraction`` (the end reaches 0).

        Args:
            fraction: Blur fraction in [0.0, 0.70].

        Returns:
            Blur radius in pixels.
        """
        font_px = self._word_font_size_px()
        if fraction >= self.BLUR_START_FRACTION:
            return float(max(8, int(font_px * fraction)))
        return font_px * fraction

    # ── Tick Timer ─────────────────────────────────────────────────────

    def _on_tick(self) -> None:
        """Update countdown display and blur radius; end word when time runs out."""
        elapsed = self._elapsed.elapsed()
        remaining = self._remaining_ms - elapsed
        if remaining <= 0:
            self._on_timeout()
            return
        self._timer_label.setText(f"\u23f1 {remaining / 1000.0:.1f}s")
        # While the hint shows the translation, keep the blur off.
        if not self._hint_active:
            self._blur_effect.setBlurRadius(
                self._blur_radius(self._blur_fraction(elapsed))
            )

    def _on_timeout(self) -> None:
        """Handle countdown expiry — record wrong, show word, advance."""
        if self._tick_timer is not None:
            self._tick_timer.stop()

        self.record_answer(self._current_word.id, False)
        self._score_label.setText(f"Score: {self.score_text}")
        self._timer_label.setText("\u23f1 0.0s")

        # Show the word unblurred briefly
        self._blur_effect.setBlurRadius(0)
        self._word_label.setText(f"{self._current_word.word}  ({self._current_word.translation})")
        self._input.setEnabled(False)
        self._status_label.setText("\u23f0  Time's up!")
        self._status_label.setStyleSheet(
            label_style(Fonts.CALLOUT, Colors.RED)
        )

        self._progress_label.setText(
            f"Words: {self._current_index}/{len(self._current_words)}"
        )

        self._schedule(self._show_word, 1500)

    # ── Answer Handling ────────────────────────────────────────────────

    def _on_submit(self) -> None:
        """Handle user pressing Enter in the input field."""
        text = self._input.text().strip().lower()
        if not text:
            return

        correct_text = self._current_word.word.strip().lower()

        if text == correct_text:
            self._on_correct()
        else:
            self._on_wrong()

    def _on_correct(self) -> None:
        """Handle a correct answer."""
        if self._tick_timer is not None:
            self._tick_timer.stop()

        self.record_answer(self._current_word.id, True)
        self._score_label.setText(f"Score: {self.score_text}")

        # Green feedback
        self._blur_effect.setBlurRadius(0)
        self._word_label.setText(
            f"{self._current_word.word} \u2713"
        )
        self._word_label.setStyleSheet(
            label_style(Fonts.TITLE_1, Colors.GREEN)
        )
        self._input.setEnabled(False)
        self._status_label.setText("\u2705  Correct!")
        self._status_label.setStyleSheet(
            label_style(Fonts.CALLOUT, Colors.GREEN)
        )

        self._progress_label.setText(
            f"Words: {self._current_index}/{len(self._current_words)}"
        )

        self._schedule(self._advance_word, 600)

    def _on_wrong(self) -> None:
        """Handle a wrong answer — record, flash red, advance."""
        if self._tick_timer is not None:
            self._tick_timer.stop()

        self.record_answer(self._current_word.id, False)
        self._score_label.setText(f"Score: {self.score_text}")

        # Red flash on input
        self._input.setStyleSheet(
            f"{input_field_style()} border: 2px solid {Colors.RED};"
        )
        self._input.setEnabled(False)
        self._status_label.setText(
            f"\u274c  Wrong! It was: {self._current_word.word}"
        )
        self._status_label.setStyleSheet(
            label_style(Fonts.CALLOUT, Colors.RED)
        )

        self._progress_label.setText(
            f"Words: {self._current_index}/{len(self._current_words)}"
        )

        self._schedule(self._show_word, 1000)

    def _advance_word(self) -> None:
        """Advance to the next word (after correct feedback)."""
        # Reset word label style
        self._word_label.setStyleSheet(
            label_style(Fonts.TITLE_1, Colors.PRIMARY_LABEL)
        )
        self._show_word()

    # ── Hint Mechanic ──────────────────────────────────────────────────

    def _on_hint(self) -> None:
        """Toggle the hint: replace the blurred word with the translation.

        First click shows the translation in the word label (blur disabled,
        input hidden).  Second click restores the blurred word + input and
        exhausts the hint (1 use per word).  Clicks after that are no-ops.
        """
        if self._current_word is None or self._hint_used:
            return
        if not self._input.isEnabled():
            return

        if not self._hint_active:
            # Show the translation instead of the blurred word
            self._hint_active = True
            self._blur_effect.setBlurRadius(0)
            self._word_label.setText(self._current_word.translation)
            self._input.setVisible(False)
            self._hint_btn.setText("\U0001f4a1 Hide hint")
            self._hint_btn.setStyleSheet(
                label_style(Fonts.CALLOUT, Colors.ORANGE)
            )
        else:
            # Restore the blurred word + input; hint is now exhausted
            self._hint_active = False
            self._hint_used = True
            self._word_label.setText(self._current_word.word)
            self._blur_effect.setBlurRadius(
                self._blur_radius(self._blur_fraction(self._elapsed.elapsed()))
            )
            self._input.setVisible(True)
            self._input.setFocus()
            self._hint_btn.setText("\U0001f4a1 Hint (0 left)")
            self._hint_btn.setStyleSheet(
                label_style(Fonts.CALLOUT, Colors.TERTIARY_LABEL)
            )

    # ── Game Finish ────────────────────────────────────────────────────

    def _finish_game(self) -> None:
        """End the game — stop timers, show final status, emit finished."""
        if self._finished_emitted:
            return
        self._finished_emitted = True

        self._cancel_pending_timers()
        if self._tick_timer is not None:
            self._tick_timer.stop()
            self._tick_timer.deleteLater()
            self._tick_timer = None

        self._input.setEnabled(False)
        self._blur_effect.setBlurRadius(0)
        self._word_label.setStyleSheet(
            label_style(Fonts.TITLE_1, Colors.PRIMARY_LABEL)
        )
        self._word_label.setText("Game Over")
        self._hint_btn.setVisible(False)
        self._timer_label.setText("")
        self._status_label.setText(
            f"\U0001f389  Finished! Accuracy: {self.score_text}"
        )
        self._status_label.setStyleSheet(
            label_style(Fonts.CALLOUT, Colors.GREEN)
        )
        self._close_btn.setText("Finish")

    # ── Timer Management ───────────────────────────────────────────────

    def _schedule(self, callback, ms: int) -> None:
        """Schedule a delayed callback via managed pending timers.

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
