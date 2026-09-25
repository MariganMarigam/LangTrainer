"""Dialog for importing words from txt/csv files with iOS-inspired design."""
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QGroupBox, QListWidget,
    QListWidgetItem,
)
from database.db_manager import DatabaseManager
from ui.styles import (
    Colors, Fonts, pill_button_style, card_style, label_style,
    destructive_button_style,
)
from config import DICS_DIR


def _default_word_file_dir(dics_dir: Path) -> Path:
    """Return the folder the import dialog should open in."""
    return dics_dir if list(dics_dir.glob("*.txt")) else Path.home()


class AddWordsDialog(QDialog):
    """Dialog for adding words from files or manual input."""

    words_added = Signal(int, int)  # added_count, skipped_count

    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self._pending_words: list[tuple[str, str]] = []
        self._setWindowFlags()
        self._build_ui()
        self.setMinimumSize(600, 450)

    def _setWindowFlags(self) -> None:
        """Setup window flags — override title bar."""
        self.setWindowTitle("Add Words")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

    def _build_ui(self) -> None:
        """Build the dialog interface with iOS-inspired styling."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        # ── Title ──────────────────────────────────────────────────────────
        title = QLabel("Add New Words to Your Vocabulary")
        title.setStyleSheet(f"color: {Colors.BLUE}; {Fonts.TITLE_2} padding: 4px;")
        layout.addWidget(title)

        # ── Instructions ───────────────────────────────────────────────────
        info = QLabel(
            "Import words from a .txt or .csv file.\n"
            "Format: <strong>foreign_word,translation</strong> (one per line)\n"
            "Example: <em>big,большой</em>"
        )
        info.setStyleSheet(label_style(Fonts.FOOTNOTE, Colors.SECONDARY_LABEL))
        info.setWordWrap(True)
        layout.addWidget(info)

        # ── Select File button ─────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        self._import_btn = QPushButton("Select File (txt/csv)")
        self._import_btn.setStyleSheet(pill_button_style(Colors.BLUE))
        self._import_btn.clicked.connect(self._select_file)
        btn_layout.addWidget(self._import_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # ── Preview section — iOS grouped card ─────────────────────────────
        preview_group = QGroupBox("Preview")
        preview_group.setStyleSheet(f"""
            QGroupBox {{
                border: none; border-radius: 14px;
                margin-top: 8px; padding: 12px 8px 8px 8px;
                background-color: {Colors.CARD_BG};
                color: {Colors.PRIMARY_LABEL};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px; top: -6px;
                padding: 0 6px;
                color: {Colors.SECONDARY_LABEL};
                {Fonts.FOOTNOTE}
                font-weight: semibold;
            }}
        """)
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(4, 10, 4, 4)

        self._preview_list = QListWidget()
        self._preview_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {Colors.CARD_BG};
                color: {Colors.PRIMARY_LABEL};
                border: 1px solid {Colors.SEPARATOR};
                border-radius: 10px;
                padding: 4px;
                {Fonts.BODY}
            }}
            QListWidget::item {{
                padding: 6px 8px;
                border-bottom: 1px solid {Colors.SEPARATOR};
            }}
            QListWidget::item:last {{
                border-bottom: none;
            }}
            QListWidget::item:hover {{
                background-color: {Colors.CARD_BG_ALT};
            }}
        """)
        preview_layout.addWidget(self._preview_list)
        layout.addWidget(preview_group)

        # ── Stats label ────────────────────────────────────────────────────
        self._stats_label = QLabel("No words loaded yet.")
        self._stats_label.setStyleSheet(
            label_style(Fonts.FOOTNOTE, Colors.SECONDARY_LABEL)
        )
        layout.addWidget(self._stats_label)

        # ── Action buttons ─────────────────────────────────────────────────
        action_layout = QHBoxLayout()
        action_layout.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setStyleSheet(
            pill_button_style(
                Colors.CARD_BG_ALT,
                border=f"1px solid {Colors.SEPARATOR}",
            )
        )
        self._cancel_btn.clicked.connect(self.reject)
        action_layout.addWidget(self._cancel_btn)

        self._add_btn = QPushButton("Add to Database")
        self._add_btn.setEnabled(False)
        self._add_btn.setStyleSheet(pill_button_style(Colors.GREEN))
        self._add_btn.clicked.connect(self._add_words)
        action_layout.addWidget(self._add_btn)

        layout.addLayout(action_layout)

    def _select_file(self) -> None:
        """Open file dialog and parse the selected file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Word File", str(_default_word_file_dir(DICS_DIR)),
            "Word Files (*.txt *.csv);;Text Files (*.txt);;CSV Files (*.csv);;All Files (*)"
        )
        if not file_path:
            return

        self._pending_words = []
        self._preview_list.clear()

        try:
            words = self._parse_file(file_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to parse file:\n{str(e)}")
            return

        # Check for duplicates against the database
        duplicates: list[str] = []
        for word, translation in words:
            if self.db.word_exists(word):
                duplicates.append(word)
            else:
                self._pending_words.append((word, translation))
                item = QListWidgetItem(f"{word}  \u2192  {translation}")
                self._preview_list.addItem(item)

        # Show results
        total = len(words)
        skipped = len(duplicates)
        added = len(self._pending_words)

        if duplicates:
            dup_text = "\n".join(f"\u2022 {w}" for w in duplicates[:10])
            more = (
                f"\n... and {len(duplicates) - 10} more"
                if len(duplicates) > 10
                else ""
            )
            QMessageBox.warning(
                self, "Duplicates Found",
                f"The following words already exist in the database:\n"
                f"{dup_text}{more}\n\n"
                f"They were excluded. Only new words will be added.",
            )

        self._stats_label.setText(
            f"Total in file: {total}  |  "
            f"New: <b style='color:{Colors.GREEN}'>{added}</b>  |  "
            f"Skipped (duplicates): <b style='color:{Colors.RED}'>{skipped}</b>"
        )
        self._stats_label.setTextFormat(Qt.RichText)

        self._add_btn.setEnabled(added > 0)

    def _parse_file(self, file_path: str) -> list[tuple[str, str]]:
        """Parse a txt/csv file and return list of (word, translation) tuples.

        Expected format: one word per line, comma-separated:
        foreign_word,translation

        Args:
            file_path: Path to the file to parse.

        Returns:
            List of (word, translation) tuples parsed from the file.

        Raises:
            FileNotFoundError: If the file does not exist.
            UnicodeDecodeError: If the file cannot be decoded as UTF-8.
        """
        result: list[tuple[str, str]] = []
        path = Path(file_path)

        with open(path, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                if "," in line:
                    parts = line.split(",", 1)
                    word = parts[0].strip()
                    translation = parts[1].strip()
                    if word and translation:
                        result.append((word, translation))

        return result

    def _add_words(self) -> None:
        """Add the pending words to the database."""
        if not self._pending_words:
            return

        stats = self.db.add_words_batch(self._pending_words)

        QMessageBox.information(
            self, "Success",
            f"<b>{stats['added']}</b> words added successfully!\n"
            f"Total words in database: <b>{self.db.get_word_count()}</b>",
        )

        self.words_added.emit(stats["added"], stats["duplicates"])
        self.accept()
