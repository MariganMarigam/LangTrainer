"""Logic tests for the Domination game (offline, no display).

Covers: per-difficulty grid sizes, hidden "?" cells, teacher shimmer
sweep + delayed reveal, correct/wrong/timeout cell ownership, and game
over on a full board.
"""
import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication

from database.db_manager import DatabaseManager
from ui.games.game_domination import (
    DominationWidget,
    _GRID_SIZES,
    _SHIMMER_MS,
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


def _cell_text(widget, row, col):
    """Return the visible text of a grid cell."""
    return widget._cell_widgets[row][col]._label.text()


def _new_widget(db):
    """Create a DominationWidget with words loaded and game set up."""
    widget = DominationWidget(db)
    widget.setup_game(_words(db))
    return widget


# ── Grid sizes ──────────────────────────────────────────────────────────

def test_grid_sizes_per_difficulty():
    db, path = _make_db([(f"word{i}", f"trans{i}") for i in range(12)])
    widget = _new_widget(db)
    for diff, (rows, cols) in _GRID_SIZES.items():
        widget._diff_combo.setCurrentText(diff.capitalize())
        assert widget._rows == rows, f"{diff}: rows {widget._rows} != {rows}"
        assert widget._cols == cols, f"{diff}: cols {widget._cols} != {cols}"
        assert widget._cell_count == rows * cols
        assert len(widget._cell_widgets) == rows
        assert len(widget._cell_widgets[0]) == cols
        assert widget._progress_label.text() == f"Cells: 0/{rows * cols}"
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_grid_sizes_per_difficulty: PASS")


def test_cells_show_question_mark():
    db, path = _make_db([(f"word{i}", f"trans{i}") for i in range(12)])
    widget = _new_widget(db)
    for r in range(widget._rows):
        for c in range(widget._cols):
            assert _cell_text(widget, r, c) == "?"
            assert (
                _cell_text(widget, r, c) != widget._cell_words[r][c].word
            ), "cell must not show the word"
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_cells_show_question_mark: PASS")


# ── Teacher turn: shimmer sweep then reveal ─────────────────────────────

def test_teacher_turn_shimmer_then_reveal():
    db, path = _make_db([(f"word{i}", f"trans{i}") for i in range(12)])
    widget = _new_widget(db)
    widget._turn = "teacher"
    widget._show_round()

    # Instant pick + shimmer animation objects on every unclaimed cell
    assert widget._teacher_target is not None
    unclaimed = widget._unclaimed_cells()
    assert unclaimed
    for r, c in unclaimed:
        assert widget._cell_widgets[r][c]._shimmer_group is not None, (
            f"cell ({r},{c}) has no shimmer animation"
        )

    # Reveal is scheduled ~3 s after the sweep starts
    assert widget._pending_timers
    assert widget._pending_timers[-1].interval() == _SHIMMER_MS

    # Simulate the reveal timer firing
    target = widget._teacher_target
    widget._reveal_teacher_pick()
    assert widget._question_active
    assert widget._active_cell == target
    assert widget._active_word is not None
    assert widget._panel._word_label.text() == widget._active_word.word.upper()
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_teacher_turn_shimmer_then_reveal: PASS")


# ── Answer resolution ───────────────────────────────────────────────────

def test_correct_answer_claims_blue():
    db, path = _make_db([(f"word{i}", f"trans{i}") for i in range(12)])
    widget = _new_widget(db)
    row, col = widget._unclaimed_cells()[0]
    widget._start_question(row, col)
    widget._on_answer(True)
    assert widget._grid_owners[row][col] == "user"
    assert widget._user_score == 1
    assert widget._total_count == 1
    assert widget._correct_count == 1
    assert _cell_text(widget, row, col) == "\u2713"
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_correct_answer_claims_blue: PASS")


def test_wrong_answer_claims_red():
    db, path = _make_db([(f"word{i}", f"trans{i}") for i in range(12)])
    widget = _new_widget(db)
    row, col = widget._unclaimed_cells()[0]
    widget._start_question(row, col)
    widget._on_answer(False)
    assert widget._grid_owners[row][col] == "teacher"
    assert widget._teacher_score == 1
    assert widget._total_count == 1
    assert widget._correct_count == 0
    assert _cell_text(widget, row, col) == "\u2717"
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_wrong_answer_claims_red: PASS")


def test_timeout_teacher_captures():
    db, path = _make_db([(f"word{i}", f"trans{i}") for i in range(12)])
    widget = _new_widget(db)
    row, col = widget._unclaimed_cells()[0]
    widget._start_question(row, col)
    widget._on_timeout()
    assert widget._grid_owners[row][col] == "teacher"
    assert widget._teacher_score == 1
    assert widget._total_count == 1
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_timeout_teacher_captures: PASS")


def test_game_over_on_full_board():
    db, path = _make_db([(f"word{i}", f"trans{i}") for i in range(12)])
    widget = _new_widget(db)
    for r in range(widget._rows):
        for c in range(widget._cols):
            widget._grid_owners[r][c] = "user"
    widget._claimed_count = widget._cell_count
    widget._show_round()
    assert widget._game_over_shown
    assert widget._banner is not None
    assert widget._close_btn.text() == "Finish"
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_game_over_on_full_board: PASS")


if __name__ == "__main__":
    test_grid_sizes_per_difficulty()
    test_cells_show_question_mark()
    test_teacher_turn_shimmer_then_reveal()
    test_correct_answer_claims_blue()
    test_wrong_answer_claims_red()
    test_timeout_teacher_captures()
    test_game_over_on_full_board()
    print("\nALL TESTS PASSED")