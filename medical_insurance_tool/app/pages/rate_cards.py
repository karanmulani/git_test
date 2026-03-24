"""
Rate Cards management page.

Allows the broker to:
  1. Upload new Excel or PDF rate card files
  2. View loaded rate cards and their summaries
  3. Add manual rate entries (for rates received by email / quote sheet)
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from app.quotation import ExcelRateCard
from app.quotation.pdf_reader import read_pdf_rate_card, pdf_tables_to_excel
from config import RATE_CARDS_DIR, PLAN_TYPES, NETWORK_TYPES


# ── Upload Excel section ──────────────────────────────────────────────────────
def _upload_excel_section():
    st.subheader("Upload Rate Card (Excel)")
    st.caption(
        "Upload insurer Excel rate cards. Supported layouts: age-band matrix or member-list table."
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        uploaded = st.file_uploader(
            "Excel file (.xlsx / .xls)",
            type=["xlsx", "xls"],
            key="rate_card_upload",
        )
    with col2:
        insurer_name = st.text_input(
            "Insurer / Product Name",
            placeholder="e.g. Daman – Basic Network",
            key="excel_insurer_name",
        )
        sheet_name_input = st.text_input(
            "Sheet name (leave blank for first sheet)",
            placeholder="Sheet1",
        )

    if uploaded and st.button("Load Rate Card", type="primary", key="load_excel"):
        sheet = sheet_name_input.strip() or 0
        name = insurer_name.strip() or Path(uploaded.name).stem

        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name

        rc = ExcelRateCard(tmp_path, insurer_name=name, sheet_name=sheet)
        if rc.load():
            # Persist to rate_cards directory
            dest = RATE_CARDS_DIR / uploaded.name
            Path(tmp_path).rename(dest)
            rc.path = dest
            st.session_state.engine.add_rate_card(rc)
            st.success(
                f"Loaded **{name}**: {rc._layout} layout, "
                f"{len(rc.plans)} plan(s), {len(rc.all_rates())} rate rows."
            )
        else:
            st.error("Failed to parse the Excel file. Check the format and try again.")


# ── Upload PDF section ────────────────────────────────────────────────────────
def _upload_pdf_section():
    st.subheader("Upload Rate Card (PDF)")
    st.caption(
        "Upload insurer rate sheets, benefit tables, or quote PDFs. "
        "The tool extracts tables automatically from both digital and scanned PDFs."
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        uploaded_pdf = st.file_uploader(
            "PDF file",
            type=["pdf"],
            key="pdf_rate_upload",
        )
    with col2:
        pdf_insurer_name = st.text_input(
            "Insurer / Product Name",
            placeholder="e.g. Sukoon – Enhanced",
            key="pdf_insurer_name",
        )

    if uploaded_pdf and st.button("Extract from PDF", type="primary", key="load_pdf"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_pdf.read())
            tmp_path = tmp.name

        name = pdf_insurer_name.strip() or Path(uploaded_pdf.name).stem

        with st.spinner("Extracting tables from PDF..."):
            result = read_pdf_rate_card(tmp_path, insurer_name=name)

        # Show warnings
        for w in result.get("warnings", []):
            st.warning(w)

        tables = result.get("tables", [])
        method = result.get("method", "none")
        detected_name = result.get("insurer_name", name)

        if not tables:
            st.error(
                "No tables found in this PDF. Try one of these alternatives:\n"
                "- Upload the rates as Excel instead\n"
                "- Use the **Manual Entry** tab to enter rates by hand"
            )
            # Still show the extracted text so the broker can read the rates
            text = result.get("text", "")
            if text:
                with st.expander("Extracted text from PDF (for reference)"):
                    st.text(text[:5000])
            return

        st.success(
            f"Found **{len(tables)} table(s)** via {method}. "
            f"Detected insurer: **{detected_name}**"
        )

        # ── Preview each table ────────────────────────────────────────────────
        for i, df in enumerate(tables):
            st.markdown(f"**Table {i + 1}** ({len(df)} rows x {len(df.columns)} cols)")
            st.dataframe(df, use_container_width=True, hide_index=True)

        # ── Let the user pick which table to load as a rate card ──────────────
        st.divider()
        st.markdown("**Load a table as rate card:**")

        if len(tables) == 1:
            table_choice = 0
        else:
            table_choice = st.selectbox(
                "Select table to load",
                options=list(range(len(tables))),
                format_func=lambda i: f"Table {i + 1} ({len(tables[i])} rows)",
                key="pdf_table_choice",
            )

        if st.button("Load as Rate Card", type="primary", key="load_pdf_table"):
            # Convert the selected table to Excel, then load via ExcelRateCard
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_xl:
                xl_path = pdf_tables_to_excel([tables[table_choice]], tmp_xl.name)

            rc = ExcelRateCard(xl_path, insurer_name=detected_name)
            if rc.load():
                dest = RATE_CARDS_DIR / f"{detected_name.replace(' ', '_')}_from_pdf.xlsx"
                Path(xl_path).rename(dest)
                rc.path = dest
                st.session_state.engine.add_rate_card(rc)
                st.success(
                    f"Loaded **{detected_name}**: {rc._layout} layout, "
                    f"{len(rc.plans)} plan(s), {len(rc.all_rates())} rate rows."
                )
            else:
                st.warning(
                    "Could not auto-detect the rate structure from this table. "
                    "Try entering the rates via **Manual Entry** instead, "
                    "using the table preview above as reference."
                )

        # Show full text in expander
        text = result.get("text", "")
        if text:
            with st.expander("Full extracted text"):
                st.text(text[:5000])


# ── Loaded cards summary ───────────────────────────────────────────────────────
def _loaded_cards_section():
    st.subheader("Loaded Rate Cards")
    engine = st.session_state.engine

    if engine.rate_card_count == 0 and len(engine._manual_entries) == 0:
        st.info(
            "No rate cards loaded yet.  \n"
            "Upload an **Excel** or **PDF** file, or add rates via **Manual Entry**."
        )
        return

    if engine.rate_card_count > 0:
        summaries = engine.rate_card_summaries()
        df = pd.DataFrame(summaries).rename(columns={
            "insurer": "Insurer / Product",
            "file": "File",
            "layout": "Layout",
            "plans": "Plans",
            "rate_rows": "Rate Rows",
        })
        df["Plans"] = df["Plans"].apply(lambda p: ", ".join(p) if isinstance(p, list) else str(p))
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Show rate table for selected card
        if summaries:
            selected = st.selectbox(
                "Inspect rates for:",
                options=[s["insurer"] for s in summaries],
            )
            sel_card = next((c for c in engine._rate_cards if c.insurer_name == selected), None)
            if sel_card:
                rates = sel_card.all_rates()
                if rates:
                    with st.expander(f"Rate table: {selected} ({len(rates)} rows)"):
                        st.dataframe(pd.DataFrame(rates), use_container_width=True, hide_index=True)

    if engine._manual_entries:
        st.divider()
        st.caption(f"**{len(engine._manual_entries)}** manual rate entry/entries loaded.")
        for entry in engine._manual_entries:
            st.markdown(
                f"- **{entry['insurer_name']}** – {entry['plan_name']} "
                f"({len(entry.get('rates', []))} rate bands)"
            )


# ── Manual entry section ──────────────────────────────────────────────────────
def _manual_entry_section():
    st.subheader("Add Manual Rate Entry")
    st.caption(
        "Use this for rates received by email, WhatsApp, or verbal quote "
        "that are not in an Excel or PDF file."
    )

    with st.form("manual_rate_form"):
        col1, col2 = st.columns(2)
        with col1:
            insurer_name = st.text_input("Insurer / Product Name *", placeholder="e.g. Sukoon Basic")
            plan_name = st.text_input("Plan Name *", placeholder="e.g. Bronze Network")
            plan_type = st.selectbox("Plan Type", PLAN_TYPES)
            network_type = st.selectbox("Network Type", NETWORK_TYPES)
        with col2:
            source_notes = st.text_area("Source / Notes", placeholder="Received from XYZ on 01/01/2025")

        st.markdown("**Rate Bands** – enter annual premium (AED) per age group")
        st.caption("Leave blank to skip a band. Gender: Male / Female / Unisex")

        age_bands_defaults = [
            ("0", "17"), ("18", "24"), ("25", "29"), ("30", "34"),
            ("35", "39"), ("40", "44"), ("45", "49"), ("50", "54"),
            ("55", "59"), ("60", "64"), ("65", "69"), ("70", "99"),
        ]

        rate_bands = []
        for lo, hi in age_bands_defaults:
            bcol1, bcol2, bcol3, bcol4 = st.columns([1, 1, 1, 1])
            with bcol1:
                st.text(f"{lo}–{hi}")
            with bcol2:
                male_p = st.number_input(f"Male AED", min_value=0.0, step=10.0,
                                          key=f"m_{lo}_{hi}", label_visibility="collapsed")
            with bcol3:
                female_p = st.number_input(f"Female AED", min_value=0.0, step=10.0,
                                            key=f"f_{lo}_{hi}", label_visibility="collapsed")
            with bcol4:
                uni_p = st.number_input(f"Unisex AED", min_value=0.0, step=10.0,
                                         key=f"u_{lo}_{hi}", label_visibility="collapsed")
            if male_p > 0:
                rate_bands.append({"age_min": int(lo), "age_max": int(hi),
                                    "gender": "Male", "premium": male_p})
            if female_p > 0:
                rate_bands.append({"age_min": int(lo), "age_max": int(hi),
                                    "gender": "Female", "premium": female_p})
            if uni_p > 0:
                rate_bands.append({"age_min": int(lo), "age_max": int(hi),
                                    "gender": "Unisex", "premium": uni_p})

        st.markdown("**Key Benefits** (optional)")
        bcol1, bcol2, bcol3 = st.columns(3)
        with bcol1:
            annual_limit = st.text_input("Annual Limit", placeholder="AED 150,000")
            room_board = st.text_input("Room & Board", placeholder="Semi-private")
            deductible = st.text_input("Deductible", placeholder="AED 0 / AED 500")
        with bcol2:
            copay = st.text_input("Co-pay", placeholder="10% / AED 50")
            maternity = st.text_input("Maternity", placeholder="AED 10,000 normal")
            dental = st.text_input("Dental", placeholder="Basic / AED 1,500")
        with bcol3:
            optical = st.text_input("Optical", placeholder="AED 500 / Not covered")
            pre_existing = st.text_input("Pre-existing Conditions", placeholder="Covered after 6m")
            repatriation = st.text_input("Repatriation", placeholder="Included")

        submitted = st.form_submit_button("Save Manual Entry", type="primary", use_container_width=True)

    if submitted:
        if not insurer_name or not plan_name:
            st.error("Insurer name and plan name are required.")
        elif not rate_bands:
            st.error("Please enter at least one rate band.")
        else:
            entry = {
                "insurer_name": insurer_name,
                "plan_name": plan_name,
                "plan_type": plan_type,
                "network_type": network_type,
                "rates": rate_bands,
                "benefits": {
                    "annual_limit": annual_limit,
                    "room_board": room_board,
                    "deductible": deductible,
                    "copay": copay,
                    "maternity": maternity,
                    "dental": dental,
                    "optical": optical,
                    "pre_existing": pre_existing,
                    "repatriation": repatriation,
                },
                "source_notes": source_notes,
            }
            st.session_state.engine.add_manual_entry(entry)
            st.success(f"Saved: **{insurer_name} – {plan_name}** ({len(rate_bands)} rate bands)")


# ── Main page ─────────────────────────────────────────────────────────────────
def page_rate_cards():
    st.header("Rate Cards")

    tab1, tab2, tab3, tab4 = st.tabs(["Loaded Cards", "Upload Excel", "Upload PDF", "Manual Entry"])

    with tab1:
        _loaded_cards_section()

    with tab2:
        _upload_excel_section()

    with tab3:
        _upload_pdf_section()

    with tab4:
        _manual_entry_section()
