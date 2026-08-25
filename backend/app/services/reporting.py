"""
FinSight — Automated Reporting Service
Phase 6, Prompt 19. Implements §14 of the Blueprint.

Generates three report formats from a P&L + variance snapshot:
  1. Excel  (.xlsx) — styled workbook via xlsxwriter
  2. PDF    (.pdf)  — multi-page report via reportlab
  3. PPTX   (.pptx) — executive deck via python-pptx

All functions are pure (input data → bytes).
No DB calls. No API calls. No financial arithmetic.
All numbers come in as computed dicts from financial_engine / variance_engine.
"""

from __future__ import annotations

import io
from datetime import date
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# §14.1 — Excel Report
# ─────────────────────────────────────────────────────────────────────────────

def generate_excel_report(
    pnl:      dict[str, float],
    variance: dict[str, dict],
    metadata: dict | None = None,
) -> bytes:
    """
    Generate a styled Excel workbook with P&L and variance sheets.

    Returns:
        Raw .xlsx bytes ready to stream or save.
    """
    import xlsxwriter

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})

    meta = metadata or {}
    title = meta.get("title", "FinSight Financial Report")

    # ── Formats ──────────────────────────────────────────────────────────────
    hdr_fmt   = workbook.add_format({"bold": True, "bg_color": "#1E3A5F", "font_color": "#FFFFFF",
                                     "border": 1, "align": "center", "font_size": 11})
    num_fmt   = workbook.add_format({"num_format": "#,##0.00", "border": 1})
    pct_fmt   = workbook.add_format({"num_format": "0.0%", "border": 1})
    label_fmt = workbook.add_format({"bold": True, "border": 1, "indent": 1})
    title_fmt = workbook.add_format({"bold": True, "font_size": 14, "font_color": "#1E3A5F"})
    good_fmt  = workbook.add_format({"bg_color": "#E8F5E9", "num_format": "#,##0.00", "border": 1})
    bad_fmt   = workbook.add_format({"bg_color": "#FFEBEE", "num_format": "#,##0.00", "border": 1})

    # ── Sheet 1: P&L ─────────────────────────────────────────────────────────
    ws_pnl = workbook.add_worksheet("P&L Summary")
    ws_pnl.set_column("A:A", 28)
    ws_pnl.set_column("B:B", 18)

    ws_pnl.write("A1", title, title_fmt)
    ws_pnl.write("A2", f"Generated: {date.today().isoformat()}", workbook.add_format({"italic": True}))

    row = 3
    ws_pnl.write(row, 0, "Metric",   hdr_fmt)
    ws_pnl.write(row, 1, "Amount (₹K)", hdr_fmt)
    row += 1

    pnl_rows = [
        ("Revenue",             "revenue"),
        ("COGS",                "cogs"),
        ("Gross Profit",        "gross_profit"),
        ("Gross Margin %",      "gross_margin_pct"),
        ("Operating Expense",   "opex"),
        ("Operating Income",    "operating_income"),
        ("D&A",                 "da"),
        ("EBITDA",              "ebitda"),
        ("Interest Expense",    "interest"),
        ("Pre-Tax Income",      "pretax_income"),
        ("Income Tax",          "tax"),
        ("Net Income",          "net_income"),
    ]

    for label, key in pnl_rows:
        val = pnl.get(key, 0)
        ws_pnl.write(row, 0, label, label_fmt)
        if key == "gross_margin_pct":
            ws_pnl.write(row, 1, val / 100, pct_fmt)
        else:
            ws_pnl.write(row, 1, val, num_fmt)
        row += 1

    # ── Sheet 2: Variance ─────────────────────────────────────────────────────
    ws_var = workbook.add_worksheet("Variance Analysis")
    ws_var.set_column("A:A", 28)
    ws_var.set_column("B:E", 16)

    ws_var.write(0, 0, "Variance Analysis", title_fmt)

    row = 2
    for col, label in enumerate(["Metric", "Actual", "Budget", "Variance", "Var %", "Status"]):
        ws_var.write(row, col, label, hdr_fmt)
    row += 1

    for metric, v in variance.items():
        if not isinstance(v, dict):
            continue
        label    = metric.replace("_", " ").title()
        actual   = v.get("actual",   0)
        budget   = v.get("budget",   0)
        var      = v.get("variance", 0)
        var_pct  = v.get("variance_pct")
        fav_lbl  = v.get("label", "")
        is_fav   = v.get("favorable", None)

        var_fmt  = good_fmt if is_fav else (bad_fmt if is_fav is False else num_fmt)

        ws_var.write(row, 0, label,  label_fmt)
        ws_var.write(row, 1, actual, num_fmt)
        ws_var.write(row, 2, budget, num_fmt)
        ws_var.write(row, 3, var,    var_fmt)
        ws_var.write(row, 4, (var_pct or 0) / 100, pct_fmt)
        ws_var.write(row, 5, fav_lbl, num_fmt)
        row += 1

    workbook.close()
    return output.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# §14.2 — PDF Report
# ─────────────────────────────────────────────────────────────────────────────

def generate_pdf_report(
    pnl:      dict[str, float],
    variance: dict[str, dict],
    metadata: dict | None = None,
) -> bytes:
    """
    Generate a multi-page PDF report using ReportLab.

    Returns:
        Raw .pdf bytes.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable,
    )

    meta  = metadata or {}
    title = meta.get("title", "FinSight Financial Report")
    dept  = meta.get("department", "All Departments")
    period = meta.get("period", str(date.today()))

    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("title", parent=styles["Title"],
                                 fontSize=18, textColor=colors.HexColor("#1E3A5F"), spaceAfter=6)
    body_style  = styles["BodyText"]
    sub_style   = ParagraphStyle("sub", parent=styles["Heading2"],
                                 fontSize=13, textColor=colors.HexColor("#2C5F8A"), spaceAfter=4)

    BRAND_BLUE = colors.HexColor("#1E3A5F")
    GREEN      = colors.HexColor("#2ECC71")
    RED        = colors.HexColor("#E74C3C")
    LIGHT_BLUE = colors.HexColor("#EBF3FB")

    elements = []

    # Title page
    elements.append(Paragraph(title, title_style))
    elements.append(Paragraph(f"Department: {dept}  |  Period: {period}  |  Generated: {date.today()}", body_style))
    elements.append(HRFlowable(width="100%", thickness=2, color=BRAND_BLUE))
    elements.append(Spacer(1, 0.4*cm))

    # P&L table
    elements.append(Paragraph("P&L Summary", sub_style))
    pnl_data = [["Metric", "Amount (₹K)"]]
    pnl_rows = [
        ("Revenue",            pnl.get("revenue",          0)),
        ("COGS",               pnl.get("cogs",             0)),
        ("Gross Profit",       pnl.get("gross_profit",     0)),
        (f"Gross Margin %",    pnl.get("gross_margin_pct", 0)),
        ("Operating Expense",  pnl.get("opex",             0)),
        ("EBITDA",             pnl.get("ebitda",           0)),
        ("Net Income",         pnl.get("net_income",       0)),
    ]
    for label, val in pnl_rows:
        fmt = f"{val:.1f}%" if "%" in label else f"₹{val:,.0f}K"
        pnl_data.append([label, fmt])

    pnl_tbl = Table(pnl_data, colWidths=[10*cm, 7*cm])
    pnl_tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), BRAND_BLUE),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BLUE]),
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN",       (1, 0), (1, -1), "RIGHT"),
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
    ]))
    elements.append(pnl_tbl)
    elements.append(Spacer(1, 0.5*cm))

    # Variance table
    elements.append(Paragraph("Variance Analysis", sub_style))
    var_data = [["Metric", "Actual", "Budget", "Variance", "Status"]]

    for metric, v in variance.items():
        if not isinstance(v, dict):
            continue
        var_data.append([
            metric.replace("_", " ").title(),
            f"₹{v.get('actual', 0):,.0f}",
            f"₹{v.get('budget', 0):,.0f}",
            f"₹{v.get('variance', 0):+,.0f}",
            v.get("label", ""),
        ])

    var_tbl = Table(var_data, colWidths=[6*cm, 4*cm, 4*cm, 4*cm, 3*cm])
    var_style = [
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE",   (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BLUE]),
    ]
    # Colour code Favorable/Unfavorable
    for i, (metric, v) in enumerate(variance.items(), start=1):
        if isinstance(v, dict):
            fav = v.get("favorable")
            bg  = GREEN if fav else (RED if fav is False else colors.white)
            var_style.append(("BACKGROUND", (3, i), (4, i), bg))
            var_style.append(("TEXTCOLOR",  (3, i), (4, i), colors.white if fav is not None else colors.black))

    var_tbl.setStyle(TableStyle(var_style))
    elements.append(var_tbl)

    doc.build(elements)
    return output.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# §14.3 — PowerPoint Executive Deck
# ─────────────────────────────────────────────────────────────────────────────

def generate_pptx_report(
    pnl:      dict[str, float],
    variance: dict[str, dict],
    metadata: dict | None = None,
) -> bytes:
    """
    Generate a 4-slide PowerPoint executive deck using python-pptx.

    Slides:
      1. Cover  — title + period
      2. P&L    — key metrics table
      3. Variance — actual vs budget highlights
      4. Key Takeaways — top favorable + unfavorable

    Returns:
        Raw .pptx bytes.
    """
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Inches, Pt, Emu

    meta   = metadata or {}
    title  = meta.get("title",      "FinSight Financial Report")
    dept   = meta.get("department", "All Departments")
    period = meta.get("period",     str(date.today()))

    BRAND_BLUE = RGBColor(0x1E, 0x3A, 0x5F)
    ACCENT     = RGBColor(0x4F, 0x8E, 0xF7)
    WHITE      = RGBColor(0xFF, 0xFF, 0xFF)

    prs = Presentation()
    prs.slide_width  = Inches(13.33)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]   # blank

    def add_text_box(slide, text, left, top, width, height,
                     font_size=18, bold=False, color=None, align=PP_ALIGN.LEFT):
        tb = slide.shapes.add_textbox(left, top, width, height)
        tf = tb.text_frame
        tf.word_wrap = True
        p  = tf.paragraphs[0]
        p.alignment = align
        run = p.add_run()
        run.text = text
        run.font.size = Pt(font_size)
        run.font.bold = bold
        if color:
            run.font.color.rgb = color
        return tb

    def bg_fill(slide, r, g, b):
        from pptx.util import Pt
        from pptx.oxml.ns import qn
        import lxml.etree as etree
        bg = slide.background
        fill = bg.fill
        fill.solid()
        fill.fore_color.rgb = RGBColor(r, g, b)

    # ── Slide 1: Cover ────────────────────────────────────────────────────────
    s1 = prs.slides.add_slide(blank_layout)
    bg_fill(s1, 0x1E, 0x3A, 0x5F)
    add_text_box(s1, "FinSight", Inches(1), Inches(1.5), Inches(11), Inches(1),
                 font_size=14, bold=False, color=ACCENT, align=PP_ALIGN.CENTER)
    add_text_box(s1, title, Inches(1), Inches(2.3), Inches(11), Inches(1.5),
                 font_size=36, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_text_box(s1, f"{dept}  |  {period}  |  Generated {date.today()}",
                 Inches(1), Inches(4), Inches(11), Inches(0.6),
                 font_size=14, color=RGBColor(0xAA, 0xCC, 0xFF), align=PP_ALIGN.CENTER)

    # ── Slide 2: P&L Highlights ───────────────────────────────────────────────
    s2 = prs.slides.add_slide(blank_layout)
    add_text_box(s2, "P&L Highlights", Inches(0.5), Inches(0.3), Inches(12), Inches(0.7),
                 font_size=24, bold=True, color=BRAND_BLUE)

    kpis = [
        ("Revenue",      pnl.get("revenue",     0), "₹K"),
        ("Gross Profit", pnl.get("gross_profit", 0), "₹K"),
        ("EBITDA",       pnl.get("ebitda",       0), "₹K"),
        ("Net Income",   pnl.get("net_income",   0), "₹K"),
    ]
    for i, (label, val, unit) in enumerate(kpis):
        col_left = Inches(0.5 + i * 3.1)
        box = s2.shapes.add_shape(1, col_left, Inches(1.2), Inches(2.9), Inches(1.9))  # MSO_SHAPE_TYPE.RECTANGLE=1
        box.fill.solid()
        box.fill.fore_color.rgb = ACCENT if i % 2 == 0 else BRAND_BLUE
        box.line.fill.background()
        add_text_box(s2, label, col_left + Inches(0.1), Inches(1.3), Inches(2.8), Inches(0.4),
                     font_size=11, color=WHITE)
        add_text_box(s2, f"₹{val:,.0f}K", col_left + Inches(0.1), Inches(1.8), Inches(2.8), Inches(0.7),
                     font_size=18, bold=True, color=WHITE)

    # ── Slide 3: Variance Summary ─────────────────────────────────────────────
    s3 = prs.slides.add_slide(blank_layout)
    add_text_box(s3, "Variance Summary", Inches(0.5), Inches(0.3), Inches(12), Inches(0.7),
                 font_size=24, bold=True, color=BRAND_BLUE)

    var_lines = []
    for metric in ["revenue", "gross_profit", "ebitda", "net_income"]:
        v = variance.get(metric, {})
        if isinstance(v, dict):
            var_lines.append(
                f"{metric.replace('_', ' ').title():20s}  "
                f"Actual: ₹{v.get('actual', 0):>10,.0f}K  "
                f"Budget: ₹{v.get('budget', 0):>10,.0f}K  "
                f"Var: ₹{v.get('variance', 0):>+10,.0f}K  [{v.get('label', '')}]"
            )

    add_text_box(s3, "\n".join(var_lines),
                 Inches(0.5), Inches(1.2), Inches(12), Inches(5),
                 font_size=11, color=BRAND_BLUE)

    # ── Slide 4: Key Takeaways ────────────────────────────────────────────────
    s4 = prs.slides.add_slide(blank_layout)
    add_text_box(s4, "Key Takeaways", Inches(0.5), Inches(0.3), Inches(12), Inches(0.7),
                 font_size=24, bold=True, color=BRAND_BLUE)

    favorable   = [m for m, v in variance.items() if isinstance(v, dict) and v.get("favorable") is True]
    unfavorable = [m for m, v in variance.items() if isinstance(v, dict) and v.get("favorable") is False]

    add_text_box(s4, "✅ Favorable Metrics:\n" + "\n".join(f"  • {m.replace('_',' ').title()}" for m in favorable[:5]),
                 Inches(0.5), Inches(1.2), Inches(5.5), Inches(4),
                 font_size=13, color=RGBColor(0x27, 0xAE, 0x60))
    add_text_box(s4, "⚠️ Needs Attention:\n" + "\n".join(f"  • {m.replace('_',' ').title()}" for m in unfavorable[:5]),
                 Inches(6.5), Inches(1.2), Inches(5.5), Inches(4),
                 font_size=13, color=RGBColor(0xE7, 0x4C, 0x3C))

    output = io.BytesIO()
    prs.save(output)
    return output.getvalue()
