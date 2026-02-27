"""
Data models for applicants and insurance quotes.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
import json


def _today() -> date:
    return date.today()


@dataclass
class FamilyMember:
    """Represents a single insured person."""

    relation: str
    first_name: str = ""
    last_name: str = ""
    dob: Optional[date] = None
    gender: str = ""
    nationality: str = ""
    marital_status: str = ""
    visa_issuing_emirate: str = ""

    # Populated after OCR or manual entry
    passport_number: str = ""
    emirates_id: str = ""
    visa_number: str = ""

    # Internal
    member_id: int = 0

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or "—"

    @property
    def age(self) -> Optional[int]:
        if self.dob is None:
            return None
        today = _today()
        return (
            today.year
            - self.dob.year
            - ((today.month, today.day) < (self.dob.month, self.dob.day))
        )

    def age_band(self) -> str:
        """Return age-band label (e.g. '25-29') for rate lookups."""
        from config import AGE_BANDS

        a = self.age
        if a is None:
            return "Unknown"
        for lo, hi, label in AGE_BANDS:
            if lo <= a <= hi:
                return label
        return "Unknown"

    def to_dict(self) -> dict:
        return {
            "member_id": self.member_id,
            "relation": self.relation,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "dob": self.dob.isoformat() if self.dob else None,
            "age": self.age,
            "age_band": self.age_band(),
            "gender": self.gender,
            "nationality": self.nationality,
            "marital_status": self.marital_status,
            "visa_issuing_emirate": self.visa_issuing_emirate,
            "passport_number": self.passport_number,
            "emirates_id": self.emirates_id,
            "visa_number": self.visa_number,
        }


@dataclass
class InsurancePlanQuote:
    """A single insurer's quote for the full family group."""

    insurer_name: str
    plan_name: str
    plan_type: str
    network_type: str

    # Premiums (AED)
    base_premium: float = 0.0
    admin_fee: float = 0.0
    vat: float = 0.0          # 5% VAT in UAE

    # Benefits summary (AED unless noted)
    annual_limit: str = ""
    room_board: str = ""
    deductible: str = ""
    copay: str = ""
    maternity_cover: str = ""
    dental_cover: str = ""
    optical_cover: str = ""
    pre_existing_cover: str = ""
    repatriation: str = ""
    outpatient_limit: str = ""
    network_details: str = ""

    # Source metadata
    source_file: str = ""
    source_type: str = ""     # 'excel', 'rate_card', 'manual', 'website'
    quote_date: date = field(default_factory=_today)
    notes: str = ""

    # Per-member breakdown
    member_premiums: list = field(default_factory=list)

    @property
    def total_premium(self) -> float:
        return self.base_premium + self.admin_fee + self.vat

    @property
    def vat_amount(self) -> float:
        return round((self.base_premium + self.admin_fee) * 0.05, 2)

    def to_dict(self) -> dict:
        return {
            "insurer_name": self.insurer_name,
            "plan_name": self.plan_name,
            "plan_type": self.plan_type,
            "network_type": self.network_type,
            "base_premium": round(self.base_premium, 2),
            "admin_fee": round(self.admin_fee, 2),
            "vat": round(self.vat_amount, 2),
            "total_premium": round(self.total_premium, 2),
            "annual_limit": self.annual_limit,
            "room_board": self.room_board,
            "deductible": self.deductible,
            "copay": self.copay,
            "maternity_cover": self.maternity_cover,
            "dental_cover": self.dental_cover,
            "optical_cover": self.optical_cover,
            "pre_existing_cover": self.pre_existing_cover,
            "repatriation": self.repatriation,
            "outpatient_limit": self.outpatient_limit,
            "network_details": self.network_details,
            "source_file": self.source_file,
            "source_type": self.source_type,
            "quote_date": self.quote_date.isoformat(),
            "notes": self.notes,
            "member_premiums": self.member_premiums,
        }


@dataclass
class QuotationRequest:
    """A full quotation request containing all family members."""

    broker_ref: str = ""
    members: list = field(default_factory=list)  # list[FamilyMember]
    quotes: list = field(default_factory=list)    # list[InsurancePlanQuote]
    created_at: datetime = field(default_factory=datetime.now)

    def add_member(self, member: FamilyMember):
        member.member_id = len(self.members) + 1
        self.members.append(member)

    def remove_member(self, member_id: int):
        self.members = [m for m in self.members if m.member_id != member_id]

    def get_primary(self) -> Optional[FamilyMember]:
        for m in self.members:
            if m.relation == "Self":
                return m
        return self.members[0] if self.members else None

    def family_summary(self) -> str:
        if not self.members:
            return "No members added"
        return ", ".join(
            f"{m.relation} ({m.age or '?'}y)" for m in self.members
        )

    def to_dict(self) -> dict:
        return {
            "broker_ref": self.broker_ref,
            "created_at": self.created_at.isoformat(),
            "members": [m.to_dict() for m in self.members],
            "quotes": [q.to_dict() for q in self.quotes],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
