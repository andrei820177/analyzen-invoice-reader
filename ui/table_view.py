from __future__ import annotations

from typing import Any

import pandas as pd
from PyQt6.QtCore import (
    QAbstractTableModel, QModelIndex, Qt, QSortFilterProxyModel, pyqtSignal,
)
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QTableView, QVBoxLayout, QWidget,
)
from ui.lang import L

_COL_DEFS = [
    ("file_name",        "col_file"),
    ("supplier_name",    "col_supplier"),
    ("invoice_number",   "col_invoice_no"),
    ("issue_date",       "col_date"),
    ("due_date",         "col_due_date"),
    ("total",            "col_total"),
    ("currency",         "col_currency") if False else ("currency", "col_total"),  # placeholder
    ("vat_amount",       "col_vat"),
    ("category",         "col_category"),
    ("confidence_score", "col_confidence"),
    ("is_duplicate",     "flag_duplicate"),
    ("is_outlier",       "flag_outlier"),
    ("is_near_due",      "flag_near_due"),
]

# Rebuild properly
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

_FLAG_RED    = QColor("#ffebee")
_FLAG_ORANGE = QColor("#fff3e0")
_FLAG_YELLOW = QColor("#fffde7")

_FILTER_KEYS = [
    "filter_all", "filter_flagged", "filter_duplicates",
    "filter_outliers", "filter_near_due",
]


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
                return L().t(_COL_I18N[section])
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
        self._search.setFixedHeight(34)
        self._search.setStyleSheet(
            "QLineEdit { background: #fefefe; border: 1px solid #e3e5ec; border-radius: 8px;"
            " padding: 0 10px; font-size: 13px; color: #2e3552; }"
            "QLineEdit:focus { border-color: #2f8f6b; }"
        )

        self._filter_combo = QComboBox()
        self._filter_combo.setFixedHeight(34)
        self._filter_combo.setStyleSheet(
            "QComboBox { background: #fefefe; border: 1px solid #e3e5ec; border-radius: 8px;"
            " padding: 0 10px; font-size: 12px; color: #2e3552; min-width: 160px; }"
            "QComboBox:focus { border-color: #2f8f6b; }"
            "QComboBox::drop-down { border: none; }"
        )
        self._populate_filter_combo()

        self._count_label = QLabel("0")
        self._count_label.setStyleSheet("color: #6b7291; font-size: 12px;")
        self._count_label.setFixedWidth(70)

        fb_layout.addWidget(self._search, 1)
        fb_layout.addWidget(self._filter_combo)
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
        self._table.setShowGrid(True)
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setDefaultSectionSize(28)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setHighlightSections(False)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.setStyleSheet("""
            QTableView {
                background: #fefefe; border: 1px solid #e3e5ec; border-radius: 11px;
                font-size: 12px; color: #2e3552; gridline-color: #eeeff3;
                selection-background-color: rgba(47,143,107,0.12); selection-color: #1a6b4f;
            }
            QHeaderView::section {
                background: #f6f7f9; color: #6b7291; font-weight: 700;
                font-size: 11px; padding: 6px 8px; border: none;
                border-bottom: 2px solid #e3e5ec;
            }
            QTableView::item { padding: 0 4px; }
        """)

        widths = [160, 180, 110, 90, 90, 90, 55, 75, 90, 70, 55, 55, 55]
        for i, w in enumerate(widths):
            self._table.setColumnWidth(i, w)

        root.addWidget(self._table, 1)

        self._search.textChanged.connect(self._proxy.setFilterFixedString)
        self._filter_combo.currentIndexChanged.connect(self._apply_filter)
        self._table.selectionModel().selectionChanged.connect(self._on_selection)

        self._full_df: pd.DataFrame = pd.DataFrame()

    def _populate_filter_combo(self) -> None:
        current_idx = self._filter_combo.currentIndex() if self._filter_combo.count() else 0
        self._filter_combo.blockSignals(True)
        self._filter_combo.clear()
        for key in _FILTER_KEYS:
            self._filter_combo.addItem(L().t(key))
        self._filter_combo.setCurrentIndex(max(current_idx, 0))
        self._filter_combo.blockSignals(False)

    def retranslate(self) -> None:
        self._search.setPlaceholderText(L().t("search_placeholder"))
        self._populate_filter_combo()
        self._model.beginResetModel()
        self._model.endResetModel()  # refreshes headers

    def load_data(self, df: pd.DataFrame) -> None:
        self._full_df = df.copy()
        self._apply_filter()

    def _apply_filter(self) -> None:
        idx = self._filter_combo.currentIndex()
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
