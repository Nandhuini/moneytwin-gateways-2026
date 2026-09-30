"""Behaviour page: heatmap, triggers, regret predictor and overspend risk."""
from __future__ import annotations

import plotly.express as px
import streamlit as st

from ..formatting import money, pct
from ..prediction import predict_return
from .common import (PRIMARY, banners, bar, callout, card, esc, html_block, kpi_row, page_header, section,
                     show_chart, style_fig)

TRIGGER_ICONS = {"Right after payday": "💸", "Late night (10pm-5am)": "🌙", "Sale days": "🏷️"}
RISK_TONE = {"low": "good", "medium": "warn", "high": "bad"}
RANGE_BAND = "#a9d0dd"


def render(twin, store) -> None:
    page_header("Habits and forecasts", "Behaviour and prediction",
                "See when you spend, what triggers it, and what a risky purchase or month could cost you.")
    banners(twin)
    beh = twin.behaviour

    # ============================================================
    # WHEN YOU SPEND
    # ============================================================

    with card():
        section("When you spend", "Net spend by time of day and day of month. Recurring bills are left out.")
        fig = px.imshow(beh["heatmap"], text_auto=".0f", aspect="auto", color_continuous_scale=["#f1f7fa", PRIMARY],
                        labels=dict(x="Day of month", y="Time of day", color="Net spend (Rs.)"))
        fig.update_layout(coloraxis_colorbar=dict(thickness=12, title="Rs."))
        show_chart(style_fig(fig, height=330, axes=False))
    callout("How to read this",
            f"Busiest slot: **{beh['peak_band']}** on days **{beh['peak_bucket']}**. "
            "Darker squares mean more money spent in that slot.", tone="info", icon="🔎")

    if beh["triggers"]:
        kpi_row([dict(label=t["name"], value=pct(t["share"]) + " of spend", note=t["insight"], tone="info",
                      icon=TRIGGER_ICONS.get(t["name"], "•")) for t in beh["triggers"]])

    # ============================================================
    # REGRET PREDICTOR
    # ============================================================

    section("Regret predictor", "Before a purchase you often return, see what it is likely to cost you.")
    model = twin.return_model
    with card():
        c = st.columns(4)
        category = c[0].selectbox("Category", ["Shopping", "Trends"], key="rp_cat")
        amount = c[1].number_input("Item price (Rs.)", min_value=0, value=999, step=50, key="rp_amt")
        hour = c[2].slider("Hour of day", 0, 23, 23, key="rp_hour")
        sale = c[3].checkbox("Sale day", value=True, key="rp_sale")
        typical_fee = int(model.avg_fees.get(category, 30))
        fees = st.number_input("Fees on this order (Rs.)", min_value=0, value=typical_fee, step=5, key="rp_fee")

    payday = ((twin.as_of.day + 1 - int(twin.profile["payday_day"])) % 31) < 5
    p = predict_return(model, category, float(amount), int(hour), bool(sale), float(fees), payday)

    kpi_row([
        dict(label="Chance you return it", value=pct(p["prob"]), note=f"range {pct(p['low'])} to {pct(p['high'])}",
             tone="warn" if p["prob"] >= 0.3 else "good", icon="↩️"),
        dict(label="Expected money lost", value=money(p["expected_loss"]),
             note=f"range {money(p['expected_loss_low'])} to {money(p['expected_loss_high'])}", tone="bad", icon="💸"),
    ])

    basis = (f"estimated by a model trained on {model.n} of your past shopping and trend orders"
             if model.pipe is not None else "based on your past return rate for this category (too little history to train a model)")
    purchase = f"{category}, {money(amount)}, {int(hour):02d}:00" + (", sale day" if sale else "")
    html_block(f'<div class="mt-card"><div class="mt-kpi-label">How likely is a return? ({esc(purchase)})</div>'
               f'<div style="margin:12px 0 8px">{bar([(p["low"], PRIMARY), (p["high"] - p["low"], RANGE_BAND)], marker=p["prob"], height=12)}</div>'
               f'<div class="mt-note">The black marker is the best estimate. The light band is the likely range. '
               f'In plain terms: out of 10 purchases like this, about {round(p["prob"] * 10)} would come back, {esc(basis)}.</div></div>')

    if p["prob"] >= 0.3:
        st.warning(f"You usually return this kind of item. If you do, about {money(p['loss_if_returned'])} will not come back, "
                   f"and the refund takes around {p['refund_lag_days']:.0f} days.")
    else:
        st.success("This looks like a purchase you tend to keep.")
    if p["confidence"] == "low":
        st.caption("Low confidence: little purchase history, so the range is wide.")

    # ============================================================
    # OVERSPEND RISK
    # ============================================================

    section("Overspend risk this month")
    r = twin.risk
    kpi_row([
        dict(label="Projected month-end spend", value=money(r["projected"]), note=f"budget {money(r['budget'])}", tone="info", icon="🎯"),
        dict(label="Chance of breaking budget", value=pct(r["risk"]), note=r["level"] + " risk",
             tone=RISK_TONE.get(r["level"], "neutral"), icon="📊"),
        dict(label="Spent so far", value=money(r["spent_mtd"]), note=f"{twin.risk_days_left} days left this month", tone="neutral", icon="🧾"),
    ])

    scale = max(r["projected"], r["budget"], r["spent_mtd"], 1.0) * 1.1
    gap = r["projected"] - r["budget"]
    verdict = (f"At this pace you finish about {money(abs(gap))} {'over' if gap > 0 else 'under'} your budget of {money(r['budget'])}.")
    html_block(f'<div class="mt-card"><div class="mt-kpi-label">Month so far and expected rest of month</div>'
               f'<div style="margin:12px 0 8px">{bar([(r["spent_mtd"] / scale, PRIMARY), (max(r["projected"] - r["spent_mtd"], 0.0) / scale, RANGE_BAND)], marker=r["budget"] / scale, height=14)}</div>'
               f'<div class="mt-note">Dark: spent so far. Light: expected for the rest of the month. Black marker: your budget. {esc(verdict)}</div></div>')

    if r["risky_days"]:
        st.warning("Risky days ahead: " + ", ".join(f"{d['date'].strftime('%d %b')} ({d['reason']})" for d in r["risky_days"]))
    if r["confidence"] == "low":
        st.caption("Low confidence: fewer than a month of history.")
