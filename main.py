#!/usr/bin/env python3
"""LangTrainer - Cross-platform desktop application for language learning.

A system-tray application that provides passive popup training and
focused game modes for learning foreign words and phrases.
"""

import sys
import os
import secrets
import traceback
import datetime
import platform
from pathlib import Path

# Ensure the app directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _append_crash_log(text: str) -> None:
    """Append text to logs/langtrainer-crash.log. Never raises.

    The log is capped at 1 MiB: past that, only the last 256 KiB is kept, so a
    crash loop cannot fill the user's disk.
    """
    try:
        # LOGS_DIR is bound by the `from config import ...` line further down.
        # That import has NOT run yet if the failure was inside the PySide6
        # import below — which is exactly the case this hook exists for. Fall
        # back to resolving it from the config module directly.
        logs_dir = LOGS_DIR if "LOGS_DIR" in globals() else __import__("config").LOGS_DIR
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / "langtrainer-crash.log"
        max_bytes = 1024 * 1024
        keep_bytes = 256 * 1024
        if log_path.exists() and log_path.stat().st_size > max_bytes:
            with open(log_path, "rb") as fh:
                fh.seek(-keep_bytes, os.SEEK_END)
                tail = fh.read()
            with open(log_path, "wb") as fh:
                fh.write(tail)
        with open(log_path, "a", encoding="utf-8", errors="replace") as fh:
            fh.write(text)
    except Exception:
        pass


def _install_crash_hook() -> None:
    """Install a sys.excepthook that logs the crash, then delegates to the original.

    Installed as the FIRST executable statement of this module, before any
    PySide6 import: a failure inside those imports is exactly the case the user
    would otherwise never see. The original hook is called unconditionally so
    the native traceback dialog (opt-OUT) still appears.
    """
    original = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb):
        try:
            rule = "=" * 70
            header = (
                f"\n{rule}\n"
                f"LangTrainer crash — {datetime.datetime.now().isoformat()}\n"
                f"executable: {sys.executable}\n"
                f"python:     {sys.version}\n"
                f"platform:   {platform.platform()}\n"
                f"frozen:     {getattr(sys, 'frozen', False)}\n"
                f"{rule}\n"
            )
            _append_crash_log(
                header + "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            )
        except Exception:
            pass
        original(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook


_install_crash_hook()

from PySide6.QtCore import Qt, QTimer, QLockFile, QUrl
from PySide6.QtGui import QPalette, QColor, QFont, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QStyleFactory, QMessageBox, QProgressDialog, QSystemTrayIcon,
)

import config
import services.updater as updater
from config import APP_NAME, LOGS_DIR, ensure_dics_extracted
from database.db_manager import DatabaseManager
from services.timer_service import TimerService
from ui.tray import TrayManager
from ui.main_window import MainWindow
from ui.popup import PopupWindow
from ui.update_dialog import RestartConfirmDialog, UpdateAvailableDialog

# Guards against two update flows overlapping (tray menu click + balloon click).
_download_in_progress = False


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

def _open_logs_folder() -> None:
    """Open the logs folder in the system file manager (tray menu)."""
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(LOGS_DIR)))


def _show_update_balloon(tray: TrayManager, title: str, message: str, on_clicked) -> None:
    """Show a tray balloon that runs `on_clicked` when the user clicks it.

    The app is architected never to steal focus, so this balloon — not a modal
    dialog — is the default update surface. The connection is dropped after the
    first click so a second update cannot be handled twice by a stale handler.
    """
    icon = getattr(tray, "_tray", None)
    if icon is None:
        return

    def _handler() -> None:
        try:
            icon.messageClicked.disconnect(_handler)
        except (RuntimeError, TypeError):
            pass
        on_clicked()

    icon.messageClicked.connect(_handler)
    icon.showMessage(title, message, QSystemTrayIcon.Information, 10000)


def _open_data_folder(path: Path) -> None:
    """Open `path` in the system file manager (tray balloon click). Never raises."""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def _notify_data_dir_fallback(tray: TrayManager) -> None:
    """Tell the user, once per install, that the app cannot write next to itself.

    Shown only when config.FALLBACK_DATA_DIR is set (an AppImage, or any
    read-only location). When a database is already sitting at the old
    portable path, that path is named explicitly: silently starting on an
    empty database would look exactly like losing every word the user has.

    Reuses the existing update balloon — the app is architected never to steal
    focus, so no new UI is built here. The marker in LOGS_DIR (which is by
    definition writable at this point) keeps it to one balloon per install
    rather than one per launch. Never raises.
    """
    try:
        target = config.FALLBACK_DATA_DIR
        if target is None:
            return
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        marker = LOGS_DIR / config.DATA_DIR_NOTICE_MARKER
        if marker.exists():
            return

        old_db = Path(sys.executable).parent / "data" / "lang_trainer.db"
        message = (
            "LangTrainer cannot write next to the executable, so your words, "
            "logs and dictionaries now live in:\n"
            f"{target}"
        )
        if config.PORTABLE_DATA_EXISTS:
            message += (
                "\n\nYour existing database is still at:\n"
                f"{old_db}\n"
                f"Copy it to {target / 'data'} to keep your words."
            )
        _show_update_balloon(
            tray, APP_NAME, message, lambda: _open_data_folder(Path(target)),
        )
        marker.write_text(
            f"{config.APP_VERSION}\n{target}\n", encoding="utf-8",
        )
    except Exception:
        pass


def _run_update_flow(app: QApplication, db: DatabaseManager, tray: TrayManager,
                     main_window: MainWindow, timer_service: TimerService,
                     force: bool) -> None:
    """Check for an update and, if there is one, offer to install it.

    Never blocks: it is entered from a one-shot QTimer, uses an 8 s network
    timeout, and runs no worker thread (a QThread would hit the SQLite
    check_same_thread=True landmine in db_manager.py:57).

    Args:
        app: The running QApplication.
        db: Open database manager, used to close cleanly before a restart.
        tray: Tray manager, used for the balloon.
        main_window: Parent for the dialogs and the progress bar.
        timer_service: Stopped before the restart so no tick outlives the DB.
        force: True for the explicit tray-menu path, which bypasses both the
            24 h throttle and the "never" opt-out.
    """
    state = LOGS_DIR / updater.STATE_FILENAME
    if updater.load_state(state).get("disabled") and not force:
        return
    if updater.update_disabled(Path(sys.executable).parent):
        return
    if not force and not updater.should_check(state):
        return
    release = updater.fetch_latest_release(config.APP_VERSION)
    if release is None:
        # Dead network or no release published yet: completely silent, but the
        # timestamp is still recorded so a user on a plane does not retry on
        # every launch.
        updater.record_check(state)
        return
    # Recorded BEFORE any UI, so dismissing the prompt does not re-prompt on the
    # next launch.
    updater.record_check(state)
    asset = updater.select_asset(release.get("assets", []), updater.platform_asset_key())
    if asset is None:
        return
    _offer_update(app, db, tray, main_window, timer_service, release, asset, force)


def _offer_update(app: QApplication, db: DatabaseManager, tray: TrayManager,
                  main_window: MainWindow, timer_service: TimerService,
                  release: dict, asset: dict, force: bool) -> None:
    """Present an available update and run the download when accepted."""
    version = str(release.get("tag_name") or "")
    size = int(asset.get("size") or 0)

    if not updater.self_install_supported():
        # macOS / Linux: notify and open the Releases page. No download and no
        # self-install — a .app is a directory bundle os.replace cannot replace.
        _show_update_balloon(
            tray, APP_NAME,
            f"LangTrainer {version} is available — click to open the download page.",
            lambda: QDesktopServices.openUrl(QUrl(updater.release_page_url())),
        )
        return

    def _prompt_and_install() -> None:
        dialog = UpdateAvailableDialog(version, size, main_window)
        dialog.exec()
        if dialog.choice != "download":
            return  # "never" has already been persisted by the dialog itself
        _install_update(app, db, tray, main_window, timer_service, release, asset, version)

    if force:
        # Explicit tray-menu path: the user asked, so skip the balloon.
        _prompt_and_install()
        return
    _show_update_balloon(
        tray, APP_NAME,
        f"LangTrainer {version} is available — click to download",
        _prompt_and_install,
    )


def _install_update(app: QApplication, db: DatabaseManager, tray: TrayManager,
                    main_window: MainWindow, timer_service: TimerService,
                    release: dict, asset: dict, version: str) -> None:
    """Download, verify and stage the update, then restart into it.

    Args:
        release: The GitHub release object.
        asset: The asset dict selected for this platform.
        version: The release tag, shown in the dialogs.
    """
    global _download_in_progress
    if not config._is_frozen():
        # Never self-update a dev checkout: sys.executable is the interpreter.
        QMessageBox.information(
            main_window, APP_NAME,
            "Self-update is only available in the packaged app.",
        )
        return
    if _download_in_progress:
        return
    _download_in_progress = True
    try:
        exe_dir = Path(sys.executable).parent
        base = updater.exe_name()
        part = exe_dir / (base + ".part")
        dest = exe_dir / (base + ".new")
        nonce_file = exe_dir / (base + ".nonce")

        progress = QProgressDialog("Downloading update…", "Cancel", 0, 100, main_window)
        progress.setWindowTitle(APP_NAME)
        progress.setWindowModality(Qt.WindowModal)
        progress.setAutoClose(False)
        progress.setAutoReset(False)

        def _on_progress(downloaded: int, total: int) -> None:
            """Advance the bar and keep the UI responsive (main-thread download)."""
            progress.setValue(int(downloaded * 100 / total) if total > 0 else 0)
            app.processEvents()

        ok = updater.http_download(
            asset.get("browser_download_url", ""), part, progress=_on_progress,
        )
        cancelled = progress.wasCanceled()
        progress.close()
        if not ok:
            return
        if cancelled:
            # Nothing is installed and no partial file is left behind.
            _discard(part)
            return

        good, reason = updater.verify_digest(part, asset)
        if not good:
            # Never leave a bad file next to the executable.
            _discard(part)
            QMessageBox.critical(main_window, "Update failed", reason)
            return

        os.replace(part, dest)
        nonce = secrets.token_hex(16)
        nonce_file.write_text(nonce, encoding="utf-8")

        # A restart loses an in-flight game run, so offer "Later" instead while
        # a game widget is open.
        game_open = getattr(main_window, "_current_game_widget", None) is not None
        dialog = RestartConfirmDialog(
            version, restart_enabled=not game_open, parent=main_window,
        )
        dialog.exec()
        if dialog.choice != "restart":
            return  # the .new file stays staged for the next attempt

        timer_service.stop()
        tray.cleanup()
        db.disconnect()
        app.quit()
        # Never returns: the process must free its own image for the swap.
        updater.relaunch_for_update(os.getpid(), nonce)
    finally:
        _download_in_progress = False


def _discard(path: Path) -> None:
    """Delete a partial or rejected download, ignoring failures."""
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


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
    tray.quit_requested.connect(lambda: _quit_app(app, db, tray, timer_service))
    
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

    # Tray menu entries
    tray.open_logs_requested.connect(_open_logs_folder)
    tray.check_updates_requested.connect(
        lambda: _run_update_flow(app, db, tray, main_window, timer_service, force=True)
    )

    # Update check: one-shot, 24 h throttle, non-blocking, after the tray exists
    # so the balloon has an icon to hang off.
    QTimer.singleShot(
        1500,
        lambda: _run_update_flow(app, db, tray, main_window, timer_service, force=False),
    )

    # Data-location notice: only fires when the app had to leave the portable
    # path (AppImage / read-only directory), and only once per install. Staggered
    # past the update check so the two balloons never stack.
    QTimer.singleShot(2500, lambda: _notify_data_dir_fallback(tray))
    
    # Run application
    exit_code = app.exec()
    
    # Cleanup — stop the timer BEFORE closing the DB: a 1 s tick landing after
    # disconnect raises ProgrammingError inside a console-less app (bug B6).
    timer_service.stop()
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

def _quit_app(app: QApplication, db: DatabaseManager, tray: TrayManager,
              timer_service: TimerService):
    """Clean shutdown of the application."""
    tray.cleanup()
    # Stop the timer before closing the DB (bug B6): a late tick would hit a
    # closed connection and fail invisibly in a console-less build.
    timer_service.stop()
    db.disconnect()
    app.quit()

def _log_startup_warning(message: str) -> None:
    """Record a non-fatal startup problem in the crash log. Never raises."""
    _append_crash_log(f"\n{'=' * 70}\nSTARTUP WARNING: {message}\n{'=' * 70}\n")


def _acquire_single_instance() -> QLockFile | None:
    """Take the single-instance lock, or return None if another instance holds it.

    Without this a second launch is a fully functional invisible duplicate: two
    tray icons, two popup timers and two writers on one SQLite file.
    """
    # QLockFile cannot create its own parent directory: without this mkdir the
    # very first launch on a clean install fails to take the lock and the app
    # silently refuses to start.
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass  # Unusable logs/ -> the tryLock below fails cleanly, no crash.

    lock = QLockFile(str(LOGS_DIR / "langtrainer.lock"))
    # 0 disables time-based expiry; the built-in PID liveness check still reclaims
    # a lock left behind by a power cut.
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        return None
    return lock


def _bootstrap() -> None:
    """Guarded startup: recover, extract, single-instance, then run main().

    A crash here used to be invisible in a console-less build (bug B7). Every
    failure is logged to logs/langtrainer-crash.log and reported in a QMessageBox.
    """
    # 1. Recover a half-finished self-update.
    try:
        updater.self_heal(Path(sys.executable).parent)
    except Exception as exc:
        _log_startup_warning(f"self_heal failed: {exc}")

    # 2. Completer mode runs BEFORE the lock: the process being replaced holds it.
    if "--complete-update" in sys.argv:
        try:
            pid = 0
            if "--pid" in sys.argv:
                pid = int(sys.argv[sys.argv.index("--pid") + 1])
            nonce = ""
            if "--nonce" in sys.argv:
                nonce = sys.argv[sys.argv.index("--nonce") + 1]
            sys.exit(updater.complete_update(pid, nonce))
        except (IndexError, ValueError):
            _log_startup_warning("--complete-update given without a valid --pid/--nonce")
            sys.exit(2)

    # 3. Extract bundled dictionaries next to the executable.
    try:
        ok, dics_path = ensure_dics_extracted()
    except Exception as exc:
        ok, dics_path = False, str(exc)
    if not ok:
        _log_startup_warning(f"Dictionaries not available at {dics_path}")

    # 4. Single instance.
    lock = _acquire_single_instance()
    if lock is None:
        _log_startup_warning("Another LangTrainer instance is already running — exiting")
        return

    # 5-9. Run, and turn any startup failure into a visible dialog.
    try:
        main()
    except SystemExit:
        raise
    except BaseException as exc:
        # 6. Go through the installed excepthook so the crash reaches
        # logs/langtrainer-crash.log. (traceback.print_exc() only writes to
        # stderr and never invokes sys.excepthook, so it would log nothing.)
        sys.excepthook(*sys.exc_info())
        try:
            # 7. Imported here so an import-time failure cannot break startup.
            from PySide6.QtWidgets import QMessageBox
            # 8.
            QMessageBox.critical(
                None,
                f"{APP_NAME} could not start",
                f"{type(exc).__name__}: {exc}\n\n"
                f"Details were written to:\n"
                f"{LOGS_DIR / 'langtrainer-crash.log'}\n\n"
                f"Please report this — the details above will help.",
            )
        except Exception:
            pass
        # 9.
        sys.exit(1)


if __name__ == "__main__":
    _bootstrap()
