"""
OCR-based document processor for UAE identity documents.

Supports:
  - Passports (MRZ parsing + full-page OCR)
  - Emirates IDs (front / back)
  - UAE Visa copies

Falls back gracefully when pytesseract / opencv are not installed,
returning empty extraction results so the user can fill in manually.
"""

from __future__ import annotations

import re
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ── Soft imports ────────────────────────────────────────────────────────────
try:
    import pytesseract
    from PIL import Image
    import cv2
    import numpy as np
    # Verify the Tesseract binary is actually reachable
    pytesseract.get_tesseract_version()
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("pytesseract / opencv not installed – OCR disabled.")
except Exception:
    # Library installed but Tesseract binary not found on this system
    OCR_AVAILABLE = False
    logger.warning("Tesseract binary not found – OCR disabled. Install Tesseract to enable.")

try:
    import pdf2image
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("pdf2image not installed – PDF conversion disabled.")


# ── MRZ helpers ─────────────────────────────────────────────────────────────
_MRZ_GENDER = {"M": "Male", "F": "Female", "<": "Unspecified"}

_COUNTRY_CODES: dict[str, str] = {
    "ARE": "Emirati", "IND": "Indian", "PAK": "Pakistani",
    "BGD": "Bangladeshi", "PHL": "Filipino", "EGY": "Egyptian",
    "LKA": "Sri Lankan", "NPL": "Nepali", "GBR": "British",
    "USA": "American", "CAN": "Canadian", "AUS": "Australian",
    "CHN": "Chinese", "JOR": "Jordanian", "LBN": "Lebanese",
    "SYR": "Syrian", "YEM": "Yemeni", "SAU": "Saudi Arabian",
    "KWT": "Kuwaiti", "QAT": "Qatari", "BHR": "Bahraini",
    "OMN": "Omani", "IRN": "Iranian", "ETH": "Ethiopian",
    "SDN": "Sudanese", "KEN": "Kenyan", "IDN": "Indonesian",
    "MYS": "Malaysian", "RUS": "Russian", "DEU": "German",
    "FRA": "French", "ITA": "Italian",
}


def _mrz_date(s: str) -> Optional[date]:
    """Parse YYMMDD MRZ date, assuming current century."""
    try:
        yy, mm, dd = int(s[:2]), int(s[2:4]), int(s[4:6])
        year = (2000 + yy) if yy <= (date.today().year % 100) else (1900 + yy)
        return date(year, mm, dd)
    except Exception:
        return None


def _clean_mrz_name(raw: str) -> tuple[str, str]:
    """Split MRZ name field 'SURNAME<<FIRST<MIDDLE' into (first, last)."""
    parts = raw.split("<<", 1)
    last = parts[0].replace("<", " ").strip().title()
    first = parts[1].replace("<", " ").strip().title() if len(parts) > 1 else ""
    return first, last


# ── Image pre-processing ────────────────────────────────────────────────────
def _preprocess(img_array) -> "np.ndarray":
    """Enhance image for OCR accuracy."""
    gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh


def _load_image(source) -> Optional["np.ndarray"]:
    """Load from file path or PIL Image → numpy array."""
    if not OCR_AVAILABLE:
        return None
    try:
        if isinstance(source, (str, Path)):
            img = cv2.imread(str(source))
        else:
            # PIL Image
            img = cv2.cvtColor(np.array(source), cv2.COLOR_RGB2BGR)
        return img
    except Exception as exc:
        logger.error("Image load failed: %s", exc)
        return None


# ── Core OCR function ────────────────────────────────────────────────────────
def _ocr_text(img_array) -> str:
    if not OCR_AVAILABLE:
        return ""
    processed = _preprocess(img_array)
    config = "--oem 3 --psm 6"
    return pytesseract.image_to_string(processed, config=config)


def _ocr_text_mrz(img_array) -> str:
    """OCR tuned for MRZ zone (fixed-width characters)."""
    if not OCR_AVAILABLE:
        return ""
    processed = _preprocess(img_array)
    config = "--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"
    return pytesseract.image_to_string(processed, config=config)


# ── Passport parser ─────────────────────────────────────────────────────────
def _parse_mrz(text: str) -> dict:
    """Extract fields from ICAO 9303 Type-1 (ID) or Type-3 (passport) MRZ."""
    result: dict = {}
    # Find two consecutive MRZ lines (44 chars each for passports)
    lines = [l.strip() for l in text.splitlines() if len(l.strip()) >= 30]
    mrz_lines = [l for l in lines if re.match(r"[A-Z0-9<]{30,}", l)]

    if len(mrz_lines) >= 2:
        line1, line2 = mrz_lines[-2], mrz_lines[-1]

        # Type 3 Passport MRZ (44 chars × 2)
        if len(line1) >= 44 and len(line2) >= 44:
            doc_type = line1[0]
            country = line1[2:5]
            name_field = line1[5:44]
            first_name, last_name = _clean_mrz_name(name_field)

            doc_number = line2[0:9].replace("<", "")
            nationality = line2[10:13]
            dob_raw = line2[13:19]
            gender_raw = line2[20]
            expiry_raw = line2[21:27]

            result["first_name"] = first_name
            result["last_name"] = last_name
            result["passport_number"] = doc_number
            result["nationality"] = _COUNTRY_CODES.get(nationality, nationality)
            result["gender"] = _MRZ_GENDER.get(gender_raw, "")
            result["dob"] = _mrz_date(dob_raw)
            result["doc_type"] = "Passport"
            result["issuing_country"] = _COUNTRY_CODES.get(country, country)

        # Type 1 (Emirates ID / ID card) MRZ (30 chars × 3)
        elif len(line1) >= 30 and len(mrz_lines) >= 3:
            line3 = mrz_lines[-1]
            line2 = mrz_lines[-2]
            line1 = mrz_lines[-3]
            name_field = line3[0:30]
            first_name, last_name = _clean_mrz_name(name_field)
            dob_raw = line2[0:6]
            gender_raw = line2[7]
            nationality = line2[15:18]

            result["first_name"] = first_name
            result["last_name"] = last_name
            result["nationality"] = _COUNTRY_CODES.get(nationality, nationality)
            result["gender"] = _MRZ_GENDER.get(gender_raw, "")
            result["dob"] = _mrz_date(dob_raw)
            result["doc_type"] = "Emirates ID"

    return result


def _parse_passport(text: str, mrz_data: dict) -> dict:
    """Supplement MRZ data with full-page text patterns."""
    data = dict(mrz_data)

    # Try to find DOB in plain text if not in MRZ
    if not data.get("dob"):
        dob_match = re.search(
            r"\b(\d{1,2})[/\-\. ](\w{3,9}|\d{1,2})[/\-\. ](\d{2,4})\b", text
        )
        if dob_match:
            try:
                dob_str = dob_match.group(0)
                for fmt in ("%d %b %Y", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
                            "%d %B %Y", "%d/%m/%y"):
                    try:
                        data["dob"] = datetime.strptime(dob_str, fmt).date()
                        break
                    except ValueError:
                        pass
            except Exception:
                pass

    # Nationality from text
    if not data.get("nationality"):
        nat_match = re.search(r"Nationality[:\s]+([A-Za-z ]+)", text)
        if nat_match:
            data["nationality"] = nat_match.group(1).strip().title()

    return data


# ── Emirates ID parser ──────────────────────────────────────────────────────
def _parse_emirates_id(text: str, mrz_data: dict) -> dict:
    data = dict(mrz_data)

    # ID number: 784-YYYY-NNNNNNN-C
    eid_match = re.search(r"784[-\s]?\d{4}[-\s]?\d{7}[-\s]?\d", text)
    if eid_match:
        data["emirates_id"] = re.sub(r"\s", "", eid_match.group(0))

    # Name
    name_match = re.search(r"Name[:\s]+([A-Za-z ]+)", text)
    if name_match and not data.get("first_name"):
        name_parts = name_match.group(1).strip().split()
        data["first_name"] = name_parts[0] if name_parts else ""
        data["last_name"] = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

    # Nationality
    nat_match = re.search(r"Nationality[:\s]+([A-Za-z ]+)", text)
    if nat_match and not data.get("nationality"):
        data["nationality"] = nat_match.group(1).strip().title()

    data["doc_type"] = "Emirates ID"
    return data


# ── UAE Visa parser ─────────────────────────────────────────────────────────
def _parse_visa(text: str) -> dict:
    data: dict = {}

    # Visa/file number
    visa_match = re.search(r"(?:Visa|File)\s*(?:No|Number)?[:\s#]+([A-Z0-9/\-]+)", text, re.I)
    if visa_match:
        data["visa_number"] = visa_match.group(1).strip()

    # Name
    name_match = re.search(r"(?:Full\s+)?Name[:\s]+([A-Za-z ]+)", text, re.I)
    if name_match:
        parts = name_match.group(1).strip().split()
        data["first_name"] = parts[0].title() if parts else ""
        data["last_name"] = " ".join(parts[1:]).title() if len(parts) > 1 else ""

    # Nationality
    nat_match = re.search(r"Nationality[:\s]+([A-Za-z ]+)", text, re.I)
    if nat_match:
        data["nationality"] = nat_match.group(1).strip().title()

    # Gender
    gender_match = re.search(r"(?:Sex|Gender)[:\s]+(Male|Female|M|F)\b", text, re.I)
    if gender_match:
        g = gender_match.group(1).upper()
        data["gender"] = "Male" if g.startswith("M") else "Female"

    # Emirate from "Place of Issue / Emirates" field
    for emirate in ["Abu Dhabi", "Dubai", "Sharjah", "Ajman",
                     "Umm Al Quwain", "Ras Al Khaimah", "Fujairah"]:
        if emirate.lower() in text.lower():
            data["visa_issuing_emirate"] = emirate
            break

    # DOB
    dob_match = re.search(r"(?:DOB|Date of Birth)[:\s]+(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})", text, re.I)
    if dob_match:
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y"):
            try:
                data["dob"] = datetime.strptime(dob_match.group(1), fmt).date()
                break
            except ValueError:
                pass

    data["doc_type"] = "Visa"
    return data


# ── Public API ───────────────────────────────────────────────────────────────
def process_document(
    source,
    doc_type: str = "auto",
) -> dict:
    """
    Process an uploaded document image or PDF.

    Parameters
    ----------
    source : str | Path | PIL.Image
        File path or PIL Image object.
    doc_type : str
        One of 'Passport', 'Emirates ID', 'Visa Copy', 'auto'.

    Returns
    -------
    dict with keys: first_name, last_name, dob, gender, nationality,
                    visa_issuing_emirate, passport_number, emirates_id,
                    visa_number, doc_type, raw_text, confidence, warnings
    """
    result: dict = {
        "first_name": "",
        "last_name": "",
        "dob": None,
        "gender": "",
        "nationality": "",
        "visa_issuing_emirate": "",
        "passport_number": "",
        "emirates_id": "",
        "visa_number": "",
        "doc_type": doc_type,
        "raw_text": "",
        "confidence": 0,
        "warnings": [],
    }

    if not OCR_AVAILABLE:
        result["warnings"].append(
            "OCR libraries not installed. Please enter data manually."
        )
        return result

    # ── Load image ───────────────────────────────────────────────────────────
    img = None
    if isinstance(source, (str, Path)):
        path = Path(source)
        if path.suffix.lower() == ".pdf":
            if PDF_AVAILABLE:
                pages = pdf2image.convert_from_path(str(path), dpi=300)
                if pages:
                    img = _load_image(pages[0])
            else:
                result["warnings"].append("pdf2image not installed. Cannot convert PDF.")
                return result
        else:
            img = _load_image(path)
    else:
        img = _load_image(source)

    if img is None:
        result["warnings"].append("Could not load image.")
        return result

    # ── OCR ──────────────────────────────────────────────────────────────────
    full_text = _ocr_text(img)
    mrz_text = _ocr_text_mrz(img)
    result["raw_text"] = full_text

    # ── Auto-detect document type ─────────────────────────────────────────────
    if doc_type == "auto":
        low = full_text.lower()
        if "passport" in low or "united arab emirates" in low[:200]:
            doc_type = "Passport"
        elif "784-" in full_text or "identity" in low or "emirates id" in low:
            doc_type = "Emirates ID"
        elif "visa" in low or "entry permit" in low or "residence permit" in low:
            doc_type = "Visa Copy"
        else:
            doc_type = "Passport"  # default fallback

    result["doc_type"] = doc_type

    # ── Parse ────────────────────────────────────────────────────────────────
    mrz_data = _parse_mrz(mrz_text + "\n" + full_text)

    if doc_type == "Passport":
        extracted = _parse_passport(full_text, mrz_data)
    elif doc_type == "Emirates ID":
        extracted = _parse_emirates_id(full_text, mrz_data)
    elif doc_type == "Visa Copy":
        extracted = _parse_visa(full_text)
        extracted.update({k: v for k, v in mrz_data.items() if v and not extracted.get(k)})
    else:
        extracted = mrz_data

    # ── Merge into result ────────────────────────────────────────────────────
    for key in ["first_name", "last_name", "dob", "gender", "nationality",
                "visa_issuing_emirate", "passport_number", "emirates_id", "visa_number"]:
        if extracted.get(key):
            result[key] = extracted[key]

    # ── Confidence score (simple heuristic) ─────────────────────────────────
    filled = sum(1 for k in ["first_name", "dob", "gender", "nationality"] if result.get(k))
    result["confidence"] = int(filled / 4 * 100)

    if result["confidence"] < 50:
        result["warnings"].append(
            "Low OCR confidence – please verify and correct the extracted fields."
        )

    return result


def pdf_to_images(pdf_path: str | Path):
    """Convert PDF to list of PIL Images."""
    if not PDF_AVAILABLE:
        return []
    return pdf2image.convert_from_path(str(pdf_path), dpi=300)
