from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.charts.barcharts import VerticalBarChart, HorizontalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.legends import Legend
from reportlab.platypus import (
    HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from core.currency import base_currency, convert
from ui.lang import L

if TYPE_CHECKING:
    from data.processor import InvoiceDataFrame

_PRIMARY = colors.HexColor("#2f8f6b")
_PRIMARY_DK = colors.HexColor("#247055")
_LIGHT = colors.HexColor("#eef6f2")
_CARD = colors.HexColor("#f6f8fa")
_DARK = colors.HexColor("#1a2332")
_INK = colors.HexColor("#2e3552")
_MUTED = colors.HexColor("#8a90a6")
_LINE = colors.HexColor("#d8dce4")
_RED = colors.HexColor("#e74c3c")
_ORANGE = colors.HexColor("#f39c12")
_BLUE = colors.HexColor("#3498db")
_PURPLE = colors.HexColor("#9b59b6")

_CHART_PALETTE = [
    colors.HexColor("#2f8f6b"), colors.HexColor("#3498db"),
    colors.HexColor("#9b59b6"), colors.HexColor("#f39c12"),
    colors.HexColor("#e74c3c"), colors.HexColor("#1abc9c"),
    colors.HexColor("#34495e"), colors.HexColor("#e67e22"),
    colors.HexColor("#16a085"), colors.HexColor("#7f8c8d"),
]

_PAGE_W, _PAGE_H = A4
_MARGIN = 1.7 * cm
_CONTENT_W = _PAGE_W - 2 * _MARGIN


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def _fmt(n: float) -> str:
    return f"{n:,.2f}"


def _valid_dates(series):
    out = []
    for d in series:
        try:
            if d is None or pd.isna(d):
                continue
        except (TypeError, ValueError):
            pass
        if hasattr(d, "strftime"):
            out.append(d)
    return out


def _logo(size: float = 40):
    d = Drawing(size, size)
    d.add(Rect(0, 0, size, size, rx=9, ry=9, fillColor=_PRIMARY, strokeColor=None))
    d.add(String(size / 2, size / 2 - size * 0.18, "A",
                 fontSize=size * 0.52, fillColor=colors.white,
                 textAnchor="middle", fontName="Helvetica-Bold"))
    return d


# --------------------------------------------------------------------------
# charts
# --------------------------------------------------------------------------

def _bar_chart(pairs, color=_PRIMARY, width=_CONTENT_W, height=170):
    d = Drawing(width, height)
    if not pairs:
        return d
    labels = [str(k) for k, _ in pairs]
    values = [float(v) for _, v in pairs]
    bc = VerticalBarChart()
    bc.x = 34
    bc.y = 38
    bc.width = width - 50
    bc.height = height - 52
    bc.data = [values]
    bc.categoryAxis.categoryNames = labels
    bc.categoryAxis.labels.angle = 30
    bc.categoryAxis.labels.boxAnchor = "ne"
    bc.categoryAxis.labels.fontSize = 7
    bc.categoryAxis.labels.fontName = "Helvetica"
    bc.valueAxis.valueMin = 0
    bc.valueAxis.labels.fontSize = 7
    bc.valueAxis.labels.fontName = "Helvetica"
    bc.barWidth = 8
    bc.groupSpacing = 6
    bc.bars[0].fillColor = color
    bc.bars[0].strokeColor = None
    d.add(bc)
    return d


def _hbar_chart(pairs, color=_BLUE, width=_CONTENT_W, height=200):
    d = Drawing(width, height)
    if not pairs:
        return d
    pairs = pairs[::-1]  # so the largest ends up on top
    labels = [(str(k)[:26]) for k, _ in pairs]
    values = [float(v) for _, v in pairs]
    bc = HorizontalBarChart()
    bc.x = 130
    bc.y = 20
    bc.width = width - 150
    bc.height = height - 30
    bc.data = [values]
    bc.categoryAxis.categoryNames = labels
    bc.categoryAxis.labels.fontSize = 7
    bc.categoryAxis.labels.fontName = "Helvetica"
    bc.valueAxis.valueMin = 0
    bc.valueAxis.labels.fontSize = 7
    bc.barWidth = 9
    bc.bars[0].fillColor = color
    bc.bars[0].strokeColor = None
    d.add(bc)
    return d


def _pie_chart(pairs, width=_CONTENT_W, height=190):
    d = Drawing(width, height)
    if not pairs:
        return d
    labels = [str(k) for k, _ in pairs]
    values = [float(v) for _, v in pairs]
    total = sum(values) or 1.0

    pie = Pie()
    pie.x = 20
    pie.y = (height - 150) / 2
    pie.width = 150
    pie.height = 150
    pie.data = values
    pie.labels = None
    pie.slices.strokeColor = colors.white
    pie.slices.strokeWidth = 1
    for i in range(len(values)):
        pie.slices[i].fillColor = _CHART_PALETTE[i % len(_CHART_PALETTE)]
    d.add(pie)

    leg = Legend()
    leg.x = 195
    leg.y = height - 24
    leg.fontName = "Helvetica"
    leg.fontSize = 8
    leg.alignment = "right"
    leg.dxTextSpace = 6
    leg.deltay = 13
    leg.columnMaximum = 11
    leg.colorNamePairs = [
        (_CHART_PALETTE[i % len(_CHART_PALETTE)],
         f"{labels[i]}  {values[i] / total * 100:.0f}%")
        for i in range(len(values))
    ]
    d.add(leg)
    return d


# --------------------------------------------------------------------------
# styles
# --------------------------------------------------------------------------

def _styles():
    base = getSampleStyleSheet()["Normal"]
    return {
        "h1": ParagraphStyle("h1", parent=base, fontName="Helvetica-Bold",
                             fontSize=26, textColor=_DARK, leading=30),
        "cover_sub": ParagraphStyle("cs", parent=base, fontName="Helvetica",
                                    fontSize=12, textColor=_MUTED, leading=18,
                                    alignment=TA_CENTER),
        "cover_lbl": ParagraphStyle("cl", parent=base, fontName="Helvetica-Bold",
                                    fontSize=9, textColor=_PRIMARY, leading=14,
                                    alignment=TA_CENTER),
        "cover_val": ParagraphStyle("cv", parent=base, fontName="Helvetica",
                                    fontSize=13, textColor=_INK, leading=18,
                                    alignment=TA_CENTER),
        "section": ParagraphStyle("sec", parent=base, fontName="Helvetica-Bold",
                                  fontSize=15, textColor=_DARK, spaceAfter=4),
        "chart_title": ParagraphStyle("ct", parent=base, fontName="Helvetica-Bold",
                                      fontSize=10.5, textColor=_PRIMARY_DK,
                                      spaceBefore=8, spaceAfter=2),
        "card_val": ParagraphStyle("cardv", parent=base, fontName="Helvetica-Bold",
                                   fontSize=19, textColor=_DARK, leading=22),
        "card_lbl": ParagraphStyle("cardl", parent=base, fontName="Helvetica-Bold",
                                   fontSize=8, textColor=_MUTED, leading=11),
        "cell": ParagraphStyle("cell", parent=base, fontName="Helvetica",
                               fontSize=7.5, textColor=_INK, leading=9),
        "cell_b": ParagraphStyle("cellb", parent=base, fontName="Helvetica-Bold",
                                 fontSize=7.5, textColor=_INK, leading=9),
        "foot": ParagraphStyle("foot", parent=base, fontName="Helvetica",
                               fontSize=9, textColor=_MUTED, leading=14,
                               alignment=TA_CENTER),
    }


def _kpi_card(value: str, label: str, accent, st):
    inner = Table(
        [[Paragraph(value, st["card_val"])], [Paragraph(label.upper(), st["card_lbl"])]],
        colWidths=[(_CONTENT_W - 2 * 0.5 * cm) / 3 - 0.3 * cm],
    )
    inner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _CARD),
        ("LINEBEFORE", (0, 0), (0, -1), 3, accent),
        ("LEFTPADDING", (0, 0), (-1, -1), 11),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (0, 0), 12),
        ("TOPPADDING", (0, 1), (0, 1), 0),
        ("BOTTOMPADDING", (0, 0), (0, 0), 2),
        ("BOTTOMPADDING", (0, 1), (0, 1), 12),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return inner


def _table_style(header_bg=_PRIMARY, fs=7.5):
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), fs),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, _LINE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, _PRIMARY_DK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def export_pdf(idf: "InvoiceDataFrame", output_path: str,
               company_name: str = "") -> str:
    """Generate a 7-section PDF report. Returns the output path."""
    t = L().t
    st = _styles()
    summary = idf.get_summary()
    df = idf.get_all()
    base = base_currency()
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    brand = "Analyzen — Invoice Reader"

    # ---- derived stats -------------------------------------------------
    dates = _valid_dates(df["issue_date"]) if not df.empty else []
    if dates:
        period = (f"{min(dates).strftime('%d.%m.%Y')} – "
                  f"{max(dates).strftime('%d.%m.%Y')}")
    else:
        period = "—"

    suppliers = [s for s in df["supplier_name"].tolist() if str(s).strip()] if not df.empty else []
    unique_suppliers = len(set(suppliers))
    currencies = sorted({str(c) for c in df["currency"].tolist() if str(c).strip()}) if not df.empty else []

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(_LINE)
        canvas.setLineWidth(0.5)
        canvas.line(_MARGIN, 1.25 * cm, _PAGE_W - _MARGIN, 1.25 * cm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(_MUTED)
        canvas.drawString(_MARGIN, 0.85 * cm, f"{brand}  ·  {now}")
        canvas.drawRightString(_PAGE_W - _MARGIN, 0.85 * cm, str(doc.page))
        canvas.restoreState()

    story = []

    # ================================================================
    # PAGE 1 - Cover
    # ================================================================
    story.append(Spacer(1, 4.5 * cm))
    logo_tbl = Table([[_logo(46)]], colWidths=[_CONTENT_W])
    logo_tbl.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    story.append(logo_tbl)
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(t("report_title"),
                           ParagraphStyle("ct2", parent=st["h1"], alignment=TA_CENTER)))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph("Analyzen Invoice Reader", st["cover_sub"]))
    story.append(Spacer(1, 1.6 * cm))

    company = company_name.strip() or t("report_company_unset")
    cover_meta = Table(
        [
            [Paragraph(t("report_period").upper(), st["cover_lbl"])],
            [Paragraph(period, st["cover_val"])],
            [Spacer(1, 0.35 * cm)],
            [Paragraph(t("report_for").upper(), st["cover_lbl"])],
            [Paragraph(company, st["cover_val"])],
            [Spacer(1, 0.35 * cm)],
            [Paragraph(t("report_generated").upper(), st["cover_lbl"])],
            [Paragraph(now, st["cover_val"])],
        ],
        colWidths=[_CONTENT_W],
    )
    cover_meta.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    story.append(cover_meta)

    # ================================================================
    # PAGE 2 - Executive summary
    # ================================================================
    story.append(PageBreak())
    story.append(Paragraph(t("report_exec_summary"), st["section"]))
    story.append(HRFlowable(width="100%", thickness=1.2, color=_PRIMARY,
                            spaceBefore=2, spaceAfter=12))

    cards = [
        (str(summary["total_invoices"]), t("kpi_total_invoices"), _PRIMARY),
        (f"{_fmt(summary['total_value'])} {base}", t("kpi_total_value"), _BLUE),
        (f"{_fmt(summary['total_vat'])} {base}", t("kpi_total_vat"), _PURPLE),
        (str(summary["flagged_count"]), t("kpi_flagged"), _RED),
        (str(unique_suppliers), t("report_unique_suppliers"), _PRIMARY_DK),
        (str(len(currencies)), t("report_currencies"), _ORANGE),
    ]
    card_cells = [_kpi_card(v, l, a, st) for v, l, a in cards]
    grid = Table(
        [card_cells[0:3], [Spacer(1, 0.4 * cm)] * 3, card_cells[3:6]],
        colWidths=[(_CONTENT_W) / 3] * 3,
    )
    grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(grid)
    story.append(Spacer(1, 0.8 * cm))
    if currencies:
        story.append(Paragraph(
            f"<b>{t('report_currencies')}:</b> {', '.join(currencies)}", st["cover_val"]
        ))

    # ================================================================
    # PAGE 3 - Visualizations
    # ================================================================
    story.append(PageBreak())
    story.append(Paragraph(t("report_visualizations"), st["section"]))
    story.append(HRFlowable(width="100%", thickness=1.2, color=_PRIMARY,
                            spaceBefore=2, spaceAfter=6))

    month_pairs = [(k, v) for k, v in summary["per_month"].items() if k != "N/A"]
    story.append(Paragraph(f"{t('chart_by_month')} ({base})", st["chart_title"]))
    story.append(_bar_chart(month_pairs, color=_PRIMARY))

    supp_pairs = list(summary["per_supplier"].items())[:10]
    story.append(Paragraph(f"{t('chart_top_suppliers')} ({base})", st["chart_title"]))
    story.append(_hbar_chart(supp_pairs, color=_BLUE))

    story.append(PageBreak())
    story.append(Paragraph(t("report_visualizations"), st["section"]))
    story.append(HRFlowable(width="100%", thickness=1.2, color=_PRIMARY,
                            spaceBefore=2, spaceAfter=6))

    cat_pairs = sorted(summary["per_category"].items(), key=lambda x: -x[1])
    story.append(Paragraph(t("chart_by_category"), st["chart_title"]))
    story.append(_pie_chart(cat_pairs))
    story.append(Spacer(1, 0.4 * cm))

    cur_counts = df["currency"].value_counts().to_dict() if not df.empty else {}
    cur_pairs = sorted(cur_counts.items(), key=lambda x: -x[1])
    story.append(Paragraph(t("report_chart_currency"), st["chart_title"]))
    story.append(_pie_chart(cur_pairs))

    # ================================================================
    # PAGE 4 - Flagged invoices
    # ================================================================
    story.append(PageBreak())
    story.append(Paragraph(t("report_flagged"), st["section"]))
    story.append(HRFlowable(width="100%", thickness=1.2, color=_RED,
                            spaceBefore=2, spaceAfter=8))

    flagged = df[df["is_duplicate"] | df["is_outlier"] | df["is_near_due"]] if not df.empty else df
    if flagged is None or flagged.empty:
        story.append(Paragraph(t("report_no_flagged"), st["cover_val"]))
    else:
        head = [t("col_supplier"), t("col_invoice_no"), t("col_total"),
                t("col_reason"), t("col_recommendation")]
        data = [[Paragraph(h, st["cell_b"]) for h in head]]
        for _, r in flagged.iterrows():
            reasons, recs = [], []
            if r["is_duplicate"]:
                reasons.append(t("reason_duplicate")); recs.append(t("rec_duplicate"))
            if r["is_outlier"]:
                reasons.append(t("reason_outlier")); recs.append(t("rec_outlier"))
            if r["is_near_due"]:
                reasons.append(t("reason_near_due")); recs.append(t("rec_near_due"))
            data.append([
                Paragraph(str(r["supplier_name"])[:40], st["cell"]),
                Paragraph(str(r["invoice_number"]), st["cell"]),
                Paragraph(f"{_fmt(float(r['total'] or 0))} {r['currency']}", st["cell"]),
                Paragraph(", ".join(reasons), st["cell"]),
                Paragraph("; ".join(recs), st["cell"]),
            ])
        tbl = Table(data, colWidths=[3.6 * cm, 2.4 * cm, 2.6 * cm, 3.0 * cm, 5.0 * cm],
                    repeatRows=1)
        tbl.setStyle(_table_style(header_bg=_RED))
        story.append(tbl)

    # ================================================================
    # PAGE 5 - Top suppliers
    # ================================================================
    story.append(PageBreak())
    story.append(Paragraph(t("report_top_suppliers"), st["section"]))
    story.append(HRFlowable(width="100%", thickness=1.2, color=_PRIMARY,
                            spaceBefore=2, spaceAfter=8))

    if df.empty:
        story.append(Paragraph(t("no_invoices"), st["cover_val"]))
    else:
        df2 = df.copy()
        df2["_base"] = df2.apply(
            lambda r: convert(float(r["total"] or 0), str(r.get("currency", base))), axis=1)
        grand = float(df2["_base"].sum()) or 1.0
        agg = df2.groupby("supplier_name").agg(
            cnt=("invoice_number", "count"),
            tot=("_base", "sum"),
        ).sort_values("tot", ascending=False)
        cur_by_supp = df2.groupby("supplier_name")["currency"].agg(
            lambda s: ", ".join(sorted(set(str(x) for x in s))))

        head = [t("col_supplier"), t("col_count"), f"{t('col_total')} ({base})",
                t("col_pct"), t("col_currency")]
        data = [[Paragraph(h, st["cell_b"]) for h in head]]
        for name, row in agg.iterrows():
            data.append([
                Paragraph(str(name)[:42], st["cell"]),
                Paragraph(str(int(row["cnt"])), st["cell"]),
                Paragraph(_fmt(float(row["tot"])), st["cell"]),
                Paragraph(f"{row['tot'] / grand * 100:.1f}%", st["cell"]),
                Paragraph(str(cur_by_supp.get(name, "")), st["cell"]),
            ])
        tbl = Table(data, colWidths=[6.0 * cm, 2.0 * cm, 3.4 * cm, 2.2 * cm, 3.0 * cm],
                    repeatRows=1)
        tbl.setStyle(_table_style())
        story.append(tbl)

    # ================================================================
    # PAGE 6 - Full invoice detail
    # ================================================================
    story.append(PageBreak())
    story.append(Paragraph(t("report_full_detail"), st["section"]))
    story.append(HRFlowable(width="100%", thickness=1.2, color=_PRIMARY,
                            spaceBefore=2, spaceAfter=8))

    if df.empty:
        story.append(Paragraph(t("no_invoices"), st["cover_val"]))
    else:
        head = [t("col_supplier"), t("col_invoice_no"), t("col_issue"), t("col_due"),
                t("col_net"), t("col_vat"), t("col_total"), t("col_currency"),
                t("col_category"), t("col_confidence")]
        data = [[Paragraph(h, st["cell_b"]) for h in head]]

        def _d(x):
            return x.strftime("%d.%m.%y") if hasattr(x, "strftime") else "—"

        for _, r in df.iterrows():
            try:
                conf = float(r["confidence_score"] or 0)
            except (TypeError, ValueError):
                conf = 0.0
            conf_pct = conf * 100 if conf <= 1 else conf
            data.append([
                Paragraph(str(r["supplier_name"])[:30], st["cell"]),
                Paragraph(str(r["invoice_number"])[:16], st["cell"]),
                Paragraph(_d(r["issue_date"]), st["cell"]),
                Paragraph(_d(r["due_date"]), st["cell"]),
                Paragraph(_fmt(float(r["subtotal"] or 0)), st["cell"]),
                Paragraph(_fmt(float(r["vat_amount"] or 0)), st["cell"]),
                Paragraph(_fmt(float(r["total"] or 0)), st["cell"]),
                Paragraph(str(r["currency"]), st["cell"]),
                Paragraph(str(r["category"])[:14], st["cell"]),
                Paragraph(f"{conf_pct:.0f}%", st["cell"]),
            ])
        widths = [3.2, 2.1, 1.4, 1.4, 1.7, 1.6, 1.8, 1.0, 1.7, 1.3]
        tbl = Table(data, colWidths=[w * cm for w in widths], repeatRows=1)
        tbl.setStyle(_table_style(fs=7))
        story.append(tbl)

    # ================================================================
    # PAGE 7 - Footer / branding
    # ================================================================
    story.append(PageBreak())
    story.append(Spacer(1, 7 * cm))
    brand_tbl = Table([[_logo(40)]], colWidths=[_CONTENT_W])
    brand_tbl.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    story.append(brand_tbl)
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("Analyzen", ParagraphStyle(
        "bg", parent=st["h1"], alignment=TA_CENTER, fontSize=20)))
    story.append(Paragraph("Invoice Reader", st["cover_sub"]))
    story.append(Spacer(1, 1.0 * cm))
    story.append(Paragraph(t("report_contact"), st["foot"]))
    story.append(Spacer(1, 0.8 * cm))
    story.append(HRFlowable(width="50%", thickness=0.6, color=_LINE))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(t("report_disclaimer"), st["foot"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(f"{t('report_generated')}: {now}", st["foot"]))

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=_MARGIN, rightMargin=_MARGIN,
        topMargin=_MARGIN, bottomMargin=1.6 * cm,
        title=t("report_title"), author="Analyzen Invoice Reader",
    )
    doc.build(story, onLaterPages=footer)
    return output_path
