"""Word Snake — letter-scatter selection + snake letter collection.

Phase 1 (selection): a translation is shown with foreign-word option
buttons.  Picking any option scatters that word's letters onto the grid
and removes the option; picking the correct word ends selection and
starts Phase 2.

Phase 2 (collection): a snake moves across the grid.  The head cell is
the "window": when it lands on the next needed letter of the target word
the letter locks into the snake (which grows by one cell).  Landing on a
wrong letter resets the snake to a single cell and ALL letters that were
on the board (including already-eaten ones) return at NEW random
positions — each attempt is a fresh shuffle.  Collecting the full word
advances to the next word (10 words per game).

Difficulty: Easy shows the full target word, Normal shows it masked
(s_to_e), Hard hides it entirely.  Tick speed grows per word
(×1.0, ×1.3, ×1.6, ...); double-tapping a direction boosts the next tick
to two cells.
"""
import random
import time
from collections import deque

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget,
)

from ui.games.components.multiple_choice import generate_options
from ui.games.components.word_features import letters_of
from ui.games.game_base import BaseGame
from ui.styles import (
    Colors, Fonts, combo_box_style, destructive_button_style,
    label_style, pill_button_style, progress_label_style, score_label_style,
)

_BASE_SPEED_MS = 500          # Tick interval for word 1 (speed ×1.0).
_BOOST_WINDOW_S = 0.3         # Double-tap window for the speed boost.
_OPTION_COUNTS = {"easy": 4, "normal": 6, "hard": 6}
_CELL_PX = 26
_GRID_ROWS = 10
_GRID_COLS = 20
_GRID_SPACING = 2

_EMPTY_STYLE = (
    f"QFrame {{ background-color: {Colors.CARD_BG}; border: none; "
    "border-radius: 6px; }"
)
_LETTER_STYLE = (
    f"QFrame {{ background-color: {Colors.CARD_BG_ALT}; "
    f"border: 1px solid {Colors.SEPARATOR}; border-radius: 6px; }}"
)
_SNAKE_STYLE = (
    f"QFrame {{ background-color: {Colors.GREEN}; border: none; "
    "border-radius: 6px; }"
)
_HEAD_STYLE = (
    f"QFrame {{ background-color: {Colors.GREEN_LIGHT}; "
    f"border: 2px solid {Colors.GREEN}; border-radius: 6px; }}"
)
_LETTER_TEXT_STYLE = (
    f"color: {Colors.PRIMARY_LABEL}; font-size: 14px; font-weight: semibold; "
    "background: transparent;"
)
_SNAKE_TEXT_STYLE = (
    "color: #0B3D1E; font-size: 14px; font-weight: semibold; "
    "background: transparent;"
)


class SnakeWidget(BaseGame):
    """Letter-scatter selection + snake letter collection game."""

    finished = Signal()

    def __init__(self, db_manager, parent=None):
        super().__init__(db_manager, parent)
        self._rows = _GRID_ROWS
        self._cols = 10
        self._cells: list[list[QFrame]] = []
        self._cell_labels: list[list[QLabel]] = []
        self._board: dict[tuple[int, int], str] = {}
        self._pre_scatter_letters: list[str] = []
        self._snake: deque[tuple[int, int]] = deque()
        self._direction: tuple[int, int] = (0, 1)
        self._collected: list[str] = []
        self._phase: str = "selection"
        self._word_index: int = 0
        self._target_word = None
        self._correct_option: str = ""
        self._options: list[str] = []
        self._option_buttons: list[QPushButton] = []
        self._tick_timer: QTimer | None = None
        self._pending_timers: list[QTimer] = []
        self._finished_emitted: bool = False
        self._wrong_events: int = 0
        self._boost_pending: bool = False
        self._last_dir_key: tuple[int, int] | None = None
        self._last_key_time: float = 0.0
        self._layout.setContentsMargins(16, 8, 16, 8)
        self._layout.setSpacing(8)
        self._build_ui()

    # ── UI Construction ────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the game interface (difficulty, board, labels, options)."""
        diff_layout = QHBoxLayout()
        diff_label = QLabel("Difficulty:")
        diff_label.setStyleSheet(
            label_style(Fonts.CALLOUT, Colors.SECONDARY_LABEL),
        )
        diff_layout.addWidget(diff_label)
        self._diff_combo = QComboBox()
        self._diff_combo.addItems(["Easy", "Normal", "Hard"])
        self._diff_combo.setStyleSheet(combo_box_style())
        self._diff_combo.currentTextChanged.connect(self._on_difficulty_change)
        diff_layout.addWidget(self._diff_combo)
        diff_layout.addStretch()
        self._layout.addLayout(diff_layout)

        self._grid_widget = QWidget()
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(_GRID_SPACING)
        self._grid_widget.setFixedSize(
            _GRID_COLS * _CELL_PX + (_GRID_COLS - 1) * _GRID_SPACING,
            _GRID_ROWS * _CELL_PX + (_GRID_ROWS - 1) * _GRID_SPACING,
        )
        self._grid_center = QHBoxLayout()
        self._grid_center.setContentsMargins(0, 0, 0, 0)
        self._grid_center.addStretch(1)
        self._grid_center.addWidget(self._grid_widget)
        self._grid_center.addStretch(1)
        self._layout.addLayout(self._grid_center)

        self._translation_label = QLabel("")
        self._translation_label.setStyleSheet(
            f"color: {Colors.PRIMARY_LABEL}; {Fonts.TITLE_2} "
            "background: transparent; padding: 4px;",
        )
        self._translation_label.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._translation_label)

        self._hint_label = QLabel("")
        self._hint_label.setStyleSheet(
            label_style(Fonts.HEADLINE, Colors.BLUE_LIGHT),
        )
        self._hint_label.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._hint_label)

        self._options_widget = QWidget()
        self._options_grid = QGridLayout(self._options_widget)
        self._options_grid.setContentsMargins(0, 0, 0, 0)
        self._options_grid.setSpacing(8)
        self._layout.addWidget(self._options_widget)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet(
            label_style(Fonts.BODY, Colors.SECONDARY_LABEL),
        )
        self._status_label.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._status_label)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 2, 0, 0)
        self._progress_label = QLabel("Words: 0/10")
        self._progress_label.setStyleSheet(progress_label_style())
        bottom.addWidget(self._progress_label)
        bottom.addStretch()
        self._score_label = QLabel("Score: 0%")
        self._score_label.setStyleSheet(score_label_style())
        bottom.addWidget(self._score_label)
        self._layout.addLayout(bottom)

        self._close_btn = QPushButton("\u2715  Close")
        self._close_btn.setStyleSheet(destructive_button_style())
        self._close_btn.clicked.connect(self._request_close)
        self._layout.addWidget(self._close_btn)

        self.setFocusPolicy(Qt.StrongFocus)

    def _build_board(self, words) -> None:
        """Build the fixed 10×20 letter grid.

        Args:
            words: List of WordRecord objects (kept for interface parity).
        """
        self._cols = _GRID_COLS
        self._rows = _GRID_ROWS
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cells = []
        self._cell_labels = []
        for r in range(self._rows):
            row_cells: list[QFrame] = []
            row_labels: list[QLabel] = []
            for c in range(self._cols):
                frame = QFrame()
                frame.setFixedSize(_CELL_PX, _CELL_PX)
                frame.setStyleSheet(_EMPTY_STYLE)
                lay = QVBoxLayout(frame)
                lay.setContentsMargins(0, 0, 0, 0)
                letter = QLabel("")
                letter.setAlignment(Qt.AlignCenter)
                letter.setStyleSheet(_LETTER_TEXT_STYLE)
                lay.addWidget(letter)
                self._grid.addWidget(frame, r, c)
                row_cells.append(frame)
                row_labels.append(letter)
            self._cells.append(row_cells)
            self._cell_labels.append(row_labels)

    # ── Game Lifecycle ─────────────────────────────────────────────────

    def setup_game(self, words) -> None:
        """Initialize the game with a word pool.

        Args:
            words: List of WordRecord objects.
        """
        super().setup_game(words)
        self._finished_emitted = False
        self._wrong_events = 0
        self._word_index = 0
        self._cancel_pending_timers()
        self._stop_tick_timer()
        self._close_btn.setText("\u2715  Close")
        self._score_label.setText("Score: 0%")
        self._build_board(words)
        self._start_word()
        self.setFocus()

    def _start_word(self) -> None:
        """Begin a new word round with the selection phase."""
        if self._word_index >= len(self._current_words):
            self._game_over()
            return
        self._target_word = self._current_words[self._word_index]
        self._phase = "selection"
        self._collected = []
        self._board = {}
        self._pre_scatter_letters = []
        self._snake = deque()
        self._boost_pending = False
        self._last_dir_key = None
        self._stop_tick_timer()
        self._render_board()
        self._show_selection()

    def _game_over(self) -> None:
        """End the game: stop timers, show stats, emit finished once."""
        if self._finished_emitted:
            return
        self._finished_emitted = True
        self._stop_tick_timer()
        self._cancel_pending_timers()
        self._status_label.setText(
            f"Game over! Words: {self._current_index}/{len(self._current_words)} "
            f"| Accuracy: {self.score_text}",
        )
        self._close_btn.setText("Finish")
        self.finished.emit()

    def _request_close(self) -> None:
        """Emit ``finished`` once (guarded)."""
        if self._finished_emitted:
            return
        self._finished_emitted = True
        self.finished.emit()

    # ── Phase 1: Word Selection ────────────────────────────────────────

    def _show_selection(self) -> None:
        """Show the translation prompt and word option buttons."""
        word = self._target_word
        self._translation_label.setText(word.translation)
        self._hint_label.setText("")
        count = _OPTION_COUNTS[self._diff_combo.currentText().lower()]
        options, correct_index = generate_options(
            self.db, word, count, "reverse",
        )
        self._correct_option = options[correct_index]
        self._options = [opt for opt in options if letters_of(opt)]
        while self._options_grid.count():
            item = self._options_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._option_buttons = []
        btn_style = pill_button_style(
            Colors.CARD_BG_ALT, height="40px", font_size="14px",
        )
        for i, opt in enumerate(self._options):
            btn = QPushButton(opt)
            btn.setStyleSheet(btn_style)
            btn.setMinimumHeight(40)
            btn.clicked.connect(
                lambda checked, text=opt: self._on_word_picked(text),
            )
            self._options_grid.addWidget(btn, i // 2, i % 2)
            self._option_buttons.append(btn)
        self._options_widget.show()
        self._translation_label.show()
        self._status_label.setText("Pick the word for the translation:")
        self.setFocus()

    def _on_word_picked(self, word_text: str) -> None:
        """Handle an option pick: scatter letters, remove the option.

        Args:
            word_text: The foreign word the user picked.
        """
        if self._phase != "selection":
            return
        self._scatter_letters(word_text)
        for btn in self._option_buttons:
            if btn.text() == word_text:
                btn.hide()
                break
        if word_text == self._correct_option:
            for btn in self._option_buttons:
                btn.hide()
            self._options_widget.hide()
            self._status_label.setText("Correct! Collect the word letters.")
            self._schedule(self._start_snake, 600)
        else:
            self._wrong_events += 1
            self._score_label.setText(f"Score: {self.score_text}")
            remaining = [b for b in self._option_buttons if not b.isHidden()]
            if not remaining:
                self._status_label.setText("No options left — new options!")
                self._schedule(self._restart_selection, 600)
            else:
                self._status_label.setText(
                    f"Wrong! Letters scattered. {len(remaining)} options left.",
                )
                self.setFocus()

    def _restart_selection(self) -> None:
        """Restart Phase 1 with fresh options on a cleared board."""
        if self._phase != "selection":
            return
        self._board = {}
        self._render_board()
        self._show_selection()

    def _scatter_letters(self, word_text: str) -> None:
        """Place each letter of *word_text* into a distinct empty cell.

        Args:
            word_text: The word whose letters are scattered.
        """
        empty = [
            (r, c)
            for r in range(self._rows)
            for c in range(self._cols)
            if (r, c) not in self._board
        ]
        random.shuffle(empty)
        for letter, pos in zip(letters_of(word_text), empty):
            self._board[pos] = letter
        self._render_board()

    # ── Phase 2: Snake Collection ──────────────────────────────────────

    def _start_snake(self) -> None:
        """Begin Phase 2: place the snake and start the tick timer."""
        if self._phase != "selection":
            return
        self._phase = "snake"
        self._collected = []
        self._pre_scatter_letters = list(self._board.values())
        self._snake = deque([self._random_free_cell()])
        self._direction = random.choice([(-1, 0), (1, 0), (0, -1), (0, 1)])
        self._boost_pending = False
        self._last_dir_key = None
        self._update_hint()
        self._status_label.setText("Collect the letters in order!")
        self._render_board()
        self._start_tick_timer()
        self.setFocus()

    def _random_free_cell(self) -> tuple[int, int]:
        """Pick a random cell with no letter and no snake body."""
        occupied = set(self._snake)
        free = [
            (r, c)
            for r in range(self._rows)
            for c in range(self._cols)
            if (r, c) not in occupied and (r, c) not in self._board
        ]
        if not free:
            free = [
                (r, c)
                for r in range(self._rows)
                for c in range(self._cols)
                if (r, c) not in occupied
            ]
        return random.choice(free)

    def _on_tick(self) -> None:
        """Advance the snake one cell (two when boosted)."""
        if self._phase != "snake":
            return
        steps = 2 if self._boost_pending else 1
        self._boost_pending = False
        for _ in range(steps):
            if self._phase != "snake":
                return
            self._step_snake()

    def _step_snake(self) -> None:
        """Move the snake one cell and handle letter collection."""
        head_r, head_c = self._snake[0]
        dr, dc = self._direction
        new_head = ((head_r + dr) % self._rows, (head_c + dc) % self._cols)
        target_letters = letters_of(self._target_word.word)
        letter = self._board.get(new_head)
        will_grow = self._is_needed_letter(letter, target_letters)
        body = set(self._snake) if will_grow else set(list(self._snake)[:-1])
        if new_head in body:
            self._reset_snake()
            return
        self._snake.appendleft(new_head)
        if will_grow:
            self._collect_letter(letter, target_letters)
        elif letter is not None:
            self._reset_snake()
        else:
            self._snake.pop()
            self._render_board()

    def _is_needed_letter(self, letter: str | None, target_letters: list[str]) -> bool:
        """Return True if *letter* is the next letter the snake needs.

        Args:
            letter: The letter on the cell the head moved onto.
            target_letters: The target word's letters in order.

        Returns:
            True when the letter matches the next uncollected target letter.
        """
        return (
            letter is not None
            and len(self._collected) < len(target_letters)
            and letter == target_letters[len(self._collected)]
        )

    def _collect_letter(self, letter: str, target_letters: list[str]) -> None:
        """Lock *letter* into the snake and grow by one cell.

        Args:
            letter: The collected letter.
            target_letters: The target word's letters in order.
        """
        self._collected.append(letter)
        del self._board[self._snake[0]]
        self._update_hint()
        if self._collected == target_letters:
            self._complete_word()
            return
        if self._diff_combo.currentText().lower() == "hard":
            # Hard hides the target word: never reveal the next letter.
            self._status_label.setText(f"Collected {letter}")
        else:
            self._status_label.setText(
                f"Collected {letter} — next: {target_letters[len(self._collected)]}",
            )
        self._render_board()

    def _reset_snake(self) -> None:
        """Reset the snake; restore ALL letters (incl. eaten) reshuffled.

        Every letter that was on the board when the snake phase started
        (including letters already collected) returns to the board at NEW
        random positions.  The snake resets to a single cell.
        """
        self._wrong_events += 1
        self._collected = []
        self._board = {}
        self._scatter_letters("".join(self._pre_scatter_letters))
        self._snake = deque([self._random_free_cell()])
        self._direction = random.choice([(-1, 0), (1, 0), (0, -1), (0, 1)])
        self._boost_pending = False
        self._score_label.setText(f"Score: {self.score_text}")
        self._status_label.setText("Wrong letter! Letters reshuffled, snake reset.")
        self._update_hint()
        self._render_board()

    def _complete_word(self) -> None:
        """Word fully collected: record the answer, advance to next word."""
        self._phase = "selection"  # stops any in-flight boosted tick loop
        self._stop_tick_timer()
        self.record_answer(self._target_word.id, True)
        self._score_label.setText(f"Score: {self.score_text}")
        self._progress_label.setText(self.progress_text)
        self._status_label.setText("Word complete!")
        self._word_index += 1
        self._schedule(self._start_word, 800)

    # ── Difficulty & Hint ──────────────────────────────────────────────

    def _on_difficulty_change(self, _text: str) -> None:
        """Restart the game from word 1 on difficulty change."""
        if not self._current_words:
            return
        self._cancel_pending_timers()
        self._stop_tick_timer()
        # Remember the word on screen so the restart avoids repeating it.
        current_id = self._target_word.id if self._target_word is not None else None
        self._word_index = 0
        self._wrong_events = 0
        self._score_label.setText("Score: 0%")
        # Force a NEW word: skip the first word if it repeats the current one.
        if (
            current_id is not None
            and len(self._current_words) > 1
            and self._current_words[0].id == current_id
        ):
            self._word_index = 1
        self._start_word()

    def _update_hint(self) -> None:
        """Update the target-word hint based on difficulty and progress."""
        if self._phase != "snake":
            self._hint_label.setText("")
            return
        diff = self._diff_combo.currentText().lower()
        if diff == "easy":
            self._hint_label.setText(self._target_word.word.upper())
        elif diff == "normal":
            self._hint_label.setText(self._mask_word(self._target_word.word))
        else:
            self._hint_label.setText("")

    def _mask_word(self, word: str) -> str:
        """Hide ~45% of the middle letters, keeping the first and last.

        Args:
            word: The word to mask.

        Returns:
            The masked word, e.g. "STONE" -> "S__NE".
        """
        letters = letters_of(word)
        n = len(letters)
        if n <= 3:
            return "".join(letters)
        hidden = min(n - 2, max(1, int(round(n * 0.45))))
        indices = list(range(1, n - 1))
        random.shuffle(indices)
        hide_set = set(indices[:hidden])
        return "".join("_" if i in hide_set else ch for i, ch in enumerate(letters))

    # ── Keyboard ───────────────────────────────────────────────────────

    def keyPressEvent(self, event) -> None:
        """Arrow keys and WASD steer the snake; double-tap boosts."""
        key = event.key()
        mapping = {
            Qt.Key_Up: (-1, 0), Qt.Key_W: (-1, 0),
            Qt.Key_Down: (1, 0), Qt.Key_S: (1, 0),
            Qt.Key_Left: (0, -1), Qt.Key_A: (0, -1),
            Qt.Key_Right: (0, 1), Qt.Key_D: (0, 1),
        }
        if key not in mapping:
            super().keyPressEvent(event)
            return
        if self._phase != "snake":
            return
        new_dir = mapping[key]
        if (new_dir[0] + self._direction[0] == 0
                and new_dir[1] + self._direction[1] == 0):
            return  # no 180° reversal
        self._direction = new_dir
        now = time.monotonic()
        if (new_dir == self._last_dir_key
                and (now - self._last_key_time) < _BOOST_WINDOW_S):
            self._boost_pending = True
        self._last_dir_key = new_dir
        self._last_key_time = now

    # ── Board Rendering ────────────────────────────────────────────────

    def _render_board(self) -> None:
        """Update cell styles and letters for the whole board."""
        snake_list = list(self._snake)
        head = snake_list[0] if snake_list else None
        body = snake_list[1:] if len(snake_list) > 1 else []
        body_letters: dict[tuple[int, int], str] = {}
        for offset, pos in enumerate(reversed(body)):
            if offset < len(self._collected):
                body_letters[pos] = self._collected[offset]
        for r in range(self._rows):
            for c in range(self._cols):
                pos = (r, c)
                frame = self._cells[r][c]
                label = self._cell_labels[r][c]
                if pos == head:
                    frame.setStyleSheet(_HEAD_STYLE)
                    label.setText("")
                elif pos in body_letters:
                    frame.setStyleSheet(_SNAKE_STYLE)
                    label.setText(body_letters[pos])
                    label.setStyleSheet(_SNAKE_TEXT_STYLE)
                elif pos in self._board:
                    frame.setStyleSheet(_LETTER_STYLE)
                    label.setText(self._board[pos])
                    label.setStyleSheet(_LETTER_TEXT_STYLE)
                else:
                    frame.setStyleSheet(_EMPTY_STYLE)
                    label.setText("")

    # ── Properties ─────────────────────────────────────────────────────

    @property
    def progress_text(self) -> str:
        """Show the number of completed words."""
        return f"Words: {self._current_index}/{len(self._current_words)}"

    @property
    def score_text(self) -> str:
        """Accuracy including wrong picks and wrong letters."""
        total = self._total_count + self._wrong_events
        if total == 0:
            return "0%"
        return f"{int(self._correct_count / total * 100)}%"

    # ── Timer Management ───────────────────────────────────────────────

    def _start_tick_timer(self) -> None:
        """Start the snake movement timer at the current speed."""
        self._stop_tick_timer()
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(self._current_interval())
        self._tick_timer.timeout.connect(self._on_tick)
        self._tick_timer.start()

    def _stop_tick_timer(self) -> None:
        """Stop and discard the tick timer."""
        if self._tick_timer is not None:
            self._tick_timer.stop()
            self._tick_timer.deleteLater()
            self._tick_timer = None

    def _current_interval(self) -> int:
        """Tick interval for the current word (speed grows per word)."""
        multiplier = 1.0 + 0.3 * self._word_index
        return max(50, int(_BASE_SPEED_MS / multiplier))

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
        self._stop_tick_timer()
        self._cancel_pending_timers()
        super().cleanup()