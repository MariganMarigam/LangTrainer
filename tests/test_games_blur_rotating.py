"""Logic tests for Blur and Rotating Word games (offline, no display)."""
import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEvent, QPointF, QEasingCurve
from PySide6.QtGui import QMouseEvent

from database.db_manager import DatabaseManager
from ui.games.game_blur import BlurWidget
from ui.games.game_rotating_word import RotatingWordWidget

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


# ── Blur tests ──────────────────────────────────────────────────────────

def test_blur_setup():
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    widget = BlurWidget(db)
    widget.setup_game(_words(db))
    assert widget._current_word is not None
    assert widget._word_label.text() == widget._current_word.word
    # Start blur = 70% of the word font size (28px TITLE_1 → 19px)
    assert widget._blur_effect.blurRadius() == 19
    assert widget._input.isEnabled()
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_blur_setup: PASS")


def test_blur_piecewise_schedule_easy():
    """Easy (30s): 0-10s 70→40%, 10-20s 40→25%, 20-30s 25→0%."""
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    widget = BlurWidget(db)
    widget.setup_game(_words(db))
    widget._diff_combo.setCurrentText("Easy")
    assert abs(widget._blur_fraction(0) - 0.70) < 1e-9
    assert abs(widget._blur_fraction(5_000) - 0.55) < 1e-9
    assert abs(widget._blur_fraction(10_000) - 0.40) < 1e-9
    assert abs(widget._blur_fraction(15_000) - 0.325) < 1e-9
    assert abs(widget._blur_fraction(20_000) - 0.25) < 1e-9
    assert abs(widget._blur_fraction(25_000) - 0.125) < 1e-9
    assert widget._blur_fraction(30_000) == 0.0
    assert widget._blur_fraction(35_000) == 0.0
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_blur_piecewise_schedule_easy: PASS")


def test_blur_piecewise_schedule_normal():
    """Normal (20s): 0-7s 70→40%, 7-14s 40→25%, 14-20s 25→0%."""
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    widget = BlurWidget(db)
    widget.setup_game(_words(db))
    widget._diff_combo.setCurrentText("Normal")
    assert abs(widget._blur_fraction(0) - 0.70) < 1e-9
    assert abs(widget._blur_fraction(3_500) - 0.55) < 1e-9
    assert abs(widget._blur_fraction(7_000) - 0.40) < 1e-9
    assert abs(widget._blur_fraction(10_500) - 0.325) < 1e-9
    assert abs(widget._blur_fraction(14_000) - 0.25) < 1e-9
    assert abs(widget._blur_fraction(17_000) - 0.125) < 1e-9
    assert widget._blur_fraction(20_000) == 0.0
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_blur_piecewise_schedule_normal: PASS")


def test_blur_piecewise_schedule_hard():
    """Hard (15s): 0-6s 70→40%, 6-10s 40→25%, 10-15s 25→0%."""
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    widget = BlurWidget(db)
    widget.setup_game(_words(db))
    widget._diff_combo.setCurrentText("Hard")
    assert abs(widget._blur_fraction(0) - 0.70) < 1e-9
    assert abs(widget._blur_fraction(3_000) - 0.55) < 1e-9
    assert abs(widget._blur_fraction(6_000) - 0.40) < 1e-9
    assert abs(widget._blur_fraction(8_000) - 0.325) < 1e-9
    assert abs(widget._blur_fraction(10_000) - 0.25) < 1e-9
    assert abs(widget._blur_fraction(12_500) - 0.125) < 1e-9
    assert widget._blur_fraction(15_000) == 0.0
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_blur_piecewise_schedule_hard: PASS")


def test_blur_piecewise_radius_start_and_end():
    """Start radius = max(8, int(font_px * 0.70)); end reaches 0."""
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    widget = BlurWidget(db)
    widget.setup_game(_words(db))
    assert widget._word_font_size_px() == 28
    # Start value keeps the max(8, ...) floor: max(8, int(28*0.70)) = 19
    assert widget._blur_radius(0.70) == 19.0
    assert widget._blur_effect.blurRadius() == 19.0
    # Intermediate values are font_px * fraction (no floor)
    assert abs(widget._blur_radius(0.40) - 28 * 0.40) < 1e-9
    assert abs(widget._blur_radius(0.25) - 28 * 0.25) < 1e-9
    assert widget._blur_radius(0.0) == 0.0
    # Timeout clears the blur fully
    widget._on_timeout()
    assert widget._blur_effect.blurRadius() == 0.0
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_blur_piecewise_radius_start_and_end: PASS")


def test_blur_tick_drives_piecewise_radius():
    """The 100ms tick drives the blur radius from the elapsed time."""
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    widget = BlurWidget(db)
    widget.setup_game(_words(db))

    class FakeElapsed:
        """QElapsedTimer stand-in with a fixed elapsed value."""

        def __init__(self, ms):
            self._ms = ms

        def elapsed(self):
            return self._ms

    # Easy: at 10s the fraction is 0.40 → radius 28*0.40 = 11.2
    widget._elapsed = FakeElapsed(10_000)
    widget._on_tick()
    assert abs(widget._blur_effect.blurRadius() - 28 * 0.40) < 1e-9
    # At 20s the fraction is 0.25 → radius 28*0.25 = 7.0
    widget._elapsed = FakeElapsed(20_000)
    widget._on_tick()
    assert abs(widget._blur_effect.blurRadius() - 28 * 0.25) < 1e-9
    # At 30s the countdown expires → timeout clears the blur
    widget._elapsed = FakeElapsed(30_000)
    widget._on_tick()
    assert widget._blur_effect.blurRadius() == 0.0
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_blur_tick_drives_piecewise_radius: PASS")


def test_blur_correct_input_advances():
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    widget = BlurWidget(db)
    widget.setup_game(_words(db))
    first_word = widget._current_word
    widget._input.setText(first_word.word)
    widget._on_submit()
    assert widget._current_index == 1
    assert widget._current_word.id != first_word.id or widget._current_index == 1
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_blur_correct_input_advances: PASS")


def test_blur_wrong_input_flash():
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    widget = BlurWidget(db)
    widget.setup_game(_words(db))
    widget._input.setText("wrongword")
    widget._on_submit()
    # Wrong answer recorded, input disabled, index advanced
    assert widget._total_count == 1
    assert widget._correct_count == 0
    assert widget._current_index == 1
    assert widget._input.isEnabled() is False
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_blur_wrong_input_flash: PASS")


def test_blur_timeout_advances():
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    widget = BlurWidget(db)
    widget.setup_game(_words(db))
    widget._on_timeout()
    assert widget._total_count == 1
    assert widget._correct_count == 0
    assert widget._current_index == 1
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_blur_timeout_advances: PASS")


def test_blur_difficulty_durations():
    """Each difficulty maps to its own countdown duration."""
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    widget = BlurWidget(db)
    widget.setup_game(_words(db))
    for diff, expected_ms in widget._DURATIONS.items():
        widget._diff_combo.setCurrentText(diff.capitalize())
        widget._show_word()
        assert widget._duration_ms == expected_ms, f"{diff} duration mismatch"
        assert widget._remaining_ms == expected_ms, (
            f"{diff} countdown mismatch"
        )
        # The piecewise schedule's final segment ends exactly at the
        # duration with a 0 blur fraction (fully clear).
        schedule = widget.BLUR_SCHEDULES[diff]
        assert schedule[-1][1] == expected_ms, (
            f"{diff} schedule end mismatch"
        )
        assert schedule[-1][3] == 0.0, (
            f"{diff} blur must still end fully clear"
        )
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_blur_difficulty_durations: PASS")


def test_blur_hint_first_click_shows_translation():
    """First hint click: word label shows the translation, input hidden,
    blur disabled (translation fully readable)."""
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    widget = BlurWidget(db)
    widget.setup_game(_words(db))
    translation = widget._current_word.translation
    widget._on_hint()
    assert widget._hint_active is True
    assert widget._hint_used is False
    assert widget._word_label.text() == translation
    assert widget._input.isHidden() is True
    assert widget._blur_effect.blurRadius() == 0.0
    assert widget._hint_btn.text() == "\U0001f4a1 Hide hint"
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_blur_hint_first_click_shows_translation: PASS")


def test_blur_hint_second_click_restores_word():
    """Second hint click: blurred word + input return, hint exhausted."""
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    widget = BlurWidget(db)
    widget.setup_game(_words(db))
    word = widget._current_word
    widget._on_hint()
    widget._on_hint()
    assert widget._hint_active is False
    assert widget._hint_used is True
    assert widget._word_label.text() == word.word
    assert widget._input.isHidden() is False
    assert widget._hint_btn.text() == "\U0001f4a1 Hint (0 left)"
    # Blur resumes from the schedule (elapsed ~0 → start radius 19px)
    assert widget._blur_effect.blurRadius() > 0
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_blur_hint_second_click_restores_word: PASS")


def test_blur_hint_exhausted_after_second_click():
    """After the second click the hint is exhausted: clicks no-op."""
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    widget = BlurWidget(db)
    widget.setup_game(_words(db))
    widget._on_hint()
    widget._on_hint()
    label_text = widget._word_label.text()
    widget._on_hint()
    assert widget._word_label.text() == label_text
    assert widget._hint_used is True
    assert widget._hint_active is False
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_blur_hint_exhausted_after_second_click: PASS")


def test_blur_hint_resets_on_next_word():
    """Hint state resets for the next word (1 use per word)."""
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    widget = BlurWidget(db)
    widget.setup_game(_words(db))
    widget._on_hint()
    widget._on_hint()
    assert widget._hint_used is True
    # Next word resets the hint
    widget._input.setText(widget._current_word.word)
    widget._on_submit()
    widget._advance_word()
    assert widget._hint_used is False
    assert widget._hint_active is False
    assert widget._hint_btn.text() == "\U0001f4a1 Hint (1 left)"
    widget._on_hint()
    assert widget._hint_active is True
    assert widget._word_label.text() == widget._current_word.translation
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_blur_hint_resets_on_next_word: PASS")


def test_blur_finish_after_10_words():
    db, path = _make_db(
        [(f"word{i}", f"trans{i}") for i in range(12)]
    )
    widget = BlurWidget(db)
    widget.setup_game(_words(db))
    # Answer all 10 words correctly
    for _ in range(10):
        widget._input.setText(widget._current_word.word)
        widget._on_submit()
        widget._advance_word()
    assert widget.is_finished
    widget._finish_game()
    assert widget._close_btn.text() == "Finish"
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_blur_finish_after_10_words: PASS")


# ── Rotating Word tests ─────────────────────────────────────────────────

def test_rotating_setup():
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    widget = RotatingWordWidget(db)
    widget.setup_game(_words(db))
    assert widget._current_word is not None
    assert len(widget._letter_cards) == len(widget._current_word.word)
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_rotating_setup: PASS")


def test_rotating_letter_order():
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    widget = RotatingWordWidget(db)
    widget.setup_game(_words(db))
    # Cards start empty (sequential reveal) — reveal all, then check order
    for card in widget._letter_cards:
        card.reveal_letter()
    from PySide6.QtWidgets import QLabel
    letters = []
    for card in widget._letter_cards:
        label = card.findChild(QLabel)
        letters.append(label.text())
    expected = [ch.upper() for ch in widget._current_word.word if ch.isalpha()]
    assert letters == expected, f"Expected {expected}, got {letters}"
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_rotating_letter_order: PASS")


def test_rotating_rotation_amplitude_by_difficulty():
    """Rotation amplitude is 45/70/110 degrees for easy/normal/hard."""
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    widget = RotatingWordWidget(db)
    widget.setup_game(_words(db))
    assert widget.ROTATION_AMPLITUDES == {
        "easy": 45.0,
        "normal": 70.0,
        "hard": 110.0,
    }
    # DIFFICULTIES rot_max (index 2) must match the amplitudes
    for diff, amplitude in widget.ROTATION_AMPLITUDES.items():
        assert widget.DIFFICULTIES[diff][2] == amplitude, (
            f"{diff} rot_max mismatch"
        )
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_rotating_rotation_amplitude_by_difficulty: PASS")


def test_rotating_tick_oscillates_sinusoidally():
    """Rotation is pure sinusoidal oscillation: sin(t*speed*1.3 + phase)
    * rot_max — bounded by ±amplitude, per-card random phase, no
    accumulation over ticks."""
    import math

    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    widget = RotatingWordWidget(db)
    widget.setup_game(_words(db))
    diff = widget._diff_combo.currentText().lower()
    _, _, rot_max, speed, _, _ = widget.DIFFICULTIES[diff]
    n = len(widget._letter_cards)
    assert n > 0

    # Per-card random phases exist and are within [0, 2π)
    assert len(widget._phases) == n
    for phase in widget._phases:
        assert 0.0 <= phase < 2 * math.pi

    # First tick: rotation matches the pure sinusoidal formula
    widget._on_tick()
    t = widget._anim_time
    for i, card in enumerate(widget._letter_cards):
        expected = math.sin(t * speed * 1.3 + widget._phases[i]) * rot_max
        assert abs(card._rotation - expected) < 1e-9, (
            f"card {i} rotation {card._rotation} != expected {expected}"
        )
        assert abs(card._rotation) <= rot_max + 1e-9, (
            f"card {i} rotation {card._rotation} exceeds amplitude {rot_max}"
        )

    # Second tick: still matches the formula (no accumulation)
    widget._on_tick()
    t = widget._anim_time
    for i, card in enumerate(widget._letter_cards):
        expected = math.sin(t * speed * 1.3 + widget._phases[i]) * rot_max
        assert abs(card._rotation - expected) < 1e-9, (
            f"card {i} rotation {card._rotation} != expected {expected} "
            "(accumulation detected)"
        )
        assert abs(card._rotation) <= rot_max + 1e-9

    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_rotating_tick_oscillates_sinusoidally: PASS")


def test_rotating_chaos_multipliers_applied():
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    widget = RotatingWordWidget(db)
    widget.setup_game(_words(db))
    for diff, mult in widget.CHAOS_MULTIPLIERS.items():
        base = widget.DIFFICULTIES[diff]
        sx, sy, jm = widget._scaled_chaos(diff)
        assert abs(sx - base[0] * mult) < 1e-9, f"{diff} spread_x not scaled"
        assert abs(sy - base[1] * mult) < 1e-9, f"{diff} spread_y not scaled"
        assert abs(jm - base[4] * mult) < 1e-9, f"{diff} jitter_max not scaled"
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_rotating_chaos_multipliers_applied: PASS")


def test_rotating_sequential_reveal():
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    widget = RotatingWordWidget(db)
    widget.setup_game(_words(db))
    n = len(widget._letter_cards)
    assert n > 0
    # Cards start empty and invisible (opacity 0, no letter text)
    for card in widget._letter_cards:
        assert card._label.text() == ""
        assert card._opacity_effect.opacity() == 0.0
    # n reveal timers (1s apart) + 1 mark-all timer
    assert len(widget._pending_timers) == n + 1
    intervals = [t.interval() for t in widget._pending_timers]
    assert sorted(intervals[:-1]) == [i * 1000 for i in range(n)]
    assert intervals[-1] == n * 1000 + 500
    # reveal_letter sets the text and starts a 1000ms fade-in animation
    card = widget._letter_cards[0]
    card.reveal_letter()
    assert card._label.text() == card._letter
    assert card._opacity_anim is not None
    assert card._opacity_anim.duration() == 1000
    assert card._opacity_anim.startValue() == 0.0
    assert card._opacity_anim.endValue() == 1.0
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_rotating_sequential_reveal: PASS")


def test_rotating_cards_continue_after_reveal():
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    widget = RotatingWordWidget(db)
    widget.setup_game(_words(db))
    widget._mark_all_revealed()
    assert widget._all_revealed is True
    # Animation keeps running after all cards are revealed
    assert widget._anim_timer is not None
    assert widget._anim_timer.isActive()
    # Correct answer stops the animation
    widget._input.setText(widget._current_word.translation)
    widget._on_submit()
    assert widget._anim_timer.isActive() is False
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_rotating_cards_continue_after_reveal: PASS")


def test_rotating_correct_translation_advances():
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    widget = RotatingWordWidget(db)
    widget.setup_game(_words(db))
    first_word = widget._current_word
    widget._input.setText(first_word.translation)
    widget._on_submit()
    assert widget._current_index == 1
    assert widget._correct_count == 1
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_rotating_correct_translation_advances: PASS")


def test_rotating_wrong_translation_flash():
    db, path = _make_db([("apple", "яблоко"), ("sky", "небо"), ("dog", "собака")])
    widget = RotatingWordWidget(db)
    widget.setup_game(_words(db))
    widget._input.setText("wrongtranslation")
    widget._on_submit()
    # Wrong answer recorded, input disabled, index advanced
    assert widget._total_count == 1
    assert widget._correct_count == 0
    assert widget._current_index == 1
    assert widget._input.isEnabled() is False
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_rotating_wrong_translation_flash: PASS")


def test_rotating_finish_after_10_words():
    db, path = _make_db(
        [(f"word{i}", f"trans{i}") for i in range(12)]
    )
    widget = RotatingWordWidget(db)
    widget.setup_game(_words(db))
    for _ in range(10):
        widget._input.setText(widget._current_word.translation)
        widget._on_submit()
        widget._show_word()
    assert widget.is_finished
    widget._finish_game()
    assert widget._close_btn.text() == "Finish"
    widget.cleanup()
    db.disconnect()
    os.unlink(path)
    print("test_rotating_finish_after_10_words: PASS")


if __name__ == "__main__":
    test_blur_setup()
    test_blur_piecewise_schedule_easy()
    test_blur_piecewise_schedule_normal()
    test_blur_piecewise_schedule_hard()
    test_blur_piecewise_radius_start_and_end()
    test_blur_tick_drives_piecewise_radius()
    test_blur_correct_input_advances()
    test_blur_wrong_input_flash()
    test_blur_timeout_advances()
    test_blur_difficulty_durations()
    test_blur_hint_first_click_shows_translation()
    test_blur_hint_second_click_restores_word()
    test_blur_hint_exhausted_after_second_click()
    test_blur_hint_resets_on_next_word()
    test_blur_finish_after_10_words()
    test_rotating_setup()
    test_rotating_letter_order()
    test_rotating_rotation_amplitude_by_difficulty()
    test_rotating_tick_oscillates_sinusoidally()
    test_rotating_chaos_multipliers_applied()
    test_rotating_sequential_reveal()
    test_rotating_cards_continue_after_reveal()
    test_rotating_correct_translation_advances()
    test_rotating_wrong_translation_flash()
    test_rotating_finish_after_10_words()
    print("\nALL TESTS PASSED")