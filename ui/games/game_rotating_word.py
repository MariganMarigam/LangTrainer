"""Rotating Word: Animated letter cards — type the translation.

The foreign word is shown as individual letter cards that oscillate
around their own axis (sinusoidal CW/CCW rotation, per-card random
phase) while letters are revealed one by one in random order (1 second
per card, fade-in).  Cards keep animating until the player types the
correct translation.  10 words per game.

Difficulty controls animation chaos:
- Easy:   gentle drift, subtle rotation (±45°, +15% chaos)
- Normal: medium spread, moderate rotation (±70°, +20% chaos)
- Hard:   chaotic scatter, heavy rotation (±110°) + scale (+30% chaos)
"""
import math
import random
from PySide6.QtCore import Qt, Signal, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QTransform, QPainter
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QFrame, QWidget, QSplitter, QGraphicsOpacityEffect,
)
from ui.games.game_base import BaseGame
from ui.games.components.word_features import letters_of
from ui.styles import (
    Colors, Fonts, label_style, combo_box_style, input_field_style,
    progress_label_style, score_label_style, destructive_button_style,
)


class LetterCard(QFrame):
    """Custom letter card with sinusoidal rotation, scale, and fade-in.

    Renders its frame background and child labels via paintEvent,
    applying translate → rotate → scale → translate-back around center.
    The letter stays hidden until reveal_letter() fades it in.
    """

    def __init__(self, letter: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAutoFillBackground(False)

        # Transform state
        self._rotation: float = 0.0
        self._scale: float = 1.0

        # Reveal state
        self._letter: str = letter
        self._is_revealed: bool = False
        self._opacity_anim: QPropertyAnimation | None = None

        self.setFixedSize(56, 56)
        self.setStyleSheet(
            f"""
            QFrame {{
                background-color: {Colors.CARD_BG};
                border: 2px solid {Colors.BLUE};
                border-radius: 10px;
            }}
            """
        )

        # Card layout with empty label (letter appears on reveal)
        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel("")
        self._label.setStyleSheet(
            f"color: {Colors.PRIMARY_LABEL}; {Fonts.TITLE_2}; "
            "background: transparent;"
        )
        self._label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self._label)

        # Opacity effect for fade-in animation (starts invisible)
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

    def reveal_letter(self) -> None:
        """Reveal the letter with a 1000ms fade-in animation.

        Sets the label text and animates the card opacity from 0 to 1
        using an OutCubic easing curve.  Guarded by _is_revealed.
        """
        if self._is_revealed:
            return
        self._label.setText(self._letter)
        self._is_revealed = True

        self._opacity_anim = QPropertyAnimation(
            self._opacity_effect, b"opacity", self
        )
        self._opacity_anim.setDuration(1000)
        self._opacity_anim.setStartValue(0.0)
        self._opacity_anim.setEndValue(1.0)
        self._opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._opacity_anim.start()

    def set_transform_effects(self, degrees: float, scale: float) -> None:
        """Set rotation (degrees) and scale around the card's own axis.

        Args:
            degrees: Sinusoidal rotation angle in degrees (CW/CCW).
            scale: Scale factor (clamped to a minimum of 0.2).
        """
        self._rotation = degrees
        self._scale = max(scale, 0.2)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        """Paint with QTransform: translate→center, rotate, scale, back."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setClipping(False)
        cx, cy = self.width() / 2.0, self.height() / 2.0
        t = QTransform()
        t.translate(cx, cy)
        t.rotate(self._rotation)
        t.scale(self._scale, self._scale)
        t.translate(-cx, -cy)
        painter.setTransform(t)
        super().paintEvent(event)
        painter.end()


# Difficulty → (spread_x, spread_y, rot_max, speed_mult, jitter_max, scale_max)
DifficultyParams = tuple[float, float, float, float, float, float]


class RotatingWordWidget(BaseGame):
    """Animated letter cards — type the translation to advance.

    Letters are revealed one by one in random order (1s apart, fade-in)
    while each card oscillates around its own axis (sinusoidal CW/CCW
    rotation, per-card random phase).  Cards keep animating until the
    correct translation is typed.  10 words per game.
    """

    finished = Signal()

    WORDS_PER_GAME: int = 10
    TICK_MS: int = 30
    CARD_SIZE: int = 56
    CARD_SPACING: int = 8
    CARDS_CONTAINER_HEIGHT: int = 160

    DIFFICULTIES: dict[str, DifficultyParams] = {
        "easy":   (15.0,  5.0,  45.0, 1.5, 0.5,  0.10),
        "normal": (40.0, 20.0,  70.0, 3.0, 1.5,  0.25),
        "hard":   (85.0, 45.0, 110.0, 5.0, 3.5,  0.45),
    }

    # Chaos multipliers: Easy +15%, Normal +20%, Hard +30%
    CHAOS_MULTIPLIERS: dict[str, float] = {
        "easy": 1.15,
        "normal": 1.20,
        "hard": 1.30,
    }

    # Sinusoidal rotation amplitude (degrees) per difficulty
    ROTATION_AMPLITUDES: dict[str, float] = {
        "easy": 45.0,
        "normal": 70.0,
        "hard": 110.0,
    }

    def __init__(self, db_manager, parent=None) -> None:
        super().__init__(db_manager, parent)
        self._anim_timer: QTimer | None = None
        self._anim_time: float = 0.0
        self._pending_timers: list[QTimer] = []
        self._letter_cards: list[LetterCard] = []
        self._base_positions: list[tuple[int, int]] = []
        self._phases: list[float] = []
        self._current_word = None
        self._pool: list = []
        self._pool_index: int = 0
        self._last_word_id: int | None = None
        self._finished_emitted: bool = False
        self._all_revealed: bool = False

        self._layout.setContentsMargins(16, 8, 16, 8)
        self._layout.setSpacing(8)
        self._build_ui()

    # ── Layout ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the rotating word interface with 50/50 split layout."""
        # ── Difficulty picker ──
        diff_layout = QHBoxLayout()
        diff_label = QLabel("Difficulty:")
        diff_label.setStyleSheet(
            label_style(Fonts.CALLOUT, Colors.SECONDARY_LABEL)
        )
        diff_layout.addWidget(diff_label)

        self._diff_combo = QComboBox()
        self._diff_combo.addItems(["Easy", "Normal", "Hard"])
        self._diff_combo.setStyleSheet(combo_box_style())
        self._diff_combo.currentTextChanged.connect(self._on_difficulty_changed)
        diff_layout.addWidget(self._diff_combo)
        diff_layout.addStretch()
        self._layout.addLayout(diff_layout)

        # ── 50/50 split: cards top, input+close bottom ──
        self._splitter = QSplitter(Qt.Vertical)
        self._splitter.setChildrenCollapsible(False)

        # Top half: letter cards container (fixed height)
        self._cards_container = QWidget()
        self._cards_container.setMinimumHeight(self.CARDS_CONTAINER_HEIGHT)
        self._cards_container.setStyleSheet("background: transparent;")
        self._splitter.addWidget(self._cards_container)

        # Bottom half: input area
        bottom = QWidget()
        bottom.setMinimumHeight(self.CARDS_CONTAINER_HEIGHT)
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 8, 0, 0)
        bottom_layout.setSpacing(6)

        # ── Status label ──
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(
            label_style(Fonts.CALLOUT, Colors.SECONDARY_LABEL)
        )
        self._status_label.setAlignment(Qt.AlignCenter)
        bottom_layout.addWidget(self._status_label)

        # ── Input field ──
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type the translation...")
        self._input.setStyleSheet(input_field_style())
        self._input.returnPressed.connect(self._on_submit)
        bottom_layout.addWidget(self._input)

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
        bottom_layout.addLayout(progress_layout)

        # ── Close button ──
        self._close_btn = QPushButton("\u2715  Close")
        self._close_btn.setStyleSheet(destructive_button_style())
        self._close_btn.clicked.connect(self.finished.emit)
        bottom_layout.addWidget(self._close_btn)

        bottom_layout.addStretch()
        self._splitter.addWidget(bottom)

        # Equal stretch: 50% cards, 50% input area
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([1000, 1000])

        self._layout.addWidget(self._splitter)

    # ── Difficulty Change ──────────────────────────────────────────────

    def _on_difficulty_changed(self, _text: str) -> None:
        """Handle difficulty change — reset the game and show a new word.

        Cancels pending timers, stops the animation timer, resets counters,
        then shows a fresh word (``_pick_next_word`` skips the current word
        id, so no immediate repeat).
        """
        if not self._current_words:
            return

        self._cancel_pending_timers()
        if self._anim_timer is not None:
            self._anim_timer.stop()

        self._current_index = 0
        self._correct_count = 0
        self._total_count = 0
        self._finished_emitted = False
        self._all_revealed = False

        self._score_label.setText("Score: 0%")
        self._progress_label.setText(f"Words: 0/{len(self._current_words)}")
        self._close_btn.setText("\u2715  Close")

        self._show_word()

    # ── Resize tracking (centering fix) ─────────────────────────────────

    def resizeEvent(self, event) -> None:  # noqa: N802
        """Recalculate base positions when widget is resized.

        Fixes the first-word centering bug: at show() time the container
        width is still 0, so start_x is calculated wrong.  By recalculating
        on every resize (including the first one after show), all words
        including the first are centered correctly.
        """
        super().resizeEvent(event)
        if self._base_positions:
            self._recalc_base_positions()

    # ── Game Lifecycle ─────────────────────────────────────────────────

    def setup_game(self, words) -> None:
        """Initialize game with words.

        Args:
            words: List of WordRecord objects.
        """
        super().setup_game(words)
        self._finished_emitted = False
        self._last_word_id = None
        self._cancel_pending_timers()

        game_words = self._current_words[: self.WORDS_PER_GAME]
        self._current_words = game_words
        self._current_index = 0
        self._correct_count = 0
        self._total_count = 0

        self._pool = list(game_words)
        random.shuffle(self._pool)
        self._pool_index = 0

        self._score_label.setText("Score: 0%")
        self._progress_label.setText(f"Words: 0/{len(game_words)}")
        self._close_btn.setText("\u2715  Close")

        self._show_word()

    def cleanup(self) -> None:
        """Clean up resources — stop animation timer, cancel pending timers."""
        self._cancel_pending_timers()
        if self._anim_timer is not None:
            self._anim_timer.stop()
            self._anim_timer.deleteLater()
            self._anim_timer = None
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
        """Display the next word as animated letter cards."""
        if self.is_finished:
            self._finish_game()
            return

        self._current_word = self._pick_next_word()
        self._cancel_pending_timers()
        self._clear_cards()
        self._all_revealed = False

        letters = letters_of(self._current_word.word)
        total_width = (
            len(letters) * self.CARD_SIZE
            + (len(letters) - 1) * self.CARD_SPACING
        )
        cw = self._cards_container.width()
        start_x = max(0, (cw - total_width) // 2)
        base_y = max(
            0, (self._cards_container.height() - self.CARD_SIZE) // 2
        )

        self._phases = []
        diff_name = self._diff_combo.currentText().lower()

        # Create cards with per-card random sinusoidal phase
        for index, letter in enumerate(letters):
            card = LetterCard(letter, self._cards_container)
            base_x = start_x + index * (self.CARD_SIZE + self.CARD_SPACING)
            card.move(base_x, base_y)
            card.show()
            self._letter_cards.append(card)
            self._base_positions.append((base_x, base_y))
            self._phases.append(random.uniform(0, 2 * math.pi))

        # Reset input + status
        self._input.clear()
        self._input.setStyleSheet(input_field_style())
        self._input.setEnabled(True)
        self._input.setFocus()
        self._status_label.setText("Type the translation!")
        self._status_label.setStyleSheet(
            label_style(Fonts.CALLOUT, Colors.SECONDARY_LABEL)
        )

        # Start animation
        self._anim_time = 0.0
        if self._anim_timer is None:
            self._anim_timer = QTimer(self)
            self._anim_timer.setInterval(self.TICK_MS)
            self._anim_timer.timeout.connect(self._on_tick)
        self._anim_timer.start()

        # Defer first centering to after layout settles (fixes first-word bug)
        QTimer.singleShot(0, self._recalc_base_positions)

        # Start sequential letter reveal
        self._reveal_letters_sequentially()

    def _reveal_letters_sequentially(self) -> None:
        """Reveal letter cards one by one in random order, 1 second per card."""
        if not self._letter_cards:
            return

        # Create random order of card indices
        indices = list(range(len(self._letter_cards)))
        random.shuffle(indices)

        # Schedule reveal for each card
        for i, card_idx in enumerate(indices):
            card = self._letter_cards[card_idx]
            delay = i * 1000

            def reveal(c=card):
                try:
                    if not c._is_revealed:
                        c.reveal_letter()
                except RuntimeError:
                    pass

            self._schedule(reveal, delay)

        # Mark all revealed after last card
        total_time = len(self._letter_cards) * 1000 + 500
        self._schedule(self._mark_all_revealed, total_time)

    def _mark_all_revealed(self) -> None:
        """Mark that all letters have been revealed."""
        self._all_revealed = True

    def _clear_cards(self) -> None:
        """Remove all letter cards from the container."""
        for card in self._letter_cards:
            try:
                # Stop active animations before deletion
                if card._opacity_anim is not None:
                    card._opacity_anim.stop()
                card.deleteLater()
            except RuntimeError:
                pass
        self._letter_cards.clear()
        self._base_positions.clear()
        self._phases.clear()

    def _recalc_base_positions(self) -> None:
        """Recalculate and reposition letter cards centered in container."""
        if not self._letter_cards:
            return
        cw = self._cards_container.width()
        ch = self._cards_container.height()
        n = len(self._letter_cards)
        total_w = n * self.CARD_SIZE + (n - 1) * self.CARD_SPACING
        start_x = max(0, (cw - total_w) // 2)
        base_y = max(0, (ch - self.CARD_SIZE) // 2)

        self._base_positions = []
        for i, card in enumerate(self._letter_cards):
            x = start_x + i * (self.CARD_SIZE + self.CARD_SPACING)
            card.move(x, base_y)
            self._base_positions.append((x, base_y))

    # ── Animation ──────────────────────────────────────────────────────

    def _scaled_chaos(self, diff_name: str) -> tuple[float, float, float]:
        """Return chaos-scaled (spread_x, spread_y, jitter_max).

        Args:
            diff_name: Difficulty key ("easy", "normal", "hard").

        Returns:
            spread_x, spread_y, and jitter_max each multiplied by the
            difficulty's chaos multiplier (easy 1.15, normal 1.20, hard 1.30).
        """
        base = self.DIFFICULTIES.get(diff_name, self.DIFFICULTIES["normal"])
        mult = self.CHAOS_MULTIPLIERS.get(
            diff_name, self.CHAOS_MULTIPLIERS["normal"]
        )
        return base[0] * mult, base[1] * mult, base[4] * mult

    def _on_tick(self) -> None:
        """Drive one animation frame — sinusoidal rotation, spread, jitter.

        Per-letter chaos via:
        - sinusoidal rotation around the card's own axis:
          rot = sin(t * speed * 1.3 + phase) * rot_max (CW/CCW oscillation)
        - sinusoidal spread from word center (left −1, right +1)
        - scale   = 1 + cos(t * speed * 1.7 + phase) * scale_max * |spread|
        - high-freq jitter + micro-jitter (half amplitude) on x/y
        """
        self._anim_time += self.TICK_MS / 1000.0
        n = len(self._letter_cards)
        if n == 0:
            return

        # Recalc base positions in case container resized
        self._recalc_base_positions()

        diff_name = self._diff_combo.currentText().lower()
        _, _, rot_max, speed, _, scale_max = self.DIFFICULTIES.get(
            diff_name, self.DIFFICULTIES["normal"]
        )
        spread_x, spread_y, jitter_max = self._scaled_chaos(diff_name)
        dt = self.TICK_MS / 1000.0
        hw = (n - 1) / 2.0  # half-width in letter indices

        for i, card in enumerate(self._letter_cards):
            try:
                base_x, base_y = self._base_positions[i]
                phase = self._phases[i]

                # Direction: left letters −1, center 0, right letters +1
                if n > 1:
                    direction = (i - hw) / hw
                else:
                    direction = 0.0

                # Spread factor: sinusoidal wave from center outward and back
                spread_factor = math.sin(self._anim_time * speed * 0.4 + phase)

                # Positional offsets (distance from center scales the offset)
                dist = abs(i - hw) / max(hw, 1.0)
                dx = direction * spread_x * spread_factor * dist
                dy = spread_y * spread_factor * math.sin(
                    self._anim_time * speed * 0.6 + phase * 1.3
                ) * dist

                # Rotation: pure sinusoidal oscillation around own axis
                current_rot = (
                    math.sin(self._anim_time * speed * 1.3 + phase) * rot_max
                )

                # Scale: cosine wave, tied to spread
                scale_wave = math.cos(self._anim_time * speed * 1.7 + phase)
                current_scale = 1.0 + scale_wave * scale_max * abs(spread_factor)

                # High-frequency jitter + micro-jitter (half amplitude)
                dx += random.uniform(-jitter_max, jitter_max)
                dy += random.uniform(-jitter_max, jitter_max)
                dx += random.uniform(-jitter_max * 0.5, jitter_max * 0.5)
                dy += random.uniform(-jitter_max * 0.5, jitter_max * 0.5)

                # Position within container bounds
                card.set_transform_effects(current_rot, current_scale)
                new_x = int(base_x + dx)
                new_y = int(base_y + dy)
                cw = self._cards_container.width()
                ch = self._cards_container.height()
                new_x = max(0, min(new_x, cw - self.CARD_SIZE))
                new_y = max(0, min(new_y, ch - self.CARD_SIZE))
                card.move(new_x, new_y)
            except RuntimeError:
                pass

    # ── Answer Handling ────────────────────────────────────────────────

    def _on_submit(self) -> None:
        """Handle user pressing Enter in the input field."""
        text = self._input.text().strip().lower()
        if not text:
            return

        correct_text = self._current_word.translation.strip().lower()
        if text == correct_text:
            self._on_correct()
        else:
            self._on_wrong()

    def _on_correct(self) -> None:
        """Handle a correct answer."""
        if self._anim_timer is not None:
            self._anim_timer.stop()

        self.record_answer(self._current_word.id, True)
        self._score_label.setText(f"Score: {self.score_text}")

        self._status_label.setText("\u2705  Correct!")
        self._status_label.setStyleSheet(
            label_style(Fonts.CALLOUT, Colors.GREEN)
        )
        self._input.setEnabled(False)

        self._progress_label.setText(
            f"Words: {self._current_index}/{len(self._current_words)}"
        )
        self._schedule(self._show_word, 600)

    def _on_wrong(self) -> None:
        """Handle a wrong answer — record, flash red, advance."""
        self.record_answer(self._current_word.id, False)
        self._score_label.setText(f"Score: {self.score_text}")

        self._input.setStyleSheet(
            f"{input_field_style()} border: 2px solid {Colors.RED};"
        )
        self._input.setEnabled(False)
        self._status_label.setText(
            f"\u274c  Wrong! It was: {self._current_word.translation}"
        )
        self._status_label.setStyleSheet(
            label_style(Fonts.CALLOUT, Colors.RED)
        )

        self._progress_label.setText(
            f"Words: {self._current_index}/{len(self._current_words)}"
        )
        self._schedule(self._show_word, 1000)

    # ── Game Finish ────────────────────────────────────────────────────

    def _finish_game(self) -> None:
        """End the game — stop timers, show final status, emit finished."""
        if self._finished_emitted:
            return
        self._finished_emitted = True

        self._cancel_pending_timers()
        if self._anim_timer is not None:
            self._anim_timer.stop()
            self._anim_timer.deleteLater()
            self._anim_timer = None

        self._input.setEnabled(False)
        self._clear_cards()
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