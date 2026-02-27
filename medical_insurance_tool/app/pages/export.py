"""
Export page – PDF report and JSON data export.
"""

from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path

import streamlit as st

from app.quotation.pdf_export import export_to_pdf, PDF_EXPORT_AVAILABLE


def page_export():
    st.header("Export")

    request = st.session_state.request

    if not request.members:
        st.warning("Add members and generate quotes before exporting.")
        return

    if not request.quotes:
        st.warning("Generate quotes first (Generate Quotes page).")
        return

    st.subheader("Quotation Summary")
    col1, col2, col3 = st.columns(3)
    col1.metric("Members", len(request.members))
    col2.metric("Quotes Generated", len(request.quotes))
    col3.metric(
        "Lowest Premium",
        f"AED {min(q.total_premium for q in request.quotes):,.2f}"
        if request.quotes else "—",
    )

    st.divider()
    st.subheader("Download Options")

    # ── PDF ───────────────────────────────────────────────────────────────────
    col_pdf, col_json = st.columns(2)

    with col_pdf:
        st.markdown("**PDF Quotation Report**")
        st.caption("A broker-ready PDF with member table, premium comparison and plan details.")

        if not PDF_EXPORT_AVAILABLE:
            st.error("fpdf2 is not installed. Run: `pip install fpdf2`")
        else:
            top_n = st.slider(
                "Include top N quotes in detail pages",
                min_value=1,
                max_value=min(10, len(request.quotes)),
                value=min(5, len(request.quotes)),
            )

            if st.button("Generate PDF", type="primary"):
                with st.spinner("Generating PDF…"):
                    with tempfile.TemporaryDirectory() as tmp_dir:
                        out_path = Path(tmp_dir) / f"quote_{request.broker_ref}_{date.today()}.pdf"
                        result = export_to_pdf(request, out_path)

                        if result and result.exists():
                            with open(result, "rb") as f:
                                pdf_bytes = f.read()

                st.success("PDF ready!")
                st.download_button(
                    label="Download PDF",
                    data=pdf_bytes,
                    file_name=f"quote_{request.broker_ref}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )

    with col_json:
        st.markdown("**JSON Data Export**")
        st.caption("Full quotation data as JSON – useful for integrating with other systems.")

        json_str = request.to_json()
        st.download_button(
            label="Download JSON",
            data=json_str,
            file_name=f"quote_{request.broker_ref}.json",
            mime="application/json",
            use_container_width=True,
        )

        with st.expander("Preview JSON"):
            st.code(json_str[:3000], language="json")

    st.divider()

    # ── Print-friendly table ──────────────────────────────────────────────────
    st.subheader("Quick Print View")
    st.caption("Copy this table for quick sharing via email or chat.")

    import pandas as pd
    rows = []
    for i, q in enumerate(request.quotes, 1):
        rows.append({
            "Rank": i,
            "Insurer": q.insurer_name,
            "Plan": q.plan_name,
            "Type": q.plan_type,
            "Network": q.network_type,
            "Base (AED)": f"{q.base_premium:,.2f}",
            "VAT (AED)": f"{q.vat_amount:,.2f}",
            "Total (AED)": f"{q.total_premium:,.2f}",
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
