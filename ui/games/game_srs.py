"""SRS Game: Flashcard review with SM-2 spaced repetition."""
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFrame
)
from ui.games.game_base import BaseGame
from ui.styles import (
    Colors, Fonts, pill_button_style, card_style,
    label_style, progress_label_style, score_label_style,
    destructive_button_style,
)


class SRSWidget(BaseGame):
    """Flashcard-style review using SM-2 algorithm.

    Shows foreign word -> flip -> rate with 4 buttons (Again/Hard/Good/Easy).
    Cards are fetched from get_words_for_review().
    """

    finished = Signal()

    RATING_LABELS = {
        1: ("Again", "#7d2d2d", "#f44336"),
        2: ("Hard", "#7d5a2d", "#ff9800"),
        3: ("Good", "#2d6a2d", "#4caf50"),
        5: ("Easy", "#2d4d7d", "#2196f3"),
    }

    def __init__(self, db_manager, parent=None):
        super().__init__(db_manager, parent)
        self._current_word = None
        self._card_flipped = False
        self._review_words = []
        self._review_index = 0
        self._is_done = False
        self._build_ui()

    def _build_ui(self):
        """Build the flashcard interface."""
        # Override base layout margins for iOS-style spacing
        self._layout.setContentsMargins(16, 12, 16, 12)
        self._layout.setSpacing(10)

        # ── Card display area ──────────────────────────────────────────────
        self._card_frame = QFrame()
        self._card_frame.setStyleSheet(card_style(Colors.CARD_FRONT_BG, "20px"))
        card_layout = QVBoxLayout(self._card_frame)
        card_layout.setContentsMargins(20, 24, 20, 24)
        card_layout.setSpacing(8)

        self._word_label = QLabel("Ready?")
        self._word_label.setStyleSheet(
            label_style(Fonts.LARGE_TITLE, Colors.PRIMARY_LABEL)
        )
        self._word_label.setAlignment(Qt.AlignCenter)
        self._word_label.setWordWrap(True)
        card_layout.addWidget(self._word_label)

        self._trans_label = QLabel("")
        self._trans_label.setStyleSheet(
            label_style(Fonts.TITLE_2, Colors.SECONDARY_LABEL)
        )
        self._trans_label.setAlignment(Qt.AlignCenter)
        self._trans_label.setWordWrap(True)
        self._trans_label.hide()
        card_layout.addWidget(self._trans_label)

        self._layout.addWidget(self._card_frame)

        # ── Stats label ────────────────────────────────────────────────────
        self._stats_label = QLabel("")
        self._stats_label.setStyleSheet(progress_label_style())
        self._stats_label.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._stats_label)

        # ── Show Answer button ─────────────────────────────────────────────
        self._show_btn = QPushButton("Show Answer  (Space)")
        self._show_btn.setStyleSheet(pill_button_style(Colors.BLUE, height="48px"))
        self._show_btn.clicked.connect(self._flip_card)
        self._layout.addWidget(self._show_btn)

        # ── Rating buttons ─────────────────────────────────────────────────
        self._rating_buttons = {}
        rating_row = QHBoxLayout()
        rating_row.setSpacing(8)
        rating_row.setContentsMargins(0, 4, 0, 0)

        for quality, (label, bg, accent) in self.RATING_LABELS.items():
            btn = QPushButton(label)
            btn.setStyleSheet(pill_button_style(bg, accent))
            btn.clicked.connect(lambda checked, q=quality: self._rate_card(q))
            btn.hide()
            self._rating_buttons[quality] = btn
            rating_row.addWidget(btn)

        self._layout.addLayout(rating_row)

        # ── Keyboard hint labels ───────────────────────────────────────────
        hint_row = QHBoxLayout()
        hint_row.setSpacing(8)
        hint_row.setContentsMargins(0, 0, 0, 0)
        self._hint_labels = {}
        hints = {1: "[1]", 2: "[2]", 3: "[3]", 5: "[4]"}
        for q, hint in hints.items():
            label = QLabel(hint)
            label.setStyleSheet(
                f"color: {Colors.TERTIARY_LABEL}; {Fonts.CAPTION_1}"
            )
            label.setAlignment(Qt.AlignCenter)
            label.hide()
            self._hint_labels[q] = label
            hint_row.addWidget(label)
        self._layout.addLayout(hint_row)

        # ── Progress / Score ───────────────────────────────────────────────
        self._progress_label = QLabel("")
        self._progress_label.setStyleSheet(score_label_style())
        self._progress_label.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._progress_label)

        # ── Close button ──────────────────────────────────────────────────
        self._close_btn = QPushButton("✕  Close")
        self._close_btn.setStyleSheet(destructive_button_style())
        self._close_btn.clicked.connect(self.finished.emit)
        self._layout.addWidget(self._close_btn)

        self._layout.addStretch()

    def setup_game(self, words):
        """Initialize SRS review - fetch words due for review."""
        super().setup_game(words)
        self._review_words = self.db.get_words_for_review(20)
        self._review_index = 0
        self._is_done = False

        if not self._review_words:
            self._word_label.setText("All caught up!")
            self._stats_label.setText(
                "No words due for review. Add more words or check back later!"
            )
            self._show_btn.hide()
            self._progress_label.setText("Done!")
            self._close_btn.setText("Close")
            return

        self._show_next_card()

    def _show_next_card(self):
        """Display the next card."""
        if self._review_index >= len(self._review_words):
            self._finish_review()
            return

        self._current_word = self._review_words[self._review_index]
        self._card_flipped = False

        self._word_label.setText(self._current_word.word.upper())
        self._trans_label.setText(self._current_word.translation)
        self._trans_label.hide()

        self._stats_label.setText(
            f"Card {self._review_index + 1} of {len(self._review_words)}"
        )

        self._show_btn.show()
        self._show_btn.setEnabled(True)
        self._show_btn.setText("Show Answer  (Space)")

        for btn in self._rating_buttons.values():
            btn.hide()
        for label in self._hint_labels.values():
            label.hide()

    def _flip_card(self):
        """Flip the card to show translation and rating buttons."""
        if self._card_flipped or not self._current_word:
            return

        self._card_flipped = True
        self._trans_label.show()
        self._show_btn.hide()

        for q in [1, 2, 3, 5]:
            self._rating_buttons[q].show()
            self._hint_labels[q].show()

    def _rate_card(self, quality: int):
        """Rate the current card and record SRS review."""
        if not self._current_word:
            return

        self.db.record_srs_review(self._current_word.id, quality)

        was_correct = quality >= 3
        # Update local counters only (DB already updated by record_srs_review)
        self._total_count += 1
        if was_correct:
            self._correct_count += 1

        self._progress_label.setText(f"Score: {self.score_text}")

        self._review_index += 1
        QTimer.singleShot(300, self._show_next_card)

    def _finish_review(self):
        """Handle review completion."""
        self._is_done = True
        self._word_label.setText("Review Complete!")
        self._trans_label.setText(f"Final score: {self.score_text}")
        self._trans_label.show()
        self._stats_label.setText(f"Reviewed {len(self._review_words)} cards")
        self._show_btn.hide()
        for btn in self._rating_buttons.values():
            btn.hide()
        for label in self._hint_labels.values():
            label.hide()
        self._close_btn.setText("Finish")

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key_Space:
            if not self._card_flipped and not self._is_done:
                self._flip_card()
        elif event.key() == Qt.Key_1 and self._card_flipped:
            self._rate_card(1)
        elif event.key() == Qt.Key_2 and self._card_flipped:
            self._rate_card(2)
        elif event.key() == Qt.Key_3 and self._card_flipped:
            self._rate_card(3)
        elif event.key() == Qt.Key_4 and self._card_flipped:
            self._rate_card(5)
        super().keyPressEvent(event)
