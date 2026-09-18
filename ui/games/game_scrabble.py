"""Scrabble Game: Type the translation with hint support — iOS-style."""
import re
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QLineEdit,
    QFrame, QComboBox
)
from ui.games.game_base import BaseGame
from ui.styles import Colors, Fonts, pill_button_style, card_style, \
    input_field_style, combo_box_style, label_style, progress_label_style, \
    score_label_style, destructive_button_style


class ScrabbleWidget(BaseGame):
    """Type the translation or word with hint functionality — iOS-style."""
    
    finished = Signal()
    
    def __init__(self, db_manager, parent=None):
        super().__init__(db_manager, parent)
        self._current_word = None
        self._correct_answer = ""
        self._reverse_mode = False
        self._build_ui()
    
    def _build_ui(self):
        """Build the iOS-style Scrabble interface."""
        # Mode picker
        mode_layout = QHBoxLayout()
        mode_layout.setContentsMargins(16, 12, 16, 4)
        mode_layout.setSpacing(8)
        
        mode_label = QLabel("Mode")
        mode_label.setStyleSheet(label_style(Fonts.SUBHEADLINE, Colors.SECONDARY_LABEL))
        mode_layout.addWidget(mode_label)
        
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Word → Translation", "Translation → Word"])
        self._mode_combo.setStyleSheet(combo_box_style())
        mode_layout.addWidget(self._mode_combo)
        mode_layout.addStretch()
        self._layout.addLayout(mode_layout)
        
        # Card with word
        card = QFrame()
        card.setStyleSheet(card_style() + "margin: 8px 16px;")
        card.setMinimumHeight(100)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        
        self._word_label = QLabel("Word")
        self._word_label.setStyleSheet(
            f"color: {Colors.PRIMARY_LABEL}; {Fonts.TITLE_1}; background: transparent;"
        )
        self._word_label.setAlignment(Qt.AlignCenter)
        self._word_label.setWordWrap(True)
        card_layout.addWidget(self._word_label)
        self._layout.addWidget(card)
        
        # Prompt
        self._prompt_label = QLabel("Type the translation:")
        self._prompt_label.setStyleSheet(label_style(Fonts.BODY, Colors.SECONDARY_LABEL))
        self._prompt_label.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._prompt_label)
        
        # Input field
        self._input_field = QLineEdit()
        self._input_field.setStyleSheet(input_field_style())
        self._input_field.setPlaceholderText("Type your answer...")
        self._input_field.returnPressed.connect(self._check_answer)
        input_container = QHBoxLayout()
        input_container.setContentsMargins(16, 0, 16, 0)
        input_container.addWidget(self._input_field)
        self._layout.addLayout(input_container)
        
        # Hint display
        self._hint_label = QLabel("")
        self._hint_label.setStyleSheet(
            f"color: {Colors.ORANGE}; {Fonts.TITLE_3}; background: transparent; "
            f"font-family: 'Courier New', monospace; padding: 4px 16px;"
        )
        self._hint_label.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._hint_label)
        
        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(16, 4, 16, 4)
        btn_layout.setSpacing(8)
        
        self._hint_btn = QPushButton("💡 Hint")
        self._hint_btn.setStyleSheet(pill_button_style(Colors.CARD_BG_ALT, Colors.PRIMARY_LABEL,
                                                        border=f"1px solid {Colors.SEPARATOR}", height="32px", font_size="13px"))
        self._hint_btn.clicked.connect(self._show_hint)
        btn_layout.addWidget(self._hint_btn)
        
        self._skip_btn = QPushButton("Skip")
        self._skip_btn.setStyleSheet(pill_button_style(Colors.CARD_BG_ALT, Colors.SECONDARY_LABEL,
                                                        border=f"1px solid {Colors.SEPARATOR}", height="32px", font_size="13px"))
        self._skip_btn.clicked.connect(self._skip_word)
        btn_layout.addWidget(self._skip_btn)
        
        self._layout.addLayout(btn_layout)
        
        # Progress row
        progress_layout = QHBoxLayout()
        progress_layout.setContentsMargins(16, 4, 16, 4)
        self._progress_label = QLabel("0 / 0")
        self._progress_label.setStyleSheet(progress_label_style())
        progress_layout.addWidget(self._progress_label)
        progress_layout.addStretch()
        self._score_label = QLabel("Score: 0%")
        self._score_label.setStyleSheet(score_label_style())
        progress_layout.addWidget(self._score_label)
        self._layout.addLayout(progress_layout)
        
        # Close
        close_container = QHBoxLayout()
        close_container.setContentsMargins(16, 4, 16, 8)
        self._close_btn = QPushButton("✕ Close Game")
        self._close_btn.setStyleSheet(destructive_button_style())
        self._close_btn.clicked.connect(self.finished.emit)
        close_container.addWidget(self._close_btn)
        self._layout.addLayout(close_container)
        self._layout.addStretch()
    
    def setup_game(self, words):
        """Initialize game with words."""
        super().setup_game(words)
        self._score_label.setText("Score: 0%")
        self._show_next()
    
    def _show_next(self):
        """Show the next word."""
        if self.is_finished:
            self._finish_game()
            return
        
        self._current_word = self._current_words[self._current_index]
        self._reverse_mode = (self._mode_combo.currentIndex() == 1)
        
        if self._reverse_mode:
            self._word_label.setText(self._current_word.translation.upper())
            self._prompt_label.setText("Type the foreign word:")
            self._correct_answer = self._current_word.word
        else:
            self._word_label.setText(self._current_word.word.upper())
            self._prompt_label.setText("Type the translation:")
            self._correct_answer = self._current_word.translation
        
        self._progress_label.setText(self.progress_text)
        self._input_field.clear()
        self._input_field.setEnabled(True)
        self._input_field.setFocus()
        self._hint_label.setText("")
        self._hint_btn.setEnabled(True)
        self._skip_btn.setEnabled(True)
    
    def _check_answer(self):
        """Check the typed answer."""
        user_answer = self._input_field.text().strip()
        is_correct = (
            re.sub(r'\s+', ' ', user_answer).strip().lower()
            == re.sub(r'\s+', ' ', self._correct_answer).strip().lower()
        )
        
        self.record_answer(self._current_word.id, is_correct)
        self._score_label.setText(f"Score: {self.score_text}")
        
        if is_correct:
            self._prompt_label.setStyleSheet(f"color: {Colors.GREEN}; {Fonts.CALLOUT}; background: transparent; padding: 4px 16px;")
            self._prompt_label.setText("✓ Correct!")
        else:
            self._prompt_label.setStyleSheet(f"color: {Colors.RED}; {Fonts.CALLOUT}; background: transparent; padding: 4px 16px;")
            self._prompt_label.setText(f"✗ Answer: {self._correct_answer}")
        
        self._input_field.setEnabled(False)
        self._hint_btn.setEnabled(False)
        self._skip_btn.setEnabled(False)
        
        QTimer.singleShot(1500, self._show_next)
    
    def _show_hint(self):
        """Show a hint replacing vowels with underscores."""
        target = self._correct_answer
        hint = re.sub(r'[aeiouyAEIOUYаеёиоуыэюяАЕЁИОУЫЭЮЯ]', '_', target)
        self._hint_label.setText(f"💡 {hint}")
    
    def _skip_word(self):
        """Skip current word (counts as incorrect)."""
        self.record_answer(self._current_word.id, False)
        self._score_label.setText(f"Score: {self.score_text}")
        self._prompt_label.setStyleSheet(f"color: {Colors.ORANGE}; {Fonts.CALLOUT}; background: transparent; padding: 4px 16px;")
        self._prompt_label.setText(f"Skipped: {self._correct_answer}")
        self._input_field.setEnabled(False)
        self._hint_btn.setEnabled(False)
        self._skip_btn.setEnabled(False)
        QTimer.singleShot(1000, self._show_next)
    
    def _finish_game(self):
        """Handle game completion."""
        self._word_label.setText("✓ Complete!")
        self._prompt_label.setStyleSheet(f"color: {Colors.GREEN}; {Fonts.TITLE_3}; background: transparent; padding: 4px 16px;")
        self._prompt_label.setText(f"Final score: {self.score_text}")
        self._input_field.setEnabled(False)
        self._hint_btn.setEnabled(False)
        self._skip_btn.setEnabled(False)
        self._hint_label.setText("")
        self._close_btn.setText("Finish")
        self.finished.emit()
