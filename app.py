"""MoneyTwin: a digital twin that shows where your money leaks. Run with: streamlit run app.py"""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from moneytwin import synthetic
from moneytwin.config import ALL_CATEGORIES, data_dir
from moneytwin.consent import usage_entry
from moneytwin.pipeline import build_twin
from moneytwin.twin_store import TwinStore
from moneytwin.views import behaviour_view, leaks_view, overview, privacy, whatif


# ============================================================
# MONEYTWIN UI THEME
# ============================================================

def apply_theme():
    st.markdown(
        """
        <style>

        /* ================================
           MAIN APP
        ================================= */

        .stApp {
            background: #f7f8fa;
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            max-width: 1400px;
        }


        /* ================================
           SIDEBAR
        ================================= */

        section[data-testid="stSidebar"] {
            background: #111827;
            border-right: 1px solid #1f2937;
        }

        section[data-testid="stSidebar"] * {
            color: #f9fafb;
        }

        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3 {
            color: #ffffff;
        }

        section[data-testid="stSidebar"] .stCaption {
            color: #9ca3af;
        }

        /* Sidebar radio buttons */

        section[data-testid="stSidebar"]
        div[role="radiogroup"] label {
            border-radius: 10px;
            padding: 8px 10px;
            margin: 3px 0;
            transition: all 0.2s ease;
        }

        section[data-testid="stSidebar"]
        div[role="radiogroup"] label:hover {
            background: #1f2937;
        }


        /* ================================
           HEADINGS
        ================================= */

        h1 {
            color: #111827;
            font-weight: 750;
            letter-spacing: -0.5px;
        }

        h2 {
            color: #111827;
            font-weight: 700;
        }

        h3 {
            color: #1f2937;
            font-weight: 650;
        }


        /* ================================
           METRIC CARDS
        ================================= */

        div[data-testid="stMetric"] {
            background: #ffffff;
            padding: 18px;
            border-radius: 14px;
            border: 1px solid #e5e7eb;
            box-shadow: 0 3px 12px rgba(0, 0, 0, 0.04);
        }

        div[data-testid="stMetricLabel"] {
            color: #6b7280;
            font-size: 0.9rem;
        }

        div[data-testid="stMetricValue"] {
            color: #111827;
            font-weight: 750;
        }


        /* ================================
           BUTTONS
        ================================= */

        .stButton > button {
            border-radius: 10px;
            font-weight: 600;
            border: 1px solid #d1d5db;
            padding: 8px 18px;
            transition: all 0.2s ease;
        }

        .stButton > button:hover {
            border-color: #111827;
            transform: translateY(-1px);
        }


        /* ================================
           FILE UPLOADER
        ================================= */

        [data-testid="stFileUploader"] {
            background: #ffffff;
            border-radius: 12px;
            padding: 8px;
            border: 1px solid #e5e7eb;
        }


        /* ================================
           INPUTS
        ================================= */

        div[data-baseweb="input"] {
            border-radius: 9px;
        }

        div[data-baseweb="select"] {
            border-radius: 9px;
        }


        /* ================================
           EXPANDERS
        ================================= */

        [data-testid="stExpander"] {
            border-radius: 12px;
            border: 1px solid #e5e7eb;
            background: #ffffff;
        }


        /* ================================
           DATA TABLES
        ================================= */

        [data-testid="stDataFrame"] {
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid #e5e7eb;
        }


        /* ================================
           ALERTS
        ================================= */

        div[data-testid="stAlert"] {
            border-radius: 12px;
        }


        /* ================================
           DIVIDERS
        ================================= */

        hr {
            border-color: #e5e7eb;
        }


        /* ================================
           SLIDERS
        ================================= */

        div[data-testid="stSlider"] {
            padding: 5px 0;
        }


        /* ================================
           CHECKBOXES
        ================================= */

        div[data-testid="stCheckbox"] {
            padding: 2px 0;
        }


        /* ================================
           REMOVE EXTRA TOP SPACE
        ================================= */

        header[data-testid="stHeader"] {
            background: transparent;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# PAGES
# ============================================================

PAGES = {
    "Overview": overview,
    "Money leaks": leaks_view,
    "Behaviour and prediction": behaviour_view,
    "What-if simulator": whatif,
    "Privacy and data": privacy,
}


# ============================================================
# DEMO DATA
# ============================================================

def load_demo() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Read the synthetic demo files, generating them first if they are missing."""
    folder = data_dir()

    if not (folder / "transactions.csv").exists():
        synthetic.write_files(folder)

    return (
        pd.read_csv(folder / "transactions.csv"),
        pd.read_csv(folder / "returns.csv"),
        pd.read_csv(folder / "autopay.csv"),
        json.loads((folder / "user_profile.json").read_text()),
    )


# ============================================================
# CSV UPLOAD
# ============================================================

def read_upload(file) -> pd.DataFrame | None:
    return pd.read_csv(file) if file is not None else None


# ============================================================
# SIDEBAR
# ============================================================

def sidebar_inputs(store: TwinStore):
    """Choose data and set goals. Returns raw tables and the profile,
    or stops the app with a clear message.
    """

    if st.session_state.pop("_reset", False):
        for k in list(st.session_state.keys()):
            if k.startswith(
                ("allow_", "rp_", "lbl_", "del_", "up_")
            ) or k in (
                "allowance",
                "payday",
                "goal",
                "last_plan",
                "consent",
            ):
                st.session_state.pop(k, None)

    # Sidebar title
    st.sidebar.markdown(
        """
        <div style="
            padding: 8px 0 18px 0;
            border-bottom: 1px solid #374151;
            margin-bottom: 18px;
        ">
            <div style="
                font-size: 26px;
                font-weight: 800;
                color: white;
                letter-spacing: -0.5px;
            ">
                💰 MoneyTwin
            </div>

            <div style="
                font-size: 12px;
                color: #9ca3af;
                margin-top: 4px;
            ">
                Your personal spending twin
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Data source
    st.sidebar.markdown(
        '<div style="color:#d1d5db;font-size:13px;font-weight:600;'
        'margin-bottom:5px;">DATA SOURCE</div>',
        unsafe_allow_html=True,
    )

    source = st.sidebar.radio(
        "Data source",
        ["Demo data (synthetic)", "Upload my CSV files"],
        key="source",
        label_visibility="collapsed",
    )

    if source.startswith("Demo"):

        tx, ret, ap, profile = load_demo()

    else:

        st.sidebar.caption(
            "Files stay in this session. Nothing is sent to a bank or shop."
        )

        tx = read_upload(
            st.sidebar.file_uploader(
                "Transactions CSV (required)",
                type=["csv"],
                key="up_tx",
            )
        )

        ret = read_upload(
            st.sidebar.file_uploader(
                "Returns CSV (optional)",
                type=["csv"],
                key="up_ret",
            )
        )

        ap = read_upload(
            st.sidebar.file_uploader(
                "Autopay CSV (optional)",
                type=["csv"],
                key="up_ap",
            )
        )

        profile = {
            "monthly_allowance": 15000,
            "payday_day": 1,
            "monthly_savings_goal": 2000,
        }

        if tx is None:
            st.title("MoneyTwin")

            st.info(
                "Upload a transactions CSV with at least: "
                "order_id, date, merchant, total. "
                "Optional: time, category, item_amount, delivery_fee, "
                "platform_fee, handling_fee, surge_fee."
            )

            st.stop()

    # User plan
    defaults = dict(profile)
    saved = {**defaults, **store.profile}

    st.sidebar.markdown(
        """
        <div style="
            margin-top: 22px;
            margin-bottom: 8px;
            color: #d1d5db;
            font-size: 13px;
            font-weight: 600;
        ">
            YOUR PLAN
        </div>
        """,
        unsafe_allow_html=True,
    )

    profile = {
        "monthly_allowance": st.sidebar.number_input(
            "Monthly allowance (Rs.)",
            min_value=1000,
            max_value=500000,
            value=int(saved["monthly_allowance"]),
            step=500,
            key="allowance",
        ),

        "payday_day": st.sidebar.number_input(
            "Money arrives on day",
            min_value=1,
            max_value=28,
            value=int(saved["payday_day"]),
            key="payday",
        ),

        "monthly_savings_goal": st.sidebar.number_input(
            "Monthly savings goal (Rs.)",
            min_value=0,
            max_value=200000,
            value=int(saved["monthly_savings_goal"]),
            step=250,
            key="goal",
        ),
    }

    if profile != {k: saved[k] for k in profile}:
        store.set_profile(profile)

    return source, tx, ret, ap, profile


# ============================================================
# MAIN APPLICATION
# ============================================================

def main() -> None:

    st.set_page_config(
        page_title="MoneyTwin",
        page_icon="💰",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Apply UI theme
    apply_theme()

    # Session store
    if "store" not in st.session_state:
        st.session_state["store"] = TwinStore()

    store = st.session_state["store"]

    # Sidebar + data
    source, tx, ret, ap, profile = sidebar_inputs(store)

    # Consent
    consent = st.session_state.get("consent", {})

    allowed = [
        c
        for c in ALL_CATEGORIES
        if st.session_state.get(
            f"allow_{c}",
            consent.get(c, True),
        )
    ]

    # Build twin
    try:

        twin = build_twin(
            tx,
            ret,
            ap,
            profile,
            store,
            allowed,
        )

    except ValueError as err:

        st.error(str(err))
        st.stop()

    # Usage logging
    signature = (
        source,
        tuple(allowed),
        len(tx),
    )

    if st.session_state.get("usage_sig") != signature:

        store.log_usage(
            usage_entry(
                source,
                allowed,
                len(twin.tx),
            )
        )

        st.session_state["usage_sig"] = signature

    # Navigation
    st.sidebar.markdown(
        """
        <div style="
            margin-top: 28px;
            margin-bottom: 8px;
            color: #d1d5db;
            font-size: 13px;
            font-weight: 600;
        ">
            DASHBOARD
        </div>
        """,
        unsafe_allow_html=True,
    )

    page = st.sidebar.radio(
        "Go to",
        list(PAGES),
        key="page",
        label_visibility="collapsed",
    )

    # Render selected page
    PAGES[page].render(twin, store)


# ============================================================
# RUN
# ============================================================

main()