"""Main application window with game selection — iOS-style design."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QScrollArea, QSpinBox, QSizePolicy
)
from database.db_manager import DatabaseManager
from ui.add_words_dialog import AddWordsDialog
from ui.stats_window import StatsWindow
from ui.games.teach import TeachWidget
from ui.games.game_srs import SRSWidget
from ui.games.game_meteorites import MeteoritesWidget
from ui.games.game_wordle import WordleWidget
from ui.games.game_memory_palace import MemoryPalaceWidget
from ui.games.game_scrabble import ScrabbleWidget
from ui.games.game_chain_reaction import ChainReactionWidget
from ui.games.game_domination import DominationWidget
from ui.games.game_sudoku import WordSudokuWidget
from ui.games.game_snake import SnakeWidget
from ui.games.game_bomb import BombWidget
from ui.games.game_blur import BlurWidget
from ui.games.game_rotating_word import RotatingWordWidget
from config import APP_NAME, APP_VERSION
from ui.styles import Colors, Fonts, pill_button_style, card_style, \
    label_style, progress_label_style, score_label_style, destructive_button_style, \
    action_button_style


class MainWindow(QMainWindow):
    """Main application window with game selection — iOS-style."""
    
    close_to_tray_requested = Signal()
    
    GAMES = {
        "teach": {"title": "Teach", "desc": "Browse words with translations", "cls": TeachWidget, "icon": "📖"},
        "srs": {"title": "SRS Review", "desc": "Spaced repetition flashcards", "cls": SRSWidget, "icon": "🔁"},
        "meteorites": {"title": "Meteorites", "desc": "Pick correct translation fast", "cls": MeteoritesWidget, "icon": "☄️"},
        "wordle": {"title": "Wordle", "desc": "Guess the word letter by letter", "cls": WordleWidget, "icon": "🎯"},
        "memory_palace": {"title": "Memory Palace", "desc": "Match word pairs", "cls": MemoryPalaceWidget, "icon": "🃏"},
        "scrabble": {"title": "Scrabble", "desc": "Type with hints", "cls": ScrabbleWidget, "icon": "✏️"},
        "chain_reaction": {"title": "Chain Reaction", "desc": "Direction-flipping quiz", "cls": ChainReactionWidget, "icon": "⚡"},
        "domination": {"title": "Domination", "desc": "Territory-control quiz", "cls": DominationWidget, "icon": "\U0001f3f0"},
        "word_sudoku": {"title": "Word Sudoku", "desc": "Latin-square word puzzle", "cls": WordSudokuWidget, "icon": "\U0001f9e9"},
        "snake": {"title": "Word Snake", "desc": "Steer snake, eat food, answer questions", "cls": SnakeWidget, "icon": "\U0001f40d"},
        "bomb": {"title": "Bomb", "desc": "Survive the countdown", "cls": BombWidget, "icon": "\U0001f4a3"},
        "blur": {"title": "Blur", "desc": "Type the blurred word", "cls": BlurWidget, "icon": "\U0001f32b\ufe0f"},
        "rotating_word": {"title": "Rotating Word", "desc": "Animated letters, type translation", "cls": RotatingWordWidget, "icon": "\U0001f504"},
    }
    
    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self._current_game_widget = None
        self._build_ui()
        self.setMinimumSize(600, 650)
    
    def _build_ui(self):
        """Build the iOS-style interface."""
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        
        # Outer container
        outer = QFrame()
        outer.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.SYSTEM_GROUPED_BG};
            }}
        """)
        self.setCentralWidget(outer)
        main_layout = QVBoxLayout(outer)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # ── iOS-style Navigation Bar ──
        nav_bar = QFrame()
        nav_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.SYSTEM_BG};
                border-bottom: 1px solid {Colors.SEPARATOR};
            }}
        """)
        nav_bar.setFixedHeight(80)
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(20, 12, 20, 10)
        
        # Title area
        title_container = QVBoxLayout()
        title_container.setSpacing(2)
        
        title_label = QLabel("LangTrainer")
        title_label.setStyleSheet(f"color: {Colors.PRIMARY_LABEL}; {Fonts.TITLE_1}")
        title_container.addWidget(title_label)
        
        subtitle_label = QLabel("Train your vocabulary")
        subtitle_label.setStyleSheet(f"color: {Colors.SECONDARY_LABEL}; {Fonts.SUBHEADLINE}")
        title_container.addWidget(subtitle_label)
        
        nav_layout.addLayout(title_container)
        nav_layout.addStretch()
        
        # Word count badge
        self._word_count_label = QLabel("0 words")
        self._word_count_label.setStyleSheet(f"""
            color: {Colors.SECONDARY_LABEL}; {Fonts.CALLOUT}
            background-color: {Colors.CARD_BG};
            border-radius: 14px; padding: 6px 14px;
        """)
        nav_layout.addWidget(self._word_count_label)
        
        main_layout.addWidget(nav_bar)
        
        # ── Header Action Row (iOS-style toolbar) ──
        toolbar = QFrame()
        toolbar.setStyleSheet(f"background-color: {Colors.SYSTEM_BG};")
        toolbar.setFixedHeight(52)
        tool_layout = QHBoxLayout(toolbar)
        tool_layout.setContentsMargins(20, 6, 20, 6)
        tool_layout.setSpacing(8)
        
        self._add_btn = QPushButton("➕  Add Words")
        self._add_btn.setStyleSheet(action_button_style(Colors.BLUE, border="1px solid transparent"))
        self._add_btn.clicked.connect(self._open_add_dialog)
        tool_layout.addWidget(self._add_btn)
        
        self._stats_btn = QPushButton("📊  Statistics")
        self._stats_btn.setStyleSheet(action_button_style(Colors.CARD_BG_ALT, border=f"1px solid {Colors.SEPARATOR}"))
        self._stats_btn.clicked.connect(self._open_stats)
        tool_layout.addWidget(self._stats_btn)
        
        self._clear_btn = QPushButton("🗑  Clear")
        self._clear_btn.setStyleSheet(destructive_button_style())
        self._clear_btn.clicked.connect(self._clear_database)
        tool_layout.addWidget(self._clear_btn)
        
        tool_layout.addStretch()
        
        # Timer controls
        timer_container = QFrame()
        timer_container.setStyleSheet(f"""
            background-color: {Colors.CARD_BG};
            border-radius: 18px; padding: 2px 12px;
        """)
        timer_layout = QHBoxLayout(timer_container)
        timer_layout.setContentsMargins(10, 4, 10, 4)
        timer_layout.setSpacing(6)
        
        timer_label = QLabel("Popup")
        timer_label.setStyleSheet(f"color: {Colors.SECONDARY_LABEL}; {Fonts.CAPTION_1}")
        timer_layout.addWidget(timer_label)
        
        self._timer_spin = QSpinBox()
        self._timer_spin.setRange(1, 30)
        self._timer_spin.setValue(3)
        self._timer_spin.setSuffix(" min")
        timer_layout.addWidget(self._timer_spin)
        
        tool_layout.addWidget(timer_container)
        
        
        main_layout.addWidget(toolbar)
        
        # ── Scrollable Content Area ──
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setStyleSheet(f"""
            QScrollArea {{ background-color: transparent; border: none; }}
        """)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Stack widget for switching between menu and games
        self._stack = QWidget()
        self._stack.setStyleSheet(f"background-color: transparent;")
        self._stack_layout = QVBoxLayout(self._stack)
        self._stack_layout.setContentsMargins(20, 16, 20, 16)
        self._stack_layout.setSpacing(8)
        
        self._build_menu()
        
        self._scroll_area.setWidget(self._stack)
        main_layout.addWidget(self._scroll_area, stretch=1)
    
    def _build_menu(self):
        """Build the iOS-style game selection menu."""
        # Clear any existing content
        while self._stack_layout.count():
            item = self._stack_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Section header
        section_header = QLabel("Training Modes")
        section_header.setStyleSheet(f"color: {Colors.SECONDARY_LABEL}; {Fonts.CAPTION_1}; padding: 4px 4px 8px 4px; text-transform: uppercase; letter-spacing: 1px;")
        self._stack_layout.addWidget(section_header)
        
        self._menu_info = QLabel("")
        self._menu_info.setStyleSheet(f"color: {Colors.SECONDARY_LABEL}; {Fonts.FOOTNOTE}; padding: 2px 4px 8px 4px;")
        self._menu_info.setWordWrap(True)
        self._stack_layout.addWidget(self._menu_info)
        self._update_word_count()
        
        # iOS-style game list cells
        for key, game_info in self.GAMES.items():
            cell = QFrame()
            cell.setStyleSheet(f"""
                QFrame {{
                    background-color: {Colors.CARD_BG};
                    border-radius: 14px;
                    margin: 2px 0;
                }}
                QFrame:hover {{
                    background-color: {Colors.CARD_BG_ALT};
                }}
            """)
            cell.setFixedHeight(72)
            cell_layout = QHBoxLayout(cell)
            cell_layout.setContentsMargins(16, 8, 12, 8)
            cell_layout.setSpacing(12)
            
            # Icon circle
            icon_frame = QFrame()
            icon_frame.setFixedSize(48, 48)
            icon_frame.setStyleSheet(f"""
                background-color: {_icon_bg(key)};
                border-radius: 24px;
            """)
            icon_layout = QHBoxLayout(icon_frame)
            icon_layout.setContentsMargins(0, 0, 0, 0)
            
            icon_label = QLabel(game_info.get("icon", "📚"))
            icon_label.setStyleSheet("font-size: 22px; background: transparent;")
            icon_label.setAlignment(Qt.AlignCenter)
            icon_layout.addWidget(icon_label)
            
            cell_layout.addWidget(icon_frame)
            
            # Text
            text_layout = QVBoxLayout()
            text_layout.setSpacing(2)
            
            title = QLabel(game_info["title"])
            title.setStyleSheet(f"color: {Colors.PRIMARY_LABEL}; {Fonts.HEADLINE}; background: transparent;")
            text_layout.addWidget(title)
            
            desc = QLabel(game_info["desc"])
            desc.setStyleSheet(f"color: {Colors.SECONDARY_LABEL}; {Fonts.FOOTNOTE}; background: transparent;")
            text_layout.addWidget(desc)
            
            cell_layout.addLayout(text_layout)
            cell_layout.addStretch()
            
            # iOS disclosure indicator + Start button
            control_layout = QHBoxLayout()
            control_layout.setSpacing(6)
            
            # Disclosure arrow
            arrow = QLabel("›")
            arrow.setStyleSheet(f"color: {Colors.TERTIARY_LABEL}; font-size: 24px; font-weight: light; background: transparent; padding-right: 4px;")
            control_layout.addWidget(arrow)
            
            play_btn = QPushButton("Start")
            play_btn.setStyleSheet(pill_button_style(Colors.BLUE, height="32px", font_size="13px"))
            play_btn.clicked.connect(lambda checked, k=key: self._start_game(k))
            control_layout.addWidget(play_btn)
            
            cell_layout.addLayout(control_layout)
            
            self._stack_layout.addWidget(cell)
        
        self._stack_layout.addStretch()
    
    def _update_word_count(self):
        """Update the word count display."""
        count = self.db.get_word_count()
        self._word_count_label.setText(f"📚 {count} words")
        if count < 4:
            self._menu_info.setText(
                "⚠️  Need at least 4 words. Tap 'Add Words' to import!"
            )
        else:
            self._menu_info.setText(f"✅ {count} words ready. Pick a mode below.")
    
    def _start_game(self, game_key: str):
        """Start a specific game."""
        if game_key not in self.GAMES:
            return
        
        game_info = self.GAMES[game_key]
        word_count = self.db.get_word_count()
        
        if word_count < 4:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Not Enough Words",
                "You need at least 4 words in the database to play.\n"
                "Please add words first using the 'Add Words' button.")
            return
        
        # Get words for the game
        from config import DEFAULT_WORDS_PER_GAME
        words = self.db.get_words_for_test(DEFAULT_WORDS_PER_GAME)
        
        if not words:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "No Words", "No words available for training.")
            return
        
        # Clear stack and show game
        while self._stack_layout.count():
            item = self._stack_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Create game widget
        game_cls = game_info["cls"]
        self._current_game_widget = game_cls(self.db)
        self._current_game_widget.finished.connect(self._back_to_menu)
        self._current_game_widget.setup_game(words)
        
        self._stack_layout.addWidget(self._current_game_widget)
    
    def _back_to_menu(self):
        """Return to the game selection menu."""
        if self._current_game_widget:
            self._current_game_widget.cleanup()
            self._current_game_widget = None
        
        self._build_menu()
        self._update_word_count()
    
    def _open_add_dialog(self):
        """Open the add words dialog."""
        dialog = AddWordsDialog(self.db, self)
        dialog.words_added.connect(lambda a, s: self._update_word_count())
        dialog.exec()
    
    def _open_stats(self):
        """Open the statistics window."""
        if self.db.get_word_count() == 0:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "No Data", "No words in database yet. Add some words first!")
            return
        stats = StatsWindow(self.db, self)
        stats.exec()
    
    def _clear_database(self):
        """Confirm and permanently clear all words, statistics, and game results.

        Destructive action: shows a warning dialog and only executes the
        full database reset if the user explicitly confirms.
        """
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.warning(
            self,
            "Clear Database",
            "This will permanently delete ALL words, statistics, and game results.\n\n"
            "This action cannot be undone. Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.db.clear_all_data()
            self._update_word_count()
    
    def closeEvent(self, event):
        """Handle close - minimize to tray instead."""
        event.ignore()
        self.close_to_tray_requested.emit()


def _icon_bg(game_key: str) -> str:
    """Get icon background color for each game type."""
    colors = {
        "teach": "#1E3A5F",
        "srs": "#2D4D7D",
        "meteorites": "#4A2D2D",
        "wordle": "#3A4A2D",
        "memory_palace": "#2D3A5F",
        "scrabble": "#4A2D4A",
        "chain_reaction": "#2D4A3A",
        "domination": "#3A2D4A",
        "word_sudoku": "#2D3A4A",
        "snake": "#2D4A2D",
        "bomb": "#4A3A2D",
        "blur": "#3A3A4A",
        "rotating_word": "#4A3A3A",
    }
    return colors.get(game_key, Colors.CARD_BG_ALT)
