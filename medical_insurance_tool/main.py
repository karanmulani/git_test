"""
UAE Medical Insurance Quotation Tool
Streamlit application entry point.

Run with:
    streamlit run main.py
"""

import sys
import os

# Ensure the tool root is on the path so all internal imports resolve
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st

from config import APP_TITLE, APP_ICON, VERSION
from app.pages import (
    page_members,
    page_rate_cards,
    page_quotes,
    page_export,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .main-header {
        background: linear-gradient(90deg, #00529B 0%, #0077CC 100%);
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    .main-header h1 { color: white; margin: 0; font-size: 1.6rem; }
    .main-header p  { color: #d0e8ff; margin: 0; font-size: 0.85rem; }

    .metric-card {
        background: #f0f8ff;
        border: 1px solid #cce0ff;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        text-align: center;
    }
    .quote-card {
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 0.5rem;
    }
    .quote-card-best {
        border: 2px solid #00994C;
        background: #f0fff5;
    }
    .stTabs [data-baseweb="tab"] { font-size: 1rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session state bootstrap ───────────────────────────────────────────────────
if "request" not in st.session_state:
    from app.models import QuotationRequest
    from app.utils import generate_broker_ref

    st.session_state.request = QuotationRequest(
        broker_ref=generate_broker_ref()
    )

if "engine" not in st.session_state:
    from app.quotation import QuotationEngine

    engine = QuotationEngine()
    engine.load_rate_cards()
    st.session_state.engine = engine

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f"""
        <div style='text-align:center;padding:0.5rem 0 1rem;'>
            <span style='font-size:2.5rem;'>🏥</span><br>
            <strong style='font-size:1.1rem;'>Insurance Quotation Tool</strong><br>
            <small style='color:#888;'>v{VERSION}</small>
        </div>
        """,
        unsafe_allow_html=True,
    )

    req = st.session_state.request
    st.info(f"**Ref:** {req.broker_ref}")
    st.caption(
        f"Members: **{len(req.members)}** | "
        f"Quotes: **{len(req.quotes)}**"
    )
    st.divider()

    nav = st.radio(
        "Navigation",
        options=["Members & Documents", "Rate Cards", "Generate Quotes", "Export"],
        index=0,
        label_visibility="collapsed",
    )

    st.divider()
    if st.button("New Quotation", use_container_width=True):
        from app.models import QuotationRequest
        from app.utils import generate_broker_ref
        st.session_state.request = QuotationRequest(broker_ref=generate_broker_ref())
        st.rerun()

    engine = st.session_state.engine
    card_count = engine.rate_card_count
    manual_count = len(engine._manual_entries)
    st.caption(
        f"Rate cards loaded: **{card_count}**\n\n"
        f"Manual entries: **{manual_count}**"
    )

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div class="main-header">
        <h1>{APP_ICON} UAE Medical Insurance Quotation Tool</h1>
        <p>Broker reference: {st.session_state.request.broker_ref}</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Route pages ───────────────────────────────────────────────────────────────
if nav == "Members & Documents":
    page_members()
elif nav == "Rate Cards":
    page_rate_cards()
elif nav == "Generate Quotes":
    page_quotes()
elif nav == "Export":
    page_export()
