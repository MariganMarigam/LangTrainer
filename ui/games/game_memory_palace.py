"""Memory Palace: Match word-translation pairs in a grid.

Three difficulty levels:
- Easy:    4 pairs (8 cards), 4×2 grid — simple find all pairs
- Hard:    8 pairs (16 cards), 4×4 grid — more cards to remember
- Chaos:   8 pairs (16 cards), 4×4 grid — matched pair disappears,
           remaining cards shuffle positions (board keeps rearranging!)
"""
import random
import math
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout,
    QFrame, QMessageBox, QComboBox, QWidget
)
from ui.games.game_base import BaseGame
from ui.styles import (
    Colors, Fonts,
    pill_button_style, card_style, label_style,
    progress_label_style, score_label_style,
    destructive_button_style, combo_box_style,
    HIDDEN_CARD_STYLE, SELECTED_CARD_STYLE, MATCHED_CARD_STYLE,
)


class MemoryPalaceWidget(BaseGame):
    """Grid of facedown cards — match foreign words to translations.
    
    Easy:   4 pairs, 4×2 grid, no penalties
    Hard:   8 pairs, 4×4 grid, more cards
    Chaos:  8 pairs, 4×4 grid, matched pair vanishes, rest shuffle
    """
    
    finished = Signal()
    
    DIFFICULTIES = {
        "easy":  {"pairs": 4, "cols": 4},
        "hard":  {"pairs": 8, "cols": 4},
        "chaos": {"pairs": 8, "cols": 4},
    }
    
    def __init__(self, db_manager, parent=None):
        super().__init__(db_manager, parent)
        self._cards = []
        self._selected = None
        self._matched_count = 0
        self._streak = 0
        self._total_pairs = 0
        self._difficulty = "easy"
        self._lock_grid = False
        self._pending_timers = []
        self._last_board_ids: set[int] | None = None
        self._layout.setContentsMargins(16, 8, 16, 8)
        self._layout.setSpacing(8)
        self._build_ui()
    
    def _build_ui(self):
        """Build the memory game interface."""
        # ── Difficulty picker ──
        diff_layout = QHBoxLayout()
        diff_label = QLabel("Difficulty:")
        diff_label.setStyleSheet(label_style(Fonts.CALLOUT, Colors.SECONDARY_LABEL))
        diff_layout.addWidget(diff_label)
        
        self._diff_combo = QComboBox()
        self._diff_combo.addItems(["Easy", "Hard", "Chaos"])
        self._diff_combo.setStyleSheet(combo_box_style())
        self._diff_combo.currentTextChanged.connect(self._on_difficulty_change)
        diff_layout.addWidget(self._diff_combo)
        diff_layout.addStretch()
        self._layout.addLayout(diff_layout)
        
        # ── Status label ──
        self._status_label = QLabel("Click two cards to find matching pairs!")
        self._status_label.setStyleSheet(label_style(Fonts.CALLOUT, Colors.SECONDARY_LABEL))
        self._status_label.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._status_label)
        
        # ── Card grid ──
        self._grid_widget = QWidget()
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setSpacing(6)
        self._layout.addWidget(self._grid_widget)
        
        # ── Progress & score ──
        progress_layout = QHBoxLayout()
        self._progress_label = QLabel("Matched: 0 / 0")
        self._progress_label.setStyleSheet(progress_label_style())
        progress_layout.addWidget(self._progress_label)
        progress_layout.addStretch()
        self._score_label = QLabel("Score: 0%")
        self._score_label.setStyleSheet(score_label_style())
        progress_layout.addWidget(self._score_label)
        self._layout.addLayout(progress_layout)
        
        # ── Close button ──
        self._close_btn = QPushButton("✕  Close")
        self._close_btn.setStyleSheet(destructive_button_style())
        self._close_btn.clicked.connect(self.finished.emit)
        self._layout.addWidget(self._close_btn)
        self._layout.addStretch()
    
    def _on_difficulty_change(self, text):
        """Handle difficulty change — rebuild board for new difficulty."""
        self._difficulty = text.lower()
        if self._current_words:
            self._matched_count = 0
            self._streak = 0
            self._score_label.setText("Score: 0%")
            self._selected = None
            self._lock_grid = False
            self._cancel_pending_timers()
            self._build_board()
    
    def setup_game(self, words):
        """Initialize game with words."""
        super().setup_game(words)
        self._matched_count = 0
        self._streak = 0
        self._score_label.setText("Score: 0%")
        self._last_board_ids = None
        self._build_board()
    
    def cleanup(self):
        """Clean up resources — cancel all pending timers."""
        self._cancel_pending_timers()
        super().cleanup()
    
    def _cancel_pending_timers(self):
        """Cancel and clean up all pending delayed callbacks."""
        for timer in self._pending_timers:
            try:
                timer.stop()
                timer.deleteLater()
            except RuntimeError:
                pass
        self._pending_timers.clear()
    
    def _safe_widget(self, card):
        """Check if a card's widget is still valid (not deleted by Qt)."""
        try:
            return card["widget"] is not None and card["widget"].text() is not None
        except RuntimeError:
            return False
    
    def _pick_board_words(self, num_pairs):
        """Pick num_pairs random words for the board, avoiding the previous set.

        Shuffles the word pool and takes the first ``num_pairs``.  When the
        pool is larger than the board, re-shuffles (bounded) until the picked
        set differs from the previous board's set, so a difficulty change
        always shows fresh words.

        Args:
            num_pairs: Number of word-translation pairs to pick.

        Returns:
            List of WordRecord objects (length ``num_pairs``).
        """
        pool = list(self._current_words)
        random.shuffle(pool)
        picked = pool[:num_pairs]
        if self._last_board_ids is not None and len(pool) > num_pairs:
            for _ in range(10):
                if {w.id for w in picked} != self._last_board_ids:
                    break
                random.shuffle(pool)
                picked = pool[:num_pairs]
        self._last_board_ids = {w.id for w in picked}
        return picked

    def _build_board(self):
        """Build the memory board based on difficulty."""
        self._cancel_pending_timers()
        # Clear old grid
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        diff = self.DIFFICULTIES[self._difficulty]
        # How many word-translation pairs we can actually make
        num_pairs = min(diff["pairs"], len(self._current_words))
        self._total_pairs = num_pairs
        cols = diff["cols"]
        
        game_words = self._pick_board_words(num_pairs)
        
        # Build card data: each word → 2 cards (word + translation)
        self._cards = []
        pair_id = 0
        for w in game_words:
            self._cards.append({
                "id": f"word_{w.id}",
                "text": w.word.upper(),
                "pair_id": pair_id,
                "matched": False,
                "widget": None,
            })
            self._cards.append({
                "id": f"trans_{w.id}",
                "text": w.translation,
                "pair_id": pair_id,
                "matched": False,
                "widget": None,
            })
            pair_id += 1
        
        random.shuffle(self._cards)
        
        rows = math.ceil(len(self._cards) / cols)
        
        for i, card in enumerate(self._cards):
            row = i // cols
            col = i % cols
            btn = QPushButton("?")
            btn.setStyleSheet(HIDDEN_CARD_STYLE)
            btn.card_data = card
            btn.clicked.connect(lambda checked, c=card: self._on_card_click(c))
            card["widget"] = btn
            self._grid.addWidget(btn, row, col)
        
        self._progress_label.setText(f"Matched: 0 / {num_pairs}")
        self._status_label.setText("Click two cards to find matching pairs!")
    
    def _on_card_click(self, card):
        """Handle clicking a card."""
        if self._lock_grid or card["matched"]:
            return
        
        btn = card["widget"]
        btn.setText(card["text"])
        btn.setStyleSheet(SELECTED_CARD_STYLE)
        
        if self._selected is None:
            # First card of the pair
            self._selected = card
            self._status_label.setText("Now click the matching card...")
        else:
            # Second card — check match
            first = self._selected
            second = card
            
            if first["id"] == second["id"]:
                return  # Same card
            
            self._lock_grid = True
            diff_name = self._difficulty
            
            if first["pair_id"] == second["pair_id"]:
                # ✅ CORRECT MATCH
                self._handle_match(first, second)
            else:
                # ❌ WRONG MATCH
                self._handle_wrong(first, second, diff_name)
    
    def _handle_match(self, first, second):
        """Handle a correct pair match."""
        first["matched"] = True
        second["matched"] = True
        self._matched_count += 1
        self._streak += 1
        
        # Mark cards as matched (visually)
        for c in [first, second]:
            c["widget"].setStyleSheet(MATCHED_CARD_STYLE)
            c["widget"].setEnabled(False)
        
        # Record correct answer
        word_id = None
        for c in [first, second]:
            cid = c["id"]
            if cid.startswith("word_"):
                word_id = int(cid.split("_")[1])
                break
        if word_id:
            self.record_answer(word_id, True)
        
        self._score_label.setText(f"Score: {self.score_text}")
        self._progress_label.setText(
            f"Matched: {self._matched_count} / {self._total_pairs}"
        )
        
        if self._streak >= 3:
            self._status_label.setText(f"🔥  {self._streak}x streak!")
        else:
            self._status_label.setText("✅  Match found!")
        
        # Check if all pairs matched → game won
        if self._matched_count >= self._total_pairs:
            self._status_label.setText(f"🎉  All matched! {self.score_text}")
            self._close_btn.setText("Finish")
            t = QTimer(self)
            t.setSingleShot(True)
            t.timeout.connect(self.finished.emit)
            t.start(500)
            self._pending_timers.append(t)
            return
        
        # ── Chaos mode: matched pair disappears, rest shuffle ──
        if self._difficulty == "chaos":
            # Briefly pause to show the match, then remove + shuffle
            t = QTimer(self)
            t.setSingleShot(True)
            t.timeout.connect(lambda: self._chaos_remove_and_shuffle(first, second))
            t.start(400)
            self._pending_timers.append(t)
        else:
            # Easy/Hard: just continue
            self._selected = None
            self._lock_grid = False
    
    def _handle_wrong(self, first, second, diff_name):
        """Handle a wrong match — flip cards back."""
        self._streak = 0
        self._status_label.setText("❌  Wrong! Try again.")
        
        _first, _second = first, second
        t = QTimer(self)
        t.setSingleShot(True)
        t.timeout.connect(lambda: self._flip_back(_first, _second))
        t.start(800)
        self._pending_timers.append(t)
    
    def _flip_back(self, first, second):
        """Flip two cards back to hidden state."""
        cards_to_flip = [c for c in [first, second] if c is not None and not c["matched"]]
        for card in cards_to_flip:
            if not self._safe_widget(card):
                continue
            try:
                btn = card["widget"]
                btn.setText("?")
                btn.setStyleSheet(HIDDEN_CARD_STYLE)
            except RuntimeError:
                pass
        self._selected = None
        self._lock_grid = False
        self._status_label.setText("Click two cards to find matching pairs!")
    
    def _chaos_remove_and_shuffle(self, first, second):
        """Chaos mode: remove matched pair visually, then shuffle remaining cards."""
        self._cancel_pending_timers()
        
        # Hide the matched pair's widgets (remove from grid)
        for c in [first, second]:
            if self._safe_widget(c):
                try:
                    self._grid.removeWidget(c["widget"])
                    c["widget"].hide()
                except RuntimeError:
                    pass
        
        # Collect all still-visible unmatched cards
        unmatched = [c for c in self._cards if not c["matched"] and self._safe_widget(c)]
        
        if len(unmatched) < 2:
            # Not enough cards to shuffle meaningfully
            self._selected = None
            self._lock_grid = False
            return
        
        # Shuffle the unmatched cards' positions
        random.shuffle(unmatched)
        
        cols = self.DIFFICULTIES[self._difficulty]["cols"]
        for i, card in enumerate(unmatched):
            if not self._safe_widget(card):
                continue
            try:
                row = i // cols
                col = i % cols
                self._grid.removeWidget(card["widget"])
                self._grid.addWidget(card["widget"], row, col)
                # Ensure card is face-down
                card["widget"].setText("?")
                card["widget"].setStyleSheet(HIDDEN_CARD_STYLE)
            except RuntimeError:
                pass
        
        self._status_label.setText("🌀  Board shuffled! Find the next pair...")
        self._selected = None
        self._lock_grid = False
