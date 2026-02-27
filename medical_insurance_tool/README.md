# UAE Medical Insurance Quotation Tool

A local-first insurance broker tool for generating and comparing individual/family medical insurance quotations in the UAE.

## Features

- **Document OCR** – Scan passports, Emirates IDs, and UAE visa copies to auto-fill member details
- **Manual entry** – Full form-based entry with UAE-specific fields (Visa Issuing Emirate, Emirates ID, etc.)
- **Family groups** – Add multiple family members with relations (Self, Spouse, Son, Daughter, Father, Mother, etc.)
- **Rate card engine** – Reads insurer Excel rate cards (age-band matrix or member-list format)
- **Manual rate entry** – Add rates received by email/WhatsApp directly in the app
- **Quote comparison** – Side-by-side premium comparison with per-member breakdown
- **PDF export** – Broker-ready PDF quotation report
- **CSV export** – Download quote comparison as CSV

## Quick Start

### 1. Install system dependencies

**Tesseract OCR** (required for document scanning):
```bash
# Ubuntu / Debian
sudo apt-get install tesseract-ocr poppler-utils

# macOS
brew install tesseract poppler

# Windows
# Download from https://github.com/UB-Mannheim/tesseract/wiki
# Download poppler from https://github.com/oschwartz10612/poppler-windows
```

### 2. Install Python dependencies

```bash
cd medical_insurance_tool
pip install -r requirements.txt
```

### 3. Generate sample rate cards (optional)

```bash
python create_sample_rates.py
```

This creates three sample insurer rate cards in `data/rate_cards/`.

### 4. Run the app

```bash
streamlit run main.py
```

The app opens at **http://localhost:8501**

## Usage Workflow

1. **Members & Documents** – Add the primary insured and all family members
   - Upload a passport/Emirates ID/visa image for OCR auto-fill
   - Or enter details manually
   - Add as many family members as needed

2. **Rate Cards** – Load insurer pricing
   - Upload Excel rate cards from insurers
   - Or add manual rate entries for rates received by phone/email

3. **Generate Quotes** – Click "Generate Quotes" to calculate premiums
   - View quote cards with per-member breakdowns
   - Compare via chart and table
   - Filter by source or max premium

4. **Export** – Download PDF report or CSV/JSON data

## Adding Your Rate Cards

Place insurer Excel files in `data/rate_cards/` or upload them via the **Rate Cards** page.
See `data/rate_cards/RATE_CARD_FORMAT.md` for supported Excel formats.

## Project Structure

```
medical_insurance_tool/
├── main.py                    # Streamlit app entry point
├── config.py                  # UAE reference data, paths, settings
├── requirements.txt
├── create_sample_rates.py     # Generates sample Excel rate cards
├── app/
│   ├── models/
│   │   └── applicant.py       # FamilyMember, InsurancePlanQuote, QuotationRequest
│   ├── ocr/
│   │   └── document_processor.py  # Passport / Emirates ID / Visa OCR
│   ├── quotation/
│   │   ├── engine.py          # Quote calculation engine
│   │   ├── excel_reader.py    # Excel rate card parser
│   │   └── pdf_export.py      # PDF report generator
│   ├── pages/
│   │   ├── members.py         # Members & Documents UI
│   │   ├── rate_cards.py      # Rate Cards UI
│   │   ├── quotes.py          # Quote generation & comparison UI
│   │   └── export.py          # Export UI
│   └── utils/
│       └── helpers.py         # Formatting, validation utilities
└── data/
    ├── rate_cards/            # Place insurer Excel files here
    └── uploads/               # Temporary OCR uploads
```

## Family Discount Logic

The engine applies default family discounts on top of individual premiums:

| Relation | Default Discount |
|---|---|
| Spouse | 5% |
| Son | 10% |
| Daughter | 10% |
| Father | 0% |
| Mother | 0% |

These can be overridden per insurer in `app/quotation/engine.py`.

## UAE Compliance Notes

- All plans enforce the **DHA minimum premium floor** (AED 650/year)
- **5% VAT** is calculated and shown separately
- Admin/policy fee defaults to **5% of base premium**
- Visa Issuing Emirate affects plan eligibility (especially for DHA and HAAD plans)

## Future Deployment

The app is built with Streamlit, which supports easy deployment to:
- **Streamlit Community Cloud** (free)
- **Docker** (included Dockerfile coming)
- **Internal server** (reverse proxy with nginx)
- **AWS / Azure / GCP** app services
