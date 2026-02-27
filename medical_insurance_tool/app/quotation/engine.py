"""
Quotation engine.

Aggregates premiums from all loaded rate cards, applies UAE-specific
adjustments (family discounts, DHA compliance loading, etc.) and
produces a ranked list of InsurancePlanQuote objects.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from app.models.applicant import FamilyMember, InsurancePlanQuote, QuotationRequest
from app.quotation.excel_reader import ExcelRateCard, load_all_rate_cards
from config import RATE_CARDS_DIR

logger = logging.getLogger(__name__)

# ── Family discount rules ─────────────────────────────────────────────────────
# Applied on top of summed individual premiums (insurer-specific in practice;
# these are illustrative defaults you can override per insurer).
_FAMILY_DISCOUNT_RULES: dict[str, float] = {
    # relation → discount % applied to that member's premium
    "Spouse": 0.05,
    "Son": 0.10,
    "Daughter": 0.10,
    "Father": 0.00,
    "Mother": 0.00,
}

# Minimum premium floor per member per year (AED) for DHA-compliant plans
_DHA_MINIMUM_PREMIUM = 650.0


# ── Helpers ───────────────────────────────────────────────────────────────────
def _family_discount(relation: str) -> float:
    """Return discount fraction for a given family relation."""
    return _FAMILY_DISCOUNT_RULES.get(relation, 0.0)


def _admin_fee(base: float, insurer: str = "") -> float:
    """Admin/policy fee – typically 5-10 % or a flat AED amount."""
    return round(base * 0.05, 2)   # default 5%; override per insurer if needed


# ── Engine ────────────────────────────────────────────────────────────────────
class QuotationEngine:
    """
    Core engine that coordinates rate cards and produces quotes.

    Usage::

        engine = QuotationEngine()
        engine.load_rate_cards()                # from data/rate_cards/
        quotes = engine.generate_quotes(request)
    """

    def __init__(self):
        self._rate_cards: list[ExcelRateCard] = []
        self._manual_entries: list[dict] = []   # manually typed rates

    # ── Rate card management ──────────────────────────────────────────────────
    def load_rate_cards(self, directory: str | Path = RATE_CARDS_DIR) -> int:
        """Scan *directory* and load all Excel rate cards. Returns count."""
        cards = load_all_rate_cards(directory)
        self._rate_cards.extend(cards)
        logger.info("Loaded %d rate card(s) from %s", len(cards), directory)
        return len(cards)

    def add_rate_card(self, card: ExcelRateCard):
        self._rate_cards.append(card)

    def add_manual_entry(self, entry: dict):
        """
        Add a manually-typed rate entry.

        entry keys: insurer_name, plan_name, plan_type, network_type,
                    age_band (str), gender, annual_premium (float),
                    benefits (dict), source_notes (str)
        """
        self._manual_entries.append(entry)

    @property
    def rate_card_count(self) -> int:
        return len(self._rate_cards)

    def rate_card_summaries(self) -> list[dict]:
        return [rc.summary() for rc in self._rate_cards]

    # ── Quote generation ──────────────────────────────────────────────────────
    def generate_quotes(self, request: QuotationRequest) -> list[InsurancePlanQuote]:
        """
        Produce one InsurancePlanQuote per (insurer × plan) combination
        that has pricing for all members in the request.

        Returns a list sorted by total premium ascending.
        """
        quotes: list[InsurancePlanQuote] = []

        # ── From Excel rate cards ─────────────────────────────────────────────
        for rc in self._rate_cards:
            for plan in rc.plans or ["Default"]:
                quote = self._quote_from_card(rc, plan, request)
                if quote is not None:
                    quotes.append(quote)

        # ── From manual entries ───────────────────────────────────────────────
        for entry in self._manual_entries:
            quote = self._quote_from_manual(entry, request)
            if quote is not None:
                quotes.append(quote)

        # ── Sort by total premium ─────────────────────────────────────────────
        quotes.sort(key=lambda q: q.total_premium)
        request.quotes = quotes
        return quotes

    def _quote_from_card(
        self,
        rc: ExcelRateCard,
        plan: str,
        request: QuotationRequest,
    ) -> Optional[InsurancePlanQuote]:
        """Attempt to price all members from *rc* / *plan*."""
        if not request.members:
            return None

        member_premiums = []
        base_total = 0.0
        missing = 0

        for member in request.members:
            age = member.age
            if age is None:
                missing += 1
                continue

            raw_premium = rc.get_premium(
                age=age,
                gender=member.gender or "Unisex",
                plan=plan,
            )

            if raw_premium is None:
                # try gender-neutral
                raw_premium = rc.get_premium(age=age, gender="Unisex", plan=plan)

            if raw_premium is None:
                missing += 1
                logger.debug(
                    "No rate for %s age=%d in %s / %s",
                    member.relation, age, rc.insurer_name, plan
                )
                continue

            # Apply family discount
            discount = _family_discount(member.relation)
            discounted = round(raw_premium * (1 - discount), 2)

            # DHA floor
            if discounted < _DHA_MINIMUM_PREMIUM:
                discounted = _DHA_MINIMUM_PREMIUM

            member_premiums.append({
                "member_id": member.member_id,
                "relation": member.relation,
                "name": member.full_name,
                "age": age,
                "raw_premium": raw_premium,
                "discount_pct": discount * 100,
                "premium": discounted,
            })
            base_total += discounted

        # Require pricing for at least the primary member
        if not member_premiums:
            return None

        admin = _admin_fee(base_total, rc.insurer_name)
        vat = round((base_total + admin) * 0.05, 2)

        quote = InsurancePlanQuote(
            insurer_name=rc.insurer_name,
            plan_name=plan,
            plan_type=_infer_plan_type(plan),
            network_type=_infer_network(plan),
            base_premium=round(base_total, 2),
            admin_fee=admin,
            vat=vat,
            source_file=rc.path.name,
            source_type="excel",
            member_premiums=member_premiums,
        )

        if missing:
            quote.notes = f"Note: {missing} member(s) could not be priced."

        return quote

    def _quote_from_manual(
        self,
        entry: dict,
        request: QuotationRequest,
    ) -> Optional[InsurancePlanQuote]:
        """Price all members from a manually entered rate."""
        member_premiums = []
        base_total = 0.0

        for member in request.members:
            age = member.age
            if age is None:
                continue

            raw_premium = _lookup_manual_premium(entry, age, member.gender)
            if raw_premium is None:
                continue

            discount = _family_discount(member.relation)
            discounted = round(raw_premium * (1 - discount), 2)
            if discounted < _DHA_MINIMUM_PREMIUM:
                discounted = _DHA_MINIMUM_PREMIUM

            member_premiums.append({
                "member_id": member.member_id,
                "relation": member.relation,
                "name": member.full_name,
                "age": age,
                "raw_premium": raw_premium,
                "discount_pct": discount * 100,
                "premium": discounted,
            })
            base_total += discounted

        if not member_premiums:
            return None

        admin = _admin_fee(base_total, entry.get("insurer_name", ""))
        vat = round((base_total + admin) * 0.05, 2)
        benefits = entry.get("benefits", {})

        return InsurancePlanQuote(
            insurer_name=entry.get("insurer_name", "Manual Entry"),
            plan_name=entry.get("plan_name", "Custom Plan"),
            plan_type=entry.get("plan_type", ""),
            network_type=entry.get("network_type", ""),
            base_premium=round(base_total, 2),
            admin_fee=admin,
            vat=vat,
            annual_limit=benefits.get("annual_limit", ""),
            room_board=benefits.get("room_board", ""),
            deductible=benefits.get("deductible", ""),
            copay=benefits.get("copay", ""),
            maternity_cover=benefits.get("maternity", ""),
            dental_cover=benefits.get("dental", ""),
            optical_cover=benefits.get("optical", ""),
            pre_existing_cover=benefits.get("pre_existing", ""),
            repatriation=benefits.get("repatriation", ""),
            outpatient_limit=benefits.get("outpatient_limit", ""),
            network_details=benefits.get("network_details", ""),
            source_type="manual",
            notes=entry.get("source_notes", ""),
            member_premiums=member_premiums,
        )


# ── Utility helpers ───────────────────────────────────────────────────────────
def _infer_plan_type(plan_name: str) -> str:
    low = plan_name.lower()
    if "basic" in low or "dha" in low or "essential" in low:
        return "Basic (DHA Compliant)"
    if "enhanced" in low or "standard" in low:
        return "Enhanced"
    if "comprehensive" in low or "comp" in low:
        return "Comprehensive"
    if "premium" in low or "silver" in low:
        return "Premium"
    if "executive" in low or "gold" in low or "platinum" in low:
        return "Executive"
    return "Enhanced"


def _infer_network(plan_name: str) -> str:
    low = plan_name.lower()
    if "int" in low and "usa" not in low:
        return "International (Excl. USA)"
    if "worldwide" in low or "usa" in low:
        return "Worldwide (Incl. USA)"
    if "gcc" in low:
        return "GCC"
    if "regional" in low or "middle east" in low:
        return "Regional (Middle East)"
    return "Local (UAE Only)"


def _lookup_manual_premium(entry: dict, age: int, gender: str) -> Optional[float]:
    """Resolve premium from a manual entry dict."""
    rates = entry.get("rates", [])
    for r in rates:
        lo = r.get("age_min", 0)
        hi = r.get("age_max", 999)
        entry_gender = r.get("gender", "Unisex")
        if lo <= age <= hi and entry_gender in (gender, "Unisex", ""):
            return r.get("premium")

    # Flat premium (applies to all members)
    if "annual_premium" in entry:
        return entry["annual_premium"]

    return None
