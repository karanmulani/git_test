"""
PDF export for quotation reports.
Generates a clean, broker-ready PDF summary.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from fpdf import FPDF
    PDF_EXPORT_AVAILABLE = True
except ImportError:
    PDF_EXPORT_AVAILABLE = False
    logger.warning("fpdf2 not installed – PDF export disabled.")


class QuotationPDF:
    """Generates a PDF quotation report."""

    PRIMARY_COLOR = (0, 82, 155)     # Deep blue
    SECONDARY_COLOR = (240, 248, 255)  # Light blue background
    TEXT_COLOR = (30, 30, 30)
    ACCENT_COLOR = (0, 153, 76)       # Green for totals

    def __init__(self):
        if not PDF_EXPORT_AVAILABLE:
            raise RuntimeError("fpdf2 is not installed. Run: pip install fpdf2")
        self.pdf = FPDF()
        self.pdf.set_auto_page_break(auto=True, margin=15)

    def generate(self, request, output_path: str | Path) -> Path:
        """
        Build a PDF from a QuotationRequest and save to *output_path*.
        Returns the path to the saved file.
        """
        self.pdf.add_page()
        self._header(request)
        self._member_table(request)

        if request.quotes:
            self._quote_comparison(request)
            # Detailed pages for top 5 quotes
            for quote in request.quotes[:5]:
                self._quote_detail(quote)

        self._footer()

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        self.pdf.output(str(out))
        logger.info("PDF saved to %s", out)
        return out

    # ── Sections ──────────────────────────────────────────────────────────────
    def _header(self, request):
        pdf = self.pdf
        r, g, b = self.PRIMARY_COLOR

        # Banner
        pdf.set_fill_color(r, g, b)
        pdf.rect(0, 0, 210, 30, "F")
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_xy(10, 8)
        pdf.cell(0, 12, "UAE Medical Insurance Quotation", ln=True)

        pdf.set_font("Helvetica", "", 10)
        pdf.set_xy(10, 20)
        pdf.cell(0, 8, f"Generated: {date.today().strftime('%d %B %Y')}   |   Ref: {request.broker_ref or 'N/A'}")

        pdf.set_text_color(*self.TEXT_COLOR)
        pdf.ln(15)

    def _member_table(self, request):
        pdf = self.pdf
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*self.PRIMARY_COLOR)
        pdf.cell(0, 8, "Insured Members", ln=True)
        pdf.set_text_color(*self.TEXT_COLOR)
        pdf.set_font("Helvetica", "B", 9)

        headers = ["#", "Relation", "Name", "DOB", "Age", "Gender", "Nationality", "Emirate"]
        widths = [8, 25, 45, 22, 10, 16, 30, 30]

        r, g, b = self.PRIMARY_COLOR
        pdf.set_fill_color(r, g, b)
        pdf.set_text_color(255, 255, 255)
        for h, w in zip(headers, widths):
            pdf.cell(w, 7, h, border=1, fill=True)
        pdf.ln()

        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*self.TEXT_COLOR)
        fill = False
        for m in request.members:
            if fill:
                pdf.set_fill_color(*self.SECONDARY_COLOR)
            else:
                pdf.set_fill_color(255, 255, 255)
            dob_str = m.dob.strftime("%d/%m/%Y") if m.dob else "—"
            row = [
                str(m.member_id),
                m.relation,
                m.full_name,
                dob_str,
                str(m.age or "?"),
                m.gender,
                m.nationality,
                m.visa_issuing_emirate,
            ]
            for val, w in zip(row, widths):
                pdf.cell(w, 6, str(val)[:20], border=1, fill=True)
            pdf.ln()
            fill = not fill

        pdf.ln(5)

    def _quote_comparison(self, request):
        pdf = self.pdf
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*self.PRIMARY_COLOR)
        pdf.cell(0, 8, "Quote Comparison Summary", ln=True)
        pdf.set_text_color(*self.TEXT_COLOR)

        pdf.set_font("Helvetica", "B", 8)
        headers = ["Insurer", "Plan", "Type", "Network", "Base (AED)", "VAT (AED)", "Total (AED)"]
        widths = [35, 35, 25, 35, 22, 18, 22]

        r, g, b = self.PRIMARY_COLOR
        pdf.set_fill_color(r, g, b)
        pdf.set_text_color(255, 255, 255)
        for h, w in zip(headers, widths):
            pdf.cell(w, 7, h, border=1, fill=True)
        pdf.ln()

        pdf.set_font("Helvetica", "", 8)
        fill = False
        for i, q in enumerate(request.quotes[:15]):
            if fill:
                pdf.set_fill_color(*self.SECONDARY_COLOR)
            else:
                pdf.set_fill_color(255, 255, 255)

            # Highlight cheapest in green
            if i == 0:
                pdf.set_text_color(*self.ACCENT_COLOR)
                pdf.set_font("Helvetica", "B", 8)
            else:
                pdf.set_text_color(*self.TEXT_COLOR)
                pdf.set_font("Helvetica", "", 8)

            row = [
                q.insurer_name,
                q.plan_name,
                q.plan_type,
                q.network_type,
                f"{q.base_premium:,.2f}",
                f"{q.vat_amount:,.2f}",
                f"{q.total_premium:,.2f}",
            ]
            for val, w in zip(row, widths):
                pdf.cell(w, 6, str(val)[:22], border=1, fill=True)
            pdf.ln()
            fill = not fill

        pdf.set_text_color(*self.TEXT_COLOR)
        pdf.ln(5)

    def _quote_detail(self, quote):
        pdf = self.pdf
        pdf.add_page()

        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(*self.PRIMARY_COLOR)
        pdf.cell(0, 8, f"{quote.insurer_name} – {quote.plan_name}", ln=True)

        # Premium summary box
        pdf.set_fill_color(*self.SECONDARY_COLOR)
        pdf.set_text_color(*self.TEXT_COLOR)
        pdf.set_font("Helvetica", "", 10)

        def kv(label, value):
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(55, 7, label + ":", border=0)
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(0, 7, str(value), ln=True)

        kv("Plan Type", quote.plan_type)
        kv("Network", quote.network_type)
        kv("Base Premium", f"AED {quote.base_premium:,.2f}")
        kv("Admin Fee", f"AED {quote.admin_fee:,.2f}")
        kv("VAT (5%)", f"AED {quote.vat_amount:,.2f}")

        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*self.ACCENT_COLOR)
        pdf.cell(55, 8, "TOTAL ANNUAL PREMIUM:")
        pdf.cell(0, 8, f"AED {quote.total_premium:,.2f}", ln=True)
        pdf.set_text_color(*self.TEXT_COLOR)
        pdf.ln(3)

        # Benefits
        if any([quote.annual_limit, quote.room_board, quote.deductible]):
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(*self.PRIMARY_COLOR)
            pdf.cell(0, 7, "Key Benefits", ln=True)
            pdf.set_text_color(*self.TEXT_COLOR)

            benefits = {
                "Annual Limit": quote.annual_limit,
                "Room & Board": quote.room_board,
                "Deductible": quote.deductible,
                "Co-pay": quote.copay,
                "Maternity": quote.maternity_cover,
                "Dental": quote.dental_cover,
                "Optical": quote.optical_cover,
                "Pre-existing Conditions": quote.pre_existing_cover,
                "Repatriation": quote.repatriation,
                "Outpatient Limit": quote.outpatient_limit,
                "Network Details": quote.network_details,
            }
            for label, val in benefits.items():
                if val:
                    kv(label, val)

        # Per-member breakdown
        if quote.member_premiums:
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(*self.PRIMARY_COLOR)
            pdf.cell(0, 7, "Per-Member Premium Breakdown", ln=True)
            pdf.set_text_color(*self.TEXT_COLOR)

            pdf.set_font("Helvetica", "B", 8)
            headers = ["Relation", "Name", "Age", "Base Rate", "Discount", "Premium (AED)"]
            widths = [25, 55, 15, 28, 22, 28]
            r, g, b = self.PRIMARY_COLOR
            pdf.set_fill_color(r, g, b)
            pdf.set_text_color(255, 255, 255)
            for h, w in zip(headers, widths):
                pdf.cell(w, 7, h, border=1, fill=True)
            pdf.ln()

            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*self.TEXT_COLOR)
            for mp in quote.member_premiums:
                row = [
                    mp.get("relation", ""),
                    mp.get("name", ""),
                    str(mp.get("age", "?")),
                    f"AED {mp.get('raw_premium', 0):,.2f}",
                    f"{mp.get('discount_pct', 0):.0f}%",
                    f"AED {mp.get('premium', 0):,.2f}",
                ]
                for val, w in zip(row, widths):
                    pdf.cell(w, 6, str(val)[:25], border=1)
                pdf.ln()

        if quote.notes:
            pdf.ln(3)
            pdf.set_font("Helvetica", "I", 8)
            pdf.multi_cell(0, 5, f"Notes: {quote.notes}")

    def _footer(self):
        pdf = self.pdf
        pdf.set_y(-15)
        pdf.set_font("Helvetica", "I", 7)
        pdf.set_text_color(128, 128, 128)
        pdf.cell(
            0, 5,
            "This quotation is indicative only. Final premiums subject to insurer underwriting. "
            "Prepared by your insurance broker.",
            align="C",
        )


def export_to_pdf(request, output_path: str | Path) -> Optional[Path]:
    """Convenience wrapper. Returns path or None on failure."""
    if not PDF_EXPORT_AVAILABLE:
        logger.error("fpdf2 not available")
        return None
    try:
        gen = QuotationPDF()
        return gen.generate(request, output_path)
    except Exception as exc:
        logger.error("PDF export failed: %s", exc)
        return None
