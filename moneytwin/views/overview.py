"""Overview page: KPIs, money map and key findings."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from ..formatting import money, pct
from .common import (ACCENT, NEUTRAL, PRIMARY, banners, callout, card, cta_card, finding_card, hero, kpi_row,
                     leak_banner, section, show_chart, style_fig)

RISK_TONE = {"low": "good", "medium": "warn", "high": "bad"}


def render(twin, store) -> None:
    lk, risk = twin.leaks, twin.risk

    # Header
    hero("MoneyTwin", "Where is my money leaking, and what should I change?",
         [f"Data up to {twin.as_of.strftime('%d %b %Y')}", f"{len(twin.tx)} orders analysed", f"Confidence: {twin.confidence}"])
    banners(twin)

    # KPI cards
    kpi_row([
        dict(label="Net spend this month", value=money(risk["spent_mtd"]), note="After refunds", tone="info", icon="💳",
             help="After refunds. Pending refunds are counted as coming back."),
        dict(label="Hidden fees paid", value=money(lk["total_fees"]), note=f"{lk['fee_pct_of_item']:.0f}% on top of prices",
             tone="bad", icon="⚠️"),
        dict(label="Lost on returns", value=money(lk["return_loss_confirmed"] + lk["return_loss_expected"]),
             note=f"{lk['pending_count']} refunds pending", tone="warn", icon="↩️"),
        dict(label="Chance of breaking budget", value=pct(risk["risk"]), note=f"budget {money(risk['budget'])}",
             tone=RISK_TONE.get(risk["level"], "neutral"), icon="📊"),
    ])

    # Leakage headline
    leak_banner(lk)

    # Money insight
    if lk["top_fee_category"]:
        insight = (f"Most of your hidden fees are coming from **{lk['top_fee_category']}**, "
                   f"adding up to **{money(lk['top_fee_amount'])}**.")
    elif lk["pending_count"]:
        insight = (f"You currently have **{lk['pending_count']} pending refunds** "
                   f"worth **{money(lk['pending_refund_amount'])}**.")
    else:
        insight = "Your MoneyTwin has analyzed your recent spending and identified patterns that may affect your savings."
    callout("MoneyTwin insight", insight, tone="info", icon="✨")

    # Charts
    left, right = st.columns(2)

    with left:
        with card():
            section("Money map", "Product price against hidden fees, by category.")
            fig = go.Figure()
            fig.add_bar(x=twin.fees["category"], y=twin.fees["item_amount"], name="Product price", marker_color=PRIMARY,
                        hovertemplate="Rs. %{y:,.0f}<extra>Product price</extra>")
            fig.add_bar(x=twin.fees["category"], y=twin.fees["fees"], name="Hidden fees", marker_color=ACCENT,
                        hovertemplate="Rs. %{y:,.0f}<extra>Hidden fees</extra>")
            fig.update_layout(barmode="stack", yaxis_title="Rs.", hovermode="x unified")
            show_chart(style_fig(fig, height=380, legend=True))

    with right:
        with card():
            section("Net spend by month", "The dashed line is your monthly budget.")
            monthly = twin.tx.groupby("month")["net_total"].sum()
            colours = [NEUTRAL] * (len(monthly) - 1) + [PRIMARY]
            fig2 = go.Figure(go.Bar(x=list(monthly.index), y=list(monthly.values), marker_color=colours,
                                    hovertemplate="Rs. %{y:,.0f}<extra>Net spend</extra>"))
            fig2.add_hline(y=risk["budget"], line_dash="dash", line_color=ACCENT, annotation_text="Budget",
                           annotation_position="top right")
            fig2.update_layout(yaxis_title="Rs.")
            show_chart(style_fig(fig2, height=380))

    # What the twin found
    section("What your twin found")
    trig = twin.behaviour["triggers"]
    findings = []
    if lk["top_fee_category"]:
        findings.append(f"**{lk['top_fee_category']}** carries the most hidden fees: {money(lk['top_fee_amount'])}.")
    findings += [t["insight"] for t in trig]
    if lk["pending_count"]:
        findings.append(f"{lk['pending_count']} refunds worth {money(lk['pending_refund_amount'])} are still pending.")
    if lk["upcoming_autopay_30d"]:
        findings.append(f"{money(lk['upcoming_autopay_30d'])} of autopay is due in the next 30 days.")

    if findings:
        cols = st.columns(2)
        for index, finding in enumerate(findings):
            with cols[index % 2]:
                finding_card(finding)
    else:
        st.info("Your MoneyTwin did not find any major spending patterns yet.")

    # Next action
    cta_card("🔮 Ready to test a change?",
             "Open the What-if simulator to see how a different spending choice could affect your month.")
