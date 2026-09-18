"""Timer service for scheduling popup training sessions."""
from PySide6.QtCore import QTimer, Signal, QObject


class TimerService(QObject):
    """Manages the periodic popup training timer.
    
    Fires a signal at configurable intervals (1-30 minutes)
    to trigger the popup training window.
    """
    
    time_to_show_popup = Signal()
    timer_ticked = Signal(int)  # seconds remaining
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timeout)
        self._interval_minutes = 3  # default
        self._remaining_seconds = 0
        self._is_running = False
    
    @property
    def interval_minutes(self) -> int:
        return self._interval_minutes
    
    def set_interval(self, minutes: int):
        """Set timer interval (1-30 minutes)."""
        self._interval_minutes = max(1, min(30, minutes))
    
    def start(self):
        """Start the timer."""
        self._remaining_seconds = self._interval_minutes * 60
        self._timer.start(1000)  # tick every second
        self._is_running = True
    
    def stop(self):
        """Stop the timer."""
        self._timer.stop()
        self._is_running = False
        self._remaining_seconds = 0
    
    def pause(self):
        """Pause the timer."""
        self._timer.stop()
        self._is_running = False
    
    def resume(self):
        """Resume the timer."""
        if self._remaining_seconds > 0:
            self._timer.start(1000)
            self._is_running = True
        else:
            self.start()
    
    @property
    def is_running(self) -> bool:
        return self._is_running
    
    def _on_timeout(self):
        """Called every second."""
        self._remaining_seconds -= 1
        self.timer_ticked.emit(self._remaining_seconds)
        
        if self._remaining_seconds <= 0:
            self._timer.stop()
            self._is_running = False
            self.time_to_show_popup.emit()
            # Restart the cycle
            self.start()
    
    def reset(self):
        """Reset the timer to start fresh."""
        self.stop()
        self.start()
