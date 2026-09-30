"""What-if page: compare scenarios, get one recommendation, and teach the twin with feedback."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from ..advisor import advise
from ..formatting import money, pct
from ..simulator import default_scenarios, parse_whatif, recommend, simulate
from .common import ACCENT, NEUTRAL, PRIMARY, banners

FACTOR_LABELS = {"cook_adherence": "Cooked nights you actually keep", "wait_cancel_rate": "Impulse buys dropped after waiting 48h",
                 "save_first_elasticity": "Upfront saving that reduces spending", "leftover_saved_fraction": "Leftover money that really gets saved"}


def _what_changed(twin, base_saved: float, rec_name: str) -> None:
    """Compare with the previous plan whenever the goal or autopay changes."""
    key = (twin.profile["monthly_savings_goal"], len(twin.autopay))
    prev = st.session_state.get("last_plan")
    if prev and prev["key"] != key:
        st.info(f"What changed since your last plan: goal {money(prev['key'][0])} to {money(key[0])}, "
                f"autopay items {prev['key'][1]} to {key[1]}. "
                f"Expected savings if nothing changes: {money(prev['base_saved'])} to {money(base_saved)}. "
                f"Recommendation: {prev['rec']} to {rec_name}.")
    st.session_state["last_plan"] = {"key": key, "base_saved": base_saved, "rec": rec_name}


def render(twin, store) -> None:
    st.title("What-if simulator")
    st.caption("Play out the rest of this month under different choices and compare the results.")
    banners(twin)
    text = st.text_input("Ask a what-if", placeholder="What if I cook 3 nights a week and move Rs. 1000 to savings?")
    c = st.columns(2)
    cook = c[0].slider("Nights cooked per week", 0, 7, 3)
    save_now = c[1].number_input("Move to savings now (Rs.)", min_value=0, max_value=10000, value=1000, step=250)
    scenarios = parse_whatif(text) if text.strip() else None
    if text.strip() and scenarios is None:
        st.warning("I could not read that question. Try 'cook 3 nights', 'wait 48 hours' or 'save Rs. 1000'. Showing the standard comparison.")
    scenarios = scenarios or default_scenarios(cook, float(save_now))

    results = simulate(twin.forecast, twin.profile, twin.factors, scenarios)
    rec = recommend(results)
    _what_changed(twin, float(results.iloc[0]["projected_saved"]), rec["scenario"])

    fig = go.Figure(go.Bar(x=list(results["scenario"]), y=list(results["projected_saved"]),
                           marker_color=[ACCENT if s == rec["scenario"] else NEUTRAL for s in results["scenario"]]))
    fig.add_hline(y=float(twin.profile["monthly_savings_goal"]), line_dash="dash", line_color=PRIMARY, annotation_text="Savings goal")
    fig.update_layout(yaxis_title="Projected savings at month end (Rs.)", margin=dict(t=10, b=10))
    st.plotly_chart(fig)
    show = results[["scenario", "projected_spend", "projected_saved", "goal_miss_risk"]].copy()
    show["goal_miss_risk"] = show["goal_miss_risk"].map(pct)
    st.dataframe(show.round(0).rename(columns={"scenario": "Option", "projected_spend": "Month spend (Rs.)",
                                               "projected_saved": "Saved (Rs.)", "goal_miss_risk": "Chance of missing goal"}), hide_index=True)

    st.subheader("Advisor")
    text_out, source = advise(twin, results, rec)
    st.markdown(text_out)
    st.caption("Written by an AI model from summary numbers only." if source == "llm" else "Built-in explanation (no LLM key set).")
    used = sorted(twin.tx["category"].unique())
    st.caption(f"Data used for this advice: {len(twin.tx)} orders in {', '.join(used)}.")
    if rec["levers"]:
        b = st.columns(2)
        if b[0].button("Accept this advice", key="fb_accept"):
            store.record_feedback(rec["scenario"], list(rec["levers"]), "accept")
            st.session_state["flash"] = "Saved. The twin now trusts this kind of change a little more."
            st.rerun()
        if b[1].button("Ignore this advice", key="fb_ignore"):
            store.record_feedback(rec["scenario"], list(rec["levers"]), "ignore")
            st.session_state["flash"] = "Saved. The twin will expect you to follow this less and adjust its next recommendation."
            st.rerun()
    with st.expander("What the twin has learned about you"):
        for k, label in FACTOR_LABELS.items():
            st.write(f"{label}: {twin.factors[k] * 100:.0f}%")
        st.caption(f"{len(store.state['decisions'])} decisions recorded.")
    with st.expander("Assumptions"):
        st.write("The plan covers the rest of this month. Cooking replaces a delivery order at about Rs. 90 a meal. "
                 "Waiting 48 hours drops some late-night and sale-day purchases. Moving money now reduces spending by a share "
                 "of that amount. Effects are added together, so the combined plan is approximate.")
