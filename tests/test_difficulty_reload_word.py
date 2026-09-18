"""Logic tests: difficulty change must RELOAD a new word (no immediate repeat).

Covers all 4 games that reset on difficulty change:
- ChainReactionWidget (game_chain_reaction.py)
- BombWidget (game_bomb.py)
- DominationWidget (game_domination.py)
- SnakeWidget (game_snake.py)

Each test: setup_game → note current word → trigger difficulty change →
verify the new word is DIFFERENT from the current one and the game state
was reset.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication

from database.db_manager import DatabaseManager
from ui.games.game_chain_reaction import ChainReactionWidget
from ui.games.game_bomb import BombWidget
from ui.games.game_domination import DominationWidget
from ui.games.game_snake import SnakeWidget
from ui.games.game_blur import BlurWidget
from ui.games.game_rotating_word import RotatingWordWidget
from ui.games.game_memory_palace import MemoryPalaceWidget

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


def _flat_layout(widget):
    """Return the grid's word-id layout as a flat tuple (row-major)."""
    return tuple(
        widget._cell_words[r][c].id
        for r in range(widget._rows)
        for c in range(widget._cols)
    )


# ── Chain Reaction ──────────────────────────────────────────────────────

def test_chain_reaction_difficulty_change_reloads_word():
    db, path = _make_db([(f"word{i}", f"trans{i}") for i in range(5)])
    widget = ChainReactionWidget(db)
    widget.setup_game(_words(db))
    first_id = widget._current_words[widget._current_index].id

    widget._diff_combo.setCurrentText("Hard")

    new_id = widget._current_words[widget._current_index].id
    assert new_id != first_id, "difficulty change must show a DIFFERENT word"
    # Game state reset (and the skip advanced the index past word 0).
    assert widget._current_index == 1
    assert widget._correct_count == 0
    assert widget._total_count == 0
    assert widget._finished_emitted is False
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_chain_reaction_difficulty_change_reloads_word: PASS")


# ── Bomb ────────────────────────────────────────────────────────────────

def test_bomb_difficulty_change_reloads_word():
    db, path = _make_db([(f"word{i}", f"trans{i}") for i in range(5)])
    widget = BombWidget(db)
    widget.setup_game(_words(db))
    first_id = widget._current_word.id

    widget._diff_combo.setCurrentText("Hard")

    new_id = widget._current_word.id
    assert new_id != first_id, "difficulty change must show a DIFFERENT word"
    # Game state reset.
    assert widget._combo == 0
    assert widget._words_survived == 0
    assert widget._correct_count == 0
    assert widget._total_count == 0
    assert widget._game_over_emitted is False
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_bomb_difficulty_change_reloads_word: PASS")


# ── Domination ──────────────────────────────────────────────────────────

def test_domination_difficulty_change_rebuilds_grid_differently():
    db, path = _make_db([(f"word{i}", f"trans{i}") for i in range(12)])
    widget = DominationWidget(db)
    widget.setup_game(_words(db))
    layout1 = _flat_layout(widget)

    widget._diff_combo.setCurrentText("Hard")
    layout2 = _flat_layout(widget)
    assert layout2 != layout1, "difficulty change must reshuffle the grid"

    # A second change also produces a different arrangement.
    widget._diff_combo.setCurrentText("Easy")
    layout3 = _flat_layout(widget)
    assert layout3 != layout2, "second difficulty change must reshuffle again"

    # Game state reset.
    assert widget._user_score == 0
    assert widget._teacher_score == 0
    assert widget._claimed_count == 0
    assert widget._question_active is False
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_domination_difficulty_change_rebuilds_grid_differently: PASS")


# ── Snake ───────────────────────────────────────────────────────────────

def test_snake_difficulty_change_reloads_word():
    db, path = _make_db([(f"word{i}", f"trans{i}") for i in range(5)])
    widget = SnakeWidget(db)
    widget.setup_game(_words(db))
    first_id = widget._target_word.id

    widget._diff_combo.setCurrentText("Hard")

    new_id = widget._target_word.id
    assert new_id != first_id, "difficulty change must show a DIFFERENT word"
    # Game state reset (and the skip advanced the index past word 0).
    assert widget._word_index == 1
    assert widget._wrong_events == 0
    assert widget._finished_emitted is False
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_snake_difficulty_change_reloads_word: PASS")


# ── Blur ────────────────────────────────────────────────────────────────

def test_blur_difficulty_change_reloads_word():
    db, path = _make_db([(f"word{i}", f"trans{i}") for i in range(5)])
    widget = BlurWidget(db)
    widget.setup_game(_words(db))
    first_id = widget._current_word.id

    widget._diff_combo.setCurrentText("Hard")

    new_id = widget._current_word.id
    assert new_id != first_id, "difficulty change must show a DIFFERENT word"
    # Game state reset.
    assert widget._current_index == 0
    assert widget._correct_count == 0
    assert widget._total_count == 0
    assert widget._finished_emitted is False
    assert widget._hint_used is False
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_blur_difficulty_change_reloads_word: PASS")


# ── Rotating Word ───────────────────────────────────────────────────────

def test_rotating_difficulty_change_reloads_word():
    db, path = _make_db([(f"word{i}", f"trans{i}") for i in range(5)])
    widget = RotatingWordWidget(db)
    widget.setup_game(_words(db))
    first_id = widget._current_word.id

    widget._diff_combo.setCurrentText("Hard")

    new_id = widget._current_word.id
    assert new_id != first_id, "difficulty change must show a DIFFERENT word"
    # Game state reset.
    assert widget._current_index == 0
    assert widget._correct_count == 0
    assert widget._total_count == 0
    assert widget._finished_emitted is False
    assert widget._all_revealed is False
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_rotating_difficulty_change_reloads_word: PASS")


# ── Memory Palace ───────────────────────────────────────────────────────

def test_memory_palace_difficulty_change_reloads_words():
    db, path = _make_db([(f"word{i}", f"trans{i}") for i in range(12)])
    widget = MemoryPalaceWidget(db)
    widget.setup_game(_words(db))
    first_ids = {c["id"] for c in widget._cards if c["id"].startswith("word_")}

    widget._diff_combo.setCurrentText("Hard")

    new_ids = {c["id"] for c in widget._cards if c["id"].startswith("word_")}
    assert new_ids != first_ids, "difficulty change must re-pick DIFFERENT words"
    # A second change (same pair count) also re-picks different words.
    widget._diff_combo.setCurrentText("Chaos")
    chaos_ids = {c["id"] for c in widget._cards if c["id"].startswith("word_")}
    assert chaos_ids != new_ids, "second difficulty change must re-pick again"
    # Game state reset.
    assert widget._matched_count == 0
    assert widget._streak == 0
    assert widget._selected is None
    assert widget._lock_grid is False
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_memory_palace_difficulty_change_reloads_words: PASS")


if __name__ == "__main__":
    test_chain_reaction_difficulty_change_reloads_word()
    test_bomb_difficulty_change_reloads_word()
    test_domination_difficulty_change_rebuilds_grid_differently()
    test_snake_difficulty_change_reloads_word()
    test_blur_difficulty_change_reloads_word()
    test_rotating_difficulty_change_reloads_word()
    test_memory_palace_difficulty_change_reloads_words()
    print("\nALL DIFFICULTY-RELOAD TESTS PASSED")