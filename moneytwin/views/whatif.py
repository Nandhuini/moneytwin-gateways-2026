"""What-if page: compare scenarios, get one recommendation, and teach the twin with feedback."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from ..advisor import advise
from ..formatting import money, pct
from ..simulator import default_scenarios, parse_whatif, recommend, simulate
from .common import (ACCENT, NEUTRAL, PRIMARY, banners, bar, card, esc, html_block, page_header, pill, section, show_chart,
                     show_table, style_fig)

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


def _scenario_panel(heading: str, row, goal: float, is_plan: bool) -> None:
    """One side of the current-versus-simulated comparison."""
    saved = float(row["projected_saved"])
    share = min(saved / goal, 1.0) if goal > 0 else 1.0
    goal_text = f"{share * 100:.0f}% of your goal of {money(goal)}" if goal > 0 else "No savings goal set"
    rows = [("Spending this month", money(row["projected_spend"])),
            ("Chance of missing your goal", pct(row["goal_miss_risk"])),
            ("Still short of goal", money(row["goal_gap"]))]
    rows_html = "".join(f"<div><span>{esc(k)}</span><b>{esc(v)}</b></div>" for k, v in rows)
    html_block(f'<div class="mt-card mt-side{" is-plan" if is_plan else ""}"><div class="mt-side-head">{esc(heading)}</div>'
               f'<div class="mt-side-name">{esc(row["scenario"])}</div><div class="mt-side-big">{esc(money(saved))}</div>'
               f'<div class="mt-note">projected savings at month end</div>'
               f'<div style="margin:12px 0 6px">{bar([(share, PRIMARY if is_plan else NEUTRAL)], height=10)}</div>'
               f'<div class="mt-note">{esc(goal_text)}</div><div class="mt-rows">{rows_html}</div></div>')


def _saving_banner(base, rec) -> None:
    """The headline: how much more the recommended plan saves compared with doing nothing."""
    extra = float(rec["projected_saved"]) - float(base["projected_saved"])
    if rec["n_levers"] > 0 and extra > 0:
        html_block(f'<div class="mt-saving"><div class="mt-saving-label">Potential extra savings this month</div>'
                   f'<div class="mt-saving-big">+{esc(money(extra))}</div>'
                   f'<div class="mt-saving-sub">by choosing <b>{esc(rec["scenario"])}</b>. The chance of missing your goal moves from '
                   f'{esc(pct(base["goal_miss_risk"]))} to {esc(pct(rec["goal_miss_risk"]))}.</div></div>')
        parts = [("Cooking at home", rec["cook_saving"]), ("Waiting 48 hours", rec["wait_saving"]), ("Saving first", rec["save_effect"])]
        chips = [pill(f"{name}: {money(v)}", "good") for name, v in parts if float(v) > 0.5]
        if chips:
            html_block('<div class="mt-note" style="margin:-6px 0 12px">Where it comes from: ' + " ".join(chips) + "</div>")
    else:
        reason = ("Your current habits already reach your savings goal." if float(base["projected_saved"]) >= float(base["goal"])
                  else "None of the options tested beats your current plan, so there is nothing extra to gain from these changes.")
        html_block(f'<div class="mt-saving is-flat"><div class="mt-saving-label">Potential extra savings this month</div>'
                   f'<div class="mt-saving-big">{esc(money(0))}</div><div class="mt-saving-sub">{esc(reason)}</div></div>')


def render(twin, store) -> None:
    page_header("Scenario lab", "What-if simulator", "Play out the rest of this month under different choices and compare the results.")
    banners(twin)

    with card():
        section("Build your scenario", "Type a question, or set the two controls below.")
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

    # ---- current versus simulated ----
    base_rows = results[results["n_levers"] == 0]
    base = base_rows.iloc[0] if len(base_rows) else results.iloc[0]
    goal = float(rec["goal"])
    _saving_banner(base, rec)
    left, right = st.columns(2)
    with left:
        _scenario_panel("Today: if nothing changes", base, goal, is_plan=False)
    with right:
        _scenario_panel("Simulated: recommended plan", rec, goal, is_plan=True)

    # ---- all options ----
    with card():
        section("All options compared", "The highlighted bar is the recommendation. The dashed line is your savings goal.")
        fig = go.Figure(go.Bar(x=list(results["scenario"]), y=list(results["projected_saved"]),
                               marker_color=[PRIMARY if s == rec["scenario"] else NEUTRAL for s in results["scenario"]],
                               text=[money(v) for v in results["projected_saved"]], textposition="outside", cliponaxis=False,
                               hovertemplate="Rs. %{y:,.0f}<extra>%{x}</extra>"))
        fig.add_hline(y=float(twin.profile["monthly_savings_goal"]), line_dash="dash", line_color=ACCENT, annotation_text="Savings goal")
        fig.update_layout(yaxis_title="Projected savings at month end (Rs.)")
        show_chart(style_fig(fig, height=360))
        show = results[["scenario", "projected_spend", "projected_saved", "goal_miss_risk"]].copy()
        show["goal_miss_risk"] = show["goal_miss_risk"].map(pct)
        show_table(show.round(0).rename(columns={"scenario": "Option", "projected_spend": "Month spend (Rs.)",
                                                 "projected_saved": "Saved (Rs.)", "goal_miss_risk": "Chance of missing goal"}))

    # ---- advisor and feedback ----
    with card():
        section("Advisor")
        text_out, source = advise(twin, results, rec)
        st.markdown(text_out)
        st.caption("Written by an AI model from summary numbers only." if source == "llm" else "Built-in explanation (no LLM key set).")
        used = sorted(twin.tx["category"].unique())
        st.caption(f"Data used for this advice: {len(twin.tx)} orders in {', '.join(used)}.")
        if rec["levers"]:
            b = st.columns(2)
            if b[0].button("Accept this advice", key="fb_accept", type="primary"):
                store.record_feedback(rec["scenario"], list(rec["levers"]), "accept")
                st.session_state["flash"] = "Saved. The twin now trusts this kind of change a little more."
                st.rerun()
            if b[1].button("Ignore this advice", key="fb_ignore"):
                store.record_feedback(rec["scenario"], list(rec["levers"]), "ignore")
                st.session_state["flash"] = "Saved. The twin will expect you to follow this less and adjust its next recommendation."
                st.rerun()
    with st.expander("What the twin has learned about you"):
        for k, label in FACTOR_LABELS.items():
            st.progress(min(max(float(twin.factors[k]), 0.0), 1.0), text=f"{label}: {twin.factors[k] * 100:.0f}%")
        st.caption(f"{len(store.state['decisions'])} decisions recorded.")
    with st.expander("Assumptions"):
        st.write("The plan covers the rest of this month. Cooking replaces a delivery order at about Rs. 90 a meal. "
                 "Waiting 48 hours drops some late-night and sale-day purchases. Moving money now reduces spending by a share "
                 "of that amount. Effects are added together, so the combined plan is approximate.")
