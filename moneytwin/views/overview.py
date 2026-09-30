"""Overview page: KPIs, money map and key findings."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from ..formatting import money, pct
from .common import ACCENT, NEUTRAL, PRIMARY, banners


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
                PERSONAL FINANCE DIGITAL TWIN
            </div>

            <div style="
                font-size: 42px;
                font-weight: 800;
                color: #111827;
                letter-spacing: -1.5px;
            ">
                MoneyTwin
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption(
        "Where is my money leaking, and what should I change? "
        "Data up to " + twin.as_of.strftime("%d %b %Y") + "."
    )

    banners(twin)

    lk, risk = twin.leaks, twin.risk

    # ============================================================
    # KPI CARDS
    # ============================================================

    cols = st.columns(4)

    with cols[0]:
        st.markdown(
            """
            <div style="
                font-size: 13px;
                color: #6b7280;
                margin-bottom: -8px;
            ">
                💰 NET SPEND
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.metric(
            "Net spend this month",
            money(risk["spent_mtd"]),
            help="After refunds. Pending refunds are counted as coming back.",
        )

    with cols[1]:
        st.markdown(
            """
            <div style="
                font-size: 13px;
                color: #6b7280;
                margin-bottom: -8px;
            ">
                ⚠️ HIDDEN FEES
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.metric(
            "Hidden fees paid",
            money(lk["total_fees"]),
            f"{lk['fee_pct_of_item']:.0f}% on top of prices",
            delta_color="off",
        )

    with cols[2]:
        st.markdown(
            """
            <div style="
                font-size: 13px;
                color: #6b7280;
                margin-bottom: -8px;
            ">
                ↩️ RETURN LOSSES
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.metric(
            "Lost on returns",
            money(
                lk["return_loss_confirmed"]
                + lk["return_loss_expected"]
            ),
            f"{lk['pending_count']} refunds pending",
            delta_color="off",
        )

    with cols[3]:
        st.markdown(
            """
            <div style="
                font-size: 13px;
                color: #6b7280;
                margin-bottom: -8px;
            ">
                📊 BUDGET RISK
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.metric(
            "Chance of breaking budget",
            pct(risk["risk"]),
            f"budget {money(risk['budget'])}",
            delta_color="off",
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ============================================================
    # MONEY INSIGHT
    # ============================================================

    insight = None

    if lk["top_fee_category"]:
        insight = (
            f"Most of your hidden fees are coming from "
            f"**{lk['top_fee_category']}**, adding up to "
            f"**{money(lk['top_fee_amount'])}**."
        )
    elif lk["pending_count"]:
        insight = (
            f"You currently have **{lk['pending_count']} pending refunds** "
            f"worth **{money(lk['pending_refund_amount'])}**."
        )
    else:
        insight = (
            "Your MoneyTwin has analyzed your recent spending "
            "and identified patterns that may affect your savings."
        )

    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #eef6ff, #f8fbff);
            border: 1px solid #dbeafe;
            border-radius: 16px;
            padding: 18px 22px;
            margin: 4px 0 24px 0;
        ">
            <div style="
                font-size: 13px;
                font-weight: 700;
                color: #2563eb;
                margin-bottom: 5px;
            ">
                ✨ MONEYTWIN INSIGHT
            </div>

            <div style="
                font-size: 16px;
                color: #1f2937;
                line-height: 1.5;
            ">
                {insight}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ============================================================
    # CHARTS
    # ============================================================

    left, right = st.columns(2)

    # ------------------------------------------------------------
    # MONEY MAP
    # ------------------------------------------------------------

    with left:

        st.subheader("Money map")

        fig = go.Figure()

        fig.add_bar(
            x=twin.fees["category"],
            y=twin.fees["item_amount"],
            name="Product price",
            marker_color=PRIMARY,
            hovertemplate="₹%{y:,.0f}<extra>Product price</extra>",
        )

        fig.add_bar(
            x=twin.fees["category"],
            y=twin.fees["fees"],
            name="Hidden fees",
            marker_color=ACCENT,
            hovertemplate="₹%{y:,.0f}<extra>Hidden fees</extra>",
        )

        fig.update_layout(
            barmode="stack",
            yaxis_title="Rs.",
            margin=dict(t=10, b=10, l=10, r=10),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="left",
                x=0,
            ),
            height=420,
            plot_bgcolor="white",
            paper_bgcolor="white",
            hovermode="x unified",
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

    # ------------------------------------------------------------
    # MONTHLY SPEND
    # ------------------------------------------------------------

    with right:

        st.subheader("Net spend by month")

        monthly = twin.tx.groupby("month")["net_total"].sum()

        fig2 = go.Figure(
            go.Bar(
                x=list(monthly.index),
                y=list(monthly.values),
                marker_color=NEUTRAL,
                hovertemplate="₹%{y:,.0f}<extra>Net spend</extra>",
            )
        )

        fig2.add_hline(
            y=risk["budget"],
            line_dash="dash",
            line_color=ACCENT,
            annotation_text="Budget",
            annotation_position="top right",
        )

        fig2.update_layout(
            yaxis_title="Rs.",
            margin=dict(t=10, b=10, l=10, r=10),
            height=420,
            plot_bgcolor="white",
            paper_bgcolor="white",
            showlegend=False,
        )

        fig2.update_xaxes(
            showgrid=False,
            title=None,
        )

        fig2.update_yaxes(
            gridcolor="#e5e7eb",
            zeroline=False,
        )

        st.plotly_chart(
            fig2,
            use_container_width=True,
        )

    # ============================================================
    # WHAT THE TWIN FOUND
    # ============================================================

    st.markdown("<br>", unsafe_allow_html=True)

    st.subheader("What your twin found")

    trig = twin.behaviour["triggers"]

    findings = []

    if lk["top_fee_category"]:
        findings.append(
            f"**{lk['top_fee_category']}** carries the most hidden fees: "
            f"{money(lk['top_fee_amount'])}."
        )

    findings += [t["insight"] for t in trig]

    if lk["pending_count"]:
        findings.append(
            f"{lk['pending_count']} refunds worth "
            f"{money(lk['pending_refund_amount'])} are still pending."
        )

    if lk["upcoming_autopay_30d"]:
        findings.append(
            f"{money(lk['upcoming_autopay_30d'])} of autopay "
            f"is due in the next 30 days."
        )

    if findings:

        finding_cols = st.columns(2)

        for index, finding in enumerate(findings):

            with finding_cols[index % 2]:

                st.markdown(
                    f"""
                    <div style="
                        background: white;
                        border: 1px solid #e5e7eb;
                        border-radius: 14px;
                        padding: 15px 17px;
                        margin-bottom: 12px;
                        min-height: 70px;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.03);
                    ">
                        <span style="
                            color: #2563eb;
                            font-size: 18px;
                            margin-right: 7px;
                        ">
                            •
                        </span>
                        <span style="
                            color: #374151;
                            line-height: 1.5;
                        ">
                            {finding}
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    else:

        st.info(
            "Your MoneyTwin did not find any major spending patterns yet."
        )

    # ============================================================
    # NEXT ACTION
    # ============================================================

    st.markdown(
        """
        <div style="
            background: #111827;
            border-radius: 16px;
            padding: 20px 24px;
            margin-top: 18px;
        ">
            <div style="
                color: white;
                font-size: 17px;
                font-weight: 700;
            ">
                🔮 Ready to test a change?
            </div>

            <div style="
                color: #d1d5db;
                font-size: 14px;
                margin-top: 5px;
            ">
                Open the What-if simulator to see how a different
                spending choice could affect your month.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )