"""Behaviour page: heatmap, triggers, regret predictor and overspend risk."""
from __future__ import annotations

import plotly.express as px
import streamlit as st

from ..formatting import money, pct
from ..prediction import predict_return
from .common import banners


def render(twin, store) -> None:
    st.title("Behaviour and prediction")
    banners(twin)
    beh = twin.behaviour
    st.subheader("When you spend")
    fig = px.imshow(beh["heatmap"], text_auto=".0f", aspect="auto", color_continuous_scale="Blues",
                    labels=dict(x="Day of month", y="Time of day", color="Net spend (Rs.)"))
    fig.update_layout(margin=dict(t=10, b=10))
    st.plotly_chart(fig)
    st.caption(f"Busiest slot: {beh['peak_band']} on days {beh['peak_bucket']}.")
    cols = st.columns(len(beh["triggers"]))
    for col, t in zip(cols, beh["triggers"]):
        col.metric(t["name"], pct(t["share"]) + " of spend")
        col.caption(t["insight"])

    st.subheader("Regret predictor")
    st.caption("Before a purchase you often return, see what it is likely to cost you.")
    model = twin.return_model
    c = st.columns(4)
    category = c[0].selectbox("Category", ["Shopping", "Trends"], key="rp_cat")
    amount = c[1].number_input("Item price (Rs.)", min_value=0, value=999, step=50, key="rp_amt")
    hour = c[2].slider("Hour of day", 0, 23, 23, key="rp_hour")
    sale = c[3].checkbox("Sale day", value=True, key="rp_sale")
    typical_fee = int(model.avg_fees.get(category, 30))
    fees = st.number_input("Fees on this order (Rs.)", min_value=0, value=typical_fee, step=5, key="rp_fee")
    payday = ((twin.as_of.day + 1 - int(twin.profile["payday_day"])) % 31) < 5
    p = predict_return(model, category, float(amount), int(hour), bool(sale), float(fees), payday)
    m = st.columns(2)
    m[0].metric("Chance you return it", pct(p["prob"]), f"range {pct(p['low'])} to {pct(p['high'])}", delta_color="off")
    m[1].metric("Expected money lost", money(p["expected_loss"]), f"range {money(p['expected_loss_low'])} to {money(p['expected_loss_high'])}", delta_color="off")
    if p["prob"] >= 0.3:
        st.warning(f"You usually return this kind of item. If you do, about {money(p['loss_if_returned'])} will not come back, "
                   f"and the refund takes around {p['refund_lag_days']:.0f} days.")
    else:
        st.success("This looks like a purchase you tend to keep.")
    if p["confidence"] == "low":
        st.caption("Low confidence: little purchase history, so the range is wide.")

    st.subheader("Overspend risk this month")
    r = twin.risk
    m = st.columns(3)
    m[0].metric("Projected month-end spend", money(r["projected"]), f"budget {money(r['budget'])}", delta_color="off")
    m[1].metric("Chance of breaking budget", pct(r["risk"]), r["level"] + " risk", delta_color="off")
    m[2].metric("Spent so far", money(r["spent_mtd"]))
    if r["risky_days"]:
        st.warning("Risky days ahead: " + ", ".join(f"{d['date'].strftime('%d %b')} ({d['reason']})" for d in r["risky_days"]))
    if r["confidence"] == "low":
        st.caption("Low confidence: fewer than a month of history.")
