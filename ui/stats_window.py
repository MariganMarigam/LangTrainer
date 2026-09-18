"""Statistics window showing word list with performance metrics."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
)
from database.db_manager import DatabaseManager
from ui.styles import Colors, Fonts, pill_button_style, card_style, label_style, progress_label_style, score_label_style


class StatsWindow(QDialog):
    """Window displaying all words with their statistics."""

    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self._build_ui()
        self._load_data()
        self.setMinimumSize(700, 500)

    def _build_ui(self):
        """Build the statistics interface."""
        self.setWindowTitle(" Word Statistics")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 16, 20, 16)

        # ── Summary bar ────────────────────────────────────────────────
        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(8)

        # Total badge (iOS pill)
        self._total_label = QLabel("Total: 0")
        _badge = pill_button_style(Colors.BLUE, height="24px", font_size="11px")
        _badge = _badge.replace("QPushButton", "QLabel").replace("padding: 6px 20px;", "padding: 2px 10px;")
        self._total_label.setStyleSheet(_badge)
        summary_layout.addWidget(self._total_label)

        # Mastered badge (iOS pill)
        self._mastered_label = QLabel("Mastered: 0")
        _badge = pill_button_style(Colors.GREEN, height="24px", font_size="11px")
        _badge = _badge.replace("QPushButton", "QLabel").replace("padding: 6px 20px;", "padding: 2px 10px;")
        self._mastered_label.setStyleSheet(_badge)
        summary_layout.addWidget(self._mastered_label)

        # Learning badge (iOS pill)
        self._learning_label = QLabel("Learning: 0")
        _badge = pill_button_style(Colors.ORANGE, height="24px", font_size="11px")
        _badge = _badge.replace("QPushButton", "QLabel").replace("padding: 6px 20px;", "padding: 2px 10px;")
        self._learning_label.setStyleSheet(_badge)
        summary_layout.addWidget(self._learning_label)

        # New badge (iOS pill)
        self._new_label = QLabel("New: 0")
        _badge = pill_button_style(Colors.CARD_BG_ALT, height="24px", font_size="11px")
        _badge = _badge.replace("QPushButton", "QLabel").replace("padding: 6px 20px;", "padding: 2px 10px;")
        self._new_label.setStyleSheet(_badge)
        summary_layout.addWidget(self._new_label)

        summary_layout.addStretch()

        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setStyleSheet(
            pill_button_style(Colors.CARD_BG_ALT, border=f"1px solid {Colors.SEPARATOR}")
        )
        refresh_btn.clicked.connect(self._load_data)
        summary_layout.addWidget(refresh_btn)

        layout.addLayout(summary_layout)

        # ── Table ──────────────────────────────────────────────────────
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels([
            "Word", "Translation", "Correct", "Incorrect",
            "Total", "Success Rate"
        ])

        self._table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Colors.CARD_BG}; color: {Colors.PRIMARY_LABEL};
                gridline-color: {Colors.SEPARATOR};
                border: 1px solid {Colors.SEPARATOR}; border-radius: 10px;
                alternate-background-color: {Colors.SYSTEM_BG};
            }}
            QTableWidget::item {{
                padding: 4px 6px;
            }}
            QHeaderView::section {{
                background-color: {Colors.CARD_BG_ALT}; color: {Colors.SECONDARY_LABEL};
                font-weight: semibold; padding: 8px;
                border: none; border-right: 1px solid {Colors.SEPARATOR};
            }}
        """)

        # Set column widths
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)

        layout.addWidget(self._table)

        # ── Close button ───────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(
            pill_button_style(Colors.CARD_BG_ALT, border=f"1px solid {Colors.SEPARATOR}")
        )
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _load_data(self):
        """Load data from database and populate table."""
        words = self.db.get_all_words()

        # Update summary
        total = len(words)
        mastered = sum(1 for w in words if w.is_mastered)
        learning = sum(1 for w in words if not w.is_mastered and w.total_attempts > 0)
        new_words = sum(1 for w in words if w.total_attempts == 0)

        self._total_label.setText(f"📚 Total: {total}")
        self._mastered_label.setText(f"✅ Mastered: {mastered}")
        self._learning_label.setText(f"📖 Learning: {learning}")
        self._new_label.setText(f"🆕 New: {new_words}")

        # Populate table
        self._table.setRowCount(len(words))

        for row, word in enumerate(words):
            # Word
            word_item = QTableWidgetItem(word.word)
            word_item.setToolTip(f"ID: {word.id}")
            self._table.setItem(row, 0, word_item)

            # Translation
            self._table.setItem(row, 1, QTableWidgetItem(word.translation))

            # Correct count
            correct_item = QTableWidgetItem(str(word.correct_count))
            correct_item.setTextAlignment(Qt.AlignCenter)
            correct_item.setForeground(
                QColor(Colors.GREEN) if word.correct_count > 0 else QColor(Colors.TERTIARY_LABEL)
            )
            self._table.setItem(row, 2, correct_item)

            # Incorrect count
            incorrect_item = QTableWidgetItem(str(word.incorrect_count))
            incorrect_item.setTextAlignment(Qt.AlignCenter)
            incorrect_item.setForeground(
                QColor(Colors.RED) if word.incorrect_count > 0 else QColor(Colors.TERTIARY_LABEL)
            )
            self._table.setItem(row, 3, incorrect_item)

            # Total
            total_item = QTableWidgetItem(str(word.total_attempts))
            total_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 4, total_item)

            # Success rate (percentage)
            pct = word.success_rate * 100 if word.total_attempts > 0 else 0
            rate_item = QTableWidgetItem(f"{pct:.0f}%")
            rate_item.setTextAlignment(Qt.AlignCenter)

            if word.total_attempts == 0:
                rate_item.setForeground(QColor(Colors.TERTIARY_LABEL))  # gray for new words
            elif pct >= 80:
                rate_item.setForeground(QColor(Colors.GREEN))  # green
            elif pct >= 50:
                rate_item.setForeground(QColor(Colors.ORANGE))  # orange
            else:
                rate_item.setForeground(QColor(Colors.RED))  # red

            self._table.setItem(row, 5, rate_item)

        self._table.resizeRowsToContents()
