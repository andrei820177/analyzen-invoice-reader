from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget

from ui.theme import C

_LANGUAGES = [
    ("ro", "Română"),
    ("en", "English"),
    ("de", "Deutsch"),
    ("fr", "Français"),
    ("it", "Italiano"),
    ("es", "Español"),
    ("pt", "Português"),
    ("pl", "Polski"),
    ("ru", "Русский"),
    ("nl", "Nederlands"),
    ("da", "Dansk"),
]


class LanguageToggle(QWidget):
    language_changed = pyqtSignal(str)

    def __init__(self, current: str = "ro", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        lbl = QLabel("Lang:")
        lbl.setStyleSheet(f"color:{C('ink4')};font-size:10px;font-weight:700;background:transparent;")
        layout.addWidget(lbl)

        self._combo = QComboBox()
        self._combo.setStyleSheet(f"""
            QComboBox {{
                background: {C('surface')};
                color: {C('ink')};
                border: 1px solid {C('line')};
                border-radius: 8px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: 600;
                min-width: 100px;
            }}
            QComboBox:focus {{ border-color: {C('accent')}; }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background: {C('surface')};
                color: {C('ink')};
                selection-background-color: {C('sel')};
                selection-color: {C('accent_ink')};
                border: 1px solid {C('line')};
            }}
        """)

        for code, label in _LANGUAGES:
            self._combo.addItem(label, code)

        self._select(current, emit=False)
        self._combo.currentIndexChanged.connect(self._on_changed)
        layout.addWidget(self._combo)

    def _select(self, lang: str, emit: bool = True) -> None:
        for i in range(self._combo.count()):
            if self._combo.itemData(i) == lang:
                self._combo.setCurrentIndex(i)
                break
        if emit:
            self.language_changed.emit(lang)

    def _on_changed(self, _index: int) -> None:
        lang = self._combo.currentData()
        self.language_changed.emit(lang)

    def current(self) -> str:
        return self._combo.currentData() or "ro"
