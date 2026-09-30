"""Privacy and data page: consent toggles, data-used log, labelling and deletion."""
from __future__ import annotations

import streamlit as st

from ..config import ALL_CATEGORIES, CATEGORIES
from .common import banners


def render(twin, store) -> None:
    st.title("Privacy and data")
    banners(twin)
    st.subheader("What the twin may use")
    st.caption("Switch a category off and it disappears from every chart, model and explanation straight away.")
    consent = st.session_state.setdefault("consent", {})
    cols = st.columns(3)
    for i, cat in enumerate(ALL_CATEGORIES):
        consent[cat] = cols[i % 3].checkbox(cat, value=consent.get(cat, True), key=f"allow_{cat}")
    st.write(f"Using **{len(twin.tx)}** orders across **{len(twin.allowed)}** categories.")
    if twin.excluded:
        st.warning("Not considered: " + ", ".join(f"{c} ({v['rows']} orders)" for c, v in twin.excluded.items()))

    st.subheader("Data used")
    log = store.state["usage_log"]
    if log:
        st.dataframe([{"When": e["time"], "Source": e["source"], "Orders used": e["rows"],
                       "Switched off": ", ".join(e["switched_off"]) or "nothing"} for e in reversed(log)], hide_index=True)
    else:
        st.caption("Nothing logged yet.")

    if twin.report.uncategorised:
        st.subheader("Label unknown merchants")
        st.caption("Label a merchant once and the twin remembers it.")
        merchant = st.selectbox("Merchant", twin.report.uncategorised, key="lbl_merchant")
        category = st.selectbox("Category", CATEGORIES, key="lbl_cat")
        if st.button("Save label", key="lbl_save"):
            store.label_merchant(merchant, category)
            st.session_state["flash"] = f"Saved: {merchant} is now {category}."
            st.rerun()

    st.subheader("Delete my data")
    sure = st.checkbox("I understand this erases everything the twin has learned", key="del_sure")
    if st.button("Delete all twin data", key="del_go", disabled=not sure):
        store.delete_all()
        st.session_state["_reset"] = True
        st.session_state["flash"] = "Deleted. The twin has been reset."
        st.rerun()
