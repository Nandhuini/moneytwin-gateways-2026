"""Privacy and data page: consent toggles, data-used log, labelling and deletion."""
from __future__ import annotations

import streamlit as st

from ..config import ALL_CATEGORIES, CATEGORIES
from ..formatting import money
from .common import banners, callout, card, esc, html_block, kpi_row, page_header, pill, section, show_table

CATEGORY_NOTES = {
    "Food Delivery": "Food orders and their delivery, platform and handling fees.",
    "Shopping": "Online shopping orders, including returns and refunds.",
    "Trends": "Trend and sale-day purchases, including returns and refunds.",
    "Groceries": "Grocery orders.",
    "Subscriptions": "Recurring charges. Also controls the autopay calendar.",
    "Other": "Anything that does not fit the other categories.",
    "Uncategorised": "Merchants the twin could not classify yet.",
}

HANDLING = [
    ("🔐", "Stays in your session", "Uploaded files are read in this session. Nothing is sent to a bank or a shop."),
    ("💾", "Saved locally", "What the twin learns (goals, habits, labels) is kept in a small local JSON file (twin_profile.json)."),
    ("🧮", "Summary numbers only", "If an AI key is configured, only summary numbers reach the advisor, never raw transactions."),
    ("🗑️", "Yours to delete", "Erase everything the twin has learned at any time, using the button at the bottom of this page."),
]


def _footprint(twin, cat: str, on: bool) -> str:
    """One line about how much data sits in this category."""
    if on:
        rows = twin.tx[twin.tx["category"] == cat]
        return f"{len(rows)} orders, {money(rows['total'].sum())}" if len(rows) else "No orders in this category"
    off = twin.excluded.get(cat)
    return f"{off['rows']} orders hidden, {money(off['amount'])}" if off else "No orders in this category"


def render(twin, store) -> None:
    page_header("Privacy centre", "Privacy and data",
                "You decide which parts of your spending the twin may learn from.")
    banners(twin)

    switched_off = [c for c in ALL_CATEGORIES if c not in twin.allowed]
    kpi_row([
        dict(label="Categories in use", value=f"{len(twin.allowed)} of {len(ALL_CATEGORIES)}",
             note="Every chart and model uses only these.", tone="good" if not switched_off else "info", icon="✅"),
        dict(label="Orders analysed", value=str(len(twin.tx)), note="After your choices below are applied.", tone="info", icon="🧾"),
        dict(label="Switched off", value=str(len(switched_off)), note=", ".join(switched_off) if switched_off else "Nothing is hidden.",
             tone="warn" if switched_off else "neutral", icon="🙈"),
    ])

    # ============================================================
    # CONSENT CONTROLS
    # ============================================================

    section("What the twin may use")
    st.caption("Switch a category off and it disappears from every chart, model and explanation straight away.")
    consent = st.session_state.setdefault("consent", {})
    cols = st.columns(3)
    for i, cat in enumerate(ALL_CATEGORIES):
        with cols[i % 3]:
            with card():
                consent[cat] = st.checkbox(cat, value=consent.get(cat, True), key=f"allow_{cat}")
                on = bool(consent[cat])
                status = pill("Enabled", "good") if on else pill("Switched off", "neutral")
                html_block(f'<div>{status}</div><div class="mt-note" style="margin-top:8px">{esc(CATEGORY_NOTES.get(cat, ""))}</div>'
                           f'<div class="mt-note" style="margin-top:4px"><b>{esc(_footprint(twin, cat, on))}</b></div>')
    st.write(f"Using **{len(twin.tx)}** orders across **{len(twin.allowed)}** categories.")
    if twin.excluded:
        st.warning("Not considered: " + ", ".join(f"{c} ({v['rows']} orders)" for c, v in twin.excluded.items()))

    # ============================================================
    # HOW DATA IS HANDLED
    # ============================================================

    section("How your data is handled")
    for col, (icon, title, body) in zip(st.columns(len(HANDLING)), HANDLING):
        with col:
            html_block(f'<div class="mt-card" style="min-height:150px"><div style="font-size:22px">{icon}</div>'
                       f'<div style="font-weight:700;color:#0f172a;margin:6px 0 4px">{esc(title)}</div>'
                       f'<div class="mt-note">{esc(body)}</div></div>')

    # ============================================================
    # DATA USED LOG
    # ============================================================

    section("Data used", "Each line records what the twin used and what you had switched off at the time.")
    log = store.state["usage_log"]
    if log:
        show_table([{"When": e["time"], "Source": e["source"], "Orders used": e["rows"],
                     "Switched off": ", ".join(e["switched_off"]) or "nothing"} for e in reversed(log)])
    else:
        st.caption("Nothing logged yet.")

    # ============================================================
    # LABEL UNKNOWN MERCHANTS
    # ============================================================

    if twin.report.uncategorised:
        with card():
            section("Label unknown merchants", "Label a merchant once and the twin remembers it.")
            merchant = st.selectbox("Merchant", twin.report.uncategorised, key="lbl_merchant")
            category = st.selectbox("Category", CATEGORIES, key="lbl_cat")
            if st.button("Save label", key="lbl_save"):
                store.label_merchant(merchant, category)
                st.session_state["flash"] = f"Saved: {merchant} is now {category}."
                st.rerun()

    # ============================================================
    # DELETE
    # ============================================================

    section("Delete my data")
    callout("This cannot be undone", "Deleting resets the twin: your goals, labels, feedback and the data-used log are erased.", tone="bad", icon="⚠️")
    sure = st.checkbox("I understand this erases everything the twin has learned", key="del_sure")
    if st.button("Delete all twin data", key="del_go", disabled=not sure):
        store.delete_all()
        st.session_state["_reset"] = True
        st.session_state["flash"] = "Deleted. The twin has been reset."
        st.rerun()
