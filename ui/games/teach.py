"""Teach mode - browse through words with translations."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QFrame, QSizePolicy,
)
from ui.games.game_base import BaseGame
from ui.styles import (
    Colors,
    Fonts,
    pill_button_style,
    card_style,
    label_style,
    destructive_button_style,
    combo_box_style,
    input_field_style,
)


class TeachWidget(BaseGame):
    """Browse through words with their translations.
    
    Shows foreign word → translation with prev/next navigation.
    """
    
    finished = Signal()
    
    def __init__(self, db_manager, parent=None):
        super().__init__(db_manager, parent)
        self._build_ui()
    
    def _build_ui(self):
        """Build the teach interface."""
        # iOS-style grouped margins and spacing
        self._layout.setContentsMargins(16, 8, 16, 8)
        self._layout.setSpacing(8)
        
        # ── Word display (large, centered card) ────────────────────────
        word_card = QFrame()
        word_card.setStyleSheet(card_style())
        word_card_layout = QVBoxLayout(word_card)
        word_card_layout.setContentsMargins(16, 12, 16, 12)
        
        self._word_label = QLabel("Word")
        self._word_label.setStyleSheet(label_style(Fonts.TITLE_1))
        self._word_label.setAlignment(Qt.AlignCenter)
        self._word_label.setMinimumHeight(80)
        word_card_layout.addWidget(self._word_label)
        
        self._layout.addWidget(word_card)
        
        # ── Translation display (card below word) ──────────────────────
        trans_card = QFrame()
        trans_card.setStyleSheet(card_style())
        trans_card_layout = QVBoxLayout(trans_card)
        trans_card_layout.setContentsMargins(16, 12, 16, 12)
        
        self._trans_label = QLabel("translation")
        self._trans_label.setStyleSheet(
            label_style(Fonts.TITLE_3, Colors.SECONDARY_LABEL)
        )
        self._trans_label.setAlignment(Qt.AlignCenter)
        self._trans_label.setMinimumHeight(60)
        trans_card_layout.addWidget(self._trans_label)
        
        self._layout.addWidget(trans_card)
        
        # ── Progress label ─────────────────────────────────────────────
        self._progress_label = QLabel("0 / 0")
        self._progress_label.setStyleSheet(
            label_style(Fonts.FOOTNOTE, Colors.SECONDARY_LABEL)
        )
        self._progress_label.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._progress_label)
        
        # ── Navigation buttons (Previous / Next) ───────────────────────
        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(0, 4, 0, 4)
        nav_layout.setSpacing(12)
        
        self._prev_btn = QPushButton("◀  Previous")
        self._prev_btn.setStyleSheet(
            pill_button_style(
                Colors.CARD_BG_ALT,
                border=f"1px solid {Colors.SEPARATOR}",
            )
        )
        self._prev_btn.clicked.connect(self._go_prev)
        nav_layout.addWidget(self._prev_btn)
        
        self._next_btn = QPushButton("Next  ▶")
        self._next_btn.setStyleSheet(pill_button_style(Colors.BLUE))
        self._next_btn.clicked.connect(self._go_next)
        nav_layout.addWidget(self._next_btn)
        
        self._layout.addLayout(nav_layout)
        
        # ── Close button (destructive style, right-aligned) ────────────
        close_layout = QHBoxLayout()
        close_layout.setContentsMargins(0, 4, 0, 8)
        close_layout.addStretch()
        
        self._close_btn = QPushButton("Close")
        self._close_btn.setStyleSheet(destructive_button_style())
        self._close_btn.clicked.connect(self.finished.emit)
        close_layout.addWidget(self._close_btn)
        
        self._layout.addLayout(close_layout)
    
    def setup_game(self, words):
        """Initialize with a list of words."""
        super().setup_game(words)
        self._show_current()
    
    def _show_current(self):
        """Display the current word."""
        if not self._current_words or self._current_index >= len(self._current_words):
            return
        
        word = self._current_words[self._current_index]
        self._word_label.setText(word.word.upper())
        self._trans_label.setText(word.translation)
        self._progress_label.setText(
            f"{self._current_index + 1} of {len(self._current_words)}"
        )
    
    def _go_next(self):
        """Go to next word."""
        if self._current_index < len(self._current_words) - 1:
            self._current_index += 1
            self._show_current()
    
    def _go_prev(self):
        """Go to previous word."""
        if self._current_index > 0:
            self._current_index -= 1
            self._show_current()
