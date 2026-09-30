"""Leaks page: hidden fees, return losses and the autopay calendar."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from ..formatting import money
from .common import ACCENT, PRIMARY, banners


FEE_LABELS = {
    "delivery_fee": "Delivery",
    "platform_fee": "Platform",
    "handling_fee": "Handling",
    "surge_fee": "Surge",
    "other_fees": "Other",
}


def render(twin, store) -> None:

    # ============================================================
    # HEADER
    # ============================================================

    st.markdown(
        """
        <div style="
            padding: 8px 0 4px 0;
        ">
            <div style="
                font-size: 15px;
                font-weight: 600;
                color: #6b7280;
                margin-bottom: 4px;
            ">
                SPENDING ANALYSIS
            </div>

            <div style="
                font-size: 40px;
                font-weight: 800;
                color: #111827;
                letter-spacing: -1px;
            ">
                Money leaks
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption(
        "See where extra money is being lost through fees, returns and recurring payments."
    )

    banners(twin)

    lk = twin.leaks

    # ============================================================
    # TOP SUMMARY
    # ============================================================

    total_leak = (
        lk["total_fees"]
        + lk["return_loss_confirmed"]
        + lk["return_loss_expected"]
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "💸 Total money leaks",
            money(total_leak),
            "Fees + return losses",
            delta_color="off",
        )

    with c2:
        st.metric(
            "⚠️ Hidden fees",
            money(lk["total_fees"]),
            f"{lk['fee_pct_of_item']:.0f}% on top of prices",
            delta_color="off",
        )

    with c3:
        st.metric(
            "📅 Autopay next 30 days",
            money(lk["upcoming_autopay_30d"]),
            f"about {money(lk['monthly_autopay'])}/month",
            delta_color="off",
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ============================================================
    # TABS
    # ============================================================

    tab_fees, tab_returns, tab_auto = st.tabs(
        [
            "💸 Hidden fees",
            "↩️ Return losses",
            "📅 Autopay calendar",
        ]
    )

    # ============================================================
    # HIDDEN FEES
    # ============================================================

    with tab_fees:

        st.markdown(
            """
            <div style="
                background: linear-gradient(135deg, #fff7ed, #ffffff);
                border: 1px solid #fed7aa;
                border-radius: 14px;
                padding: 16px 20px;
                margin: 10px 0 20px 0;
            ">
                <div style="
                    font-size: 13px;
                    font-weight: 700;
                    color: #c2410c;
                ">
                    WHERE THE EXTRA COST COMES FROM
                </div>

                <div style="
                    font-size: 14px;
                    color: #4b5563;
                    margin-top: 5px;
                ">
                    Money added on top of the actual product prices.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.metric(
            "Total hidden fees",
            money(lk["total_fees"]),
            f"{lk['fee_pct_of_item']:.0f}% on top of product prices",
            delta_color="off",
        )

        by_type = {
            FEE_LABELS[k]: v
            for k, v in lk["fees_by_type"].items()
            if v > 0
        }

        if by_type:

            fig = go.Figure(
                go.Bar(
                    x=list(by_type.keys()),
                    y=list(by_type.values()),
                    marker_color=ACCENT,
                    hovertemplate="₹%{y:,.0f}<extra>%{x}</extra>",
                )
            )

            fig.update_layout(
                yaxis_title="Rs.",
                margin=dict(t=20, b=10, l=10, r=10),
                height=360,
                plot_bgcolor="white",
                paper_bgcolor="white",
                showlegend=False,
            )

            fig.update_xaxes(
                showgrid=False,
                title=None,
            )

            fig.update_yaxes(
                gridcolor="#e5e7eb",
                zeroline=False,
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
            )

        st.markdown("### Fees by category")

        show = twin.fees[
            ["category", "item_amount", "fees", "fee_pct"]
        ].rename(
            columns={
                "category": "Category",
                "item_amount": "Product price (Rs.)",
                "fees": "Fees (Rs.)",
                "fee_pct": "Fees as % of price",
            }
        )

        st.dataframe(
            show.round(1),
            hide_index=True,
            use_container_width=True,
        )

    # ============================================================
    # RETURN LOSSES
    # ============================================================

    with tab_returns:

        st.markdown(
            """
            <div style="
                background: linear-gradient(135deg, #eff6ff, #ffffff);
                border: 1px solid #bfdbfe;
                border-radius: 14px;
                padding: 16px 20px;
                margin: 10px 0 20px 0;
            ">
                <div style="
                    font-size: 13px;
                    font-weight: 700;
                    color: #2563eb;
                ">
                    RETURN MONEY TRACKER
                </div>

                <div style="
                    font-size: 14px;
                    color: #4b5563;
                    margin-top: 5px;
                ">
                    See confirmed losses, expected losses and refunds still pending.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        c = st.columns(3)

        with c[0]:
            st.metric(
                "Confirmed loss",
                money(lk["return_loss_confirmed"]),
                help="Fees and deductions that were not refunded.",
            )

        with c[1]:
            st.metric(
                "Expected loss",
                money(lk["return_loss_expected"]),
                "Pending returns",
                delta_color="off",
                help="Estimated from fees on returns still awaiting refund.",
            )

        with c[2]:
            st.metric(
                "Refunds pending",
                money(lk["pending_refund_amount"]),
                f"{lk['pending_count']} returns",
                delta_color="off",
            )

        st.markdown("<br>", unsafe_allow_html=True)

        rl = twin.return_loss

        if len(rl):

            show = rl[
                [
                    "return_id",
                    "merchant",
                    "category",
                    "return_date",
                    "status",
                    "total",
                    "refund_amount",
                    "loss",
                ]
            ].copy()

            show["return_date"] = show[
                "return_date"
            ].dt.strftime("%Y-%m-%d")

            show = show.rename(
                columns={
                    "return_id": "Return ID",
                    "merchant": "Merchant",
                    "category": "Category",
                    "return_date": "Return date",
                    "status": "Status",
                    "total": "Original total",
                    "refund_amount": "Refund",
                    "loss": "Loss",
                }
            )

            st.dataframe(
                show.round(0),
                hide_index=True,
                use_container_width=True,
            )

        else:

            st.info(
                "No returns found in the data you shared."
            )

        unmatched = (
            twin.returns[
                twin.returns["status"] == "unmatched"
            ]
            if len(twin.returns)
            else twin.returns
        )

        if len(unmatched):

            st.warning(
                f"{len(unmatched)} return(s) have no matching order "
                "and are left out of the totals instead of being guessed: "
                + ", ".join(
                    unmatched["order_id"].astype(str)
                )
                + ". Add the original order to include them."
            )

        if lk["pending_count"]:

            st.info(
                "Refunds marked 'pending' have not arrived yet. "
                "Their product value is treated as coming back."
            )

    # ============================================================
    # AUTOPAY
    # ============================================================

    with tab_auto:

        st.markdown(
            """
            <div style="
                background: linear-gradient(135deg, #f5f3ff, #ffffff);
                border: 1px solid #ddd6fe;
                border-radius: 14px;
                padding: 16px 20px;
                margin: 10px 0 20px 0;
            ">
                <div style="
                    font-size: 13px;
                    font-weight: 700;
                    color: #7c3aed;
                ">
                    UPCOMING RECURRING PAYMENTS
                </div>

                <div style="
                    font-size: 14px;
                    color: #4b5563;
                    margin-top: 5px;
                ">
                    Keep track of subscriptions and recurring payments before they renew.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.metric(
            "Autopay due in the next 30 days",
            money(lk["upcoming_autopay_30d"]),
            f"about {money(lk['monthly_autopay'])} a month",
            delta_color="off",
        )

        st.markdown("<br>", unsafe_allow_html=True)

        cal = twin.autopay

        if len(cal):

            show = cal[
                [
                    "merchant",
                    "amount",
                    "cycle",
                    "next_due",
                    "days_until",
                    "source",
                ]
            ].copy()

            show["next_due"] = show[
                "next_due"
            ].dt.strftime("%Y-%m-%d")

            show = show.rename(
                columns={
                    "merchant": "Merchant",
                    "amount": "Amount",
                    "cycle": "Cycle",
                    "next_due": "Next due",
                    "days_until": "Days left",
                    "source": "Source",
                }
            )

            st.dataframe(
                show,
                hide_index=True,
                use_container_width=True,
            )

            for r in cal.itertuples():

                if r.source.startswith(
                    "declared, new"
                ):

                    st.warning(
                        f"New autopay: {r.merchant} "
                        f"({money(r.amount)}) starts in "
                        f"{r.days_until} days. "
                        "The plan has been updated."
                    )

                elif r.source == "detected, not declared":

                    st.info(
                        f"{r.merchant} renews automatically "
                        "but was not in your declared autopay list."
                    )

        else:

            st.info(
                "No recurring payments detected yet. "
                "They appear after two or more regular charges."
            )