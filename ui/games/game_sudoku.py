"""Word Sudoku: Latin-square word placement puzzle.

Three difficulty levels:
- Easy:    4×4 grid (4 words), large cells
- Hard:    6×6 grid (6 words), medium cells
- Expert:  9×9 grid (9 words), small cells

Each row/column has each word exactly once.  Empty cells (~40%) must be
filled by the player using the word palette.  Correct placement locks green;
wrong placement flashes red and reverts.
"""
import random

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.games.game_base import BaseGame
from ui.games.components.flip_card import FlipCard
from ui.styles import (
    Colors,
    Fonts,
    card_style,
    combo_box_style,
    destructive_button_style,
    label_style,
    pill_button_style,
    progress_label_style,
    score_label_style,
    HIDDEN_CARD_STYLE,
    MATCHED_CARD_STYLE,
    SELECTED_CARD_STYLE,
)


class WordSudokuWidget(BaseGame):
    """Latin-square word placement puzzle.

    Easy:   4×4, 4 words
    Hard:   6×6, 6 words
    Expert: 9×9, 9 words

    Each row/column contains each word exactly once (Latin square).
    Player fills empty cells using the word palette.
    """

    finished = Signal()

    DIFFICULTIES: dict[str, dict] = {
        "easy":   {"size": 4},
        "hard":   {"size": 6},
        "expert": {"size": 9},
    }

    # Qt applies QPushButton stylesheet min/max-height to the CONTENT area
    # (excluding padding + border).  The shared card styles use padding: 10px
    # (x2) + border: 2px (x2) = 24px of chrome, so stylesheet heights must be
    # cell_height - 24 to yield an exact cell_height widget.
    _CELL_CHROME = 24

    # Cell metrics are computed dynamically from the longest word in the
    # current board (see _compute_cell_metrics) — no static per-difficulty sizes.

    def __init__(self, db_manager, parent=None):
        super().__init__(db_manager, parent)
        self._difficulty: str = "easy"
        self._grid_size: int = 4
        self._solution: list[list[str]] = []
        self._cells: list[list[FlipCard | None]] = []
        self._empty_cells: list[tuple[int, int]] = []
        self._filled_count: int = 0
        self._empty_total: int = 0
        self._selected_cell: tuple[int, int] | None = None
        self._selected_palette: QPushButton | None = None
        self._palette_buttons: list[QPushButton] = []
        self._cell_width: int = 72
        self._cell_height: int = 48
        self._cell_font_size: int = 15
        self._finished_emitted: bool = False
        self._pending_timers: list[QTimer] = []
        self._layout.setContentsMargins(16, 8, 16, 8)
        self._layout.setSpacing(8)
        self._build_ui()

    # ── UI Construction ────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the word sudoku interface."""
        # ── Difficulty picker ──
        diff_layout = QHBoxLayout()
        diff_label = QLabel("Difficulty:")
        diff_label.setStyleSheet(
            label_style(Fonts.CALLOUT, Colors.SECONDARY_LABEL)
        )
        diff_layout.addWidget(diff_label)
        self._diff_combo = QComboBox()
        self._diff_combo.addItems(["Easy", "Hard", "Expert"])
        self._diff_combo.setStyleSheet(combo_box_style())
        self._diff_combo.currentTextChanged.connect(self._on_difficulty_change)
        diff_layout.addWidget(self._diff_combo)
        diff_layout.addStretch()
        self._layout.addLayout(diff_layout)

        # ── Status label ──
        self._status_label = QLabel("Fill the empty cells using the word palette!")
        self._status_label.setStyleSheet(
            label_style(Fonts.CALLOUT, Colors.SECONDARY_LABEL)
        )
        self._status_label.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._status_label)

        # ── Word palette (compact, directly below the label) ──
        self._palette_scroll = QScrollArea()
        self._palette_scroll.setWidgetResizable(True)
        self._palette_scroll.setFrameShape(QFrame.NoFrame)
        self._palette_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._palette_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._palette_scroll.setFixedHeight(48)
        self._palette_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )
        self._palette_widget = QWidget()
        self._palette_layout = QHBoxLayout(self._palette_widget)
        self._palette_layout.setContentsMargins(0, 4, 0, 4)
        self._palette_layout.setSpacing(6)
        self._palette_scroll.setWidget(self._palette_widget)
        self._layout.addWidget(self._palette_scroll)

        # ── Grid (horizontal scroll only; height fixed to the board so the
        #    whole grid is always visible without vertical scrolling) ──
        self._grid_scroll = QScrollArea()
        self._grid_scroll.setWidgetResizable(True)
        self._grid_scroll.setFrameShape(QFrame.NoFrame)
        self._grid_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._grid_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._grid_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )
        self._grid_widget = QWidget()
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(4)
        self._grid.setAlignment(Qt.AlignCenter)
        self._grid_scroll.setWidget(self._grid_widget)
        self._layout.addWidget(self._grid_scroll)

        # ── Bottom bar: progress | score ──
        progress_layout = QHBoxLayout()
        progress_layout.setContentsMargins(0, 2, 0, 0)
        self._progress_label = QLabel("Filled: 0/0")
        self._progress_label.setStyleSheet(progress_label_style())
        progress_layout.addWidget(self._progress_label)
        progress_layout.addStretch()
        self._score_label = QLabel("")
        self._score_label.setStyleSheet(score_label_style())
        progress_layout.addWidget(self._score_label)
        self._layout.addLayout(progress_layout)

        # ── Footer: close button, full width (matches all other games) ──
        self._layout.addStretch()
        self._close_btn = QPushButton("\u2715  Close")
        self._close_btn.setStyleSheet(destructive_button_style())
        self._close_btn.clicked.connect(self.finished.emit)
        self._layout.addWidget(self._close_btn)

    # ── Adaptive Sizing ────────────────────────────────────────────────

    def _compute_cell_metrics(self, words_upper: list[str]) -> tuple[int, int, int]:
        """Compute cell width/height and font size that fit the longest word.

        Cell width = measured width of the longest word at the chosen font
        size plus padding (24px), capped at 200px so the grid stays usable.
        If the longest word does not fit at the max font (18px), the font is
        reduced until it fits within the cap.  Cell height is fixed at 48px
        so rows stay compact.  Full words always fit — the main grid never
        elides; if the grid is wider than the play area the QScrollArea
        scrolls horizontally.

        Args:
            words_upper: Uppercase words used as board symbols.

        Returns:
            Tuple of (cell_width, cell_height, font_size) in pixels.
        """
        longest = max(words_upper, key=len)
        padding = 24
        cap = 200
        cell_height = 48

        for font_size in range(18, 9, -1):
            font = QFont()
            font.setPixelSize(font_size)
            font.setBold(True)
            text_width = QFontMetrics(font).horizontalAdvance(longest)
            if text_width + padding <= cap:
                return text_width + padding, cell_height, font_size

        # Extremely long word: grow the cell beyond the cap so the full word
        # is always visible (horizontal scroll handles the overflow).
        font = QFont()
        font.setPixelSize(10)
        font.setBold(True)
        text_width = QFontMetrics(font).horizontalAdvance(longest)
        return text_width + padding, cell_height, 10

    def _elide_text(self, text: str, width: int, font_size: int) -> str:
        """Elide text with an ellipsis if it does not fit the given width.

        Args:
            text: Full text to display.
            width: Available width in pixels.
            font_size: Font size in pixels used for measurement.

        Returns:
            The elided text (e.g. "ELEPH…") or the original if it fits.
        """
        font = QFont()
        font.setPixelSize(font_size)
        metrics = QFontMetrics(font)
        return metrics.elidedText(text, Qt.ElideRight, width)

    def _apply_cell_style(self, cell: FlipCard, base_style: str) -> None:
        """Apply a card style with the adaptive font and cell sizing overrides.

        FlipCard._apply_style() applies the plain shared card styles whose
        ``min-height: 50px`` would override the fixed cell height, so every
        style application must re-assert the adaptive font size and the exact
        cell height.

        Args:
            cell: The cell to style.
            base_style: Shared card style constant (HIDDEN/MATCHED/SELECTED).
        """
        content_height = self._cell_height - self._CELL_CHROME
        cell.setStyleSheet(
            f"{base_style} QPushButton {{ font-size: {self._cell_font_size}px; "
            f"min-height: {content_height}px; max-height: {content_height}px; }}"
        )

    # ── Game Lifecycle ─────────────────────────────────────────────────

    def setup_game(self, words) -> None:
        """Initialize game with words.

        Args:
            words: List of WordRecord objects.
        """
        super().setup_game(words)
        self._finished_emitted = False
        self._cancel_pending_timers()
        self._close_btn.setText("\u2715  Close")
        try:
            self._close_btn.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        self._close_btn.clicked.connect(self.finished.emit)
        self._build_board()

    def cleanup(self) -> None:
        """Clean up resources — cancel all pending timers."""
        self._cancel_pending_timers()
        super().cleanup()

    # ── Board Generation ───────────────────────────────────────────────

    def _build_board(self) -> None:
        """Clear and rebuild the grid for the current difficulty."""
        self._cancel_pending_timers()

        # Clear old grid
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Clear old palette
        while self._palette_layout.count():
            item = self._palette_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._palette_buttons = []

        # Determine grid size
        diff = self.DIFFICULTIES[self._difficulty]
        n = min(diff["size"], len(self._current_words))
        self._grid_size = n

        # Pick n words as symbols
        game_words = self._current_words[:n]
        words_upper = [w.word.upper() for w in game_words]

        # Adaptive cell metrics from the longest word in this board
        cell_width, cell_height, font_size = self._compute_cell_metrics(words_upper)
        self._cell_width = cell_width
        self._cell_height = cell_height
        self._cell_font_size = font_size

        # Generate Latin square: solution[r][c] = words[(r + c) % n]
        self._solution = []
        for r in range(n):
            row = []
            for c in range(n):
                row.append(words_upper[(r + c) % n])
            self._solution.append(row)

        # Randomly empty ~40% of cells
        self._empty_cells = []
        self._filled_count = 0
        self._empty_total = 0
        self._cells = [[None] * n for _ in range(n)]

        for r in range(n):
            for c in range(n):
                word_upper = self._solution[r][c]
                # Find the WordRecord for this word
                word_record = game_words[words_upper.index(word_upper)]
                is_empty = random.random() < 0.4

                if is_empty:
                    # Empty cell: shows "?" on front, translation on back
                    cell = FlipCard("?", word_record.translation)
                    cell.setFixedSize(cell_width, cell_height)
                    self._apply_cell_style(cell, HIDDEN_CARD_STYLE)
                    cell.clicked.connect(
                        lambda checked, row=r, col=c: self._on_cell_click(row, col)
                    )
                    self._empty_cells.append((r, c))
                    self._empty_total += 1
                else:
                    # Filled cell: shows the full word, locked
                    cell = FlipCard(word_upper, word_upper)
                    cell.setFixedSize(cell_width, cell_height)
                    cell.setToolTip(word_upper)
                    cell.set_locked(True)
                    self._apply_cell_style(cell, MATCHED_CARD_STYLE)
                    self._filled_count += 1

                self._cells[r][c] = cell
                self._grid.addWidget(cell, r, c)

        # Fix the grid height so the whole board is always visible without
        # vertical scrolling (horizontal scroll handles wide grids).
        grid_height = n * cell_height + (n - 1) * self._grid.spacing()
        self._grid_widget.setFixedHeight(grid_height)
        self._grid_scroll.setFixedHeight(grid_height + 10)

        # Build word palette (elided text + full word tooltip)
        self._selected_cell = None
        self._selected_palette = None
        palette_max_width = max(96, cell_width * 2)
        for i, w in enumerate(game_words):
            word_upper = w.word.upper()
            btn = QPushButton(
                self._elide_text(word_upper, palette_max_width - 24, 15)
            )
            btn.setToolTip(word_upper)
            btn.setMaximumWidth(palette_max_width)
            btn.setStyleSheet(
                pill_button_style(Colors.CARD_BG_ALT, Fonts.SUBHEADLINE)
            )
            btn.clicked.connect(
                lambda checked, idx=i: self._on_palette_click(idx)
            )
            self._palette_buttons.append(btn)
            self._palette_layout.addWidget(btn)

        self._update_progress()
        self._status_label.setText("Fill the empty cells using the word palette!")

    # ── Interaction ────────────────────────────────────────────────────

    def _on_cell_click(self, row: int, col: int) -> None:
        """Handle clicking an empty cell — flip to reveal translation."""
        cell = self._cells[row][col]
        if cell is None or cell.is_flipped():
            return

        cell.flip()
        # Re-assert the adaptive style (FlipCard._apply_style drops the
        # font-size/min-height overrides, which would break cell sizing).
        self._apply_cell_style(cell, SELECTED_CARD_STYLE)
        self._selected_cell = (row, col)
        self._status_label.setText(
            f"Cell ({row + 1}, {col + 1}) — select a word from the palette"
        )

    def _on_palette_click(self, word_index: int) -> None:
        """Handle clicking a palette button — place word if cell selected."""
        if self._selected_cell is None:
            self._status_label.setText("Click an empty cell first, then a word!")
            return

        row, col = self._selected_cell
        cell = self._cells[row][col]
        if cell is None:
            return

        placed_word = self._solution[row][col]
        game_words = self._current_words[: self._grid_size]
        word_upper = [w.word.upper() for w in game_words]
        placed_index = word_upper.index(placed_word)
        word_record = game_words[placed_index]

        # Check if placement is correct (compare against the FULL word,
        # not the elided button text)
        palette_word = game_words[word_index].word.upper()
        if palette_word == placed_word:
            # ✅ CORRECT — lock cell green (full word, no elision)
            cell.set_faces(placed_word, placed_word)
            cell.setText(placed_word)  # show the word even if cell is flipped
            cell.setToolTip(placed_word)
            cell.set_locked(True)
            self._apply_cell_style(cell, MATCHED_CARD_STYLE)
            self._filled_count += 1
            self._empty_cells.remove((row, col))
            self._update_progress()
            self._status_label.setText(f"\u2705  Correct! '{placed_word}' placed.")

            # Record answer
            self.record_answer(word_record.id, True)

            # Check win
            if not self._empty_cells:
                self._handle_win()
        else:
            # ❌ WRONG — red flash then revert to "?"
            cell.setStyleSheet(
                f"QPushButton {{ background-color: {Colors.RED}; "
                f"color: {Colors.PRIMARY_LABEL}; border: 2px solid {Colors.RED}; "
                f"border-radius: 12px; padding: 10px; font-size: {self._cell_font_size}px; "
                f"font-weight: bold; "
                f"min-height: {self._cell_height - self._CELL_CHROME}px; }}"
            )
            self._status_label.setText(
                f"\u274c  Wrong! '{palette_word}' doesn't go here."
            )
            self.record_answer(word_record.id, False)

            # Revert after 500ms
            _cell = cell
            t = QTimer(self)
            t.setSingleShot(True)
            t.timeout.connect(lambda: self._revert_cell(_cell))
            t.start(500)
            self._pending_timers.append(t)

        self._selected_cell = None

    def _revert_cell(self, cell: FlipCard) -> None:
        """Revert a cell back to hidden state after wrong placement."""
        try:
            if cell is not None and not cell._locked and cell.is_flipped():
                cell.flip()  # back to front ("?"), keeps translation on back
                # Re-assert the adaptive style (FlipCard._apply_style drops
                # the font-size/min-height overrides, which would break sizing)
                self._apply_cell_style(cell, HIDDEN_CARD_STYLE)
        except RuntimeError:
            pass

    # ── Win State ──────────────────────────────────────────────────────

    def _handle_win(self) -> None:
        """Handle winning the game."""
        if self._finished_emitted:
            return
        self._finished_emitted = True
        self._status_label.setText(
            f"\U0001f389  Solved! {self.score_text}"
        )
        self._close_btn.setText("Finish")
        try:
            self._close_btn.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        self._close_btn.clicked.connect(self._finish_and_emit)

    def _finish_and_emit(self) -> None:
        """Emit finished (one-shot guard)."""
        if self._finished_emitted:
            self._finished_emitted = False
            self.finished.emit()

    # ── Difficulty Change ──────────────────────────────────────────────

    def _shuffle_word_pool(self) -> None:
        """Shuffle the word pool so the next board uses different words."""
        random.shuffle(self._current_words)

    def _on_difficulty_change(self, text: str) -> None:
        """Handle difficulty change — rebuild grid with NEW words."""
        self._difficulty = text.lower()
        if self._current_words:
            self._finished_emitted = False
            self._cancel_pending_timers()
            self._close_btn.setText("\u2715  Close")
            try:
                self._close_btn.clicked.disconnect()
            except (RuntimeError, TypeError):
                pass
            self._close_btn.clicked.connect(self.finished.emit)
            self._shuffle_word_pool()
            self._build_board()

    # ── Timer Management ───────────────────────────────────────────────

    def _cancel_pending_timers(self) -> None:
        """Cancel and clean up all pending delayed callbacks."""
        for timer in self._pending_timers:
            try:
                timer.stop()
                timer.deleteLater()
            except RuntimeError:
                pass
        self._pending_timers.clear()

    # ── Progress ───────────────────────────────────────────────────────

    def _update_progress(self) -> None:
        """Update the progress and score labels."""
        self._progress_label.setText(
            f"Filled: {self._filled_count}/{self._empty_total + self._filled_count}"
        )
        self._score_label.setText(self.score_text)

    # ── Property Overrides ─────────────────────────────────────────────

    @property
    def progress_text(self) -> str:
        return (
            f"Filled: {self._filled_count}"
            f"/{self._empty_total + self._filled_count}"
        )

    @property
    def score_text(self) -> str:
        if self._total_count == 0:
            return "0%"
        return f"{int(self._correct_count / self._total_count * 100)}%"
