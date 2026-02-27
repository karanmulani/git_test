"""
Excel rate card reader.

Supports two layouts:
  1. "Age-band" table  – rows = age bands, columns = plan/gender
  2. "Member-list" table – each row is a member with their premium

The reader is intentionally flexible: it scans for recognisable headers
and age-band patterns rather than assuming a fixed cell layout, so it
works with most insurer Excel formats without customisation.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────
_AGE_BAND_PATTERN = re.compile(
    r"(\d{1,2})\s*[-–to]+\s*(\d{1,3})|(\d{1,2})\s*\+",
    re.IGNORECASE,
)


def _is_age_band(value: str) -> bool:
    return bool(_AGE_BAND_PATTERN.search(str(value)))


def _age_in_band(age: int, band_str: str) -> bool:
    """Return True if *age* falls within the band described by *band_str*."""
    s = str(band_str).strip()
    # "70+" style
    m = re.match(r"(\d+)\s*\+", s)
    if m:
        return age >= int(m.group(1))
    # "18-24" style
    m = re.match(r"(\d+)\s*[-–to]+\s*(\d+)", s, re.I)
    if m:
        return int(m.group(1)) <= age <= int(m.group(2))
    return False


def _to_float(val) -> Optional[float]:
    if pd.isna(val):
        return None
    try:
        return float(str(val).replace(",", "").replace("AED", "").strip())
    except (ValueError, TypeError):
        return None


# ── Sheet discovery ───────────────────────────────────────────────────────────
def list_sheets(path: str | Path) -> list[str]:
    """Return all sheet names in an Excel workbook."""
    try:
        xl = pd.ExcelFile(str(path))
        return xl.sheet_names
    except Exception as exc:
        logger.error("Cannot open %s: %s", path, exc)
        return []


# ── Rate card reader ─────────────────────────────────────────────────────────
class ExcelRateCard:
    """
    Reads an insurer Excel rate card and exposes a lookup interface.

    Usage::

        rc = ExcelRateCard("Insurer_A_Rates.xlsx", insurer_name="Insurer A")
        rc.load()
        premium = rc.get_premium(age=35, gender="Male", plan="Basic")
    """

    def __init__(
        self,
        path: str | Path,
        insurer_name: str = "",
        sheet_name: str | int = 0,
    ):
        self.path = Path(path)
        self.insurer_name = insurer_name or self.path.stem
        self.sheet_name = sheet_name
        self._df: Optional[pd.DataFrame] = None
        self._layout: str = "unknown"   # 'age_band' | 'member_list' | 'raw'
        self.plans: list[str] = []
        self.metadata: dict = {}

    # ── Loading ───────────────────────────────────────────────────────────────
    def load(self) -> bool:
        """Parse the Excel sheet. Returns True on success."""
        try:
            raw = pd.read_excel(
                str(self.path),
                sheet_name=self.sheet_name,
                header=None,
                dtype=str,
            )
            self._df = raw
            self._detect_layout()
            return True
        except Exception as exc:
            logger.error("Failed to load %s: %s", self.path, exc)
            return False

    def _detect_layout(self):
        df = self._df
        if df is None:
            return

        # Search for a row that looks like an age-band index
        for i, row in df.iterrows():
            band_count = sum(1 for v in row if _is_age_band(v))
            if band_count >= 2:
                self._layout = "age_band"
                self._parse_age_band(header_row_idx=i)
                return

        # Try column-header detection
        for i, row in df.iterrows():
            headers = [str(v).lower() for v in row if not pd.isna(v)]
            if "age" in headers or "dob" in headers or "premium" in headers:
                self._layout = "member_list"
                self._parse_member_list(header_row_idx=i)
                return

        self._layout = "raw"

    def _parse_age_band(self, header_row_idx: int):
        """Parse age-band matrix layout."""
        df = self._df
        # Row above age bands → plan/column names
        col_header_row = max(0, header_row_idx - 1)
        age_band_row = df.iloc[header_row_idx]

        age_bands = []
        col_indices = []
        for ci, val in age_band_row.items():
            if _is_age_band(val):
                age_bands.append(str(val).strip())
                col_indices.append(ci)

        col_names_row = df.iloc[col_header_row]
        plan_names = [str(col_names_row.get(ci, ci)) for ci in col_indices]
        self.plans = list(dict.fromkeys(plan_names))  # unique, ordered

        # Store band→premium mapping per plan
        self._rate_table: list[dict] = []
        for data_row_idx in range(header_row_idx + 1, len(df)):
            row = df.iloc[data_row_idx]
            # Detect gender label in first filled cell
            gender = "Unisex"
            first_val = str(list(row.dropna())[0]).strip().lower() if not row.dropna().empty else ""
            if "male" in first_val or first_val in ("m",):
                gender = "Male"
            elif "female" in first_val or first_val in ("f",):
                gender = "Female"

            for band, ci, plan in zip(age_bands, col_indices, plan_names):
                val = _to_float(row.get(ci))
                if val is not None:
                    self._rate_table.append({
                        "age_band": band,
                        "gender": gender,
                        "plan": plan,
                        "premium": val,
                    })

    def _parse_member_list(self, header_row_idx: int):
        """Parse member-list (tabular) layout."""
        df = self._df
        header_row = df.iloc[header_row_idx]
        headers = [str(v).strip().lower() for v in header_row]
        df.columns = headers
        data = df.iloc[header_row_idx + 1:].copy()
        data.columns = headers
        data = data.dropna(how="all")
        self._member_df = data
        self._rate_table = []

        premium_cols = [h for h in headers if "premium" in h or "rate" in h]
        age_col = next((h for h in headers if "age" in h), None)
        gender_col = next((h for h in headers if "gender" in h or "sex" in h), None)
        plan_col = next((h for h in headers if "plan" in h or "product" in h), None)

        self.plans = (
            list(data[plan_col].dropna().unique()) if plan_col else ["Default"]
        )

        for _, row in data.iterrows():
            entry: dict = {}
            if age_col:
                entry["age"] = _to_float(row.get(age_col))
            if gender_col:
                entry["gender"] = str(row.get(gender_col, "Unisex")).strip()
            if plan_col:
                entry["plan"] = str(row.get(plan_col, "Default")).strip()
            for pc in premium_cols:
                entry[pc] = _to_float(row.get(pc))
            if premium_cols:
                entry["premium"] = _to_float(row.get(premium_cols[0]))
            self._rate_table.append(entry)

    # ── Lookup ────────────────────────────────────────────────────────────────
    def get_premium(
        self,
        age: int,
        gender: str = "Unisex",
        plan: str = "",
    ) -> Optional[float]:
        """
        Return annual premium (AED) for given age / gender / plan.
        Returns None if not found.
        """
        if not hasattr(self, "_rate_table"):
            return None

        plan_lower = plan.lower()

        for entry in self._rate_table:
            # Plan match (partial OK)
            entry_plan = str(entry.get("plan", "")).lower()
            if plan_lower and plan_lower not in entry_plan and entry_plan not in plan_lower:
                continue

            # Gender match
            entry_gender = str(entry.get("gender", "Unisex"))
            if entry_gender not in ("Unisex", "", gender):
                continue

            # Age match
            if "age_band" in entry:
                if _age_in_band(age, entry["age_band"]):
                    return entry.get("premium")
            elif "age" in entry:
                if entry["age"] is not None and abs(entry["age"] - age) <= 1:
                    return entry.get("premium")

        return None

    def all_rates(self) -> list[dict]:
        """Return the full parsed rate table."""
        return getattr(self, "_rate_table", [])

    def summary(self) -> dict:
        return {
            "insurer": self.insurer_name,
            "file": self.path.name,
            "layout": self._layout,
            "plans": self.plans,
            "rate_rows": len(self.all_rates()),
        }


# ── Convenience loader ────────────────────────────────────────────────────────
def load_all_rate_cards(directory: str | Path) -> list[ExcelRateCard]:
    """Load every .xlsx / .xls in a directory as a rate card."""
    cards = []
    for p in Path(directory).glob("*.xls*"):
        rc = ExcelRateCard(p)
        if rc.load():
            cards.append(rc)
            logger.info("Loaded rate card: %s (%s)", p.name, rc._layout)
    return cards
