from __future__ import annotations

from typing import Dict

import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)
from ui.lang import L

pg.setConfigOptions(antialias=True, background="#fefefe", foreground="#2e3552")

_PRIMARY  = "#2f8f6b"
_INK      = "#2e3552"
_SURFACE  = "#fefefe"
_BORDER   = "#e3e5ec"
_CATEGORY_COLORS = [
    "#2f8f6b", "#3498db", "#e74c3c", "#f39c12",
    "#9b59b6", "#1abc9c", "#e67e22", "#34495e",
]


class KpiCard(QFrame):
    def __init__(self, title_key: str, value: str = "0", accent: str = _PRIMARY, parent=None):
        super().__init__(parent)
        self._title_key = title_key
        self._accent = accent
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            f"QFrame {{ background: {_SURFACE}; border-radius: 11px; border: 1px solid {_BORDER}; }}"
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(90)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        self._title_lbl = QLabel(L().t(title_key))
        self._title_lbl.setStyleSheet(
            "color: #6b7291; font-size: 11px; font-weight: 700; "
            "letter-spacing: 0.5px; background: transparent; border: none;"
        )
        self._value_lbl = QLabel(value)
        self._value_lbl.setStyleSheet(
            f"color: {accent}; font-size: 22px; font-weight: 800; "
            "background: transparent; border: none; letter-spacing: -0.02em;"
        )
        layout.addWidget(self._title_lbl)
        layout.addWidget(self._value_lbl)

        bar = QFrame(self)
        bar.setGeometry(0, 0, 4, 90)
        bar.setStyleSheet(f"background: {accent}; border-radius: 2px; border: none;")

    def set_value(self, value: str) -> None:
        self._value_lbl.setText(value)

    def retranslate(self) -> None:
        self._title_lbl.setText(L().t(self._title_key))


class PieChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: Dict[str, float] = {}
        self.setMinimumSize(200, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, data: Dict[str, float]) -> None:
        self._data = {k: v for k, v in data.items() if v > 0}
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        diameter = min(w, h) - 60
        if diameter < 40:
            return
        x = (w - diameter) // 2
        y = (h - diameter) // 2
        total = sum(self._data.values()) or 1.0
        start_angle = 0
        for i, (label, value) in enumerate(self._data.items()):
            span = int(value / total * 5760)
            painter.setBrush(QBrush(QColor(_CATEGORY_COLORS[i % len(_CATEGORY_COLORS)])))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPie(x, y, diameter, diameter, start_angle, span)
            start_angle += span
        hole_d = int(diameter * 0.55)
        hole_x = (w - hole_d) // 2
        hole_y = (h - hole_d) // 2
        painter.setBrush(QBrush(QColor(_SURFACE)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(hole_x, hole_y, hole_d, hole_d)
        painter.setPen(QPen(QColor(_INK)))
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(0, 0, w, h, Qt.AlignmentFlag.AlignCenter,
                         f"{len(self._data)}\n{L().t('nav_invoices').lower()}")
        painter.end()


class ChartCard(QFrame):
    def __init__(self, title_key: str, parent=None):
        super().__init__(parent)
        self._title_key = title_key
        self.setStyleSheet(
            f"QFrame {{ background: {_SURFACE}; border-radius: 11px; border: 1px solid {_BORDER}; }}"
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)

        self._title_lbl = QLabel(L().t(title_key))
        self._title_lbl.setStyleSheet(
            f"color: {_INK}; font-size: 13px; font-weight: 700; "
            "background: transparent; border: none;"
        )
        root.addWidget(self._title_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background: {_BORDER}; max-height: 1px; border: none;")
        root.addWidget(sep)

        self._content_layout = root

    def add_widget(self, widget: QWidget) -> None:
        self._content_layout.addWidget(widget, 1)

    def retranslate(self) -> None:
        self._title_lbl.setText(L().t(self._title_key))


class DashboardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        root = QVBoxLayout(content)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # KPI row
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)
        self._kpi_invoices = KpiCard("kpi_total_invoices", "0",       "#2f8f6b")
        self._kpi_value    = KpiCard("kpi_total_value",    "0 RON",   "#3498db")
        self._kpi_vat      = KpiCard("kpi_total_vat",      "0 RON",   "#9b59b6")
        self._kpi_flagged  = KpiCard("kpi_flagged",        "0",       "#e74c3c")
        for card in (self._kpi_invoices, self._kpi_value, self._kpi_vat, self._kpi_flagged):
            kpi_row.addWidget(card)
        root.addLayout(kpi_row)

        # Charts row
        charts_row = QHBoxLayout()
        charts_row.setSpacing(12)

        self._month_card = ChartCard("chart_by_month")
        self._bar_plot = pg.PlotWidget()
        self._bar_plot.setMinimumHeight(220)
        self._bar_plot.setBackground(_SURFACE)
        self._bar_plot.getAxis("left").setTextPen(pg.mkPen(color=_INK))
        self._bar_plot.getAxis("bottom").setTextPen(pg.mkPen(color=_INK))
        self._bar_plot.showGrid(y=True, alpha=0.3)
        self._bar_plot.getPlotItem().hideAxis("top")
        self._bar_plot.getPlotItem().hideAxis("right")
        self._month_card.add_widget(self._bar_plot)
        charts_row.addWidget(self._month_card, 3)

        self._cat_card = ChartCard("chart_by_category")
        self._pie = PieChartWidget()
        self._pie.setMinimumHeight(220)
        self._cat_card.add_widget(self._pie)
        charts_row.addWidget(self._cat_card, 2)
        root.addLayout(charts_row)

        self._supplier_card = ChartCard("chart_top_suppliers")
        self._supplier_plot = pg.PlotWidget()
        self._supplier_plot.setFixedHeight(200)
        self._supplier_plot.setBackground(_SURFACE)
        self._supplier_plot.getAxis("left").setTextPen(pg.mkPen(color=_INK))
        self._supplier_plot.getAxis("bottom").setTextPen(pg.mkPen(color=_INK))
        self._supplier_plot.showGrid(x=True, alpha=0.3)
        self._supplier_plot.getPlotItem().hideAxis("top")
        self._supplier_plot.getPlotItem().hideAxis("right")
        self._supplier_card.add_widget(self._supplier_plot)
        root.addWidget(self._supplier_card)

        root.addStretch()
        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def retranslate(self) -> None:
        for card in (self._kpi_invoices, self._kpi_value, self._kpi_vat, self._kpi_flagged):
            card.retranslate()
        self._month_card.retranslate()
        self._cat_card.retranslate()
        self._supplier_card.retranslate()
        self._pie.update()

    def update_summary(self, summary: dict) -> None:
        self._kpi_invoices.set_value(str(summary.get("total_invoices", 0)))
        self._kpi_value.set_value(f"{summary.get('total_value', 0):,.0f} RON")
        self._kpi_vat.set_value(f"{summary.get('total_vat', 0):,.0f} RON")
        self._kpi_flagged.set_value(str(summary.get("flagged_count", 0)))
        self._update_monthly_chart(summary.get("per_month", {}))
        self._pie.set_data(summary.get("per_category", {}))
        self._update_supplier_chart(summary.get("per_supplier", {}))

    def _update_monthly_chart(self, per_month: dict) -> None:
        self._bar_plot.clear()
        if not per_month:
            return

        def _fmt(k: str) -> str:
            if k in ("N/A", "Unknown", ""):
                return "N/A"
            # "2024-03" → "24-03"
            return k[2:] if len(k) == 7 else k

        keys = sorted(per_month.keys())
        values = [per_month[k] for k in keys]
        bar = pg.BarGraphItem(
            x=list(range(len(keys))), height=values, width=0.6,
            brush=pg.mkBrush(_PRIMARY), pen=pg.mkPen(None),
        )
        self._bar_plot.addItem(bar)
        self._bar_plot.getAxis("bottom").setTicks(
            [[(i, _fmt(k)) for i, k in enumerate(keys)]]
        )

    def _update_supplier_chart(self, per_supplier: dict) -> None:
        self._supplier_plot.clear()
        if not per_supplier:
            return
        items = sorted(per_supplier.items(), key=lambda x: x[1], reverse=True)[:10]
        labels = [it[0][:20] for it in items]
        values = [it[1] for it in items]
        bar = pg.BarGraphItem(
            x0=0, x1=values, y=list(range(len(labels))), height=0.6,
            brush=pg.mkBrush("#3498db"), pen=pg.mkPen(None),
        )
        self._supplier_plot.addItem(bar)
        self._supplier_plot.getAxis("left").setTicks(
            [[(i, lbl) for i, lbl in enumerate(labels)]]
        )
