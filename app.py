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

PAGES = {"Overview": overview, "Money leaks": leaks_view, "Behaviour and prediction": behaviour_view,
         "What-if simulator": whatif, "Privacy and data": privacy}


def load_demo() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Read the synthetic demo files, generating them first if they are missing."""
    folder = data_dir()
    if not (folder / "transactions.csv").exists():
        synthetic.write_files(folder)
    return (pd.read_csv(folder / "transactions.csv"), pd.read_csv(folder / "returns.csv"),
            pd.read_csv(folder / "autopay.csv"), json.loads((folder / "user_profile.json").read_text()))


def read_upload(file) -> pd.DataFrame | None:
    return pd.read_csv(file) if file is not None else None


def sidebar_inputs(store: TwinStore):
    """Choose data and set goals. Returns raw tables and the profile, or stops the app with a clear message."""
    if st.session_state.pop("_reset", False):  # after 'Delete my data': forget widget choices before widgets are created
        for k in list(st.session_state.keys()):
            if k.startswith(("allow_", "rp_", "lbl_", "del_", "up_")) or k in ("allowance", "payday", "goal", "last_plan", "consent"):
                st.session_state.pop(k, None)
    st.sidebar.title("MoneyTwin")
    source = st.sidebar.radio("Data source", ["Demo data (synthetic)", "Upload my CSV files"], key="source")
    if source.startswith("Demo"):
        tx, ret, ap, profile = load_demo()
    else:
        st.sidebar.caption("Files stay in this session. Nothing is sent to a bank or shop.")
        tx = read_upload(st.sidebar.file_uploader("Transactions CSV (required)", type=["csv"], key="up_tx"))
        ret = read_upload(st.sidebar.file_uploader("Returns CSV (optional)", type=["csv"], key="up_ret"))
        ap = read_upload(st.sidebar.file_uploader("Autopay CSV (optional)", type=["csv"], key="up_ap"))
        profile = {"monthly_allowance": 15000, "payday_day": 1, "monthly_savings_goal": 2000}
        if tx is None:
            st.title("MoneyTwin")
            st.info("Upload a transactions CSV with at least: order_id, date, merchant, total. "
                    "Optional: time, category, item_amount, delivery_fee, platform_fee, handling_fee, surge_fee.")
            st.stop()
    defaults = dict(profile)
    saved = {**defaults, **store.profile}
    st.sidebar.subheader("Your plan")
    profile = {
        "monthly_allowance": st.sidebar.number_input("Monthly allowance (Rs.)", min_value=1000, max_value=500000,
                                                     value=int(saved["monthly_allowance"]), step=500, key="allowance"),
        "payday_day": st.sidebar.number_input("Money arrives on day", min_value=1, max_value=28, value=int(saved["payday_day"]), key="payday"),
        "monthly_savings_goal": st.sidebar.number_input("Monthly savings goal (Rs.)", min_value=0, max_value=200000,
                                                        value=int(saved["monthly_savings_goal"]), step=250, key="goal"),
    }
    if profile != {k: saved[k] for k in profile}:  # only persist what the user actually changed
        store.set_profile(profile)
    return source, tx, ret, ap, profile


def main() -> None:
    st.set_page_config(page_title="MoneyTwin", layout="wide")
    if "store" not in st.session_state:  # kept in the session so feedback survives even if the disk is read-only
        st.session_state["store"] = TwinStore()
    store = st.session_state["store"]
    source, tx, ret, ap, profile = sidebar_inputs(store)
    consent = st.session_state.get("consent", {})
    allowed = [c for c in ALL_CATEGORIES if st.session_state.get(f"allow_{c}", consent.get(c, True))]
    try:
        twin = build_twin(tx, ret, ap, profile, store, allowed)
    except ValueError as err:
        st.error(str(err))
        st.stop()
    signature = (source, tuple(allowed), len(tx))
    if st.session_state.get("usage_sig") != signature:
        store.log_usage(usage_entry(source, allowed, len(twin.tx)))
        st.session_state["usage_sig"] = signature
    page = st.sidebar.radio("Go to", list(PAGES), key="page")
    PAGES[page].render(twin, store)


main()
