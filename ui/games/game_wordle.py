"""Wordle Game: Guess the foreign word with letter-by-letter feedback."""
import random
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLineEdit, QFrame
)
from ui.games.game_base import BaseGame
from ui.styles import (
    Colors, Fonts, pill_button_style, card_style, label_style,
    progress_label_style, score_label_style, destructive_button_style,
    input_field_style
)


class WordleWidget(BaseGame):
    """Guess the foreign word with Wordle-style letter feedback.

    Shows the translation, user must enter the foreign word.
    Green: correct position, Yellow: wrong position, Gray: not in word.
    Max 6 attempts per word.
    """

    finished = Signal()

    def __init__(self, db_manager, parent=None):
        super().__init__(db_manager, parent)
        self._current_word = None
        self._attempts = 0
        self._max_attempts = 6
        self._cell_widgets = []
        self._build_ui()

    def _build_ui(self):
        """Build the Wordle game interface."""
        self._layout.setContentsMargins(16, 8, 16, 8)
        self._layout.setSpacing(10)

        # ── Translation card ──────────────────────────────────────────────
        self._trans_card = QFrame()
        self._trans_card.setStyleSheet(card_style())
        trans_card_layout = QVBoxLayout(self._trans_card)
        trans_card_layout.setContentsMargins(16, 12, 16, 12)

        self._trans_label = QLabel("Translation")
        self._trans_label.setStyleSheet(
            label_style(Fonts.TITLE_2, Colors.PRIMARY_LABEL)
        )
        self._trans_label.setAlignment(Qt.AlignCenter)
        trans_card_layout.addWidget(self._trans_label)

        self._layout.addWidget(self._trans_card)

        # ── Status label ──────────────────────────────────────────────────
        self._status_label = QLabel("Guess the foreign word!")
        self._status_label.setStyleSheet(
            label_style(Fonts.CALLOUT, Colors.SECONDARY_LABEL)
        )
        self._status_label.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._status_label)

        # ── Wordle grid frame ─────────────────────────────────────────────
        self._grid_frame = QFrame()
        self._grid_frame.setStyleSheet("background-color: transparent;")
        self._grid_layout = QVBoxLayout(self._grid_frame)
        self._grid_layout.setSpacing(4)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(self._grid_frame)

        # ── Input row ─────────────────────────────────────────────────────
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 0, 0, 0)

        self._input_field = QLineEdit()
        self._input_field.setStyleSheet(input_field_style())
        self._input_field.setPlaceholderText("Type word and press Enter...")
        self._input_field.setMaxLength(20)
        self._input_field.returnPressed.connect(self._submit_guess)
        input_layout.addWidget(self._input_field)

        self._submit_btn = QPushButton("Guess")
        self._submit_btn.setStyleSheet(
            pill_button_style(Colors.BLUE, height="40px")
        )
        self._submit_btn.clicked.connect(self._submit_guess)
        input_layout.addWidget(self._submit_btn)
        self._layout.addLayout(input_layout)

        # ── Progress / Score row ──────────────────────────────────────────
        progress_layout = QHBoxLayout()
        progress_layout.setContentsMargins(0, 0, 0, 0)

        self._progress_label = QLabel("0 / 0")
        self._progress_label.setStyleSheet(progress_label_style())
        progress_layout.addWidget(self._progress_label)
        progress_layout.addStretch()

        self._score_label = QLabel("Score: 0%")
        self._score_label.setStyleSheet(score_label_style())
        progress_layout.addWidget(self._score_label)
        self._layout.addLayout(progress_layout)

        # ── Close button ──────────────────────────────────────────────────
        self._close_btn = QPushButton("✕  Close")
        self._close_btn.setStyleSheet(destructive_button_style())
        self._close_btn.clicked.connect(self.finished.emit)
        self._layout.addWidget(self._close_btn)
        self._layout.addStretch()

    # ── Game Lifecycle ────────────────────────────────────────────────────

    def setup_game(self, words):
        """Initialize game with words."""
        super().setup_game(words)
        self._score_label.setText("Score: 0%")
        self._show_next()

    def _show_next(self):
        """Show the next word to guess."""
        if self.is_finished:
            self._wordle_finish()
            return

        self._current_word = self._current_words[self._current_index]
        self._attempts = 0
        self._trans_label.setText(f"  {self._current_word.translation}")
        self._progress_label.setText(self.progress_text)

        self._clear_grid()

        word_len = len(self._current_word.word)
        self._cell_widgets = []
        for row in range(self._max_attempts):
            row_widgets = []
            row_layout = QHBoxLayout()
            row_layout.setSpacing(4)
            row_layout.addStretch()
            for col in range(word_len):
                cell = QLabel("_")
                cell.setFixedSize(44, 44)
                cell.setAlignment(Qt.AlignCenter)
                cell.setStyleSheet("""
                    background-color: #007AFF; color: white;
                    border: none; border-radius: 6px;
                    font-size: 20px; font-weight: bold;
                """)
                row_layout.addWidget(cell)
                row_widgets.append(cell)
            row_layout.addStretch()
            self._grid_layout.addLayout(row_layout)
            self._cell_widgets.append(row_widgets)

        self._input_field.clear()
        self._input_field.setEnabled(True)
        self._input_field.setFocus()
        self._submit_btn.setEnabled(True)
        self._input_field.setMaxLength(word_len)
        self._status_label.setText("Guess the foreign word!")

    def _clear_grid(self):
        """Remove all grid rows."""
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
        self._cell_widgets = []

    # ── Core Game Logic ───────────────────────────────────────────────────

    def _submit_guess(self):
        """Submit the current guess."""
        if not self._current_word or self._attempts >= self._max_attempts:
            return

        guess = self._input_field.text().strip().lower()
        correct = self._current_word.word.strip().lower()

        if not guess:
            return

        if len(guess) != len(correct):
            self._status_label.setText(
                f"Word must be {len(correct)} letters long!"
            )
            return

        word_len = len(correct)
        result = [''] * word_len
        correct_chars = list(correct)
        guess_chars = list(guess)

        # First pass: exact matches (green)
        for i in range(word_len):
            if guess_chars[i] == correct_chars[i]:
                result[i] = 'green'
                correct_chars[i] = None
                guess_chars[i] = None

        # Second pass: wrong position (yellow) and not found (gray)
        for i in range(word_len):
            if guess_chars[i] is None:
                continue
            if guess_chars[i] in correct_chars:
                result[i] = 'yellow'
                idx = correct_chars.index(guess_chars[i])
                correct_chars[idx] = None
            else:
                result[i] = 'gray'

        row = self._cell_widgets[self._attempts]
        for i, (cell, color) in enumerate(zip(row, result)):
            cell.setText(guess[i].upper())
            if color == 'green':
                cell.setStyleSheet("""
                    background-color: #34C759; color: white;
                    border: none; border-radius: 6px;
                    font-size: 20px; font-weight: bold;
                """)
            elif color == 'yellow':
                cell.setStyleSheet("""
                    background-color: #FFCC00; color: white;
                    border: none; border-radius: 6px;
                    font-size: 20px; font-weight: bold;
                """)
            else:
                cell.setStyleSheet("""
                    background-color: #3a3a3a; color: #888;
                    border: none; border-radius: 6px;
                    font-size: 20px; font-weight: bold;
                """)

        self._attempts += 1

        if guess == correct:
            self.record_answer(self._current_word.id, True)
            self._score_label.setText(f"Score: {self.score_text}")
            self._status_label.setText(
                f"Correct! ({self._attempts}/{self._max_attempts})"
            )
            self._input_field.setEnabled(False)
            self._submit_btn.setEnabled(False)
            QTimer.singleShot(1500, self._show_next)
            return

        if self._attempts >= self._max_attempts:
            self.record_answer(self._current_word.id, False)
            self._score_label.setText(f"Score: {self.score_text}")
            self._status_label.setText(f"The word was: {correct.upper()}")
            self._input_field.setEnabled(False)
            self._submit_btn.setEnabled(False)
            QTimer.singleShot(2000, self._show_next)
            return

        self._input_field.clear()
        self._input_field.setFocus()
        self._status_label.setText(
            f"Attempt {self._attempts + 1}/{self._max_attempts}"
        )

    def _wordle_finish(self):
        """Handle game completion."""
        self._status_label.setText(f"Complete! {self.score_text}")
        self._trans_label.setText("DONE!")
        self._input_field.setEnabled(False)
        self._submit_btn.setEnabled(False)
        self._close_btn.setText("Finish")
        self.finished.emit()
