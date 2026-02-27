"""
Members & Documents page.

Allows the user to:
  1. Upload and OCR-scan a document (passport, Emirates ID, visa)
  2. Manually enter or edit member details
  3. Add multiple family members to the quotation request
"""

from __future__ import annotations

import io
import tempfile
from datetime import date
from pathlib import Path

import streamlit as st

from app.models import FamilyMember
from app.ocr import process_document, OCR_AVAILABLE
from app.utils import validate_emirates_id, validate_passport_number
from config import (
    FAMILY_RELATIONS, GENDERS, MARITAL_STATUSES, NATIONALITIES,
    UAE_EMIRATES, SUPPORTED_DOC_TYPES, UPLOADS_DIR,
)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _date_input_safe(label: str, value=None, key: str = "") -> date | None:
    """Date input that accepts None as an empty default."""
    default = value if isinstance(value, date) else date(1990, 1, 1)
    result = st.date_input(
        label,
        value=default,
        min_value=date(1920, 1, 1),
        max_value=date.today(),
        key=key,
        format="DD/MM/YYYY",
    )
    return result


def _member_form(
    prefix: str,
    prefill: dict | None = None,
    relation_default: str = "Self",
) -> FamilyMember | None:
    """Render the member detail form. Returns FamilyMember or None if cancelled."""
    pre = prefill or {}

    col1, col2 = st.columns(2)
    with col1:
        relation = st.selectbox(
            "Family Relation *",
            FAMILY_RELATIONS,
            index=FAMILY_RELATIONS.index(relation_default)
            if relation_default in FAMILY_RELATIONS
            else 0,
            key=f"{prefix}_relation",
        )
        first_name = st.text_input(
            "First Name *",
            value=pre.get("first_name", ""),
            key=f"{prefix}_first",
        )
        gender_idx = GENDERS.index(pre["gender"]) if pre.get("gender") in GENDERS else 0
        gender = st.selectbox("Gender *", GENDERS, index=gender_idx, key=f"{prefix}_gender")

        nat_idx = NATIONALITIES.index(pre["nationality"]) if pre.get("nationality") in NATIONALITIES else len(NATIONALITIES) - 1
        nationality = st.selectbox(
            "Nationality *",
            NATIONALITIES,
            index=nat_idx,
            key=f"{prefix}_nat",
        )

    with col2:
        last_name = st.text_input(
            "Last Name",
            value=pre.get("last_name", ""),
            key=f"{prefix}_last",
        )
        dob = _date_input_safe("Date of Birth *", value=pre.get("dob"), key=f"{prefix}_dob")

        ms_idx = MARITAL_STATUSES.index(pre["marital_status"]) if pre.get("marital_status") in MARITAL_STATUSES else 0
        marital_status = st.selectbox(
            "Marital Status",
            MARITAL_STATUSES,
            index=ms_idx,
            key=f"{prefix}_ms",
        )

        em_idx = UAE_EMIRATES.index(pre["visa_issuing_emirate"]) if pre.get("visa_issuing_emirate") in UAE_EMIRATES else 0
        visa_emirate = st.selectbox(
            "Visa Issuing Emirate",
            UAE_EMIRATES,
            index=em_idx,
            key=f"{prefix}_emirate",
        )

    with st.expander("Document Numbers (optional)"):
        col3, col4, col5 = st.columns(3)
        with col3:
            passport_no = st.text_input(
                "Passport No.",
                value=pre.get("passport_number", ""),
                key=f"{prefix}_pp",
            )
            if passport_no and not validate_passport_number(passport_no):
                st.warning("Passport number format looks unusual.")
        with col4:
            eid = st.text_input(
                "Emirates ID",
                value=pre.get("emirates_id", ""),
                placeholder="784-YYYY-NNNNNNN-C",
                key=f"{prefix}_eid",
            )
            if eid and not validate_emirates_id(eid):
                st.warning("Emirates ID format: 784-YYYY-NNNNNNN-C")
        with col5:
            visa_no = st.text_input(
                "Visa / File No.",
                value=pre.get("visa_number", ""),
                key=f"{prefix}_visa",
            )

    # Validate required fields
    if not first_name:
        st.error("First name is required.")
        return None

    member = FamilyMember(
        relation=relation,
        first_name=first_name.strip().title(),
        last_name=last_name.strip().title(),
        dob=dob,
        gender=gender,
        nationality=nationality,
        marital_status=marital_status,
        visa_issuing_emirate=visa_emirate,
        passport_number=passport_no.strip(),
        emirates_id=eid.strip(),
        visa_number=visa_no.strip(),
    )
    return member


# ── OCR Section ───────────────────────────────────────────────────────────────
def _ocr_section() -> dict:
    """Upload & OCR a document. Returns extracted data dict."""
    st.subheader("Scan Document (OCR)")

    if not OCR_AVAILABLE:
        st.warning(
            "OCR libraries are not installed. "
            "Install them with: `pip install pytesseract opencv-python-headless`  \n"
            "You also need **Tesseract OCR** installed on your system  \n"
            "  - Ubuntu/Debian: `sudo apt-get install tesseract-ocr`  \n"
            "  - macOS: `brew install tesseract`  \n"
            "  - Windows: download from https://github.com/UB-Mannheim/tesseract/wiki  \n"
            "\nFor now, please **enter member details manually** below."
        )
        return {}

    col1, col2 = st.columns([2, 1])
    with col1:
        uploaded = st.file_uploader(
            "Upload document image or PDF",
            type=["jpg", "jpeg", "png", "bmp", "tiff", "pdf"],
            help="Supports passport, Emirates ID, or UAE visa copy",
        )
    with col2:
        doc_type = st.selectbox(
            "Document Type",
            ["auto"] + SUPPORTED_DOC_TYPES,
            format_func=lambda x: "Auto-detect" if x == "auto" else x,
        )

    if uploaded is None:
        return {}

    with st.spinner("Processing document…"):
        # Save to temp file
        suffix = Path(uploaded.name).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name

        result = process_document(tmp_path, doc_type=doc_type)

    # Show image preview
    if suffix.lower() != ".pdf":
        st.image(tmp_path, caption=f"Uploaded: {uploaded.name}", width=400)

    # Show OCR result
    confidence = result.get("confidence", 0)
    if confidence >= 70:
        st.success(f"OCR completed — confidence: **{confidence}%**")
    elif confidence >= 40:
        st.warning(f"OCR partially successful — confidence: **{confidence}%**. Please review fields below.")
    else:
        st.error(f"Low OCR confidence: **{confidence}%**. Please enter details manually.")

    if result.get("warnings"):
        for w in result["warnings"]:
            st.info(w)

    # Show raw OCR text in expander
    if result.get("raw_text"):
        with st.expander("Raw OCR text (for debugging)"):
            st.text(result["raw_text"][:2000])

    return result


# ── Members table ─────────────────────────────────────────────────────────────
def _render_members_table(request):
    if not request.members:
        st.info("No members added yet. Use the form below to add the first member.")
        return

    import pandas as pd
    rows = []
    for m in request.members:
        rows.append({
            "#": m.member_id,
            "Relation": m.relation,
            "Name": m.full_name,
            "DOB": m.dob.strftime("%d/%m/%Y") if m.dob else "—",
            "Age": m.age or "?",
            "Gender": m.gender,
            "Nationality": m.nationality,
            "Emirate": m.visa_issuing_emirate,
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Delete button per member
    st.caption("To remove a member:")
    del_col1, del_col2 = st.columns([1, 3])
    with del_col1:
        del_id = st.number_input(
            "Member # to remove",
            min_value=1,
            max_value=max(m.member_id for m in request.members),
            step=1,
            key="del_member_id",
        )
    with del_col2:
        st.write("")
        st.write("")
        if st.button("Remove Member", type="secondary"):
            request.remove_member(int(del_id))
            st.success(f"Member #{del_id} removed.")
            st.rerun()


# ── Main page ─────────────────────────────────────────────────────────────────
def page_members():
    st.header("Members & Documents")

    request = st.session_state.request

    # ── Current members ───────────────────────────────────────────────────────
    with st.container():
        st.subheader("Current Members")
        _render_members_table(request)

    st.divider()

    # ── Add new member ────────────────────────────────────────────────────────
    st.subheader("Add Member")

    tabs = st.tabs(["Scan Document (OCR)", "Enter Manually"])

    ocr_data: dict = {}

    with tabs[0]:
        ocr_data = _ocr_section()
        if ocr_data:
            st.info(
                "Fields extracted from the document are pre-filled below. "
                "Please review and correct before adding."
            )

    with tabs[1]:
        st.caption("Fill in all required (*) fields manually.")

    # Always show member form (pre-filled from OCR if available)
    st.divider()
    with st.form("add_member_form", clear_on_submit=True):
        # Suggest relation based on existing members
        default_relation = "Self" if not request.members else "Spouse"
        member = _member_form("new", prefill=ocr_data, relation_default=default_relation)
        submitted = st.form_submit_button("Add Member", type="primary", use_container_width=True)

    if submitted:
        if member is not None:
            request.add_member(member)
            st.success(
                f"Added: **{member.full_name}** ({member.relation}, age {member.age or '?'})"
            )
            st.rerun()

    # ── Summary ───────────────────────────────────────────────────────────────
    if request.members:
        st.divider()
        st.caption(
            f"**Family group:** {request.family_summary()}  |  "
            f"Ready to generate quotes — go to **Generate Quotes** in the sidebar."
        )
