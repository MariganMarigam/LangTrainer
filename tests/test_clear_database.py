"""Tests for the 'Clear database' full-reset feature.

Covers the destructive full reset: all words, all per-word statistics
(including SRS fields), and all game best results are permanently deleted
in one transaction, plus the confirmation-dialog flow in the UI.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication, QMessageBox

from database.db_manager import DatabaseManager
from ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])


def _make_db(words):
    """Create a temp DB with the given (word, translation) pairs."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = DatabaseManager(path)
    db.connect()
    for word, translation in words:
        db.add_word(word, translation)
    return db, path


def _dirty_stats(db):
    """Dirty per-word stats (counters + SRS) and game results."""
    for word in db.get_all_words():
        db.record_attempt(word.id, was_correct=True)
        db.record_attempt(word.id, was_correct=False)
        db.record_srs_review(word.id, quality=5)
    db.record_game_result("bomb", "easy", 100)
    db.record_game_result("bomb", "hard", 50)
    db.record_game_result("snake", "normal", 75)


def test_clear_all_data_deletes_all_words():
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    assert db.get_word_count() == 3
    db.clear_all_data()
    assert db.get_word_count() == 0
    assert db.get_all_words() == []
    db.disconnect()
    os.unlink(path)
    print("test_clear_all_data_deletes_all_words: PASS")


def test_clear_all_data_wipes_game_best_results():
    db, path = _make_db([("apple", "яблоко")])
    db.record_game_result("bomb", "easy", 100)
    db.record_game_result("bomb", "hard", 50)
    assert db.get_game_best("bomb", "easy") == 100
    db.clear_all_data()
    assert db.get_game_best("bomb", "easy") == 0
    assert db.get_game_best("bomb", "hard") == 0
    db.disconnect()
    os.unlink(path)
    print("test_clear_all_data_wipes_game_best_results: PASS")


def test_clear_all_data_full_reset_on_populated_db():
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо")])
    _dirty_stats(db)
    # Sanity: stats and game results are dirty before the reset.
    word = db.get_all_words()[0]
    srs = db.get_word_srs_stats(word.id)
    assert srs["total_reviews"] > 0
    assert srs["ease_factor"] != 2.5
    assert db.get_game_best("bomb", "easy") == 100
    db.clear_all_data()
    # Words gone -> per-word stats (incl. SRS) gone.
    assert db.get_word_count() == 0
    assert db.get_word_srs_stats(word.id) == {}
    # Game results gone.
    assert db.get_game_best("bomb", "easy") == 0
    assert db.get_game_best("snake", "normal") == 0
    db.disconnect()
    os.unlink(path)
    print("test_clear_all_data_full_reset_on_populated_db: PASS")


def test_clear_all_data_keeps_schema_intact():
    db, path = _make_db([("apple", "яблоко")])
    db.clear_all_data()
    # Tables still exist and are usable after the reset.
    assert db.add_word("banana", "банан") is True
    db.record_game_result("bomb", "easy", 42)
    assert db.get_word_count() == 1
    assert db.get_game_best("bomb", "easy") == 42
    db.disconnect()
    os.unlink(path)
    print("test_clear_all_data_keeps_schema_intact: PASS")


def test_reset_statistics_resets_srs_fields():
    db, path = _make_db([("apple", "яблоко")])
    word = db.get_all_words()[0]
    db.record_srs_review(word.id, quality=5)
    db.record_attempt(word.id, was_correct=True)
    dirty = db.get_word_srs_stats(word.id)
    assert dirty["total_reviews"] == 1
    assert dirty["ease_factor"] != 2.5
    db.reset_statistics()
    srs = db.get_word_srs_stats(word.id)
    assert srs == {
        "ease_factor": 2.5,
        "interval_days": 0,
        "next_review_date": None,
        "total_reviews": 0,
    }
    word = db.get_all_words()[0]
    assert word.correct_count == 0
    assert word.incorrect_count == 0
    assert word.total_shown == 0
    assert word.last_shown is None
    db.disconnect()
    os.unlink(path)
    print("test_reset_statistics_resets_srs_fields: PASS")


def test_clear_database_confirmation_yes_clears(monkeypatch):
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо")])
    window = MainWindow(db)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: QMessageBox.Yes)
    window._clear_database()
    assert db.get_word_count() == 0
    window.close()
    db.disconnect()
    os.unlink(path)
    print("test_clear_database_confirmation_yes_clears: PASS")


def test_clear_database_confirmation_no_keeps_data(monkeypatch):
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо")])
    window = MainWindow(db)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: QMessageBox.No)
    window._clear_database()
    assert db.get_word_count() == 2
    window.close()
    db.disconnect()
    os.unlink(path)
    print("test_clear_database_confirmation_no_keeps_data: PASS")


if __name__ == "__main__":
    test_clear_all_data_deletes_all_words()
    test_clear_all_data_wipes_game_best_results()
    test_clear_all_data_full_reset_on_populated_db()
    test_clear_all_data_keeps_schema_intact()
    test_reset_statistics_resets_srs_fields()
    print("\nALL TESTS PASSED")