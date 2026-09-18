"""Logic tests for Word Snake game (offline, no display).

Covers the fixed 10x20 grid geometry and the wrong-letter reset
behavior (all letters restored and reshuffled, snake reset to 1).
"""
import os
import sys
import tempfile
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication

import ui.games.game_snake as game_snake_module
from database.db_manager import DatabaseManager
from ui.games.components.word_features import letters_of
from ui.games.game_snake import (
    SnakeWidget, _CELL_PX, _GRID_COLS, _GRID_ROWS, _GRID_SPACING,
)

app = QApplication.instance() or QApplication([])


def _make_db(words):
    """Create an in-memory DB with the given (word, translation) pairs."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = DatabaseManager(path)
    db.connect()
    for word, translation in words:
        db.add_word(word, translation)
    return db, path


def _words(db):
    """Fetch all words as WordRecord objects."""
    return db.get_all_words()


def _enter_snake_phase(widget):
    """Drive Phase 1 to completion and start Phase 2 directly."""
    widget._on_word_picked(widget._correct_option)
    widget._start_snake()


def test_grid_geometry():
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо")])
    widget = SnakeWidget(db)
    widget.setup_game(_words(db))
    assert widget._rows == _GRID_ROWS == 10
    assert widget._cols == _GRID_COLS == 20
    assert widget._grid.spacing() == _GRID_SPACING == 2
    frame = widget._cells[0][0]
    assert frame.minimumWidth() == _CELL_PX == 26
    assert frame.maximumWidth() == _CELL_PX
    assert frame.minimumHeight() == _CELL_PX
    assert frame.maximumHeight() == _CELL_PX
    # Grid widget fixed to exact board size and centered via stretches.
    assert widget._grid_widget.minimumWidth() == 20 * 26 + 19 * 2
    assert widget._grid_widget.minimumHeight() == 10 * 26 + 9 * 2
    assert widget._grid_center.count() == 3
    assert widget._grid_center.itemAt(0).spacerItem() is not None
    assert widget._grid_center.itemAt(2).spacerItem() is not None
    assert widget._grid_center.itemAt(1).widget() is widget._grid_widget
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_grid_geometry: PASS")


def test_wrong_letter_restores_all_letters_reshuffled():
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо")])
    widget = SnakeWidget(db)
    widget.setup_game(_words(db))
    _enter_snake_phase(widget)
    original_count = len(widget._board)
    original_letters = sorted(widget._board.values())
    original_positions = set(widget._board.keys())
    assert original_count > 0
    # Simulate a collected (eaten) letter: removed from the board.
    eaten_pos = next(iter(widget._board))
    eaten_letter = widget._board.pop(eaten_pos)
    widget._collected.append(eaten_letter)
    assert len(widget._board) == original_count - 1
    # Wrong-letter hit -> reset.
    widget._reset_snake()
    assert len(widget._board) == original_count  # ALL letters restored
    assert sorted(widget._board.values()) == original_letters
    assert set(widget._board.keys()) != original_positions  # NEW positions
    assert len(widget._snake) == 1
    assert widget._collected == []
    # Each new attempt = fresh randomization.
    positions_after_first = set(widget._board.keys())
    widget._reset_snake()
    assert len(widget._board) == original_count
    assert sorted(widget._board.values()) == original_letters
    assert set(widget._board.keys()) != positions_after_first
    assert len(widget._snake) == 1
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_wrong_letter_restores_all_letters_reshuffled: PASS")


def _fake_generate_options(db, word, count, direction="reverse"):
    """Return exactly *count* letter-bearing options (deterministic).

    Args:
        db: DatabaseManager instance (unused).
        word: WordRecord — the question word.
        count: Number of options to generate.
        direction: Unused; kept for interface parity.

    Returns:
        Tuple of (options list, index of the correct option).
    """
    options = [word.word] + [f"word{i}" for i in range(1, count)]
    return options, 0


def test_option_counts_by_difficulty():
    """Each difficulty requests the configured number of answer options."""
    db, path = _make_db([("apple", "яблоко"), ("orange", "апельсин")])
    widget = SnakeWidget(db)
    widget.setup_game(_words(db))
    original = game_snake_module.generate_options
    game_snake_module.generate_options = _fake_generate_options
    try:
        widget._on_difficulty_change("")  # restart with patched options
        for diff, expected in (("Easy", 4), ("Normal", 6), ("Hard", 6)):
            widget._diff_combo.setCurrentText(diff)
            assert len(widget._options) == expected, (
                f"{diff}: expected {expected} options, got {len(widget._options)}"
            )
    finally:
        game_snake_module.generate_options = original
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_option_counts_by_difficulty: PASS")


def test_difficulty_target_visibility():
    """Easy shows the full word, Normal masks it, Hard hides it."""
    db, path = _make_db(
        [("apple", "яблоко"), ("orange", "апельсин"), ("banana", "банан")],
    )
    widget = SnakeWidget(db)
    widget.setup_game(_words(db))
    for diff, check in (
        ("Easy", lambda t: t == widget._target_word.word.upper()),
        ("Normal", lambda t: t != "" and "_" in t),
        ("Hard", lambda t: t == ""),
    ):
        widget._diff_combo.setCurrentText(diff)
        _enter_snake_phase(widget)
        assert check(widget._hint_label.text()), (
            f"{diff}: unexpected hint text {widget._hint_label.text()!r}"
        )
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_difficulty_target_visibility: PASS")


def test_hard_difficulty_no_next_letter_reveal():
    """Hard never reveals the next target letter in the status label."""
    db, path = _make_db(
        [("apple", "яблоко"), ("orange", "апельсин"), ("banana", "банан")],
    )
    widget = SnakeWidget(db)
    widget.setup_game(_words(db))
    widget._diff_combo.setCurrentText("Hard")
    _enter_snake_phase(widget)
    board_cell = next(iter(widget._board))
    widget._snake = deque([board_cell])
    letter = widget._board[board_cell]
    widget._collect_letter(letter, letters_of(widget._target_word.word))
    assert "next:" not in widget._status_label.text().lower()
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_hard_difficulty_no_next_letter_reveal: PASS")


if __name__ == "__main__":
    test_grid_geometry()
    test_wrong_letter_restores_all_letters_reshuffled()
    test_option_counts_by_difficulty()
    test_difficulty_target_visibility()
    test_hard_difficulty_no_next_letter_reveal()
    print("ALL SNAKE LOGIC TESTS PASSED")