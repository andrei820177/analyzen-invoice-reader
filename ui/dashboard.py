from __future__ import annotations

import math
import threading
from datetime import datetime
from typing import Dict, List, Tuple

from PyQt6.QtCore import Qt, QPointF, QRectF, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QFontMetrics
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)
from core.currency import is_rates_fresh, key_rates, refresh_rates, source_name
from ui.lang import L

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
    """Donut + legend showing each category's name, colour and share."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: List[Tuple[str, float]] = []   # (category, value) desc
        self._hover = -1
        self._hover_pos = None
        self._geom = None        # (cx, cy, R, r, [(start_deg, end_deg), ...])
        self.setMouseTracking(True)
        self.setMinimumSize(200, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, data: Dict[str, float]) -> None:
        items = [(str(k), float(v)) for k, v in data.items() if v and v > 0]
        items.sort(key=lambda kv: kv[1], reverse=True)
        # keep the palette readable: fold the long tail into "..."
        cap = len(_CATEGORY_COLORS)
        if len(items) > cap:
            tail = sum(v for _, v in items[cap - 1:])
            items = items[:cap - 1] + [("…", tail)]
        self._data = items
        self._hover = -1
        self.update()

    def _slice_at(self, pos) -> int:
        """Index of the donut slice under pos, or -1."""
        if not self._geom:
            return -1
        cx, cy, R, r, ranges = self._geom
        dx, dy = pos.x() - cx, pos.y() - cy
        dist = math.hypot(dx, dy)
        if not (r <= dist <= R):
            return -1
        # angle measured clockwise from the top (12 o'clock)
        t = (90 - math.degrees(math.atan2(-dy, dx))) % 360
        for i, (a0, a1) in enumerate(ranges):
            if a0 <= t < a1:
                return i
        return -1

    def mouseMoveEvent(self, event):
        idx = self._slice_at(event.position())
        self._hover_pos = event.position()
        if idx != self._hover:
            self._hover = idx
        self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        if self._hover != -1:
            self._hover = -1
            self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        if not self._data:
            _empty_message(p, self.rect(), L().t("no_invoices"))
            p.end()
            return

        total = sum(v for _, v in self._data) or 1.0

        # ---- donut (left) -------------------------------------------------
        d = max(80, min(H - 24, int(W * 0.46)))
        dx, dy = 12, (H - d) // 2
        cx, cy, R = dx + d / 2, dy + d / 2, d / 2
        ang = 90 * 16                      # start at the top
        ranges = []                        # clockwise-from-top span per slice
        t0 = 0.0
        for i, (_cat, val) in enumerate(self._data):
            frac = val / total
            span = -int(round(frac * 5760))   # clockwise
            pop = 5 if i == self._hover else 0   # lift the hovered slice outward
            p.setBrush(QBrush(QColor(_CATEGORY_COLORS[i % len(_CATEGORY_COLORS)])))
            p.setPen(QPen(QColor(_SURFACE), 2))       # thin gap between slices
            p.drawPie(int(dx - pop), int(dy - pop), int(d + 2 * pop), int(d + 2 * pop),
                      ang, span)
            ang += span
            ranges.append((t0, t0 + frac * 360))
            t0 += frac * 360
        self._geom = (cx, cy, R + 5, d * 0.58 / 2, ranges)

        hole_d = int(d * 0.58)
        hx, hy = dx + (d - hole_d) // 2, dy + (d - hole_d) // 2
        p.setBrush(QBrush(QColor(_SURFACE)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(hx, hy, hole_d, hole_d)

        cnt_font = QFont(); cnt_font.setPointSize(15); cnt_font.setBold(True)
        p.setFont(cnt_font); p.setPen(QColor(_INK))
        p.drawText(QRectF(dx, dy + d / 2 - 18, d, 22),
                   int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom),
                   str(len(self._data)))
        sub_font = QFont(); sub_font.setPointSize(8)
        p.setFont(sub_font); p.setPen(QColor("#939ab0"))
        p.drawText(QRectF(dx, dy + d / 2 + 2, d, 16),
                   int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                   L().t("categories"))

        # ---- legend (right) ----------------------------------------------
        lx = dx + d + 18
        lw = W - lx - 10
        if lw >= 90:
            rows = self._data
            rh = min(24.0, (H - 16) / len(rows))
            ly = (H - rh * len(rows)) / 2
            name_font = QFont(); name_font.setPointSizeF(8.8)
            pct_font = QFont(); pct_font.setPointSizeF(8.8); pct_font.setBold(True)
            fm = QFontMetrics(name_font)

            for i, (cat, val) in enumerate(rows):
                ry = ly + i * rh
                if i == self._hover:           # highlight the hovered row
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QColor("#f0f1f5"))
                    p.drawRoundedRect(QRectF(lx - 4, ry + 1, lw + 4, rh - 2), 5, 5)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(_CATEGORY_COLORS[i % len(_CATEGORY_COLORS)]))
                p.drawRoundedRect(QRectF(lx, ry + rh / 2 - 5, 10, 10), 3, 3)

                name_w = lw - 46
                p.setFont(name_font); p.setPen(QColor(_INK))
                p.drawText(QRectF(lx + 17, ry, name_w, rh),
                           int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                           fm.elidedText(cat, Qt.TextElideMode.ElideRight, int(name_w)))

                p.setFont(pct_font); p.setPen(QColor("#6b7291"))
                p.drawText(QRectF(lx + lw - 40, ry, 40, rh),
                           int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
                           f"{val / total * 100:.0f}%")

        if self._hover >= 0 and self._hover_pos is not None:
            cat, val = self._data[self._hover]
            _draw_tooltip(p, self.rect(), self._hover_pos, cat,
                          f"{val:,.0f}  ·  {val / total * 100:.1f}%",
                          dot=_CATEGORY_COLORS[self._hover % len(_CATEGORY_COLORS)])
        p.end()


def _fmt_compact(v: float) -> str:
    if v >= 1_000_000:
        return f"{v / 1e6:.1f}M"
    if v >= 1_000:
        return f"{v / 1e3:.1f}k"
    return f"{v:.0f}"


def _empty_message(painter: QPainter, rect, text: str) -> None:
    painter.setPen(QColor("#939ab0"))
    f = QFont()
    f.setPointSize(10)
    painter.setFont(f)
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)


def _draw_tooltip(p: QPainter, bounds, pos: QPointF,
                  title: str, subtitle: str, dot: str = None) -> None:
    """Custom hover tooltip: rounded card with border, shadow, colour dot."""
    tf = QFont(); tf.setPointSizeF(8.8); tf.setBold(True)
    sf = QFont(); sf.setPointSizeF(8.2)
    fmt, fms = QFontMetrics(tf), QFontMetrics(sf)

    pad = 9
    dot_w = 14 if dot else 0
    tw = max(fmt.horizontalAdvance(title) + dot_w, fms.horizontalAdvance(subtitle))
    w = tw + pad * 2
    h = pad * 2 + fmt.height() + (fms.height() + 2 if subtitle else 0)

    x, y = pos.x() + 14, pos.y() + 16
    if x + w > bounds.width() - 4:
        x = pos.x() - w - 14
    if y + h > bounds.height() - 4:
        y = pos.y() - h - 14
    x = max(4, min(x, bounds.width() - w - 4))
    y = max(4, min(y, bounds.height() - h - 4))

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(16, 24, 40, 32))                 # soft shadow
    p.drawRoundedRect(QRectF(x + 1, y + 3, w, h), 8, 8)
    p.setBrush(QColor("#ffffff"))
    p.setPen(QPen(QColor("#d6d9e3"), 1))               # contour
    p.drawRoundedRect(QRectF(x, y, w, h), 8, 8)

    tx = x + pad
    if dot:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(dot))
        p.drawRoundedRect(QRectF(tx, y + pad + 3, 9, 9), 2.5, 2.5)
        tx += dot_w
    p.setFont(tf); p.setPen(QColor(_INK))
    p.drawText(QRectF(tx, y + pad - 1, w, fmt.height() + 2),
               int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), title)
    if subtitle:
        p.setFont(sf); p.setPen(QColor("#6b7291"))
        p.drawText(QRectF(x + pad, y + pad + fmt.height(), w, fms.height() + 2),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), subtitle)


class BarChartWidget(QWidget):
    """Display-only vertical bar chart (no pan/zoom/menu)."""

    def __init__(self, color: str = _PRIMARY, parent=None):
        super().__init__(parent)
        self._data: List[Tuple[str, float]] = []
        self._color = color
        self._hover = -1
        self._hover_pos = None
        self._cols = None      # (ml, slot, n) for hit-testing
        self.setMouseTracking(True)
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, pairs) -> None:
        self._data = [(str(k), float(v)) for k, v in pairs if v is not None]
        self._hover = -1
        self.update()

    def mouseMoveEvent(self, event):
        idx = -1
        if self._cols and self._data:
            ml, slot, n = self._cols
            i = int((event.position().x() - ml) // slot)
            if 0 <= i < n:
                idx = i
        self._hover_pos = event.position()
        self._hover = idx
        self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        if self._hover != -1:
            self._hover = -1
            self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        lab_font = QFont(); lab_font.setPointSizeF(8.0)
        val_font = QFont(); val_font.setPointSizeF(8.0); val_font.setBold(True)
        fm = QFontMetrics(lab_font)

        ml, mr, mt = 10, 10, 20
        n = max(len(self._data), 1)
        slot = (W - ml - mr) / n
        # rotate x labels when the full date wouldn't fit horizontally
        max_lab_w = max((fm.horizontalAdvance(k) for k, _ in self._data), default=0)
        rotate = max_lab_w > slot - 4
        mb = (int(max_lab_w * 0.72) + 16) if rotate else 26

        pw, ph = W - ml - mr, H - mt - mb
        if not self._data or pw < 30 or ph < 30:
            _empty_message(p, self.rect(), L().t("no_invoices"))
            p.end()
            return

        vmax = max(v for _, v in self._data) or 1.0
        bar_w = min(slot * 0.62, 46)
        axis_y = mt + ph
        self._cols = (ml, slot, n)

        # subtle horizontal gridlines
        p.setPen(QPen(QColor("#eef0f4")))
        for gi in range(1, 4):
            yy = mt + ph * gi / 4
            p.drawLine(int(ml), int(yy), int(ml + pw), int(yy))

        base = QColor(self._color)
        hover_col = base.darker(118)
        for i, (label, val) in enumerate(self._data):
            bh = (val / vmax) * (ph * 0.80)
            cx = ml + slot * i + slot / 2
            y = axis_y - bh
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(hover_col if i == self._hover else base)
            p.drawRoundedRect(QRectF(cx - bar_w / 2, y, bar_w, max(bh, 2)), 4, 4)

            # value above the bar
            p.setFont(val_font)
            p.setPen(QColor(_INK))
            p.drawText(QRectF(cx - slot / 2, y - 16, slot, 14),
                       int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom),
                       _fmt_compact(val))

            # x-axis label: rotated 45° (full date) or centred when it fits
            p.setFont(lab_font)
            p.setPen(QColor("#6b7291"))
            if rotate:
                p.save()
                p.translate(cx, axis_y + 6)
                p.rotate(-45)
                p.drawText(QRectF(-max_lab_w - 4, -fm.height() / 2, max_lab_w, fm.height()),
                           int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                           label)
                p.restore()
            else:
                p.drawText(QRectF(cx - slot / 2, axis_y + 4, slot, 16),
                           int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                           label)

        if self._hover >= 0 and self._hover_pos is not None:
            label, val = self._data[self._hover]
            _draw_tooltip(p, self.rect(), self._hover_pos, label,
                          f"{val:,.0f}", dot=self._color)
        p.end()


class HBarChartWidget(QWidget):
    """Display-only horizontal bar chart for ranked items (no interaction)."""

    def __init__(self, color: str = "#3498db", parent=None):
        super().__init__(parent)
        self._data: List[Tuple[str, float]] = []
        self._color = color
        self._hover = -1
        self._hover_pos = None
        self._rows = None      # (mt, row_h, n) for hit-testing
        self.setMouseTracking(True)
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, pairs) -> None:
        self._data = [(str(k), float(v)) for k, v in pairs if v is not None]
        self._hover = -1
        self.update()

    def mouseMoveEvent(self, event):
        idx = -1
        if self._rows and self._data:
            mt, row_h, n = self._rows
            i = int((event.position().y() - mt) // row_h)
            if 0 <= i < n:
                idx = i
        self._hover_pos = event.position()
        self._hover = idx
        self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        if self._hover != -1:
            self._hover = -1
            self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        mt, mb = 8, 8
        ph = H - mt - mb
        if not self._data or ph < 20 or W < 120:
            _empty_message(p, self.rect(), L().t("no_invoices"))
            p.end()
            return

        label_w = min(150.0, W * 0.34)
        val_w = 56.0
        bar_area = W - label_w - val_w - 16
        vmax = max(v for _, v in self._data) or 1.0
        n = len(self._data)
        row_h = ph / n
        self._rows = (mt, row_h, n)

        name_font = QFont(); name_font.setPointSizeF(8.5)
        val_font = QFont(); val_font.setPointSizeF(8.5); val_font.setBold(True)
        fm = QFontMetrics(name_font)
        base = QColor(self._color)
        hover_col = base.darker(118)

        for i, (label, val) in enumerate(self._data):
            y = mt + row_h * i
            bh = min(row_h * 0.62, 20)
            by = y + (row_h - bh) / 2

            if i == self._hover:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor("#f6f7f9"))
                p.drawRoundedRect(QRectF(2, y + 1, W - 4, row_h - 2), 5, 5)

            p.setFont(name_font)
            p.setPen(QColor(_INK))
            p.drawText(QRectF(0, y, label_w - 8, row_h),
                       int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
                       fm.elidedText(label, Qt.TextElideMode.ElideRight, int(label_w - 10)))

            bw = max((val / vmax) * bar_area, 2)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(hover_col if i == self._hover else base)
            p.drawRoundedRect(QRectF(label_w, by, bw, bh), 4, 4)

            p.setFont(val_font)
            p.setPen(QColor("#6b7291"))
            p.drawText(QRectF(label_w + bw + 6, y, val_w, row_h),
                       int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                       _fmt_compact(val))

        if self._hover >= 0 and self._hover_pos is not None:
            label, val = self._data[self._hover]
            _draw_tooltip(p, self.rect(), self._hover_pos, label,
                          f"{val:,.0f}", dot=self._color)
        p.end()


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
        scroll.verticalScrollBar().setSingleStep(12)   # smoother wheel scroll

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
        self._bar_plot = BarChartWidget(_PRIMARY)
        self._month_card.add_widget(self._bar_plot)
        charts_row.addWidget(self._month_card, 3)

        self._cat_card = ChartCard("chart_by_category")
        self._pie = PieChartWidget()
        self._pie.setMinimumHeight(220)
        self._cat_card.add_widget(self._pie)
        charts_row.addWidget(self._cat_card, 2)
        root.addLayout(charts_row)

        self._supplier_card = ChartCard("chart_top_suppliers")
        self._supplier_plot = HBarChartWidget("#3498db")
        self._supplier_card.add_widget(self._supplier_plot)
        root.addWidget(self._supplier_card)

        root.addStretch()
        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        # Exchange-rate status bar (bottom of page)
        self._fx_bar = QWidget()
        self._fx_bar.setFixedHeight(24)
        self._fx_bar.setStyleSheet(
            "background: #f6f7f9; border-top: 1px solid #e3e5ec;"
        )
        fx_layout = QHBoxLayout(self._fx_bar)
        fx_layout.setContentsMargins(16, 0, 16, 0)
        self._fx_label = QLabel()
        self._fx_label.setStyleSheet(
            "color: #939ab0; font-size: 10px; background: transparent;"
        )
        fx_layout.addWidget(self._fx_label)
        fx_layout.addStretch()
        outer.addWidget(self._fx_bar)

        # Fetch rates in background; update label every 2 s until fresh
        self._fx_timer = QTimer(self)
        self._fx_timer.timeout.connect(self._update_fx_label)
        self._fx_timer.start(2000)
        threading.Thread(target=refresh_rates, daemon=True).start()
        self._update_fx_label()
        self._base_currency = "RON"

    def set_base_currency(self, currency: str) -> None:
        self._base_currency = currency.upper()

    def refresh_fx(self) -> None:
        """Re-fetch rates after the source/base currency changed in settings."""
        threading.Thread(target=refresh_rates, daemon=True).start()
        if not self._fx_timer.isActive():
            self._fx_timer.start(2000)
        self._update_fx_label()

    def _update_fx_label(self) -> None:
        if is_rates_fresh():
            self._fx_timer.stop()
            rates = key_rates()
            cur   = self._base_currency
            parts = [f"{code} {rate:.4f} {cur}"
                     for code, rate in rates.items() if rate is not None]
            ts = datetime.now().strftime("%H:%M")
            src = source_name()
            self._fx_label.setText(
                f"{src}  {' · '.join(parts)}  — {ts}" if parts else ""
            )
        else:
            dots = "." * ((int(datetime.now().second) % 3) + 1)
            self._fx_label.setText(f"Se descarca cursul valutar{dots}")

    def retranslate(self) -> None:
        for card in (self._kpi_invoices, self._kpi_value, self._kpi_vat, self._kpi_flagged):
            card.retranslate()
        self._month_card.retranslate()
        self._cat_card.retranslate()
        self._supplier_card.retranslate()
        self._pie.update()

    def update_summary(self, summary: dict) -> None:
        cur = self._base_currency
        self._kpi_invoices.set_value(str(summary.get("total_invoices", 0)))
        self._kpi_value.set_value(f"{summary.get('total_value', 0):,.0f} {cur}")
        self._kpi_vat.set_value(f"{summary.get('total_vat', 0):,.0f} {cur}")
        self._kpi_flagged.set_value(str(summary.get("flagged_count", 0)))
        self._update_monthly_chart(summary.get("per_month", {}))
        self._pie.set_data(summary.get("per_category", {}))
        self._update_supplier_chart(summary.get("per_supplier", {}))

    def _update_monthly_chart(self, per_month: dict) -> None:
        def _fmt(k: str) -> str:
            if k in ("N/A", "Unknown", ""):
                return "N/A"
            return k[2:] if len(k) == 7 else k   # "2024-03" -> "24-03"

        keys = sorted(per_month.keys())
        self._bar_plot.set_data([(_fmt(k), per_month[k]) for k in keys])

    def _update_supplier_chart(self, per_supplier: dict) -> None:
        items = sorted(per_supplier.items(), key=lambda x: x[1], reverse=True)[:10]
        self._supplier_plot.set_data([(it[0], it[1]) for it in items])
