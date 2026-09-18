"""System tray icon and menu for LangTrainer."""
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QFont
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from config import APP_NAME


def _create_default_icon() -> QIcon:
    """Create a simple default icon (a 'T' letter) for the tray."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor("#0078d4"))
    painter = QPainter(pixmap)
    painter.setPen(QColor("#ffffff"))
    font = QFont("Arial", 32, QFont.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "LT")
    painter.end()
    return QIcon(pixmap)


class TrayManager(QObject):
    """Manages the system tray icon and context menu."""
    
    show_main_window_requested = Signal()
    hide_main_window_requested = Signal()
    clear_database_requested = Signal()
    quit_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tray: QSystemTrayIcon = None
        self._menu: QMenu = None
    
    def setup(self):
        """Initialize and show the tray icon."""
        self._tray = QSystemTrayIcon(_create_default_icon(), self)
        self._tray.setToolTip(APP_NAME)
        
        # Build context menu
        self._menu = QMenu()
        
        show_action = QAction("📖  Show Trainer", self._menu)
        show_action.triggered.connect(self.show_main_window_requested.emit)
        self._menu.addAction(show_action)
        
        hide_action = QAction("🔒  Hide to Tray", self._menu)
        hide_action.triggered.connect(self.hide_main_window_requested.emit)
        self._menu.addAction(hide_action)
        
        self._menu.addSeparator()
        
        clear_action = QAction("🗑  Clear Database…", self._menu)
        clear_action.triggered.connect(self.clear_database_requested.emit)
        self._menu.addAction(clear_action)
        
        self._menu.addSeparator()
        
        quit_action = QAction("🚪  Quit", self._menu)
        quit_action.triggered.connect(self.quit_requested.emit)
        self._menu.addAction(quit_action)
        
        self._tray.setContextMenu(self._menu)
        
        # Double-click to show main window
        self._tray.activated.connect(self._on_activated)
        
        self._tray.show()
    
    def _on_activated(self, reason):
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_main_window_requested.emit()
    
    def show_notification(self, title: str, message: str, duration_ms: int = 3000):
        """Show a balloon notification from the tray."""
        if self._tray and self._tray.supportsMessages():
            self._tray.showMessage(title, message, QSystemTrayIcon.Information, duration_ms)
    
    def cleanup(self):
        """Remove tray icon on shutdown."""
        if self._tray:
            self._tray.hide()
