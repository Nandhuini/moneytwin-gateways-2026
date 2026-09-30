"""Scenario Simulator: play out 'what if' choices for the rest of the month using the twin's own numbers."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

import pandas as pd

from .config import COOK_COST_PER_MEAL


@dataclass(frozen=True)
class Scenario:
    name: str
    cook_nights: int = 0
    wait_48h: bool = False
    save_now: float = 0.0

    @property
    def levers(self) -> list[str]:
        return [k for k, on in (("cook", self.cook_nights > 0), ("wait", self.wait_48h), ("save", self.save_now > 0)) if on]


def default_scenarios(cook_nights: int = 3, save_now: float = 1000.0) -> list[Scenario]:
    """The standard comparison set: do nothing, each single change, and all together."""
    return [Scenario("Keep current habits"), Scenario(f"Cook {cook_nights} nights a week", cook_nights=cook_nights),
            Scenario("Wait 48 hours before impulse buys", wait_48h=True),
            Scenario(f"Move Rs. {save_now:,.0f} to savings now", save_now=save_now),
            Scenario("Combined plan", cook_nights=cook_nights, wait_48h=True, save_now=save_now)]


def parse_whatif(text: str, default_cook: int = 3, default_save: float = 1000.0) -> list[Scenario] | None:
    """Turn a typed question like 'cook 3 nights and save Rs. 1000' into a scenario set (None if not understood)."""
    t = text.lower()
    cook = re.search(r"cook\w*\s*(?:for\s*)?(\d)\s*night", t) or re.search(r"(\d)\s*nights?", t)
    amount = re.search(r"(?:rs\.?|inr|₹)\s*([\d,]+)", t) or re.search(r"([\d,]{3,})\s*(?:to|in)?\s*saving", t)
    wait = bool(re.search(r"wait|48", t))
    if not (cook or amount or wait):
        return None
    n = int(cook.group(1)) if cook else 0
    s = float(amount.group(1).replace(",", "")) if amount else 0.0
    combo = Scenario("Your what-if", cook_nights=n, wait_48h=wait, save_now=s)
    return [Scenario("Keep current habits"), combo]


def _savings(fc: dict, factors: dict, sc: Scenario) -> dict:
    rem = fc["remaining_by_cat"]
    cook = wait = 0.0
    if sc.cook_nights > 0:
        meals = round(sc.cook_nights / 7 * fc["remaining_days"] * factors["cook_adherence"])
        avoided = min(meals, fc["expected_food_orders"])
        cook = avoided * (fc["avg_food_total"] - COOK_COST_PER_MEAL)
    if sc.wait_48h:
        impulse = float(rem.get("Shopping", 0.0) + rem.get("Trends", 0.0)) * fc["impulse_share"]
        wait = factors["wait_cancel_rate"] * impulse
    room = max(0.0, fc["remaining_total"] - float(rem.get("Subscriptions", 0.0)) - cook - wait)
    save = min(factors["save_first_elasticity"] * sc.save_now, room)
    return {"cook": max(cook, 0.0), "wait": wait, "save": save}


def simulate(fc: dict, profile: dict, factors: dict, scenarios: list[Scenario]) -> pd.DataFrame:
    """Compare month-end spend, savings and the chance of missing the goal for each scenario."""
    allowance, goal, frac = float(profile["monthly_allowance"]), float(profile["monthly_savings_goal"]), factors["leftover_saved_fraction"]
    rows = []
    for sc in scenarios:
        s = _savings(fc, factors, sc)
        spend = fc["mtd"] + fc["remaining_total"] - sum(s.values())
        saved = sc.save_now + frac * max(0.0, allowance - sc.save_now - spend)
        threshold = allowance - sc.save_now - max(goal - sc.save_now, 0.0) / frac
        miss = 1 - 0.5 * (1 + math.erf(((threshold - spend) / fc["remaining_std"]) / math.sqrt(2)))
        rows.append({"scenario": sc.name, "levers": sc.levers, "n_levers": len(sc.levers), "cook_saving": s["cook"],
                     "wait_saving": s["wait"], "save_effect": s["save"], "projected_spend": spend,
                     "projected_saved": saved, "goal": goal, "goal_gap": max(goal - saved, 0.0), "goal_miss_risk": miss})
    return pd.DataFrame(rows)


def recommend(results: pd.DataFrame, acceptable_risk: float = 0.4) -> pd.Series:
    """Pick the least-effort option that gets the user to their goal; else the best-saving option."""
    base = results[results["n_levers"] == 0].iloc[0]
    cands = results[(results["n_levers"] > 0) & (results["projected_saved"] > base["projected_saved"] + 1)]
    if cands.empty:
        return base
    ok = cands[cands["goal_miss_risk"] <= acceptable_risk]
    if not ok.empty:
        return ok.sort_values(["n_levers", "projected_saved"], ascending=[True, False]).iloc[0]
    return cands.sort_values("projected_saved", ascending=False).iloc[0]
