"""
Generate & compare quotes page.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st


def _premium_chart(quotes):
    """Bar chart of top quotes by total premium."""
    try:
        import plotly.graph_objects as go

        labels = [f"{q.insurer_name}\n{q.plan_name}" for q in quotes[:12]]
        totals = [q.total_premium for q in quotes[:12]]
        colors = ["#00994C"] + ["#00529B"] * (len(totals) - 1)

        fig = go.Figure(
            go.Bar(
                x=labels,
                y=totals,
                marker_color=colors,
                text=[f"AED {t:,.0f}" for t in totals],
                textposition="outside",
            )
        )
        fig.update_layout(
            title="Annual Premium Comparison (AED) – Top 12",
            yaxis_title="Total Annual Premium (AED)",
            height=400,
            margin=dict(t=50, b=80),
            plot_bgcolor="white",
        )
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        st.info("Install plotly for interactive charts: `pip install plotly`")


def _quote_card(q, rank: int):
    """Render a single quote card."""
    is_best = rank == 1
    border = "2px solid #00994C" if is_best else "1px solid #ddd"
    bg = "#f0fff5" if is_best else "white"
    badge = "🏆 Best Price" if is_best else f"#{rank}"

    st.markdown(
        f"""
        <div style='border:{border};background:{bg};border-radius:8px;
                    padding:1rem;margin-bottom:0.6rem;'>
            <div style='display:flex;justify-content:space-between;align-items:center;'>
                <div>
                    <strong style='font-size:1.05rem;'>{q.insurer_name}</strong>
                    &nbsp;·&nbsp; {q.plan_name}
                    <br><small>{q.plan_type} &nbsp;|&nbsp; {q.network_type}</small>
                </div>
                <div style='text-align:right;'>
                    <span style='font-size:1.4rem;font-weight:700;
                                 color:{"#00994C" if is_best else "#00529B"};'>
                        AED {q.total_premium:,.2f}
                    </span><br>
                    <small>per year &nbsp; {badge}</small>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander(f"Details – {q.insurer_name} / {q.plan_name}"):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Base Premium", f"AED {q.base_premium:,.2f}")
            st.metric("Admin Fee", f"AED {q.admin_fee:,.2f}")
            st.metric("VAT (5%)", f"AED {q.vat_amount:,.2f}")
            st.metric("Total Annual", f"AED {q.total_premium:,.2f}")

        with col2:
            benefits = {
                "Annual Limit": q.annual_limit,
                "Room & Board": q.room_board,
                "Deductible": q.deductible,
                "Co-pay": q.copay,
                "Outpatient Limit": q.outpatient_limit,
            }
            for label, val in benefits.items():
                if val:
                    st.markdown(f"**{label}:** {val}")

        with col3:
            benefits2 = {
                "Maternity": q.maternity_cover,
                "Dental": q.dental_cover,
                "Optical": q.optical_cover,
                "Pre-existing": q.pre_existing_cover,
                "Repatriation": q.repatriation,
                "Network": q.network_details,
            }
            for label, val in benefits2.items():
                if val:
                    st.markdown(f"**{label}:** {val}")

        if q.member_premiums:
            st.markdown("**Per-Member Breakdown:**")
            mp_df = pd.DataFrame(q.member_premiums)[
                ["relation", "name", "age", "raw_premium", "discount_pct", "premium"]
            ].rename(columns={
                "relation": "Relation",
                "name": "Name",
                "age": "Age",
                "raw_premium": "Base Rate (AED)",
                "discount_pct": "Discount %",
                "premium": "Premium (AED)",
            })
            mp_df["Base Rate (AED)"] = mp_df["Base Rate (AED)"].map(lambda x: f"{x:,.2f}")
            mp_df["Premium (AED)"] = mp_df["Premium (AED)"].map(lambda x: f"{x:,.2f}")
            mp_df["Discount %"] = mp_df["Discount %"].map(lambda x: f"{x:.0f}%")
            st.dataframe(mp_df, use_container_width=True, hide_index=True)

        if q.notes:
            st.caption(f"Notes: {q.notes}")
        st.caption(f"Source: {q.source_file or q.source_type}")


def _comparison_table(quotes):
    """Side-by-side comparison table for all quotes."""
    rows = []
    for q in quotes:
        rows.append({
            "Insurer": q.insurer_name,
            "Plan": q.plan_name,
            "Type": q.plan_type,
            "Network": q.network_type,
            "Base (AED)": f"{q.base_premium:,.2f}",
            "VAT (AED)": f"{q.vat_amount:,.2f}",
            "Total (AED)": f"{q.total_premium:,.2f}",
            "Source": q.source_type,
        })
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Download CSV
        csv = df.to_csv(index=False)
        st.download_button(
            "Download CSV",
            data=csv,
            file_name=f"quotes_{st.session_state.request.broker_ref}.csv",
            mime="text/csv",
        )


# ── Main page ─────────────────────────────────────────────────────────────────
def page_quotes():
    st.header("Generate & Compare Quotes")

    request = st.session_state.request
    engine = st.session_state.engine

    # Pre-flight checks
    if not request.members:
        st.warning("Please add at least one member first (Members & Documents).")
        return

    # ── Filter controls ───────────────────────────────────────────────────────
    with st.expander("Filter options", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            max_premium = st.number_input(
                "Max total annual premium (AED, 0 = no limit)",
                min_value=0.0, step=500.0, value=0.0,
            )
        with col2:
            filter_source = st.multiselect(
                "Show sources",
                options=["excel", "manual"],
                default=["excel", "manual"],
            )

    # ── Generate ──────────────────────────────────────────────────────────────
    col_gen, col_info = st.columns([1, 3])
    with col_gen:
        if st.button("Generate Quotes", type="primary", use_container_width=True):
            with st.spinner("Calculating quotes from all rate sources…"):
                quotes = engine.generate_quotes(request)
            if quotes:
                st.success(f"Generated **{len(quotes)}** quote(s).")
            else:
                st.warning(
                    "No quotes could be generated. "
                    "Please upload rate cards or add manual entries first."
                )
    with col_info:
        st.caption(
            f"Members: {len(request.members)}  |  "
            f"Rate cards: {engine.rate_card_count}  |  "
            f"Manual entries: {len(engine._manual_entries)}"
        )

    quotes = request.quotes

    # Apply filters
    if filter_source:
        quotes = [q for q in quotes if q.source_type in filter_source]
    if max_premium > 0:
        quotes = [q for q in quotes if q.total_premium <= max_premium]

    if not quotes:
        if request.quotes:
            st.info("No quotes match the current filter settings.")
        return

    st.divider()

    # ── Tabs: cards / chart / table ───────────────────────────────────────────
    tabs = st.tabs(["Quote Cards", "Chart", "Comparison Table"])

    with tabs[0]:
        st.caption(
            f"Showing **{len(quotes)}** quote(s), sorted by total annual premium."
        )
        for i, q in enumerate(quotes, 1):
            _quote_card(q, rank=i)

    with tabs[1]:
        _premium_chart(quotes)

    with tabs[2]:
        _comparison_table(quotes)
