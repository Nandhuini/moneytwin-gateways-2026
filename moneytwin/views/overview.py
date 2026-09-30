"""Overview page: KPIs, money map and key findings."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from ..formatting import money, pct
from .common import ACCENT, NEUTRAL, PRIMARY, banners


def render(twin, store) -> None:
    st.title("MoneyTwin")
    st.caption("Where is my money leaking, and what should I change? Data up to " + twin.as_of.strftime("%d %b %Y") + ".")
    banners(twin)
    lk, risk = twin.leaks, twin.risk
    cols = st.columns(4)
    cols[0].metric("Net spend this month", money(risk["spent_mtd"]), help="After refunds. Pending refunds are counted as coming back.")
    cols[1].metric("Hidden fees paid", money(lk["total_fees"]), f"{lk['fee_pct_of_item']:.0f}% on top of prices", delta_color="off")
    cols[2].metric("Lost on returns", money(lk["return_loss_confirmed"] + lk["return_loss_expected"]),
                   f"{lk['pending_count']} refunds pending", delta_color="off")
    cols[3].metric("Chance of breaking budget", pct(risk["risk"]), f"budget {money(risk['budget'])}", delta_color="off")

    left, right = st.columns(2)
    with left:
        st.subheader("Money map")
        fig = go.Figure()
        fig.add_bar(x=twin.fees["category"], y=twin.fees["item_amount"], name="Product price", marker_color=PRIMARY)
        fig.add_bar(x=twin.fees["category"], y=twin.fees["fees"], name="Hidden fees", marker_color=ACCENT)
        fig.update_layout(barmode="stack", yaxis_title="Rs.", margin=dict(t=10, b=10), legend=dict(orientation="h"))
        st.plotly_chart(fig)
    with right:
        st.subheader("Net spend by month")
        monthly = twin.tx.groupby("month")["net_total"].sum()
        fig2 = go.Figure(go.Bar(x=list(monthly.index), y=list(monthly.values), marker_color=NEUTRAL))
        fig2.add_hline(y=risk["budget"], line_dash="dash", line_color=ACCENT, annotation_text="Budget (allowance minus goal)")
        fig2.update_layout(yaxis_title="Rs.", margin=dict(t=10, b=10))
        st.plotly_chart(fig2)

    st.subheader("What the twin found")
    trig = twin.behaviour["triggers"]
    findings = []
    if lk["top_fee_category"]:
        findings.append(f"**{lk['top_fee_category']}** carries the most hidden fees: {money(lk['top_fee_amount'])}.")
    findings += [t["insight"] for t in trig]
    if lk["pending_count"]:
        findings.append(f"{lk['pending_count']} refunds worth {money(lk['pending_refund_amount'])} are still pending.")
    if lk["upcoming_autopay_30d"]:
        findings.append(f"{money(lk['upcoming_autopay_30d'])} of autopay is due in the next 30 days.")
    for f in findings:
        st.markdown("- " + f)
    st.info("Open **What-if simulator** to test changes and get a recommendation.")
