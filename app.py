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
from moneytwin.views.common import inject_theme, page_header


# ============================================================
# MONEYTWIN UI THEME (all styles live in moneytwin/views/common.py)
# ============================================================

def apply_theme():
    inject_theme()


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

PAGE_ICONS = {
    "Overview": "🏠",
    "Money leaks": "💸",
    "Behaviour and prediction": "📈",
    "What-if simulator": "🔮",
    "Privacy and data": "🔒",
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

def sidebar_heading(text: str) -> None:
    st.sidebar.markdown(f'<div class="mt-side-h">{text}</div>', unsafe_allow_html=True)


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

    # Sidebar brand
    st.sidebar.markdown(
        '<div class="mt-brand"><div class="mt-brand-name">💰 MoneyTwin</div>'
        '<div class="mt-brand-tag">Your personal spending twin</div></div>',
        unsafe_allow_html=True,
    )

    # Data source
    sidebar_heading("Data source")

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
            page_header("Get started", "MoneyTwin", "Upload your transactions to build your spending twin.")

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

    sidebar_heading("Your plan")

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
    sidebar_heading("Dashboard")

    page = st.sidebar.radio(
        "Go to",
        list(PAGES),
        key="page",
        label_visibility="collapsed",
        format_func=lambda name: f"{PAGE_ICONS.get(name, '')}  {name}",
    )

    # Sidebar status: which data the twin is using right now
    st.sidebar.markdown(
        f'<div class="mt-side-note">🔒 <b>{len(allowed)} of {len(ALL_CATEGORIES)}</b> data categories in use.'
        "<br>Change this any time in Privacy and data.</div>",
        unsafe_allow_html=True,
    )

    # Render selected page
    PAGES[page].render(twin, store)


# ============================================================
# RUN
# ============================================================

main()
