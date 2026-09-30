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
        return [
            k
            for k, on in (
                ("cook", self.cook_nights > 0),
                ("wait", self.wait_48h),
                ("save", self.save_now > 0),
            )
            if on
        ]


def default_scenarios(
    cook_nights: int = 3,
    save_now: float = 1000.0,
) -> list[Scenario]:
    """The standard comparison set: do nothing, each single change, and all together."""
    return [
        Scenario("Keep current habits"),
        Scenario(
            f"Cook {cook_nights} nights a week",
            cook_nights=cook_nights,
        ),
        Scenario(
            "Wait 48 hours before impulse buys",
            wait_48h=True,
        ),
        Scenario(
            f"Move Rs. {save_now:,.0f} to savings now",
            save_now=save_now,
        ),
        Scenario(
            "Combined plan",
            cook_nights=cook_nights,
            wait_48h=True,
            save_now=save_now,
        ),
    ]


def parse_whatif(
    text: str,
    default_cook: int = 3,
    default_save: float = 1000.0,
) -> list[Scenario] | None:
    """Turn a typed question into a small what-if scenario set."""
    if not isinstance(text, str):
        return None

    t = text.lower().strip()

    # Multi-digit cooking values are supported.
    cook = (
        re.search(r"\bcook\w*\s*(?:for\s*)?(\d+)\s*night", t)
        or re.search(r"\b(\d+)\s*nights?\b", t)
    )

    # Amounts such as Rs. 1,000 / INR 1000 / 1000 to savings.
    amount = (
        re.search(r"(?:rs\.?|inr|₹)\s*([\d,]+)", t)
        or re.search(r"\b([\d,]{3,})\s*(?:to|in)?\s*savings?\b", t)
    )

    # Only treat an explicit waiting phrase as the wait lever.
    wait = bool(
        re.search(
            r"\bwait\s*(?:for\s*)?(?:48\s*(?:hours?|hrs?)|two\s*days?)\b",
            t,
        )
        or re.search(
            r"\b48\s*(?:hours?|hrs?)\b.*\bwait\b|\bwait\b.*\b48\s*(?:hours?|hrs?)\b",
            t,
        )
    )

    if not (cook or amount or wait):
        return None

    n = min(int(cook.group(1)), 7) if cook else 0
    s = float(amount.group(1).replace(",", "")) if amount else 0.0

    combo = Scenario(
        "Your what-if",
        cook_nights=n,
        wait_48h=wait,
        save_now=s,
    )

    return [
        Scenario("Keep current habits"),
        combo,
    ]


def _savings(fc: dict, factors: dict, sc: Scenario) -> dict:
    rem = fc["remaining_by_cat"]
    cook = wait = 0.0

    if sc.cook_nights > 0:
        meals = round(
            sc.cook_nights
            / 7
            * fc["remaining_days"]
            * factors["cook_adherence"]
        )
        avoided = min(meals, fc["expected_food_orders"])
        cook = avoided * (
            fc["avg_food_total"] - COOK_COST_PER_MEAL
        )

    if sc.wait_48h:
        impulse = (
            float(rem.get("Shopping", 0.0))
            + float(rem.get("Trends", 0.0))
        ) * fc["impulse_share"]
        wait = factors["wait_cancel_rate"] * impulse

    room = max(
        0.0,
        fc["remaining_total"]
        - float(rem.get("Subscriptions", 0.0))
        - cook
        - wait,
    )

    save = min(
        factors["save_first_elasticity"] * sc.save_now,
        room,
    )

    return {
        "cook": max(cook, 0.0),
        "wait": max(wait, 0.0),
        "save": max(save, 0.0),
    }


def simulate(
    fc: dict,
    profile: dict,
    factors: dict,
    scenarios: list[Scenario],
) -> pd.DataFrame:
    """Compare month-end spend, savings and chance of missing the goal."""
    allowance = float(profile["monthly_allowance"])
    goal = float(profile["monthly_savings_goal"])

    # Prevent division-by-zero from breaking risk calculation.
    frac = float(factors.get("leftover_saved_fraction", 0.6))
    frac = max(frac, 0.05)

    remaining_std = max(float(fc.get("remaining_std", 0.0)), 0.01)

    rows = []

    for sc in scenarios:
        s = _savings(fc, factors, sc)

        spend = (
            fc["mtd"]
            + fc["remaining_total"]
            - sum(s.values())
        )

        saved = (
            sc.save_now
            + frac * max(
                0.0,
                allowance - sc.save_now - spend,
            )
        )

        threshold = (
            allowance
            - sc.save_now
            - max(goal - sc.save_now, 0.0) / frac
        )

        z = (threshold - spend) / remaining_std

        miss = 1 - 0.5 * (
            1 + math.erf(z / math.sqrt(2))
        )

        rows.append(
            {
                "scenario": sc.name,
                "levers": sc.levers,
                "n_levers": len(sc.levers),
                "cook_saving": s["cook"],
                "wait_saving": s["wait"],
                "save_effect": s["save"],
                "projected_spend": spend,
                "projected_saved": saved,
                "goal": goal,
                "goal_gap": max(goal - saved, 0.0),
                "goal_miss_risk": miss,
            }
        )

    return pd.DataFrame(rows)


def recommend(
    results: pd.DataFrame,
    acceptable_risk: float = 0.4,
) -> pd.Series:
    """Pick the least-effort option that gets the user to their goal; else best-saving option."""

    if results.empty:
        raise ValueError("No scenario results available")

    # Safely use the baseline if it exists.
    base_rows = results[results["n_levers"] == 0]

    if base_rows.empty:
        return results.sort_values(
            "projected_saved",
            ascending=False,
        ).iloc[0]

    base = base_rows.iloc[0]

    # If the current plan already meets the goal, keep the baseline.
    if base["projected_saved"] >= base["goal"]:
        return base

    cands = results[
        (results["n_levers"] > 0)
        & (
            results["projected_saved"]
            > base["projected_saved"] + 1
        )
    ]

    if cands.empty:
        return base

    ok = cands[
        cands["goal_miss_risk"] <= acceptable_risk
    ]

    if not ok.empty:
        return ok.sort_values(
            ["n_levers", "projected_saved"],
            ascending=[True, False],
        ).iloc[0]

    return cands.sort_values(
        "projected_saved",
        ascending=False,
    ).iloc[0]