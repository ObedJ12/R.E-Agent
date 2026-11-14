"""One-page-ish PDF deal report (reportlab)."""

from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from re_agents.underwrite import DealReport


def _money(x: float | None) -> str:
    return "n/a" if x is None else f"${x:,.0f}"


def _table(rows: list[list[str]], widths: list[float]) -> Table:
    t = Table(rows, colWidths=widths)
    t.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
                ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF7")),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#CCCCCC")),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return t


def build_pdf(r: DealReport, brand: str = "") -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=0.6 * inch, rightMargin=0.6 * inch,
                            topMargin=0.6 * inch, bottomMargin=0.6 * inch)
    ss = getSampleStyleSheet()
    s, v = r.subject, r.valuation
    story = []
    if brand:
        story.append(Paragraph(brand, ss["Normal"]))
    story.append(Paragraph(f"Deal Report: {s.address}", ss["Title"]))
    story.append(Paragraph(
        f"{s.bedrooms or '?'} bd / {s.bathrooms or '?'} ba &middot; {s.square_footage or '?'} sqft &middot; "
        f"built {s.year_built or '?'} &middot; data: {r.data_source}", ss["Normal"]))
    story.append(Spacer(1, 10))

    story.append(_table([
        ["Value", "Amount"],
        ["As-is value", _money(v.as_is_value)],
        ["After-repair value (ARV)", _money(v.arv)],
        ["Renovated comp range", f"{_money(v.low)} - {_money(v.high)}"],
        ["Repair estimate", f"{_money(r.repairs.total)} ({r.repairs.scope}, C{r.repairs.condition.value})"],
        ["Max allowable offer (wholesale)", _money(r.wholesale.mao)],
        ["Confidence", v.confidence],
    ], [3.3 * inch, 3.6 * inch]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Comparables used", ss["Heading3"]))
    rows = [["Address", "Price", "Bd/Ba", "Sqft", "Mi", "Days", "Adjusted"]]
    for a in v.comps_used:
        c = a.comp
        rows.append([c.address[:34], _money(c.price), f"{c.bedrooms or '-'}/{c.bathrooms or '-'}",
                     f"{c.square_footage or 0:,.0f}", f"{c.distance_miles or 0:.2f}", str(c.days_old or "-"),
                     _money(a.adjusted_price)])
    story.append(_table(rows, [2.3 * inch, 0.85 * inch, 0.6 * inch, 0.6 * inch, 0.5 * inch, 0.5 * inch, 0.95 * inch]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Exit strategies", ss["Heading3"]))
    story.append(_table([
        ["Strategy", "Key numbers"],
        ["Wholesale", f"Offer {_money(r.wholesale.mao)}; end buyer {_money(r.wholesale.buyer_price)}; "
                      f"fee {_money(r.wholesale.assignment_fee)}"],
        ["Fix and flip", f"Profit {_money(r.flip.net_profit)}; ROI {r.flip.roi_on_cash:.0%}; "
                         f"cash needed {_money(r.flip.cash_needed)}"],
        ["Rental", f"Rent {_money(r.rental.monthly_rent)}/mo; cash flow {_money(r.rental.monthly_cash_flow)}/mo; "
                   f"cap {r.rental.cap_rate:.1%}"],
        ["BRRRR", f"Cash left in {_money(r.brrrr.cash_left_in)}; cash flow {_money(r.brrrr.monthly_cash_flow)}/mo"],
    ], [1.4 * inch, 5.5 * inch]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Repairs", ss["Heading3"]))
    rep = [["Item", "Cost"]] + [[f"{l.item} {('(' + l.note + ')') if l.note else ''}", _money(l.cost)]
                                for l in r.repairs.lines]
    rep.append([f"Contingency {r.repairs.contingency_pct:.0%}", _money(r.repairs.total - r.repairs.subtotal)])
    rep.append(["Total", _money(r.repairs.total)])
    story.append(_table(rep, [5.4 * inch, 1.5 * inch]))

    if r.memo:
        story.append(Spacer(1, 12))
        story.append(Paragraph("Deal memo", ss["Heading3"]))
        for para in r.memo.split("\n"):
            if para.strip():
                story.append(Paragraph(para.replace("&", "&amp;").replace("<", "&lt;"), ss["Normal"]))

    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "Estimates only. Comps come from listing data, not recorded MLS sales; verify before making offers.",
        ss["Italic"]))
    doc.build(story)
    return buf.getvalue()
