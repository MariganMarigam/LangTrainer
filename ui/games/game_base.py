"""Base class for all game/training modes."""
from PySide6.QtWidgets import QWidget, QVBoxLayout
from database.db_manager import DatabaseManager


class BaseGame(QWidget):
    """Abstract base class for game widgets."""
    
    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self._current_words = []
        self._current_index = 0
        self._correct_count = 0
        self._total_count = 0
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
    
    def setup_game(self, words):
        """Initialize game with a list of words.
        
        Args:
            words: list of WordRecord objects
        """
        self._current_words = list(words)
        self._current_index = 0
        self._correct_count = 0
        self._total_count = 0
    
    def record_answer(self, word_id: int, was_correct: bool):
        """Record an answer and update statistics."""
        self.db.record_attempt(word_id, was_correct)
        self._total_count += 1
        if was_correct:
            self._correct_count += 1
        self._current_index += 1
    
    @property
    def is_finished(self) -> bool:
        """Check if all words have been shown."""
        return self._current_index >= len(self._current_words)
    
    @property
    def progress_text(self) -> str:
        return f"{self._current_index}/{len(self._current_words)}"
    
    @property
    def score_text(self) -> str:
        if self._total_count == 0:
            return "0%"
        return f"{int(self._correct_count / self._total_count * 100)}%"
    
    def cleanup(self):
        """Clean up resources."""
        pass
