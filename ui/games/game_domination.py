"""Domination: Territory-control game with a hidden-cell grid.

Player and teacher (CPU) alternate turns.  Each turn a cell is picked —
the player clicks one, the teacher picks a random unclaimed one — and
the player must choose the correct translation of that cell's word
before the countdown runs out.  Correct answers claim the cell for the
player (blue); wrong answers or timeouts give it to the teacher (red).
Each cell is worth 1 point; the player with the most cells wins.

Cells show only "?" — the words stay hidden until a cell is quizzed.
On the teacher's turn the pick is instant, but a glossy shimmer sweeps
across the remaining hidden cells (~3 s) before the chosen cell is
revealed with its word and translation options.

Difficulty levels:
- Easy:   4x5 grid (20 cells), 25 s per word, 4 translation options
- Normal: 4x7 grid (28 cells), 15 s per word, 6 translation options
- Hard:   4x9 grid (36 cells), 10 s per word, 6 translation options
"""
import random

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QElapsedTimer,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    Qt,
    Signal,
    QTimer,
)
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.games.game_base import BaseGame
from ui.games.components.multiple_choice import MultipleChoicePanel, generate_options
from ui.games.components.countdown_bar import CountdownBar
from ui.styles import (
    Colors,
    Fonts,
    _lighten,
    card_style,
    combo_box_style,
    destructive_button_style,
    label_style,
    progress_label_style,
    score_label_style,
)

# Grid sizes per difficulty: (rows, columns)
_GRID_SIZES: dict[str, tuple[int, int]] = {
    "easy": (4, 5),
    "normal": (4, 7),
    "hard": (4, 9),
}
_CELL_SIZE: int = 50

# Per-difficulty question settings
_TIMES: dict[str, int] = {"easy": 25000, "normal": 15000, "hard": 10000}
_OPTIONS: dict[str, int] = {"easy": 4, "normal": 6, "hard": 6}

# Teacher shimmer sweep: total reveal delay and per-card gloss duration (ms)
_SHIMMER_MS: int = 3000
_SHIMMER_SWEEP_MS: int = 1200


def _cell_style(owner: str | None, selected: bool = False) -> str:
    """Generate stylesheet for a grid cell based on owner state.

    Args:
        owner: ``"user"``, ``"teacher"``, or ``None`` (unclaimed).
        selected: True while the cell's word is being quizzed.
    """
    if owner == "user":
        bg, border = Colors.BLUE, Colors.BLUE_LIGHT
    elif owner == "teacher":
        bg, border = Colors.RED, Colors.RED_LIGHT
    elif selected:
        bg, border = Colors.CARD_BG_ALT, Colors.ORANGE
    else:
        bg, border = Colors.CARD_BG, Colors.SEPARATOR
    return (
        f"QFrame {{ background-color: {bg}; border: 2px solid {border}; "
        f"border-radius: 8px; }}"
        f"QFrame:hover {{ background-color: {_lighten(bg)}; }}"
        f"QFrame:disabled {{ background-color: {bg}; }}"
    )


class ShimmerCard(QFrame):
    """A hidden grid cell: shows "?" and can play a glossy sweep animation.

    Emits ``clicked(row, col)`` when the user clicks an enabled cell.
    """

    clicked = Signal(int, int)

    def __init__(self, row: int, col: int, parent=None):
        super().__init__(parent)
        self._row = row
        self._col = col
        self._shimmer_progress: float = -0.5
        self._shimmer_group: QSequentialAnimationGroup | None = None
        self.setFixedSize(_CELL_SIZE, _CELL_SIZE)
        self.setAttribute(Qt.WA_Hover, True)
        self.setCursor(Qt.PointingHandCursor)
        self._label = QLabel("?", self)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet(
            f"color: {Colors.PRIMARY_LABEL}; {Fonts.HEADLINE} "
            "background: transparent; border: none;"
        )
        self._label.setGeometry(0, 0, _CELL_SIZE, _CELL_SIZE)
        self.set_owner(None)

    @Property(float)
    def shimmerProgress(self) -> float:
        """Current shimmer sweep position, driven by QPropertyAnimation."""
        return self._shimmer_progress

    @shimmerProgress.setter
    def shimmerProgress(self, value: float) -> None:
        self._shimmer_progress = value
        self.update()

    def start_shimmer(self, delay_ms: int) -> None:
        """Play a glossy sweep across this card after *delay_ms*.

        Args:
            delay_ms: Delay before the sweep starts (staggered per cell).
        """
        self.stop_shimmer()
        self._shimmer_progress = -0.5
        anim = QPropertyAnimation(self, b"shimmerProgress", self)
        anim.setDuration(_SHIMMER_SWEEP_MS)
        anim.setStartValue(-0.5)
        anim.setEndValue(1.5)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        group = QSequentialAnimationGroup(self)
        group.addPause(delay_ms)
        group.addAnimation(anim)
        group.start()
        self._shimmer_group = group

    def stop_shimmer(self) -> None:
        """Stop any running shimmer animation and reset the gloss."""
        if self._shimmer_group is not None:
            self._shimmer_group.stop()
            self._shimmer_group.deleteLater()
            self._shimmer_group = None
        self._shimmer_progress = -0.5
        self.update()

    def set_owner(self, owner: str | None, selected: bool = False) -> None:
        """Apply the cell stylesheet and marker for the given owner state.

        Args:
            owner: ``"user"``, ``"teacher"``, or ``None`` (unclaimed).
            selected: True while the cell's word is being quizzed.
        """
        self.setStyleSheet(_cell_style(owner, selected))
        if owner == "user":
            self._label.setText("\u2713")  # ✓
        elif owner == "teacher":
            self._label.setText("\u2717")  # ✗
        else:
            self._label.setText("?")

    def mouseReleaseEvent(self, event) -> None:
        """Emit ``clicked(row, col)`` on a left release of an enabled card."""
        if event.button() == Qt.LeftButton and self.isEnabled():
            self.clicked.emit(self._row, self._col)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        """Paint the card, then the glossy sweep while the shimmer runs."""
        super().paintEvent(event)
        progress = self._shimmer_progress
        if not (-0.5 < progress < 1.5):
            return
        painter = QPainter(self)
        try:
            x_start = self.width() * progress
            x_end = x_start + self.width() * 0.5
            gradient = QLinearGradient(x_start, 0, x_end, 0)
            gradient.setColorAt(0.0, QColor(255, 255, 255, 0))
            gradient.setColorAt(0.5, QColor(255, 255, 255, 90))
            gradient.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_Plus
            )
            painter.setPen(Qt.NoPen)
            painter.setBrush(gradient)
            painter.drawRect(self.rect())
        finally:
            painter.end()


class DominationWidget(BaseGame):
    """Territory-control game: answer questions to capture grid cells.

    Hidden-cell grid ("?").  Player and teacher alternate turns; each
    turn one cell's word is quizzed.  Correct → player captures the
    cell, wrong/timeout → teacher captures it.  Most cells wins.
    """

    finished = Signal()

    def __init__(self, db_manager, parent=None):
        super().__init__(db_manager, parent)
        self._turn: str = "user"
        self._user_score: int = 0
        self._teacher_score: int = 0
        self._claimed_count: int = 0
        self._active_cell: tuple[int, int] | None = None
        self._active_word = None
        self._teacher_target: tuple[int, int] | None = None
        self._question_active: bool = False
        self._question_time_ms: int = 25000
        self._game_over_shown: bool = False
        self._finished_emitted: bool = False
        self._pending_timers: list[QTimer] = []
        self._tick_timer: QTimer | None = None
        self._elapsed: QElapsedTimer = QElapsedTimer()
        self._rows, self._cols = _GRID_SIZES["easy"]
        self._grid_owners: list[list[str | None]] = []
        self._cell_words: list[list] = []
        self._cell_widgets: list[list[ShimmerCard | None]] = []
        self._last_layout: tuple[int, ...] | None = None
        self._panel: MultipleChoicePanel | None = None
        self._banner: QFrame | None = None
        self._layout.setContentsMargins(16, 8, 16, 8)
        self._layout.setSpacing(8)
        self._build_ui()

    # ── UI Construction ────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the domination game interface."""
        # ── Difficulty picker ──
        diff_row = QHBoxLayout()
        diff_label = QLabel("Difficulty:")
        diff_label.setStyleSheet(
            label_style(Fonts.CALLOUT, Colors.SECONDARY_LABEL)
        )
        diff_row.addWidget(diff_label)
        self._diff_combo = QComboBox()
        self._diff_combo.addItems(["Easy", "Normal", "Hard"])
        self._diff_combo.setStyleSheet(combo_box_style())
        self._diff_combo.currentTextChanged.connect(self._on_difficulty_change)
        diff_row.addWidget(self._diff_combo)
        diff_row.addStretch()
        self._layout.addLayout(diff_row)

        # ── Score row ──
        score_row = QHBoxLayout()
        self._player_label = QLabel("You: 0")
        self._player_label.setStyleSheet(
            f"color: {Colors.BLUE}; {Fonts.HEADLINE} padding: 2px;"
        )
        score_row.addWidget(self._player_label)
        score_row.addStretch()
        self._teacher_label = QLabel("Teacher: 0")
        self._teacher_label.setStyleSheet(
            f"color: {Colors.RED}; {Fonts.HEADLINE} padding: 2px;"
        )
        score_row.addWidget(self._teacher_label)
        self._layout.addLayout(score_row)

        # ── Hidden-cell grid ──
        self._grid_widget = QWidget()
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setSpacing(4)
        self._layout.addWidget(self._grid_widget)

        # ── Countdown bar ──
        self._countdown = CountdownBar()
        self._countdown.set_max(_TIMES["easy"])
        self._layout.addWidget(self._countdown)

        # ── Multiple-choice panel (2-column options) ──
        self._panel = MultipleChoicePanel(columns=2)
        self._panel.answered.connect(self._on_answer)
        self._layout.addWidget(self._panel)

        # ── Bottom bar: progress | score ──
        progress_layout = QHBoxLayout()
        progress_layout.setContentsMargins(0, 2, 0, 0)
        self._progress_label = QLabel(f"Cells: 0/{self._cell_count}")
        self._progress_label.setStyleSheet(progress_label_style())
        progress_layout.addWidget(self._progress_label)
        progress_layout.addStretch()
        self._score_label = QLabel("")
        self._score_label.setStyleSheet(score_label_style())
        progress_layout.addWidget(self._score_label)
        self._layout.addLayout(progress_layout)

        # ── Close button ──
        self._close_btn = QPushButton("\u2715  Close")
        self._close_btn.setStyleSheet(destructive_button_style())
        self._close_btn.clicked.connect(self.finished.emit)
        self._layout.addWidget(self._close_btn)

    # ── Grid Management ────────────────────────────────────────────────

    def _build_grid(self) -> None:
        """Clear and rebuild the hidden-cell grid for the current difficulty."""
        # Remove previous banner if any
        if self._banner is not None:
            self._layout.removeWidget(self._banner)
            self._banner.deleteLater()
            self._banner = None

        self._stop_shimmer()

        # Clear existing grid widgets
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._rows, self._cols = _GRID_SIZES[self._difficulty_name()]
        self._grid_owners = [[None] * self._cols for _ in range(self._rows)]
        self._cell_words = [[None] * self._cols for _ in range(self._rows)]
        self._cell_widgets = [[None] * self._cols for _ in range(self._rows)]

        self._assign_words()

        for row in range(self._rows):
            for col in range(self._cols):
                cell = ShimmerCard(row, col)
                cell.clicked.connect(self._on_cell_clicked)
                self._grid.addWidget(cell, row, col)
                self._cell_widgets[row][col] = cell

        self._user_score = 0
        self._teacher_score = 0
        self._claimed_count = 0
        self._update_scores()
        self._progress_label.setText(self.progress_text)

    def _assign_words(self) -> None:
        """Fill the grid cells with words from the pool.

        The pool is shuffled and cycled; a few swap passes reduce cases
        where the same word lands in adjacent cells.  The arrangement is
        guaranteed to differ from the previous grid layout (no repeat).
        """
        pool = list(self._current_words)
        if not pool:
            return
        count = self._cell_count
        flat = [pool[i % len(pool)] for i in range(count)]
        # Reshuffle until the arrangement differs from the previous grid.
        attempts = 0
        while (
            self._last_layout is not None
            and tuple(w.id for w in flat) == self._last_layout
            and attempts < 50
        ):
            random.shuffle(pool)
            flat = [pool[i % len(pool)] for i in range(count)]
            attempts += 1
        for _ in range(4):
            for i in range(count):
                row, col = divmod(i, self._cols)
                if self._has_same_neighbor(flat, row, col):
                    for j in range(i + 1, count):
                        jrow, jcol = divmod(j, self._cols)
                        if (
                            flat[j].id != flat[i].id
                            and not self._has_same_neighbor(flat, jrow, jcol)
                        ):
                            flat[i], flat[j] = flat[j], flat[i]
                            if self._has_same_neighbor(flat, row, col):
                                flat[i], flat[j] = flat[j], flat[i]
                            else:
                                break
        self._last_layout = tuple(w.id for w in flat)
        for i in range(count):
            row, col = divmod(i, self._cols)
            self._cell_words[row][col] = flat[i]

    def _has_same_neighbor(self, flat: list, row: int, col: int) -> bool:
        """Return True if any 4-neighbor of (row, col) holds the same word.

        Args:
            flat: Flat list of WordRecord objects (row-major).
            row: Grid row of the cell to check.
            col: Grid column of the cell to check.
        """
        word = flat[row * self._cols + col]
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = row + dr, col + dc
            if 0 <= nr < self._rows and 0 <= nc < self._cols:
                if flat[nr * self._cols + nc].id == word.id:
                    return True
        return False

    def _update_cell(self, row: int, col: int) -> None:
        """Refresh a single cell's visual state.

        Args:
            row: Grid row of the cell.
            col: Grid column of the cell.
        """
        cell = self._cell_widgets[row][col]
        if cell is None:
            return
        cell.set_owner(self._grid_owners[row][col])

    # ── Score Display ──────────────────────────────────────────────────

    def _update_scores(self) -> None:
        """Update the score labels."""
        self._player_label.setText(f"You: {self._user_score}")
        self._teacher_label.setText(f"Teacher: {self._teacher_score}")
        self._score_label.setText(f"Accuracy: {self.score_text}")

    # ── Cell Helpers ───────────────────────────────────────────────────

    def _unclaimed_cells(self) -> list[tuple[int, int]]:
        """Return (row, col) pairs for all unclaimed cells."""
        return [
            (r, c)
            for r in range(self._rows)
            for c in range(self._cols)
            if self._grid_owners[r][c] is None
        ]

    def _enable_unclaimed_cells(self, enabled: bool) -> None:
        """Enable or disable all unclaimed cell buttons.

        Args:
            enabled: True to make unclaimed cells clickable.
        """
        for r, c in self._unclaimed_cells():
            self._cell_widgets[r][c].setEnabled(enabled)

    # ── Game Lifecycle ─────────────────────────────────────────────────

    def setup_game(self, words) -> None:
        """Initialize game with a list of words.

        Args:
            words: List of WordRecord objects.
        """
        super().setup_game(words)
        self._turn = "user"
        self._user_score = 0
        self._teacher_score = 0
        self._claimed_count = 0
        self._active_cell = None
        self._active_word = None
        self._teacher_target = None
        self._question_active = False
        self._game_over_shown = False
        self._finished_emitted = False
        self._cancel_pending_timers()
        self._stop_countdown()
        self._build_grid()
        self._panel.reset_feedback()
        self._close_btn.setText("\u2715  Close")
        self._connect_close_button()
        self._show_round()

    def _show_round(self) -> None:
        """Start the next turn: user picks a cell, or teacher picks one."""
        if self._claimed_count >= self._cell_count:
            self._game_over()
            return

        self._question_active = False
        self._active_cell = None
        self._active_word = None

        if self._turn == "user":
            self._enable_unclaimed_cells(True)
            self._panel.set_question("")
            self._panel.set_options([], -1)
            self._panel.set_status("Pick a cell")
            self._panel.set_combo_text("")
            self._panel.reset_feedback()
            self._countdown.set_remaining(0)
        else:
            self._enable_unclaimed_cells(False)
            self._teacher_pick()

    def _teacher_pick(self) -> None:
        """Teacher instantly picks a cell, then shimmers before revealing it.

        The pick itself is instant (no thinking delay); the reveal waits
        for the ~3 s glossy sweep across the remaining hidden cells.
        """
        unclaimed = self._unclaimed_cells()
        if not unclaimed:
            self._game_over()
            return
        self._teacher_target = random.choice(unclaimed)
        self._panel.set_status("Teacher is picking...")
        self._start_shimmer_sweep(unclaimed)
        self._schedule(self._reveal_teacher_pick, _SHIMMER_MS)

    def _start_shimmer_sweep(self, cells: list[tuple[int, int]]) -> None:
        """Stagger a glossy sweep across the given cells over ~3 seconds.

        Args:
            cells: (row, col) pairs of the cells to shimmer.
        """
        self._stop_shimmer()
        total = len(cells)
        for i, (r, c) in enumerate(cells):
            delay = int(i * (_SHIMMER_MS / total))
            self._cell_widgets[r][c].start_shimmer(delay)

    def _reveal_teacher_pick(self) -> None:
        """Reveal the teacher's chosen cell and start its question."""
        self._stop_shimmer()
        if self._teacher_target is None:
            return
        row, col = self._teacher_target
        self._teacher_target = None
        self._start_question(row, col)

    def _stop_shimmer(self) -> None:
        """Stop all shimmer animations on the grid."""
        for row in self._cell_widgets:
            for card in row:
                if card is not None:
                    card.stop_shimmer()

    def _on_cell_clicked(self, row: int, col: int) -> None:
        """Handle a user click on an unclaimed cell.

        Args:
            row: Grid row of the clicked cell.
            col: Grid column of the clicked cell.
        """
        if self._turn != "user" or self._question_active:
            return
        if self._grid_owners[row][col] is not None:
            return
        self._start_question(row, col)

    def _start_question(self, row: int, col: int) -> None:
        """Lock the cell, show its word + options, and start the countdown.

        Args:
            row: Grid row of the cell being quizzed.
            col: Grid column of the cell being quizzed.
        """
        self._question_active = True
        self._active_cell = (row, col)
        self._active_word = self._cell_words[row][col]

        # Lock the picked cell and disable the rest
        cell = self._cell_widgets[row][col]
        cell.setEnabled(False)
        cell.set_owner(None, selected=True)
        self._enable_unclaimed_cells(False)

        # Show the word + translation options
        option_count = _OPTIONS[self._difficulty_name()]
        options, correct_index = generate_options(
            self.db, self._active_word, option_count, "forward"
        )
        self._panel.set_question(self._active_word.word.upper())
        self._panel.set_options(options, correct_index)
        self._panel.set_status("Choose the correct translation:")
        self._panel.set_combo_text("")
        self._panel.reset_feedback()

        # Start the per-word countdown
        self._question_time_ms = _TIMES[self._difficulty_name()]
        self._start_countdown(self._question_time_ms)

    def _on_answer(self, is_correct: bool) -> None:
        """Handle the player's answer: resolve the cell, then next turn.

        Args:
            is_correct: True if the chosen option was correct.
        """
        if not self._question_active:
            return
        self._question_active = False
        self._stop_countdown()

        word = self._active_word
        self.record_answer(word.id, is_correct)

        if is_correct:
            self._panel.set_status("Correct!")
        else:
            self._panel.set_status(f"Wrong! Answer: {word.translation}")

        self._resolve_cell(is_correct)
        self._schedule(self._next_turn, 600)

    def _on_timeout(self) -> None:
        """Countdown expired — treat as a wrong answer (teacher captures)."""
        if not self._question_active:
            return
        self._question_active = False
        self._stop_countdown()

        word = self._active_word
        self.record_answer(word.id, False)
        self._panel.set_status(f"Time's up! Answer: {word.translation}")
        self._panel.set_enabled(False)
        self._resolve_cell(False)
        self._schedule(self._next_turn, 600)

    def _resolve_cell(self, is_correct: bool) -> None:
        """Assign the active cell to the winner and update scores.

        Args:
            is_correct: True → player captures the cell, else teacher.
        """
        row, col = self._active_cell
        owner = "user" if is_correct else "teacher"
        self._grid_owners[row][col] = owner
        self._claimed_count += 1
        if is_correct:
            self._user_score += 1
        else:
            self._teacher_score += 1
        self._update_cell(row, col)
        self._update_scores()
        self._progress_label.setText(self.progress_text)

    def _next_turn(self) -> None:
        """Toggle the turn and start the next round."""
        self._turn = "teacher" if self._turn == "user" else "user"
        self._show_round()

    def _game_over(self) -> None:
        """Show the final result banner and switch the close button to Finish."""
        if self._game_over_shown:
            return
        self._game_over_shown = True
        self._stop_countdown()
        self._cancel_pending_timers()
        self._stop_shimmer()

        self._panel.set_enabled(False)
        self._panel.set_combo_text("")
        self._update_scores()

        if self._user_score > self._teacher_score:
            title = "\U0001f3c6  You win!"
            status = (
                f"\U0001f3c6 You win! {self._user_score} vs {self._teacher_score}"
            )
        elif self._teacher_score > self._user_score:
            title = "\U0001f916  Teacher wins!"
            status = (
                f"\U0001f916 Teacher wins! {self._teacher_score} "
                f"vs {self._user_score}"
            )
        else:
            title = "\U0001f91d  It's a tie!"
            status = f"\U0001f91d Tie! {self._user_score} vs {self._teacher_score}"
        self._panel.set_status(status)

        # Banner card
        banner = QFrame()
        banner.setStyleSheet(
            card_style(Colors.SECONDARY_BG, border_radius="12px")
        )
        banner_layout = QVBoxLayout(banner)
        banner_layout.setContentsMargins(16, 16, 16, 16)
        banner_layout.setSpacing(6)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color: {Colors.YELLOW}; {Fonts.TITLE_2} background: transparent;"
        )
        title_lbl.setAlignment(Qt.AlignCenter)
        banner_layout.addWidget(title_lbl)

        detail = QLabel(
            f"Cells: You {self._user_score} — Teacher {self._teacher_score}"
        )
        detail.setStyleSheet(
            f"color: {Colors.SECONDARY_LABEL}; {Fonts.BODY} background: transparent;"
        )
        detail.setAlignment(Qt.AlignCenter)
        banner_layout.addWidget(detail)

        if self._total_count > 0:
            acc = int(self._correct_count / self._total_count * 100)
            acc_lbl = QLabel(f"Accuracy: {acc}%")
            acc_lbl.setStyleSheet(
                f"color: {Colors.SECONDARY_LABEL}; {Fonts.CALLOUT} "
                "background: transparent;"
            )
            acc_lbl.setAlignment(Qt.AlignCenter)
            banner_layout.addWidget(acc_lbl)

        self._banner = banner
        self._layout.insertWidget(self._layout.count() - 1, banner)

        # Finish flow
        self._close_btn.setText("Finish")
        self._connect_close_button(self._finish_and_emit)

    def _finish_and_emit(self) -> None:
        """Emit ``finished`` exactly once (single-shot guard)."""
        if self._finished_emitted:
            return
        self._finished_emitted = True
        self.finished.emit()

    # ── Difficulty Change ──────────────────────────────────────────────

    def _on_difficulty_change(self, text: str) -> None:
        """Handle difficulty change — reset and restart if words are loaded."""
        if not self._current_words:
            return
        self._cancel_pending_timers()
        self._stop_countdown()
        self._stop_shimmer()
        self._turn = "user"
        self._user_score = 0
        self._teacher_score = 0
        self._claimed_count = 0
        self._active_cell = None
        self._active_word = None
        self._teacher_target = None
        self._question_active = False
        self._game_over_shown = False
        self._finished_emitted = False
        self._correct_count = 0
        self._total_count = 0
        self._build_grid()
        self._panel.reset_feedback()
        self._close_btn.setText("\u2715  Close")
        self._connect_close_button()
        self._show_round()

    # ── Countdown Management ───────────────────────────────────────────

    def _start_countdown(self, ms: int) -> None:
        """Start the per-word countdown using QElapsedTimer + tick timer.

        Args:
            ms: Full countdown duration in milliseconds.
        """
        self._countdown.set_max(ms)
        self._countdown.set_remaining(ms)
        self._countdown.set_danger(False)
        self._elapsed = QElapsedTimer()
        self._elapsed.start()
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(100)
        self._tick_timer.timeout.connect(self._on_tick)
        self._tick_timer.start()

    def _on_tick(self) -> None:
        """Update the countdown display; timeout when it reaches zero."""
        if not self._question_active:
            return
        remaining = self._question_time_ms - self._elapsed.elapsed()
        if remaining <= 0:
            self._on_timeout()
            return
        self._countdown.set_remaining(int(remaining))
        self._countdown.set_danger(remaining < 2000)

    def _stop_countdown(self) -> None:
        """Stop and clean up the countdown tick timer."""
        if self._tick_timer is not None:
            self._tick_timer.stop()
            self._tick_timer.deleteLater()
            self._tick_timer = None

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

    def _connect_close_button(self, callback=None) -> None:
        """Reconnect the close button to *callback* (default: emit finished).

        Args:
            callback: Callable to invoke on click; defaults to ``finished.emit``.
        """
        try:
            self._close_btn.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        self._close_btn.clicked.connect(callback or self.finished.emit)

    def cleanup(self) -> None:
        """Clean up resources — stop countdown, shimmer, pending timers."""
        self._stop_countdown()
        self._cancel_pending_timers()
        self._stop_shimmer()
        if self._panel:
            self._panel.cleanup()
        super().cleanup()

    # ── Property Overrides ─────────────────────────────────────────────

    def _difficulty_name(self) -> str:
        """Return the current difficulty key (lowercase combo text)."""
        return self._diff_combo.currentText().lower()

    @property
    def _cell_count(self) -> int:
        """Total number of cells for the current difficulty."""
        return self._rows * self._cols

    @property
    def progress_text(self) -> str:
        return f"Cells: {self._claimed_count}/{self._cell_count}"