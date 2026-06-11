from __future__ import annotations

from typing import List, Tuple

from PyQt6.QtCore import pyqtSignal, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath
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

_INACTIVE_ROW = (
    "#navrow{background:transparent;border:1px solid transparent;border-radius:8px;}"
    "#navrow:hover{background:#eceef3;}"
)
_ACTIVE_ROW = (
    "#navrow{background:#fefefe;border:1px solid #e3e5ec;border-radius:8px;}"
)


class _NavItem(QFrame):
    """Clickable sidebar row with an optional count badge (.nav / .nav .ct)."""

    clicked = pyqtSignal(str)

    def __init__(self, key: str, text: str, parent=None):
        super().__init__(parent)
        self._key = key
        self._active = False
        self.setObjectName("navrow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        h = QHBoxLayout(self)
        h.setContentsMargins(10, 7, 9, 7)
        h.setSpacing(8)
        self._label = QLabel(text)
        self._badge = QLabel("")
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.addWidget(self._label)
        h.addStretch()
        h.addWidget(self._badge)

        self._apply()

    def _apply(self) -> None:
        self.setStyleSheet(_ACTIVE_ROW if self._active else _INACTIVE_ROW)
        color = "#2e3552" if self._active else "#5d6480"
        self._label.setStyleSheet(
            f"color:{color};font-size:13px;font-weight:600;"
            "background:transparent;border:none;"
        )
        if self._badge.text():
            bg = "#e6f0eb" if self._active else "#e9ebf1"
            fg = "#1a6b4f" if self._active else "#6b7291"
            self._badge.setStyleSheet(
                f"background:{bg};color:{fg};font-size:11px;font-weight:700;"
                "padding:1px 7px;border-radius:9px;border:none;"
            )
        else:
            self._badge.setStyleSheet("background:transparent;border:none;")

    def set_active(self, active: bool) -> None:
        self._active = active
        self._apply()

    def set_count(self, count: int) -> None:
        self._badge.setText(str(count) if count else "")
        self._apply()

    def set_text(self, text: str) -> None:
        self._label.setText(text)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._key)
        super().mousePressEvent(event)


class _HealthBar(QWidget):
    """Proportional valid/warning/error bar (.bar with ok/w/e segments)."""

    _COLORS = ("#2f8f6b", "#d8a72e", "#e2483a")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(7)
        self._counts = (0, 0, 0)

    def set_counts(self, valid: int, warning: int, error: int) -> None:
        self._counts = (valid, warning, error)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#eceef3"))
        p.drawRoundedRect(QRectF(rect), 3.5, 3.5)

        total = sum(self._counts)
        if total <= 0:
            return
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), 3.5, 3.5)
        p.setClipPath(path)
        x = 0.0
        w = rect.width()
        for cnt, color in zip(self._counts, self._COLORS):
            if cnt <= 0:
                continue
            seg = w * cnt / total
            p.setBrush(QColor(color))
            p.drawRect(int(x), 0, int(seg) + 1, rect.height())
            x += seg


class _SummaryCard(QFrame):
    """Bottom side-card: total value + currency chips + health bar (.side-card)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sumcard")
        self.setStyleSheet(
            "#sumcard{background:#fefefe;border:1px solid #e3e5ec;border-radius:11px;}"
        )
        v = QVBoxLayout(self)
        v.setContentsMargins(13, 12, 13, 12)
        v.setSpacing(2)

        self._lab = QLabel(L().t("side_total"))
        self._lab.setStyleSheet(
            "color:#6b7291;font-size:11px;font-weight:600;background:transparent;border:none;"
        )
        self._big = QLabel("0")
        self._big.setStyleSheet(
            "color:#2e3552;font-size:20px;font-weight:800;letter-spacing:-0.02em;"
            "background:transparent;border:none;"
        )

        self._chips_wrap = QWidget()
        self._chips_wrap.setStyleSheet("background:transparent;")
        self._chips = QHBoxLayout(self._chips_wrap)
        self._chips.setContentsMargins(0, 6, 0, 0)
        self._chips.setSpacing(4)

        self._bar = _HealthBar()

        v.addWidget(self._lab)
        v.addWidget(self._big)
        v.addWidget(self._chips_wrap)
        v.addWidget(self._bar)

    def set_data(self, total_text: str,
                 chips: List[Tuple[str, str]],
                 health: Tuple[int, int, int]) -> None:
        self._big.setText(total_text)
        while self._chips.count():
            item = self._chips.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for code, amount in chips[:3]:
            chip = QLabel(f"{code} {amount}")
            chip.setStyleSheet(
                "background:#f0f1f5;color:#5d6480;font-size:10px;font-weight:700;"
                "padding:2px 6px;border-radius:6px;border:none;"
            )
            self._chips.addWidget(chip)
        self._chips.addStretch()
        self._bar.set_counts(*health)

    def retranslate(self) -> None:
        self._lab.setText(L().t("side_total"))


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

        # Section header (.side-h in reference)
        self._section_lbl = QLabel("MENU")
        self._section_lbl.setStyleSheet(
            "color: #939ab0; font-size: 10px; font-weight: 700;"
            " letter-spacing: 1px; padding: 4px 8px 2px 8px; background: transparent;"
        )
        root.addWidget(self._section_lbl)

        # Nav items
        self._nav_items: dict[str, _NavItem] = {}
        for key, lang_key in _NAV_KEYS:
            item = _NavItem(key, L().t(lang_key))
            item.clicked.connect(self._on_nav)
            self._nav_items[key] = item
            root.addWidget(item)

        root.addStretch(1)

        # Summary side-card
        self._summary = _SummaryCard()
        self._summary.setVisible(False)
        root.addWidget(self._summary)
        root.addSpacing(8)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("background: #e3e5ec; max-height: 1px; margin: 0;")
        root.addWidget(sep2)
        root.addSpacing(4)

        self._settings_btn = QPushButton(L().t("nav_settings"))
        self._settings_btn.setStyleSheet(
            "QPushButton {"
            "  text-align: left; padding: 7px 9px; margin: 1px 0px;"
            "  border: 1px solid transparent; border-radius: 8px;"
            "  font-size: 13px; font-weight: 600; color: #5d6480; background: #f4f5f8;"
            "}"
            "QPushButton:hover { background: #eceef3; color: #2e3552; }"
        )
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
        self._nav_items["dashboard"].set_active(True)

    def _on_nav(self, key: str) -> None:
        if key == self._active:
            return
        self._nav_items[self._active].set_active(False)
        self._active = key
        self._nav_items[key].set_active(True)
        self.page_changed.emit(key)

    def set_active(self, key: str) -> None:
        self._on_nav(key)

    def set_counts(self, counts: dict) -> None:
        for key, item in self._nav_items.items():
            if key in counts:
                item.set_count(int(counts[key]))

    def set_summary(self, total_text: str,
                    chips: list, health: tuple) -> None:
        self._summary.set_data(total_text, chips, health)
        self._summary.setVisible(sum(health) > 0)

    def set_language(self, lang: str) -> None:
        self._lang_toggle._select(lang, emit=False)

    def get_language(self) -> str:
        return self._lang_toggle.current()

    def retranslate(self) -> None:
        for key, lang_key in _NAV_KEYS:
            self._nav_items[key].set_text(L().t(lang_key))
        self._settings_btn.setText(L().t("nav_settings"))
        self._summary.retranslate()
