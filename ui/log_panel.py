from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)
from ui.lang import L

_LEVEL_COLORS = {
    "info":    "#465070",
    "warning": "#b45309",
    "error":   "#b91c1c",
    "success": "#166534",
}
_LEVEL_PREFIX = {
    "info":    "·",
    "warning": "!",
    "error":   "✕",
    "success": "✓",
}


class LogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumHeight(180)
        self.setMinimumHeight(110)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(30)
        header.setStyleSheet(
            "background: #f6f7f9; border-top: 1px solid #e3e5ec;"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 0, 8, 0)

        self._title = QLabel("Log")
        self._title.setStyleSheet(
            "color: #6b7291; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;"
        )
        h_layout.addWidget(self._title)
        h_layout.addStretch()

        self._clear_btn = QPushButton(L().t("btn_clear"))
        self._clear_btn.setFixedHeight(20)
        self._clear_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #939ab0; font-size: 10px; border: none; padding: 0 6px; }"
            "QPushButton:hover { color: #2f8f6b; }"
        )
        self._clear_btn.clicked.connect(self.clear)
        h_layout.addWidget(self._clear_btn)

        root.addWidget(header)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setStyleSheet(
            "QTextEdit {"
            "  background: #fafbfd;"
            "  color: #2e3552;"
            "  font-family: Consolas, 'Courier New', monospace;"
            "  font-size: 11px;"
            "  border: none;"
            "  border-left: 1px solid #e3e5ec;"
            "  border-right: 1px solid #e3e5ec;"
            "  border-bottom: 1px solid #e3e5ec;"
            "  padding: 4px 8px;"
            "}"
        )
        root.addWidget(self._text)

    def retranslate(self) -> None:
        self._title.setText("Log")
        self._clear_btn.setText(L().t("btn_clear"))

    @pyqtSlot(str, str)
    def append(self, message: str, level: str = "info") -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = _LEVEL_COLORS.get(level, "#465070")
        prefix = _LEVEL_PREFIX.get(level, "·")

        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        ts_fmt = QTextCharFormat()
        ts_fmt.setForeground(QColor("#939ab0"))
        cursor.insertText(f"[{timestamp}] ", ts_fmt)

        msg_fmt = QTextCharFormat()
        msg_fmt.setForeground(QColor(color))
        cursor.insertText(f"{prefix} {message}\n", msg_fmt)

        self._text.setTextCursor(cursor)
        self._text.ensureCursorVisible()

    def clear(self) -> None:
        self._text.clear()
