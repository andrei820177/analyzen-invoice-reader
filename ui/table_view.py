from __future__ import annotations

from typing import Any

import pandas as pd
from PyQt6.QtCore import (
    QAbstractTableModel, QModelIndex, Qt, QSortFilterProxyModel, pyqtSignal,
)
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QTableView, QVBoxLayout, QWidget,
)
from ui.lang import L

_COL_DEFS = [
    ("file_name",        "col_file"),
    ("supplier_name",    "col_supplier"),
    ("invoice_number",   "col_invoice_no"),
    ("issue_date",       "col_date"),
    ("due_date",         "col_due_date"),
    ("total",            "col_total"),
    ("currency",         "col_currency"),
    ("vat_amount",       "col_vat"),
    ("category",         "col_category"),
    ("confidence_score", "col_confidence"),
    ("is_duplicate",     "flag_duplicate"),
    ("is_outlier",       "flag_outlier"),
    ("is_near_due",      "flag_near_due"),
]

_COL_KEYS   = [c[0] for c in _COL_DEFS]
_COL_I18N   = [c[1] for c in _COL_DEFS]

# soft state tints from reference.html (--err-soft / --warn-soft)
_FLAG_RED    = QColor("#faeae7")
_FLAG_ORANGE = QColor("#f9f0dd")
_FLAG_YELLOW = QColor("#fbf6e4")

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


class InvoiceTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._df: pd.DataFrame = pd.DataFrame(columns=_COL_KEYS)

    def load(self, df: pd.DataFrame) -> None:
        self.beginResetModel()
        cols = [k for k in _COL_KEYS if k in df.columns]
        self._df = df[cols].copy() if cols else pd.DataFrame(columns=_COL_KEYS)
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

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        key = _COL_KEYS[col]
        val = self._df.iloc[row][key] if key in self._df.columns else None

        if role == Qt.ItemDataRole.DisplayRole:
            return self._format(key, val)

        if role == Qt.ItemDataRole.BackgroundRole:
            r = self._df.iloc[row]
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
            if key in ("is_duplicate", "is_outlier", "is_near_due", "currency"):
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        return None

    def _format(self, key: str, val: Any) -> str:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return ""
        if key in ("is_duplicate", "is_outlier", "is_near_due"):
            return "✓" if val else ""
        if key in ("total", "vat_amount"):
            try:
                return f"{float(val):,.2f}"
            except Exception:
                return str(val)
        if key == "confidence_score":
            try:
                return f"{float(val):.0%}"
            except Exception:
                return str(val)
        if key in ("issue_date", "due_date"):
            return "" if val is None else str(val)
        return str(val)

    def get_row_data(self, row: int) -> dict:
        if row < 0 or row >= len(self._df):
            return {}
        return self._df.iloc[row].to_dict()


class InvoiceTableView(QWidget):
    selection_changed = pyqtSignal(dict)

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

        widths = [160, 180, 110, 90, 90, 90, 55, 75, 90, 70, 55, 55, 55]
        for i, w in enumerate(widths):
            self._table.setColumnWidth(i, w)

        root.addWidget(self._table, 1)

        self._search.textChanged.connect(self._proxy.setFilterFixedString)
        self._table.selectionModel().selectionChanged.connect(self._on_selection)

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

    def clear(self) -> None:
        self._full_df = pd.DataFrame()
        self._model.load(pd.DataFrame(columns=_COL_KEYS))
        self._count_label.setText("0")
