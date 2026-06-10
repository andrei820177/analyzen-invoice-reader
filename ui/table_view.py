from __future__ import annotations

from typing import Any

import pandas as pd
from PyQt6.QtCore import (
    QAbstractTableModel, QModelIndex, QRect, Qt, QSortFilterProxyModel, pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PyQt6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QStyle, QStyledItemDelegate,
    QTableView, QVBoxLayout, QWidget,
)
from data.processor import row_status
from ui.detail_drawer import DetailDrawer
from ui.lang import L

_COL_DEFS = [
    ("supplier_name",    "col_supplier"),
    ("invoice_number",   "col_invoice_no"),
    ("issue_date",       "col_date"),
    ("due_date",         "col_due_date"),
    ("total",            "col_total"),
    ("currency",         "col_currency"),
    ("vat_amount",       "col_vat"),
    ("category",         "col_category"),
    ("status",           "col_status"),
    ("confidence_score", "col_confidence"),
    ("file_name",        "col_file"),
]

_COL_KEYS   = [c[0] for c in _COL_DEFS]
_COL_I18N   = [c[1] for c in _COL_DEFS]
_COL_IDX    = {k: i for i, k in enumerate(_COL_KEYS)}

# required fields whose emptiness is highlighted red (.empty-val in reference)
_REQUIRED = {"supplier_name", "invoice_number", "issue_date", "total"}

# custom roles
_STATUS_ROLE = Qt.ItemDataRole.UserRole       # status key for the pill delegate
_SORT_ROLE   = Qt.ItemDataRole.UserRole + 1   # numeric/normalized sort key

_EMPTY_RED = QColor("#b3261e")

# soft state tints from reference.html (--err-soft / --warn-soft)
_FLAG_RED    = QColor("#faeae7")
_FLAG_ORANGE = QColor("#f9f0dd")
_FLAG_YELLOW = QColor("#fbf6e4")

_STATUS_RANK = {"error": 0, "warning": 1, "valid": 2}

_FILTER_KEYS = [
    "filter_all", "filter_flagged", "filter_duplicates",
    "filter_outliers", "filter_near_due",
]

# pill filter chips (.fchip / .fchip.on in reference)
_CHIP_STYLE = """
    QPushButton {
        background: #fefefe; color: #5d6480;
        border: 1px solid #e3e5ec; border-radius: 14px;
        padding: 0 12px; font-size: 12px; font-weight: 600;
    }
    QPushButton:hover { background: #f6f7f9; }
    QPushButton:checked { background: #2e3552; color: white; border-color: #2e3552; }
"""


def _is_empty(val: Any) -> bool:
    if val is None:
        return True
    try:
        if isinstance(val, float) and pd.isna(val):
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(val, str):
        return val.strip() == ""
    if isinstance(val, (int, float)):
        return float(val) == 0.0
    return False


class InvoiceTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._df: pd.DataFrame = pd.DataFrame()
        self._threshold = 0.6

    def set_threshold(self, t: float) -> None:
        self._threshold = t

    def load(self, df: pd.DataFrame) -> None:
        self.beginResetModel()
        self._df = df.reset_index(drop=True).copy()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._df)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(_COL_KEYS)

    def headerData(self, section: int, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                # uppercase headers per reference (.tbl thead th)
                return L().t(_COL_I18N[section]).upper()
            return str(section + 1)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter
        return None

    def _row(self, i: int):
        return self._df.iloc[i]

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or self._df.empty:
            return None
        r = self._row(index.row())
        key = _COL_KEYS[index.column()]
        val = r.get(key) if key != "status" else None

        if role == Qt.ItemDataRole.DisplayRole:
            if key == "status":
                return L().t(f"status_{row_status(r, self._threshold)}")
            return self._format(key, val)

        if role == _STATUS_ROLE and key == "status":
            return row_status(r, self._threshold)

        if role == _SORT_ROLE:
            return self._sort_key(key, val, r)

        if role == Qt.ItemDataRole.ForegroundRole:
            if key in _REQUIRED and _is_empty(val):
                return _EMPTY_RED

        if role == Qt.ItemDataRole.FontRole:
            if key in _REQUIRED and _is_empty(val):
                f = QFont()
                f.setItalic(True)
                return f

        if role == Qt.ItemDataRole.BackgroundRole:
            if r.get("is_duplicate", False):
                return _FLAG_ORANGE
            if r.get("is_outlier", False):
                return _FLAG_RED
            if r.get("is_near_due", False):
                return _FLAG_YELLOW
            return None

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if key in ("total", "vat_amount", "confidence_score"):
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            if key == "currency":
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        return None

    def _format(self, key: str, val: Any) -> str:
        if key in _REQUIRED and _is_empty(val):
            return "—"
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return ""
        if key in ("total", "vat_amount"):
            try:
                return f"{float(val):,.2f}"
            except (TypeError, ValueError):
                return str(val)
        if key == "confidence_score":
            try:
                return f"{float(val):.0%}"
            except (TypeError, ValueError):
                return str(val)
        if key in ("issue_date", "due_date"):
            return "" if val is None else str(val)
        return str(val)

    def _sort_key(self, key: str, val: Any, r) -> Any:
        if key == "status":
            return _STATUS_RANK.get(row_status(r, self._threshold), 9)
        if key in ("total", "vat_amount", "confidence_score"):
            try:
                return float(val or 0)
            except (TypeError, ValueError):
                return 0.0
        if key in ("issue_date", "due_date"):
            return str(val) if val is not None else ""
        return str(val or "").lower()

    def get_row_data(self, row: int) -> dict:
        if row < 0 or row >= len(self._df):
            return {}
        return self._df.iloc[row].to_dict()


class StatusPillDelegate(QStyledItemDelegate):
    """Paints valid/warning/error as a coloured pill with a dot (.stat in reference)."""

    _STYLE = {
        "valid":   ("#e3f1ea", "#1a6b4f", "#2f8f6b"),
        "warning": ("#f9f0dd", "#8a6d1a", "#d8a72e"),
        "error":   ("#faeae7", "#b3261e", "#e2483a"),
    }

    def paint(self, painter, option, index):
        status = index.data(_STATUS_ROLE) or "valid"
        label = index.data(Qt.ItemDataRole.DisplayRole) or ""
        bg, fg, dot = self._STYLE.get(status, self._STYLE["valid"])

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(47, 143, 107, 30))

        r = option.rect
        fm = QFontMetrics(option.font)
        pill_h = 20
        pill_w = fm.horizontalAdvance(label) + 26
        x = r.x() + 8
        y = r.y() + (r.height() - pill_h) // 2

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(bg))
        painter.drawRoundedRect(x, y, pill_w, pill_h, 10, 10)
        painter.setBrush(QColor(dot))
        painter.drawEllipse(x + 9, y + (pill_h - 6) // 2, 6, 6)
        painter.setPen(QColor(fg))
        painter.setFont(option.font)
        painter.drawText(QRect(x + 19, y, pill_w - 19, pill_h),
                         int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                         label)
        painter.restore()


class VendorAvatarDelegate(QStyledItemDelegate):
    """Paints a coloured initials avatar + supplier name (.vendor-cell in reference)."""

    _COLORS = ["#2f8f6b", "#3478c6", "#9b59b6", "#e08234",
               "#1f9c8f", "#c0455b", "#5b6cc4", "#d8a72e"]

    def paint(self, painter, option, index):
        name = (index.data(Qt.ItemDataRole.DisplayRole) or "").strip()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(47, 143, 107, 30))

        r = option.rect
        if not name or name == "—":
            f = QFont(option.font)
            f.setItalic(True)
            painter.setFont(f)
            painter.setPen(_EMPTY_RED)
            painter.drawText(QRect(r.x() + 10, r.y(), r.width() - 14, r.height()),
                             int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                             "—")
            painter.restore()
            return

        size = 24
        x = r.x() + 8
        y = r.y() + (r.height() - size) // 2
        initials = "".join(w[0] for w in name.split()[:2]).upper()[:2] or "?"
        color = self._COLORS[sum(ord(c) for c in name) % len(self._COLORS)]

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(x, y, size, size, 6, 6)
        af = QFont(option.font)
        af.setBold(True)
        af.setPointSizeF(max(7.5, option.font.pointSizeF() - 1))
        painter.setFont(af)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(QRect(x, y, size, size),
                         int(Qt.AlignmentFlag.AlignCenter), initials)

        tx = x + size + 9
        painter.setFont(option.font)
        painter.setPen(QColor("#2e3552"))
        fm = QFontMetrics(option.font)
        elided = fm.elidedText(name, Qt.TextElideMode.ElideRight,
                               r.right() - tx - 6)
        painter.drawText(QRect(tx, r.y(), r.right() - tx - 4, r.height()),
                         int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                         elided)
        painter.restore()


class InvoiceTableView(QWidget):
    selection_changed = pyqtSignal(dict)
    invoice_updated   = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 8)
        root.setSpacing(8)

        # Filter bar
        fb = QWidget()
        fb.setStyleSheet("background: transparent;")
        fb_layout = QHBoxLayout(fb)
        fb_layout.setContentsMargins(0, 0, 0, 0)
        fb_layout.setSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText(L().t("search_placeholder"))
        self._search.setFixedHeight(32)
        self._search.setFixedWidth(230)
        self._search.setStyleSheet(
            "QLineEdit { background: #f0f1f5; border: 1px solid #e3e5ec; border-radius: 8px;"
            " padding: 0 10px; font-size: 13px; color: #2e3552; }"
            "QLineEdit:focus { border-color: #2f8f6b; background: #fefefe; }"
        )

        # Filter chips (.fchip pills in reference)
        self._filter_idx = 0
        self._filter_btns: list[QPushButton] = []
        for i, key in enumerate(_FILTER_KEYS):
            chip = QPushButton(L().t(key))
            chip.setCheckable(True)
            chip.setChecked(i == 0)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setFixedHeight(28)
            chip.setStyleSheet(_CHIP_STYLE)
            chip.clicked.connect(lambda _, idx=i: self._on_chip(idx))
            self._filter_btns.append(chip)

        self._count_label = QLabel("0")
        self._count_label.setStyleSheet(
            "color: #6b7291; font-size: 12px; font-weight: 600; background: transparent;"
        )

        fb_layout.addWidget(self._search)
        for chip in self._filter_btns:
            fb_layout.addWidget(chip)
        fb_layout.addStretch()
        fb_layout.addWidget(self._count_label)
        root.addWidget(fb)

        # Table
        self._model = InvoiceTableModel()
        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)
        self._proxy.setSortRole(_SORT_ROLE)   # numeric/normalized sorting

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(False)
        self._table.setShowGrid(False)
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setDefaultSectionSize(40)   # --row-h
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setHighlightSections(False)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.setStyleSheet("""
            QTableView {
                background: #fefefe; border: 1px solid #e3e5ec; border-radius: 11px;
                font-size: 12px; color: #2e3552;
                selection-background-color: rgba(47,143,107,0.12); selection-color: #1a6b4f;
            }
            QHeaderView::section {
                background: #f6f7f9; color: #6b7291; font-weight: 700;
                font-size: 10px; padding: 9px 8px; border: none;
                border-bottom: 1px solid #e3e5ec;
            }
            QTableView::item {
                padding: 0 6px;
                border-bottom: 1px solid #f0f1f5;
            }
            QTableView::item:hover { background: #f6f7f9; }
            QTableView::item:selected { background: rgba(47,143,107,0.12); color: #1a6b4f; }
        """)

        widths = [200, 110, 95, 95, 95, 60, 85, 100, 110, 80, 150]
        for i, w in enumerate(widths):
            self._table.setColumnWidth(i, w)

        self._table.setItemDelegateForColumn(
            _COL_IDX["supplier_name"], VendorAvatarDelegate(self._table))
        self._table.setItemDelegateForColumn(
            _COL_IDX["status"], StatusPillDelegate(self._table))

        # Table + slide-in detail drawer side by side
        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)
        content.addWidget(self._table, 1)

        self._drawer = DetailDrawer()
        self._drawer.setVisible(False)
        self._drawer.closed.connect(self._close_drawer)
        self._drawer.saved.connect(self._on_drawer_saved)
        content.addWidget(self._drawer)
        root.addLayout(content, 1)

        self._search.textChanged.connect(self._proxy.setFilterFixedString)
        self._table.selectionModel().selectionChanged.connect(self._on_selection)
        self._table.doubleClicked.connect(self._on_double_click)

        self._full_df: pd.DataFrame = pd.DataFrame()

    def _on_chip(self, idx: int) -> None:
        self._filter_idx = idx
        for i, chip in enumerate(self._filter_btns):
            chip.setChecked(i == idx)
        self._apply_filter()

    def retranslate(self) -> None:
        self._search.setPlaceholderText(L().t("search_placeholder"))
        for chip, key in zip(self._filter_btns, _FILTER_KEYS):
            chip.setText(L().t(key))
        self._model.beginResetModel()
        self._model.endResetModel()  # refreshes headers

    def load_data(self, df: pd.DataFrame) -> None:
        self._full_df = df.copy()
        self._apply_filter()

    def _apply_filter(self) -> None:
        idx = self._filter_idx
        df = self._full_df.copy()
        if not df.empty:
            if idx == 1:
                df = df[df["is_duplicate"] | df["is_outlier"] | df["is_near_due"]]
            elif idx == 2:
                df = df[df["is_duplicate"]]
            elif idx == 3:
                df = df[df["is_outlier"]]
            elif idx == 4:
                df = df[df["is_near_due"]]
        self._model.load(df)
        self._count_label.setText(f"{len(df)}")
        self._search.clear()

    def _on_selection(self) -> None:
        indexes = self._table.selectionModel().selectedRows()
        if indexes:
            src = self._proxy.mapToSource(indexes[0])
            self.selection_changed.emit(self._model.get_row_data(src.row()))

    def _on_double_click(self, index) -> None:
        # open the review drawer only on double-click
        src = self._proxy.mapToSource(index)
        row = self._model.get_row_data(src.row())
        if not row:
            return
        self.selection_changed.emit(row)
        self._drawer.load(row)
        self._drawer.setVisible(True)

    def _close_drawer(self) -> None:
        self._drawer.setVisible(False)
        self._table.clearSelection()

    def _on_drawer_saved(self, fields: dict) -> None:
        self.invoice_updated.emit(fields)

    def retranslate_drawer(self) -> None:
        self._drawer.retranslate()

    def clear(self) -> None:
        self._full_df = pd.DataFrame()
        self._model.load(pd.DataFrame(columns=_COL_KEYS))
        self._count_label.setText("0")
