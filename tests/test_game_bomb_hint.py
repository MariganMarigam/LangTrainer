"""Logic tests for the Bomb game hint button (offline, no display).

Covers the reported bug: hint must reveal the word's translation in the
status label and be limited to one use per word.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication

from database.db_manager import DatabaseManager
from ui.games.game_bomb import BombWidget

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


def test_bomb_hint_reveals_translation():
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    widget = BombWidget(db)
    widget.setup_game(_words(db))
    word = widget._current_word
    widget._hint_btn.click()
    assert widget._hint_used is True
    assert widget._hint_btn.isEnabled() is False
    assert widget._panel._status_label.text() == f"\U0001f4a1 Hint: {word.translation}"
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_bomb_hint_reveals_translation: PASS")


def test_bomb_hint_limited_to_one_use_per_word():
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    widget = BombWidget(db)
    widget.setup_game(_words(db))
    widget._hint_btn.click()
    first_status = widget._panel._status_label.text()
    # Second click must be a no-op — hint already consumed for this word.
    widget._hint_btn.click()
    assert widget._hint_used is True
    assert widget._panel._status_label.text() == first_status
    # Next word resets the hint (fresh use available).
    widget._show_next_word()
    assert widget._hint_used is False
    assert widget._hint_btn.isEnabled() is True
    assert widget._hint_btn.text() == "\U0001f4a1 Hint"
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_bomb_hint_limited_to_one_use_per_word: PASS")


if __name__ == "__main__":
    test_bomb_hint_reveals_translation()
    test_bomb_hint_limited_to_one_use_per_word()
    print("\nALL TESTS PASSED")