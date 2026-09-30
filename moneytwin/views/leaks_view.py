"""Leaks page: hidden fees, return losses and the autopay calendar."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from ..formatting import money
from .common import (ACCENT, AMBER_SOFT, WARN, banners, callout, card, html_block, kpi_card, kpi_row, leak_banner,
                     page_header, pill, section, show_chart, show_table, style_fig)


FEE_LABELS = {
    "delivery_fee": "Delivery",
    "platform_fee": "Platform",
    "handling_fee": "Handling",
    "surge_fee": "Surge",
    "other_fees": "Other",
}


def render(twin, store) -> None:
    page_header("Spending analysis", "Money leaks",
                "See where extra money is being lost through fees, returns and recurring payments.")
    banners(twin)

    lk = twin.leaks

    # Total leakage, then the three places it comes from
    leak_banner(lk)
    kpi_row([
        dict(label="Hidden fees", value=money(lk["total_fees"]), note=f"{lk['fee_pct_of_item']:.0f}% on top of prices",
             tone="bad", icon="⚠️"),
        dict(label="Return losses", value=money(lk["return_loss_confirmed"] + lk["return_loss_expected"]),
             note=f"{lk['pending_count']} refunds pending", tone="warn", icon="↩️"),
        dict(label="Autopay next 30 days", value=money(lk["upcoming_autopay_30d"]),
             note=f"about {money(lk['monthly_autopay'])}/month", tone="info", icon="📅"),
    ])

    tab_fees, tab_returns, tab_auto = st.tabs(["💸 Hidden fees", "↩️ Return losses", "📅 Autopay calendar"])

    # ============================================================
    # HIDDEN FEES
    # ============================================================

    with tab_fees:
        callout("Where the extra cost comes from", "Money added on top of the actual product prices.", tone="bad")

        by_type = {FEE_LABELS[k]: v for k, v in lk["fees_by_type"].items() if v > 0}

        c1, c2 = st.columns([1, 2])
        with c1:
            kpi_card("Total hidden fees", money(lk["total_fees"]), f"{lk['fee_pct_of_item']:.0f}% on top of product prices",
                     tone="bad", icon="💸")
            if by_type:
                top_name = max(by_type, key=by_type.get)
                kpi_card("Biggest fee type", top_name, f"{money(by_type[top_name])}, {by_type[top_name] / sum(by_type.values()) * 100:.0f}% of all fees",
                         tone="warn", icon="🏷️")
        with c2:
            if by_type:
                with card():
                    section("Fees by type")
                    top_name = max(by_type, key=by_type.get)
                    fig = go.Figure(go.Bar(x=list(by_type.keys()), y=list(by_type.values()),
                                           marker_color=[ACCENT if n == top_name else AMBER_SOFT for n in by_type],
                                           hovertemplate="Rs. %{y:,.0f}<extra>%{x}</extra>"))
                    fig.update_layout(yaxis_title="Rs.")
                    show_chart(style_fig(fig, height=300))

        section("Fees by category")
        show = twin.fees[["category", "item_amount", "fees", "fee_pct"]].rename(
            columns={"category": "Category", "item_amount": "Product price (Rs.)", "fees": "Fees (Rs.)",
                     "fee_pct": "Fees as % of price"})
        show_table(show.round(1))

    # ============================================================
    # RETURN LOSSES
    # ============================================================

    with tab_returns:
        callout("Return money tracker", "See confirmed losses, expected losses and refunds still pending.", tone="info")

        kpi_row([
            dict(label="Confirmed loss", value=money(lk["return_loss_confirmed"]), note="Fees and deductions not refunded",
                 tone="bad", icon="❌", help="Fees and deductions that were not refunded."),
            dict(label="Expected loss", value=money(lk["return_loss_expected"]), note="Pending returns", tone="warn",
                 icon="⏳", help="Estimated from fees on returns still awaiting refund."),
            dict(label="Refunds pending", value=money(lk["pending_refund_amount"]), note=f"{lk['pending_count']} returns",
                 tone="info", icon="🔄"),
        ])

        rl = twin.return_loss

        if len(rl):
            received = int((rl["status"] == "received").sum())
            pills = [pill(f"{received} received", "good"), pill(f"{lk['pending_count']} pending", "warn")]
            if lk["unmatched_returns"]:
                pills.append(pill(f"{lk['unmatched_returns']} unmatched", "bad"))
            html_block('<div class="mt-note">Return status: ' + " ".join(pills) + "</div>")

            by_month = rl.groupby(["month", "confirmed"])["loss"].sum().unstack(fill_value=0.0)
            if float(by_month.to_numpy().sum()) > 0:
                with card():
                    section("Return losses by month", "Confirmed losses are money that never came back; expected losses are estimates.")
                    fig = go.Figure()
                    if True in by_month.columns:
                        fig.add_bar(x=list(by_month.index), y=list(by_month[True]), name="Confirmed", marker_color=ACCENT,
                                    hovertemplate="Rs. %{y:,.0f}<extra>Confirmed</extra>")
                    if False in by_month.columns:
                        fig.add_bar(x=list(by_month.index), y=list(by_month[False]), name="Expected", marker_color=WARN,
                                    hovertemplate="Rs. %{y:,.0f}<extra>Expected</extra>")
                    fig.update_layout(barmode="stack", yaxis_title="Rs.")
                    show_chart(style_fig(fig, height=280, legend=True))

            section("All returns")
            show = rl[["return_id", "merchant", "category", "return_date", "status", "total", "refund_amount", "loss"]].copy()
            show["return_date"] = show["return_date"].dt.strftime("%Y-%m-%d")
            show = show.rename(columns={"return_id": "Return ID", "merchant": "Merchant", "category": "Category",
                                        "return_date": "Return date", "status": "Status", "total": "Original total",
                                        "refund_amount": "Refund", "loss": "Loss"})
            show_table(show.round(0))
        else:
            st.info("No returns found in the data you shared.")

        unmatched = twin.returns[twin.returns["status"] == "unmatched"] if len(twin.returns) else twin.returns

        if len(unmatched):
            st.warning(f"{len(unmatched)} return(s) have no matching order "
                       "and are left out of the totals instead of being guessed: "
                       + ", ".join(unmatched["order_id"].astype(str))
                       + ". Add the original order to include them.")

        if lk["pending_count"]:
            st.info("Refunds marked 'pending' have not arrived yet. Their product value is treated as coming back.")

    # ============================================================
    # AUTOPAY
    # ============================================================

    with tab_auto:
        callout("Upcoming recurring payments", "Keep track of subscriptions and recurring payments before they renew.",
                tone="info")

        cal = twin.autopay

        items = [dict(label="Autopay due in the next 30 days", value=money(lk["upcoming_autopay_30d"]),
                      note=f"about {money(lk['monthly_autopay'])} a month", tone="info", icon="📅")]
        if len(cal):
            nxt = cal.iloc[0]
            items.append(dict(label="Recurring payments", value=str(len(cal)),
                              note=f"{int((cal['days_until'] <= 7).sum())} due within 7 days", tone="neutral", icon="🔁"))
            items.append(dict(label="Next payment", value=str(nxt["merchant"]),
                              note=f"{money(nxt['amount'])} in {int(nxt['days_until'])} days", tone="warn", icon="⏰"))
        kpi_row(items)

        if len(cal):
            section("Autopay calendar")
            show = cal[["merchant", "amount", "cycle", "next_due", "days_until", "source"]].copy()
            show["next_due"] = show["next_due"].dt.strftime("%Y-%m-%d")
            show = show.rename(columns={"merchant": "Merchant", "amount": "Amount", "cycle": "Cycle", "next_due": "Next due",
                                        "days_until": "Days left", "source": "Source"})
            show_table(show)

            for r in cal.itertuples():
                if r.source.startswith("declared, new"):
                    st.warning(f"New autopay: {r.merchant} ({money(r.amount)}) starts in {r.days_until} days. "
                               "The plan has been updated.")
                elif r.source == "detected, not declared":
                    st.info(f"{r.merchant} renews automatically but was not in your declared autopay list.")
        else:
            st.info("No recurring payments detected yet. They appear after two or more regular charges.")
