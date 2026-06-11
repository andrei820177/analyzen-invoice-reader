"""
Slide-in detail drawer for reviewing and correcting a single invoice.

Mirrors the .drawer / .field / .conf / .inp concept in design/reference.html:
each editable field carries a confidence badge (flagged "low" when the value
is missing), invoice flags are shown as badges, and Save emits the edited
values back to the data layer.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)
from ui.components.widgets import NoScrollComboBox
from ui.lang import L
from ui.theme import C

_INK     = C("ink")
_MUTED   = C("ink3")
_FAINT   = C("ink4")
_LINE    = C("line")
_SURFACE = C("surface")
_ACCENT  = C("accent")

_CURRENCIES = ["RON", "EUR", "USD", "GBP", "CHF", "PLN", "CZK", "HUF",
               "SEK", "NOK", "DKK", "CAD", "JPY", "RUB"]

_INP = (
    "QLineEdit,QComboBox{"
    f"background:{C('surface')};border:1px solid {C('line')};border-radius:8px;"
    f"padding:6px 9px;font-size:13px;color:{C('ink')};}}"
    f"QLineEdit:focus,QComboBox:focus{{border-color:{C('accent')};}}"
    "QComboBox::drop-down{border:none;}"
    f"QComboBox QAbstractItemView{{background:{C('surface')};color:{C('ink')};"
    f"border:1px solid {C('line')};selection-background-color:{C('sel')};"
    f"selection-color:{C('accent_ink')};}}"
)

# editable fields: (data_key, i18n_label_key, kind)
_FIELDS = [
    ("supplier_name",  "col_supplier",   "text"),
    ("supplier_cui",   "label_cui",      "text"),
    ("invoice_number", "col_invoice_no", "text"),
    ("issue_date",     "col_date",       "date"),
    ("due_date",       "col_due_date",   "date"),
    ("subtotal",       "label_subtotal", "num"),
    ("vat_amount",     "col_vat",        "num"),
    ("total",          "col_total",      "num"),
    ("currency",       "col_currency",   "currency"),
    ("category",       "col_category",   "text"),
]

# fields whose emptiness marks the row low-confidence
_REQUIRED = {"supplier_name", "invoice_number", "issue_date", "total"}


def _parse_date(text: str) -> Optional[date]:
    text = (text or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            from datetime import datetime
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


class DetailDrawer(QFrame):
    saved  = pyqtSignal(dict)   # {file_path, ...edited fields...}
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._target_w = 360
        # start collapsed; open_with()/close_panel() animate the width
        self.setMinimumWidth(0)
        self.setMaximumWidth(0)
        self._anim: QPropertyAnimation | None = None
        self.setStyleSheet(
            f"DetailDrawer {{ background: {_SURFACE}; border-left: 1px solid {_LINE}; }}"
        )
        self._file_path = ""
        self._inputs: dict[str, QWidget] = {}
        self._badges: dict[str, QLabel] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        head = QWidget()
        head.setStyleSheet(f"background: {_SURFACE}; border-bottom: 1px solid {_LINE};")
        hl = QVBoxLayout(head)
        hl.setContentsMargins(16, 14, 12, 12)
        hl.setSpacing(2)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        self._file_lbl = QLabel("")
        self._file_lbl.setStyleSheet(
            f"color: {_FAINT}; font-size: 11px; background: transparent;"
        )
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            f"QPushButton {{ background: {_SURFACE}; color: {_MUTED};"
            f" border: 1px solid {_LINE}; border-radius: 7px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {C('surface3')}; color: {C('ink')}; }}"
        )
        close_btn.clicked.connect(self.closed)
        top.addWidget(self._file_lbl)
        top.addStretch()
        top.addWidget(close_btn)
        hl.addLayout(top)

        self._vendor_lbl = QLabel("")
        self._vendor_lbl.setStyleSheet(
            f"color: {_INK}; font-size: 17px; font-weight: 800;"
            " letter-spacing: -0.01em; background: transparent;"
        )
        self._vendor_lbl.setWordWrap(True)
        hl.addWidget(self._vendor_lbl)

        self._flags_row = QHBoxLayout()
        self._flags_row.setContentsMargins(0, 6, 0, 0)
        self._flags_row.setSpacing(5)
        self._flags_wrap = QWidget()
        self._flags_wrap.setStyleSheet("background: transparent;")
        self._flags_wrap.setLayout(self._flags_row)
        hl.addWidget(self._flags_wrap)

        root.addWidget(head)

        # Body (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        scroll.verticalScrollBar().setSingleStep(12)   # smoother wheel scroll
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        self._form = QVBoxLayout(body)
        self._form.setContentsMargins(16, 14, 16, 14)
        self._form.setSpacing(12)

        for key, label_key, kind in _FIELDS:
            self._form.addWidget(self._make_field(key, label_key, kind))
        self._form.addStretch()

        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # Footer / save
        footer = QWidget()
        footer.setStyleSheet(f"background: {_SURFACE}; border-top: 1px solid {_LINE};")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(16, 10, 16, 12)
        self._save_btn = QPushButton(L().t("btn_save_changes"))
        self._save_btn.setFixedHeight(36)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.setStyleSheet(
            f"QPushButton {{ background: {_ACCENT}; color: white; border: none;"
            " border-radius: 8px; font-size: 13px; font-weight: 700; }}"
            f"QPushButton:hover {{ background: {C('accent_press')}; }}"
        )
        self._save_btn.clicked.connect(self._on_save)
        fl.addWidget(self._save_btn)
        root.addWidget(footer)

    def _make_field(self, key: str, label_key: str, kind: str) -> QWidget:
        wrap = QWidget()
        wrap.setStyleSheet("background: transparent;")
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(5)

        lab_row = QHBoxLayout()
        lab_row.setContentsMargins(0, 0, 0, 0)
        lab = QLabel(L().t(label_key).upper())
        lab.setStyleSheet(
            f"color: {_MUTED}; font-size: 11px; font-weight: 700;"
            " letter-spacing: 0.03em; background: transparent;"
        )
        badge = QLabel("")
        badge.setStyleSheet("background: transparent;")
        self._badges[key] = badge
        lab_row.addWidget(lab)
        lab_row.addStretch()
        lab_row.addWidget(badge)
        v.addLayout(lab_row)

        if kind == "currency":
            inp = NoScrollComboBox()
            inp.addItems(_CURRENCIES)
            inp.setStyleSheet(_INP)
        else:
            inp = QLineEdit()
            inp.setStyleSheet(_INP)
            if kind == "date":
                inp.setPlaceholderText("YYYY-MM-DD")
        self._inputs[key] = inp
        v.addWidget(inp)
        return wrap

    # ------------------------------------------------------------------

    def open_with(self, row: dict) -> None:
        """Load a row and slide the panel open (or just refresh if already open)."""
        self.load(row)
        if self.isVisible() and self.maximumWidth() >= self._target_w:
            return
        self.setVisible(True)
        self._animate(self._target_w)

    def close_panel(self) -> None:
        self._animate(0, hide=True)

    def _animate(self, to: int, hide: bool = False) -> None:
        anim = QPropertyAnimation(self, b"maximumWidth", self)
        anim.setDuration(190)
        anim.setStartValue(self.maximumWidth())
        anim.setEndValue(to)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        if hide:
            anim.finished.connect(lambda: self.setVisible(False))
        anim.start()
        self._anim = anim   # keep a reference so it isn't garbage-collected

    def load(self, row: dict) -> None:
        self._file_path = str(row.get("file_path", ""))
        self._file_lbl.setText(str(row.get("file_name", "")))
        self._vendor_lbl.setText(str(row.get("supplier_name") or L().t("unknown_supplier")))

        for key, _label, kind in _FIELDS:
            val = row.get(key)
            widget = self._inputs[key]
            text = self._fmt(val, kind)
            if isinstance(widget, QComboBox):
                i = widget.findText(text or "RON")
                widget.setCurrentIndex(i if i >= 0 else 0)
            else:
                widget.setText(text)
            self._set_badge(key, val, row)

        self._render_flags(row)

    def _fmt(self, val, kind: str) -> str:
        if val is None or val == "":
            return ""
        if kind == "num":
            try:
                return f"{float(val):.2f}"
            except (TypeError, ValueError):
                return str(val)
        if kind == "date":
            return "" if val is None else str(val)
        return str(val)

    def _set_badge(self, key: str, val, row: dict) -> None:
        badge = self._badges[key]
        empty = val is None or val == "" or (key in {"total"} and not val)
        if key in _REQUIRED and empty:
            badge.setText(L().t("conf_low"))
            badge.setStyleSheet(
                f"background: {C('warn_soft')}; color: {C('warn_ink')}; font-size: 9px;"
                " font-weight: 700; padding: 1px 6px; border-radius: 5px;"
            )
        else:
            badge.setText("")
            badge.setStyleSheet("background: transparent;")

    def _render_flags(self, row: dict) -> None:
        while self._flags_row.count():
            item = self._flags_row.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        flags = []
        if row.get("is_duplicate"):
            flags.append((L().t("flag_duplicate"), C("err_soft"), C("err_ink")))
        if row.get("is_outlier"):
            flags.append((L().t("flag_outlier"), C("warn_soft"), C("warn_ink")))
        if row.get("is_near_due"):
            flags.append((L().t("flag_near_due"), C("warn_soft"), C("warn_ink")))
        if row.get("is_scanned"):
            flags.append((L().t("flag_scanned"), C("surface3"), C("ink2")))
        for text, bg, fg in flags:
            chip = QLabel(text)
            chip.setStyleSheet(
                f"background: {bg}; color: {fg}; font-size: 10px; font-weight: 700;"
                " padding: 2px 8px; border-radius: 6px;"
            )
            self._flags_row.addWidget(chip)
        self._flags_row.addStretch()
        self._flags_wrap.setVisible(bool(flags))

    def _on_save(self) -> None:
        if not self._file_path:
            return
        out: dict = {"file_path": self._file_path}
        for key, _label, kind in _FIELDS:
            widget = self._inputs[key]
            raw = widget.currentText() if isinstance(widget, QComboBox) else widget.text()
            raw = raw.strip()
            if kind == "num":
                try:
                    out[key] = float(raw.replace(",", ".")) if raw else 0.0
                except ValueError:
                    out[key] = 0.0
            elif kind == "date":
                out[key] = _parse_date(raw)
            else:
                out[key] = raw
        self.saved.emit(out)

    def retranslate(self) -> None:
        self._save_btn.setText(L().t("btn_save_changes"))
