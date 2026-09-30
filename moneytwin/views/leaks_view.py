"""Leaks page: hidden fees, return losses and the autopay calendar."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from ..formatting import money
from .common import ACCENT, PRIMARY, banners

FEE_LABELS = {"delivery_fee": "Delivery", "platform_fee": "Platform", "handling_fee": "Handling", "surge_fee": "Surge", "other_fees": "Other"}


def render(twin, store) -> None:
    st.title("Money leaks")
    banners(twin)
    tab_fees, tab_returns, tab_auto = st.tabs(["Hidden fees", "Return losses", "Autopay calendar"])
    lk = twin.leaks
    with tab_fees:
        st.metric("Total hidden fees", money(lk["total_fees"]), f"{lk['fee_pct_of_item']:.0f}% on top of product prices", delta_color="off")
        by_type = {FEE_LABELS[k]: v for k, v in lk["fees_by_type"].items() if v > 0}
        fig = go.Figure(go.Bar(x=list(by_type.keys()), y=list(by_type.values()), marker_color=ACCENT))
        fig.update_layout(yaxis_title="Rs.", margin=dict(t=10, b=10))
        st.plotly_chart(fig)
        show = twin.fees[["category", "item_amount", "fees", "fee_pct"]].rename(columns={
            "category": "Category", "item_amount": "Product price (Rs.)", "fees": "Fees (Rs.)", "fee_pct": "Fees as % of price"})
        st.dataframe(show.round(1), hide_index=True)
    with tab_returns:
        c = st.columns(3)
        c[0].metric("Confirmed loss", money(lk["return_loss_confirmed"]), help="Fees and deductions that were not refunded.")
        c[1].metric("Expected loss (pending)", money(lk["return_loss_expected"]), help="Estimated from fees on returns still awaiting refund.")
        c[2].metric("Refunds pending", money(lk["pending_refund_amount"]), f"{lk['pending_count']} returns", delta_color="off")
        rl = twin.return_loss
        if len(rl):
            show = rl[["return_id", "merchant", "category", "return_date", "status", "total", "refund_amount", "loss"]].copy()
            show["return_date"] = show["return_date"].dt.strftime("%Y-%m-%d")
            st.dataframe(show.round(0), hide_index=True)
        else:
            st.info("No returns found in the data you shared.")
        unmatched = twin.returns[twin.returns["status"] == "unmatched"] if len(twin.returns) else twin.returns
        if len(unmatched):
            st.warning(f"{len(unmatched)} return(s) have no matching order and are left out of the totals instead of being guessed: "
                       + ", ".join(unmatched["order_id"].astype(str)) + ". Add the original order to include them.")
        if lk["pending_count"]:
            st.info("Refunds marked 'pending' have not arrived yet. Their product value is treated as coming back.")
    with tab_auto:
        cal = twin.autopay
        st.metric("Autopay due in the next 30 days", money(lk["upcoming_autopay_30d"]), f"about {money(lk['monthly_autopay'])} a month", delta_color="off")
        if len(cal):
            show = cal[["merchant", "amount", "cycle", "next_due", "days_until", "source"]].copy()
            show["next_due"] = show["next_due"].dt.strftime("%Y-%m-%d")
            st.dataframe(show, hide_index=True)
            for r in cal.itertuples():
                if r.source.startswith("declared, new"):
                    st.warning(f"New autopay: {r.merchant} ({money(r.amount)}) starts in {r.days_until} days. The plan has been updated.")
                elif r.source == "detected, not declared":
                    st.info(f"{r.merchant} renews automatically but was not in your declared autopay list.")
        else:
            st.info("No recurring payments detected yet. They appear after two or more regular charges.")
