from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)
from ui.components.language_toggle import LanguageToggle
from ui.lang import L

_NAV_KEYS = [
    ("dashboard", "nav_dashboard"),
    ("invoices",  "nav_invoices"),
    ("export",    "nav_export"),
]

_BTN_ACTIVE = """
    QPushButton {
        text-align: left; padding: 7px 9px; margin: 1px 0px;
        border: 1px solid rgba(47,143,107,0.22); border-radius: 8px;
        font-size: 13px; font-weight: 600;
        color: #1a6b4f; background: rgba(47,143,107,0.08);
    }
    QPushButton:hover { background: rgba(47,143,107,0.13); }
"""
_BTN_INACTIVE = """
    QPushButton {
        text-align: left; padding: 7px 9px; margin: 1px 0px;
        border: 1px solid transparent; border-radius: 8px;
        font-size: 13px; font-weight: 600;
        color: #6b7291; background: #f4f5f8;
    }
    QPushButton:hover { background: #eeeff3; color: #2e3552; }
"""


class Sidebar(QWidget):
    page_changed       = pyqtSignal(str)
    language_changed   = pyqtSignal(str)
    settings_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(234)
        self.setObjectName("Sidebar")
        self.setStyleSheet(
            "QWidget#Sidebar { background: #f4f5f8; border-right: 1px solid #e3e5ec; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 0, 12, 0)
        root.setSpacing(0)

        # Brand / logo
        logo_frame = QWidget()
        logo_frame.setStyleSheet("background: transparent;")
        logo_frame.setFixedHeight(64)
        ll = QHBoxLayout(logo_frame)
        ll.setContentsMargins(4, 14, 4, 10)
        ll.setSpacing(10)

        brand_mark = QLabel("A")
        brand_mark.setFixedSize(30, 30)
        brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_mark.setStyleSheet(
            "QLabel {"
            "  background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "    stop:0 #2f8f6b, stop:1 #1e7558);"
            "  border-radius: 8px;"
            "  color: white;"
            "  font-size: 14px;"
            "  font-weight: bold;"
            "}"
        )

        brand_texts = QWidget()
        brand_texts.setStyleSheet("background: transparent;")
        bt_layout = QVBoxLayout(brand_texts)
        bt_layout.setContentsMargins(0, 0, 0, 0)
        bt_layout.setSpacing(0)
        self._logo_title = QLabel("Analyzen")
        self._logo_title.setStyleSheet(
            "color: #2e3552; font-size: 15px; font-weight: 800; letter-spacing: -0.01em;"
        )
        self._logo_sub = QLabel("Invoice Reader")
        self._logo_sub.setStyleSheet("color: #939ab0; font-size: 11px; margin-top: -1px;")
        bt_layout.addWidget(self._logo_title)
        bt_layout.addWidget(self._logo_sub)

        ll.addWidget(brand_mark)
        ll.addWidget(brand_texts)
        ll.addStretch()
        root.addWidget(logo_frame)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background: #e3e5ec; max-height: 1px; margin: 0;")
        root.addWidget(sep)
        root.addSpacing(8)

        # Nav buttons
        self._nav_buttons: dict[str, QPushButton] = {}
        for key, lang_key in _NAV_KEYS:
            btn = QPushButton(L().t(lang_key))
            btn.setStyleSheet(_BTN_INACTIVE)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, k=key: self._on_nav(k))
            self._nav_buttons[key] = btn
            root.addWidget(btn)

        root.addStretch(1)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("background: #e3e5ec; max-height: 1px; margin: 0;")
        root.addWidget(sep2)
        root.addSpacing(4)

        self._settings_btn = QPushButton(L().t("nav_settings"))
        self._settings_btn.setStyleSheet(_BTN_INACTIVE)
        self._settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_btn.clicked.connect(self.settings_requested)
        root.addWidget(self._settings_btn)

        lang_container = QWidget()
        lang_container.setStyleSheet("background: transparent;")
        lc_layout = QVBoxLayout(lang_container)
        lc_layout.setContentsMargins(4, 6, 4, 14)
        self._lang_toggle = LanguageToggle(current=L().code)
        self._lang_toggle.language_changed.connect(self.language_changed)
        lc_layout.addWidget(self._lang_toggle)
        root.addWidget(lang_container)

        self._active = "dashboard"
        self._nav_buttons["dashboard"].setStyleSheet(_BTN_ACTIVE)

    def _on_nav(self, key: str) -> None:
        if key == self._active:
            return
        self._nav_buttons[self._active].setStyleSheet(_BTN_INACTIVE)
        self._active = key
        self._nav_buttons[key].setStyleSheet(_BTN_ACTIVE)
        self.page_changed.emit(key)

    def set_active(self, key: str) -> None:
        self._on_nav(key)

    def set_language(self, lang: str) -> None:
        self._lang_toggle._select(lang, emit=False)

    def get_language(self) -> str:
        return self._lang_toggle.current()

    def retranslate(self) -> None:
        for key, lang_key in _NAV_KEYS:
            self._nav_buttons[key].setText(L().t(lang_key))
        self._settings_btn.setText(L().t("nav_settings"))
