"""Popup training window — iOS-style notification."""
import random
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QSizePolicy
)
from database.db_manager import DatabaseManager
from config import APP_NAME
from ui.styles import Colors, Fonts, _lighten


class PopupWindow(QFrame):
    """Non-intrusive popup for passive word training — iOS notification style.
    
    Shows a foreign word with translation options in bottom-right corner.
    """
    
    word_answered = Signal(int, bool)
    popup_closed = Signal()
    
    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self._current_word = None
        self._answered = False
        self._blink_timer = None
        self._build_ui()
        self._position_popup()
        
        # Auto-close timer (60 seconds)
        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self.close)
    
    def _build_ui(self):
        """Build the iOS notification-style popup."""
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(340, 240)
        
        # Outer layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # iOS notification card with subtle gradient
        card = QFrame(self)
        card.setObjectName("popupCard")
        card.setStyleSheet(f"""
            #popupCard {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {_lighten(Colors.CARD_BG, 0.05)}, stop:1 {Colors.CARD_BG});
                border: 1px solid {Colors.SEPARATOR};
                border-radius: 18px;
            }}
            QLabel#appLabel {{
                color: {Colors.SECONDARY_LABEL};
                {Fonts.CAPTION_2}
            }}
            QLabel#wordLabel {{
                color: {Colors.PRIMARY_LABEL};
                {Fonts.TITLE_2}
                padding: 4px;
            }}
            QPushButton {{
                background-color: {Colors.CARD_BG_ALT};
                color: {Colors.PRIMARY_LABEL};
                border: 1px solid {Colors.SEPARATOR};
                border-radius: 10px;
                padding: 12px;
                {Fonts.BODY}
                min-height: 20px;
            }}
            QPushButton:hover {{
                background-color: {_lighten(Colors.CARD_BG_ALT)};
                border-color: {Colors.BLUE};
            }}
            QPushButton:pressed {{
                background-color: {Colors.BLUE};
            }}
            QPushButton#closeBtn {{
                background-color: transparent;
                border: none;
                color: {Colors.TERTIARY_LABEL};
                {Fonts.CAPTION_1}
                padding: 2px 6px;
                min-height: 16px;
            }}
            QPushButton#closeBtn:hover {{
                color: {Colors.RED};
            }}
        """)
        
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 12, 18, 16)
        card_layout.setSpacing(8)
        
        # Header row with app name + close button
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(4)
        
        # Icon + app name
        icon_label = QLabel("📚")
        icon_label.setStyleSheet("font-size: 14px; background: transparent;")
        header.addWidget(icon_label)
        
        self._hint_label = QLabel(APP_NAME)
        self._hint_label.setObjectName("appLabel")
        header.addWidget(self._hint_label)
        
        header.addStretch()
        
        # Dot indicator (iOS notification style)
        dot = QLabel("•")
        dot.setStyleSheet(f"color: {Colors.BLUE}; font-size: 10px; background: transparent;")
        header.addWidget(dot)
        
        self._close_btn = QPushButton("✕")
        self._close_btn.setObjectName("closeBtn")
        self._close_btn.setFixedSize(28, 28)
        self._close_btn.clicked.connect(self._on_close)
        header.addWidget(self._close_btn)
        
        card_layout.addLayout(header)
        
        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {Colors.SEPARATOR}; border: none;")
        card_layout.addWidget(sep)
        
        # Word display
        self._word_label = QLabel("word")
        self._word_label.setObjectName("wordLabel")
        self._word_label.setAlignment(Qt.AlignCenter)
        self._word_label.setWordWrap(True)
        card_layout.addWidget(self._word_label)
        
        # Translation option buttons
        self._option_buttons = []
        for i in range(3):
            btn = QPushButton(f"Option {i+1}")
            btn.clicked.connect(lambda checked, idx=i: self._on_answer(idx))
            self._option_buttons.append(btn)
            card_layout.addWidget(btn)
        
        layout.addWidget(card)
        
        self.setAttribute(Qt.WA_MouseTracking)
    
    def _position_popup(self):
        """Position popup in bottom-right corner."""
        screen = self.screen()
        if screen:
            available = screen.availableGeometry()
            self.move(
                available.right() - self.width() - 24,
                available.bottom() - self.height() - 24
            )
    
    def show_word(self, word_record):
        """Display a word for training."""
        if not word_record:
            return
        
        self._answered = False
        self._current_word = word_record
        self._word_label.setText(word_record.word)
        
        # Get options
        options = self._generate_options(word_record)
        
        for i, (btn, opt) in enumerate(zip(self._option_buttons, options)):
            btn.setText(opt["text"])
            btn.setProperty("is_correct", opt["is_correct"])
            btn.setEnabled(True)
            btn.setStyleSheet("")
        
        self._position_popup()
        self._auto_close_timer.start(60000)
        self.show()
    
    def _generate_options(self, correct_word):
        """Generate translation options: 1 correct + 2 random distractors."""
        options = [{"text": correct_word.translation, "is_correct": True}]
        
        all_words = self.db.get_all_words()
        distractors = [w for w in all_words if w.id != correct_word.id]
        random.shuffle(distractors)
        
        for word in distractors[:2]:
            options.append({"text": word.translation, "is_correct": False})
        
        while len(options) < 3:
            options.append({"text": "—", "is_correct": False})
        
        random.shuffle(options)
        return options
    
    def _on_answer(self, index: int):
        """Handle user clicking a translation option."""
        if not self._current_word:
            return
        
        btn = self._option_buttons[index]
        is_correct = btn.property("is_correct")
        
        # Disable all buttons
        for b in self._option_buttons:
            b.setEnabled(False)
        
        # iOS-style feedback: subtle color change
        if is_correct:
            btn.setStyleSheet(
                f"background-color: {Colors.GREEN}; border-color: {Colors.GREEN}; "
                f"color: #ffffff; border-radius: 10px; padding: 12px; {Fonts.BODY}"
            )
        else:
            btn.setStyleSheet(
                f"background-color: {Colors.RED}; border-color: {Colors.RED}; "
                f"color: #ffffff; border-radius: 10px; padding: 12px; {Fonts.BODY}"
            )
        
        # Record attempt
        self._answered = True
        self.db.record_attempt(self._current_word.id, is_correct)
        self.word_answered.emit(self._current_word.id, is_correct)
        
        if is_correct:
            QTimer.singleShot(1200, self.close)
        else:
            # Show correct answer with green blink
            correct_btn = None
            for b in self._option_buttons:
                if b.property("is_correct"):
                    correct_btn = b
                    break
            
            if correct_btn:
                self._blink_correct(correct_btn, times=2, interval=500)
            else:
                QTimer.singleShot(1500, self.close)
    
    def _blink_correct(self, btn, times=2, interval=500):
        """Blink the correct answer."""
        self._blink_btn = btn
        self._blink_count = 0
        self._blink_max = times * 2
        self._blink_timer = QTimer(self)
        self._blink_timer.setSingleShot(False)
        self._blink_timer.timeout.connect(self._on_blink_tick)
        self._blink_timer.start(interval)
    
    def _on_blink_tick(self):
        """Timer tick: toggle correct button green/default."""
        self._blink_count += 1
        
        if self._blink_count % 2 == 1:
            self._blink_btn.setStyleSheet(
                f"background-color: {Colors.GREEN}; border-color: {Colors.GREEN}; "
                f"color: #ffffff; border-radius: 10px; padding: 12px; {Fonts.BODY}"
            )
        else:
            self._blink_btn.setStyleSheet("")
        
        if self._blink_count >= self._blink_max:
            self._blink_timer.stop()
            self._blink_timer.deleteLater()
            self._blink_timer = None
            self.close()
    
    def _on_close(self):
        """Handle manual close."""
        self._auto_close_timer.stop()
        self.close()
        self.popup_closed.emit()
    
    def closeEvent(self, event):
        """Handle close event."""
        self._auto_close_timer.stop()
        if self._blink_timer is not None and self._blink_timer.isActive():
            self._blink_timer.stop()
        # Record dismissal if word was shown but not answered (X button or timeout)
        if self._current_word is not None and not self._answered:
            self.db.record_dismissed(self._current_word.id)
        self.popup_closed.emit()
        super().closeEvent(event)
    
    def showEvent(self, event):
        """Handle show event - reposition."""
        self._position_popup()
        super().showEvent(event)
