from __future__ import annotations

from typing import List, Tuple

from PyQt6.QtCore import pyqtSignal, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)
from ui.assets import logo_mark
from ui.components.language_toggle import LanguageToggle
from ui.lang import L
from ui.theme import C, register_reload

_NAV_KEYS = [
    ("dashboard", "nav_dashboard"),
    ("invoices",  "nav_invoices"),
    ("export",    "nav_export"),
]

def _build_row_styles():
    inactive = (
        "#navrow{background:transparent;border:1px solid transparent;border-radius:8px;}"
        f"#navrow:hover{{background:{C('surface3')};}}"
    )
    active = (
        f"#navrow{{background:{C('surface')};border:1px solid {C('line')};border-radius:8px;}}"
    )
    return inactive, active


_INACTIVE_ROW, _ACTIVE_ROW = _build_row_styles()


def _reload():
    global _INACTIVE_ROW, _ACTIVE_ROW
    _INACTIVE_ROW, _ACTIVE_ROW = _build_row_styles()


register_reload(_reload)


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
        color = C("ink") if self._active else C("ink2")
        self._label.setStyleSheet(
            f"color:{color};font-size:13px;font-weight:600;"
            "background:transparent;border:none;"
        )
        if self._badge.text():
            bg = C("accent_soft") if self._active else C("surface3")
            fg = C("accent_ink") if self._active else C("ink3")
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(7)
        self._counts = (0, 0, 0)
        self._colors = (C("ok"), C("warn"), C("err"))

    def set_counts(self, valid: int, warning: int, error: int) -> None:
        self._counts = (valid, warning, error)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(C("surface3")))
        p.drawRoundedRect(QRectF(rect), 3.5, 3.5)

        total = sum(self._counts)
        if total <= 0:
            return
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), 3.5, 3.5)
        p.setClipPath(path)
        x = 0.0
        w = rect.width()
        for cnt, color in zip(self._counts, self._colors):
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
            f"#sumcard{{background:{C('surface')};border:1px solid {C('line')};border-radius:11px;}}"
        )
        v = QVBoxLayout(self)
        v.setContentsMargins(13, 12, 13, 12)
        v.setSpacing(2)

        self._lab = QLabel(L().t("side_total"))
        self._lab.setStyleSheet(
            f"color:{C('ink3')};font-size:11px;font-weight:600;background:transparent;border:none;"
        )
        self._big = QLabel("0")
        self._big.setStyleSheet(
            f"color:{C('ink')};font-size:20px;font-weight:800;letter-spacing:-0.02em;"
            "background:transparent;border:none;"
        )

        # per-currency breakdown, one row each (code left, full amount right)
        self._rows_wrap = QWidget()
        self._rows_wrap.setStyleSheet("background:transparent;")
        self._rows = QVBoxLayout(self._rows_wrap)
        self._rows.setContentsMargins(0, 8, 0, 2)
        self._rows.setSpacing(3)

        self._bar = _HealthBar()

        v.addWidget(self._lab)
        v.addWidget(self._big)
        v.addWidget(self._rows_wrap)
        v.addWidget(self._bar)

    def set_data(self, total_text: str,
                 chips: List[Tuple[str, str]],
                 health: Tuple[int, int, int]) -> None:
        self._big.setText(total_text)
        while self._rows.count():
            item = self._rows.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for code, amount in chips[:4]:
            row = QWidget()
            row.setStyleSheet("background:transparent;")
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(6)
            code_lbl = QLabel(code)
            code_lbl.setStyleSheet(
                f"color:{C('ink4')};font-size:11px;font-weight:700;"
                "letter-spacing:0.04em;background:transparent;border:none;"
            )
            amt_lbl = QLabel(amount)
            amt_lbl.setStyleSheet(
                f"color:{C('ink')};font-size:11.5px;font-weight:600;"
                "background:transparent;border:none;"
            )
            amt_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            h.addWidget(code_lbl)
            h.addStretch()
            h.addWidget(amt_lbl)
            self._rows.addWidget(row)
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
            f"QWidget#Sidebar {{ background: {C('sidebar')}; border-right: 1px solid {C('line')}; }}"
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

        brand_mark = QLabel()
        brand_mark.setStyleSheet("background: transparent;")
        _mark = QPixmap(logo_mark())
        if not _mark.isNull():
            brand_mark.setPixmap(_mark.scaledToHeight(
                32, Qt.TransformationMode.SmoothTransformation))
        brand_mark.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        brand_texts = QWidget()
        brand_texts.setStyleSheet("background: transparent;")
        bt_layout = QVBoxLayout(brand_texts)
        bt_layout.setContentsMargins(0, 0, 0, 0)
        bt_layout.setSpacing(0)
        self._logo_title = QLabel("Analyzen")
        self._logo_title.setStyleSheet(
            f"color: {C('ink')}; font-size: 15px; font-weight: 800; letter-spacing: -0.01em;"
        )
        self._logo_sub = QLabel("Invoice Reader")
        self._logo_sub.setStyleSheet(f"color: {C('ink4')}; font-size: 11px; margin-top: -1px;")
        bt_layout.addWidget(self._logo_title)
        bt_layout.addWidget(self._logo_sub)

        ll.addWidget(brand_mark)
        ll.addWidget(brand_texts)
        ll.addStretch()
        root.addWidget(logo_frame)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background: {C('line')}; max-height: 1px; margin: 0;")
        root.addWidget(sep)
        root.addSpacing(8)

        # Section header (.side-h in reference)
        self._section_lbl = QLabel("MENU")
        self._section_lbl.setStyleSheet(
            f"color: {C('ink4')}; font-size: 10px; font-weight: 700;"
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
            f"  font-size: 13px; font-weight: 600; color: {C('ink2')}; background: {C('sidebar')};"
            "}"
            f"QPushButton:hover {{ background: {C('surface3')}; color: {C('ink')}; }}"
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

        # nav + summary stay hidden until a file/folder has been processed
        self.set_data_loaded(False)

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

    def set_data_loaded(self, has_data: bool) -> None:
        """Show the menu section + nav rows only once there is data."""
        self._section_lbl.setVisible(has_data)
        for item in self._nav_items.values():
            item.setVisible(has_data)

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
