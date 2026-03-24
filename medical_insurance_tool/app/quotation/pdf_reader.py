"""
PDF rate card reader.

Extracts rate tables from insurer PDF documents using:
  1. pdfplumber (table detection) — works on digitally-generated PDFs
  2. OCR fallback (pdf2image + pytesseract) — for scanned/image PDFs

Returns a pandas DataFrame that can be fed into ExcelRateCard's parser.
"""

from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    import pdf2image
    from app.ocr import OCR_AVAILABLE
    PDF_OCR_AVAILABLE = OCR_AVAILABLE
except ImportError:
    PDF_OCR_AVAILABLE = False


def _clean_cell(val) -> str:
    """Clean a single cell value."""
    if val is None:
        return ""
    return str(val).strip()


def _extract_tables_pdfplumber(path: str | Path) -> list[pd.DataFrame]:
    """
    Extract all tables from a PDF using pdfplumber's built-in
    table detection. Works well on digitally-generated PDFs.
    """
    if not PDFPLUMBER_AVAILABLE:
        return []

    tables = []
    try:
        with pdfplumber.open(str(path)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                page_tables = page.extract_tables()
                for t_idx, table in enumerate(page_tables):
                    if not table or len(table) < 2:
                        continue
                    # Clean cells
                    cleaned = [[_clean_cell(c) for c in row] for row in table]
                    df = pd.DataFrame(cleaned)
                    # Drop fully empty rows/columns
                    df = df.replace("", pd.NA).dropna(how="all").dropna(axis=1, how="all")
                    df = df.fillna("")
                    if len(df) >= 2 and len(df.columns) >= 2:
                        tables.append(df)
                        logger.info(
                            "PDF page %d, table %d: %d rows x %d cols",
                            page_num, t_idx, len(df), len(df.columns),
                        )
    except Exception as exc:
        logger.error("pdfplumber failed on %s: %s", path, exc)

    return tables


def _extract_text_pdfplumber(path: str | Path) -> str:
    """Extract all text from a PDF (non-table content)."""
    if not PDFPLUMBER_AVAILABLE:
        return ""
    try:
        text_parts = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        return "\n\n".join(text_parts)
    except Exception as exc:
        logger.error("Text extraction failed: %s", exc)
        return ""


def _extract_tables_ocr(path: str | Path) -> list[pd.DataFrame]:
    """
    Fallback: convert PDF pages to images and OCR them.
    Attempts to parse the OCR output into a table structure.
    """
    if not PDF_OCR_AVAILABLE:
        return []

    try:
        import pytesseract
        from PIL import Image

        images = pdf2image.convert_from_path(str(path), dpi=300)
        tables = []

        for i, img in enumerate(images):
            # Use pytesseract with TSV output for structured data
            tsv_data = pytesseract.image_to_data(
                img, output_type=pytesseract.Output.DATAFRAME
            )
            # Group by block_num to find table-like blocks
            text = pytesseract.image_to_string(img, config="--psm 6")
            if not text.strip():
                continue

            # Try to parse lines as table rows
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            rows = []
            for line in lines:
                # Split on 2+ spaces or tabs (common in OCR'd tables)
                cells = re.split(r"\s{2,}|\t", line)
                if len(cells) >= 2:
                    rows.append(cells)

            if len(rows) >= 3:
                # Normalize column count
                max_cols = max(len(r) for r in rows)
                normalized = [r + [""] * (max_cols - len(r)) for r in rows]
                df = pd.DataFrame(normalized)
                tables.append(df)
                logger.info(
                    "OCR page %d: extracted %d rows x %d cols", i + 1, len(df), max_cols
                )

        return tables
    except Exception as exc:
        logger.error("OCR table extraction failed: %s", exc)
        return []


def _detect_insurer_name(text: str) -> str:
    """Try to extract insurer name from the PDF text."""
    common_insurers = [
        "Daman", "ADNIC", "Oman Insurance", "Sukoon", "Cigna",
        "MetLife", "AXA", "Bupa", "MedNet", "NextCare", "Neuron",
        "Orient", "Salama", "Al Sagr", "Watania", "Takaful Emarat",
        "Abu Dhabi National Insurance", "National Health Insurance",
        "Dubai Insurance", "Alliance Insurance", "Noor Takaful",
    ]
    text_lower = text.lower()
    for insurer in common_insurers:
        if insurer.lower() in text_lower:
            return insurer
    return ""


# ── Public API ───────────────────────────────────────────────────────────────
def read_pdf_rate_card(
    path: str | Path,
    insurer_name: str = "",
) -> dict:
    """
    Read rate/benefit tables from a PDF.

    Returns dict with:
      - tables: list[pd.DataFrame]  — extracted tables
      - insurer_name: str           — detected or provided
      - text: str                   — full text (for benefits extraction)
      - method: str                 — 'pdfplumber' or 'ocr'
      - warnings: list[str]
    """
    result = {
        "tables": [],
        "insurer_name": insurer_name,
        "text": "",
        "method": "",
        "warnings": [],
    }

    path = Path(path)
    if not path.exists():
        result["warnings"].append(f"File not found: {path}")
        return result

    # ── Try pdfplumber first (works on digital PDFs) ─────────────────────────
    if PDFPLUMBER_AVAILABLE:
        tables = _extract_tables_pdfplumber(path)
        text = _extract_text_pdfplumber(path)
        result["text"] = text

        if tables:
            result["tables"] = tables
            result["method"] = "pdfplumber"
            if not insurer_name:
                result["insurer_name"] = _detect_insurer_name(text) or path.stem
            logger.info("Extracted %d table(s) via pdfplumber", len(tables))
            return result

    # ── Fallback to OCR ──────────────────────────────────────────────────────
    if PDF_OCR_AVAILABLE:
        tables = _extract_tables_ocr(path)
        if tables:
            result["tables"] = tables
            result["method"] = "ocr"
            if not insurer_name:
                result["insurer_name"] = path.stem
            result["warnings"].append(
                "Tables extracted via OCR — accuracy may vary. Please verify the rates."
            )
            return result

    # ── Neither method available ─────────────────────────────────────────────
    if not PDFPLUMBER_AVAILABLE and not PDF_OCR_AVAILABLE:
        result["warnings"].append(
            "No PDF processing library available. "
            "Install pdfplumber: pip install pdfplumber"
        )
    else:
        result["warnings"].append(
            "Could not detect any tables in this PDF. "
            "Try converting it to Excel manually, or use the Manual Entry tab."
        )

    if not insurer_name:
        result["insurer_name"] = path.stem

    return result


def pdf_tables_to_excel(
    tables: list[pd.DataFrame],
    output_path: str | Path,
) -> Path:
    """
    Save extracted PDF tables as an Excel file so it can be loaded
    by ExcelRateCard. Each table → a separate sheet.
    """
    output_path = Path(output_path)
    with pd.ExcelWriter(str(output_path), engine="openpyxl") as writer:
        for i, df in enumerate(tables):
            sheet_name = f"Table_{i + 1}" if len(tables) > 1 else "Rates"
            df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)
    return output_path
