#!/usr/bin/env python3
"""LangTrainer - Cross-platform desktop application for language learning.

A system-tray application that provides passive popup training and
focused game modes for learning foreign words and phrases.
"""

import sys
import os

# Ensure the app directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPalette, QColor, QFont
from PySide6.QtWidgets import QApplication, QStyleFactory

from config import APP_NAME
from database.db_manager import DatabaseManager
from services.timer_service import TimerService
from ui.tray import TrayManager
from ui.main_window import MainWindow
from ui.popup import PopupWindow

def setup_dark_theme(app: QApplication):
    """Apply an iOS-inspired dark theme to the application."""
    app.setStyle(QStyleFactory.create("Fusion"))
    
    palette = QPalette()
    
    # iOS Dark Mode colors
    bg_dark = QColor("#000000")
    bg_card = QColor("#1C1C1E")
    bg_card_alt = QColor("#2C2C2E")
    bg_secondary = QColor("#242426")
    text_primary = QColor("#FFFFFF")
    text_secondary = QColor("#98989D")
    text_tertiary = QColor("#636366")
    ios_blue = QColor("#007AFF")
    separator = QColor("#38383A")
    
    palette.setColor(QPalette.Window, bg_dark)
    palette.setColor(QPalette.WindowText, text_primary)
    palette.setColor(QPalette.Base, bg_card)
    palette.setColor(QPalette.AlternateBase, bg_card_alt)
    palette.setColor(QPalette.ToolTipBase, bg_card)
    palette.setColor(QPalette.ToolTipText, text_primary)
    palette.setColor(QPalette.Text, text_primary)
    palette.setColor(QPalette.Button, bg_secondary)
    palette.setColor(QPalette.ButtonText, text_primary)
    palette.setColor(QPalette.BrightText, QColor("#FF3B30"))
    palette.setColor(QPalette.Link, ios_blue)
    palette.setColor(QPalette.Highlight, ios_blue)
    palette.setColor(QPalette.HighlightedText, text_primary)
    
    # Disabled colors
    palette.setColor(QPalette.Disabled, QPalette.WindowText, text_tertiary)
    palette.setColor(QPalette.Disabled, QPalette.Text, text_tertiary)
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, text_tertiary)
    
    app.setPalette(palette)
    
    # Global iOS-inspired stylesheet
    app.setStyleSheet("""
        QToolTip { color: #ffffff; background-color: #1C1C1E; 
                   border: 1px solid #38383A; border-radius: 6px; padding: 6px 10px; }
        QMenu { background-color: #1C1C1E; color: #ffffff; 
                border: 1px solid #38383A; border-radius: 10px; padding: 4px; }
        QMenu::item { padding: 8px 16px; border-radius: 6px; margin: 1px 4px; }
        QMenu::item:selected { background-color: #007AFF; }
        QMenu::separator { height: 1px; background-color: #38383A; margin: 4px 12px; }
        QScrollBar:vertical { background-color: #000000; width: 6px; margin: 0; }
        QScrollBar::handle:vertical { background-color: #38383A; border-radius: 3px; min-height: 30px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        QScrollBar:horizontal { background-color: #000000; height: 6px; margin: 0; }
        QScrollBar::handle:horizontal { background-color: #38383A; border-radius: 3px; }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
        QSpinBox { background-color: #242426; color: #ffffff; 
                   border: 1px solid #38383A; border-radius: 8px; 
                   padding: 6px 10px; font-size: 14px; }
        QSpinBox::up-button, QSpinBox::down-button { border: none; }
    """)

def main():
    """Application entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("LangTrainer")
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray
    
    setup_dark_theme(app)
    
    # Initialize database
    db = DatabaseManager()
    db.connect()
    
    # Initialize components
    tray = TrayManager()
    timer_service = TimerService()
    main_window = MainWindow(db)
    popup = PopupWindow(db)
    popup._recent_popup_ids = []  # Cooldown: recently shown popup word IDs
    
    # Connect signal chains
    # Tray signals
    tray.show_main_window_requested.connect(main_window.show)
    tray.hide_main_window_requested.connect(main_window.hide)
    tray.clear_database_requested.connect(main_window._clear_database)
    tray.quit_requested.connect(lambda: _quit_app(app, db, tray))
    
    # Main window signals
    main_window.close_to_tray_requested.connect(main_window.hide)
    main_window.hideEvent = lambda event: _on_main_window_hide(event, main_window, tray, timer_service)
    
    # Timer signals
    timer_service.time_to_show_popup.connect(lambda: _show_popup(popup, db, timer_service))
    
    # Popup signals
    popup.popup_closed.connect(lambda: _on_popup_closed(popup, db))
    
    # Timer control from main window
    main_window._timer_spin.valueChanged.connect(
        lambda val: timer_service.set_interval(val)
    )

    # Timer control based on main window visibility
    # Show window → stop passive popup timer
    # Hide window → start passive popup timer
    def _on_main_window_show(event, window, timer):
        """Handle main window show — stop passive timer."""
        timer.stop()

    main_window.showEvent = lambda event: _on_main_window_show(event, main_window, timer_service)
    
    # Show main window initially
    main_window.show()
    
    # Setup tray
    tray.setup()
    
    # Run application
    exit_code = app.exec()
    
    # Cleanup
    db.disconnect()
    sys.exit(exit_code)

def _on_main_window_hide(event, window: MainWindow, tray: TrayManager, timer_service: TimerService):
    """Handle main window hide — start passive training."""
    # Don't event.ignore() — this is QHideEvent, ignore() breaks Qt state tracking
    # Don't window.hide() — we're already inside hideEvent!
    tray.show_notification(
        APP_NAME,
        "Still running in the background. Click to open."
    )
    # Start passive popup timer when window is hidden
    timer_service.set_interval(window._timer_spin.value())
    timer_service.start()

def _show_popup(popup: PopupWindow, db: DatabaseManager, timer_service: TimerService):
    """Show a popup with priority + randomness + cooldown.
    
    - Priority: struggling words are in top-10 pool more often
    - Random: picks randomly from pool (not just #1)
    - Cooldown: skips recently shown words (no repeats within 3 popups)
    """
    word = db.get_popup_word(recent_ids=popup._recent_popup_ids)
    if not word:
        return
    
    # Track for cooldown
    popup._recent_popup_ids.append(word.id)
    if len(popup._recent_popup_ids) > 3:
        popup._recent_popup_ids = popup._recent_popup_ids[-3:]
    
    popup.show_word(word)

def _on_popup_closed(popup: PopupWindow, db: DatabaseManager):
    """Handle popup window closing."""
    pass  # Timer auto-restarts in TimerService

def _quit_app(app: QApplication, db: DatabaseManager, tray: TrayManager):
    """Clean shutdown of the application."""
    tray.cleanup()
    db.disconnect()
    app.quit()

if __name__ == "__main__":
    main()
