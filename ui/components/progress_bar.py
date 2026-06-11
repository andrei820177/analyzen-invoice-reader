from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QWidget

from ui.theme import C


class ProcessingProgressBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(6)
        self._bar.setStyleSheet(f"""
            QProgressBar {{
                background: {C('surface3')};
                border-radius: 3px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: {C('accent')};
                border-radius: 3px;
            }}
        """)

        self._label = QLabel("0 / 0")
        self._label.setStyleSheet(f"color:{C('ink3')};font-size:12px;")
        self._label.setFixedWidth(60)
        self._label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(self._bar, 1)
        layout.addWidget(self._label)

    def set_progress(self, current: int, total: int) -> None:
        if total > 0:
            self._bar.setValue(int(current / total * 100))
        self._label.setText(f"{current} / {total}")

    def reset(self) -> None:
        self._bar.setValue(0)
        self._label.setText("0 / 0")
