from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
)

if TYPE_CHECKING:
    from data.processor import InvoiceDataFrame

_PRIMARY = colors.HexColor("#2f8f6b")
_LIGHT = colors.HexColor("#e8f5f0")
_DARK = colors.HexColor("#1a2332")
_RED = colors.HexColor("#e74c3c")
_ORANGE = colors.HexColor("#f39c12")
_YELLOW = colors.HexColor("#fff3cd")


def export_pdf(idf: "InvoiceDataFrame", output_path: str) -> str:
    """Generate a PDF summary report. Returns the output path."""
    summary = idf.get_summary()
    df = idf.get_all()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Normal"],
        fontSize=20,
        textColor=_PRIMARY,
        fontName="Helvetica-Bold",
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=_DARK,
        fontName="Helvetica",
        spaceAfter=16,
    )
    section_style = ParagraphStyle(
        "Section",
        parent=styles["Normal"],
        fontSize=13,
        textColor=_PRIMARY,
        fontName="Helvetica-Bold",
        spaceBefore=12,
        spaceAfter=6,
    )
    normal = styles["Normal"]

    story = []

    # Header
    story.append(Paragraph("ANALYZEN — Invoice Reader", title_style))
    story.append(Paragraph(
        f"Raport generat la: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        subtitle_style,
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=_PRIMARY))
    story.append(Spacer(1, 0.4 * cm))

    # KPI summary table
    story.append(Paragraph("Sumar General", section_style))
    kpi_data = [
        ["Indicator", "Valoare"],
        ["Total facturi", str(summary["total_invoices"])],
        ["Valoare totala", f"{summary['total_value']:,.2f} RON"],
        ["TVA total", f"{summary['total_vat']:,.2f} RON"],
        ["Facturi semnalizate", str(summary["flagged_count"])],
    ]
    kpi_table = Table(kpi_data, colWidths=[8 * cm, 8 * cm])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 1), (-1, -1), _LIGHT),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D0D0")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 0.4 * cm))

    # By category
    if summary["per_category"]:
        story.append(Paragraph("Valori pe Categorie", section_style))
        cat_data = [["Categorie", "Total (RON)", "% din total"]]
        total_val = summary["total_value"] or 1.0
        for cat, val in sorted(summary["per_category"].items(), key=lambda x: -x[1]):
            pct = val / total_val * 100
            cat_data.append([cat, f"{val:,.2f}", f"{pct:.1f}%"])
        cat_table = Table(cat_data, colWidths=[8 * cm, 5 * cm, 3 * cm])
        cat_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D0D0")),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(cat_table)
        story.append(Spacer(1, 0.4 * cm))

    # Flagged invoices
    flagged = df[df["is_duplicate"] | df["is_outlier"] | df["is_near_due"]]
    if not flagged.empty:
        story.append(Paragraph("Facturi Semnalizate", section_style))
        flag_headers = ["Fisier", "Furnizor", "Nr. Factura", "Total", "Motiv"]
        flag_data = [flag_headers]
        for _, row in flagged.iterrows():
            reasons = []
            if row["is_duplicate"]:
                reasons.append("Duplicat")
            if row["is_outlier"]:
                reasons.append("Valoare atipica")
            if row["is_near_due"]:
                reasons.append("Scadenta apropiata")
            flag_data.append([
                row["file_name"][:30],
                row["supplier_name"][:25],
                row["invoice_number"],
                f"{row['total']:,.2f} {row['currency']}",
                ", ".join(reasons),
            ])
        col_widths = [4.5 * cm, 4.5 * cm, 3 * cm, 3 * cm, 3 * cm]
        flag_table = Table(flag_data, colWidths=col_widths)
        flag_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D0D0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("WORDWRAP", (0, 0), (-1, -1), True),
        ]))
        story.append(flag_table)

    doc.build(story)
    return output_path
