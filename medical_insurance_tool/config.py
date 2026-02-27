"""
Central configuration for the Medical Insurance Quotation Tool.
"""

from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RATE_CARDS_DIR = DATA_DIR / "rate_cards"
TEMPLATES_DIR = DATA_DIR / "templates"
UPLOADS_DIR = DATA_DIR / "uploads"
EXPORTS_DIR = BASE_DIR / "exports"

for _d in [RATE_CARDS_DIR, TEMPLATES_DIR, UPLOADS_DIR, EXPORTS_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ── UAE Reference Data ─────────────────────────────────────────────────────
UAE_EMIRATES = [
    "Abu Dhabi",
    "Dubai",
    "Sharjah",
    "Ajman",
    "Umm Al Quwain",
    "Ras Al Khaimah",
    "Fujairah",
]

FAMILY_RELATIONS = [
    "Self",
    "Spouse",
    "Son",
    "Daughter",
    "Father",
    "Mother",
    "Father-in-Law",
    "Mother-in-Law",
    "Brother",
    "Sister",
    "Domestic Worker",
    "Other Dependent",
]

GENDERS = ["Male", "Female"]

MARITAL_STATUSES = ["Single", "Married", "Divorced", "Widowed"]

# Common nationalities in UAE (top 30 + Other)
NATIONALITIES = [
    "Emirati",
    "Indian",
    "Pakistani",
    "Bangladeshi",
    "Filipino",
    "Egyptian",
    "Sri Lankan",
    "Nepali",
    "British",
    "American",
    "Canadian",
    "Australian",
    "Chinese",
    "Jordanian",
    "Lebanese",
    "Syrian",
    "Yemeni",
    "Saudi Arabian",
    "Kuwaiti",
    "Qatari",
    "Bahraini",
    "Omani",
    "Iranian",
    "Ethiopian",
    "Sudanese",
    "Kenyan",
    "Indonesian",
    "Malaysian",
    "Russian",
    "German",
    "French",
    "Italian",
    "Other",
]

# ── Medical Insurance Plan Types ───────────────────────────────────────────
PLAN_TYPES = [
    "Basic (DHA Compliant)",
    "Enhanced",
    "Comprehensive",
    "Premium",
    "Executive",
]

# ── Network Types ──────────────────────────────────────────────────────────
NETWORK_TYPES = [
    "Local (UAE Only)",
    "GCC",
    "Regional (Middle East)",
    "International (Excl. USA)",
    "Worldwide (Incl. USA)",
]

# ── Age Band Brackets ──────────────────────────────────────────────────────
# Format: (min_age, max_age, label)
AGE_BANDS = [
    (0, 17, "0-17"),
    (18, 24, "18-24"),
    (25, 29, "25-29"),
    (30, 34, "30-34"),
    (35, 39, "35-39"),
    (40, 44, "40-44"),
    (45, 49, "45-49"),
    (50, 54, "50-54"),
    (55, 59, "55-59"),
    (60, 64, "60-64"),
    (65, 69, "65-69"),
    (70, 999, "70+"),
]

# ── OCR Settings ───────────────────────────────────────────────────────────
SUPPORTED_DOC_TYPES = ["Passport", "Emirates ID", "Visa Copy", "Other"]
SUPPORTED_IMAGE_FORMATS = [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]
SUPPORTED_PDF = [".pdf"]

# ── App Settings ───────────────────────────────────────────────────────────
APP_TITLE = "UAE Medical Insurance Quotation Tool"
APP_ICON = "🏥"
VERSION = "1.0.0"
