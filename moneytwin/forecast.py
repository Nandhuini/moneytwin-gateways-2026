"""Shared baseline forecast of the rest of the month (used by the risk model and the simulator)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import RETURN_CATEGORIES


def build_forecast(tx: pd.DataFrame, as_of: pd.Timestamp) -> dict:
    """Expect the rest of this month from the user's own history for the same days of the month."""
    month_start = as_of.replace(day=1)
    month_end = as_of + pd.offsets.MonthEnd(0)
    remaining = pd.date_range(as_of + pd.Timedelta(days=1), month_end)
    idx = pd.date_range(tx["date"].min(), tx["date"].max())
    daily = tx.groupby(["date", "category"])["net_total"].sum().unstack(fill_value=0.0).reindex(idx, fill_value=0.0)
    food = tx[tx["category"] == "Food Delivery"]
    food_n = food.groupby("date").size().reindex(idx, fill_value=0.0)

    hist = daily[daily.index < month_start]
    if len(hist) < 28:
        hist, hist_n = daily, food_n
    else:
        hist_n = food_n[food_n.index < month_start]
    by_dom, overall = hist.groupby(hist.index.day).mean(), hist.mean()
    n_by_dom, n_overall = hist_n.groupby(hist_n.index.day).mean(), float(hist_n.mean())

    rem_by_cat = pd.Series(0.0, index=daily.columns)
    exp_food_orders = 0.0
    dom_totals = by_dom.sum(axis=1)
    overall_daily = float(hist.sum(axis=1).mean())
    risky = []
    sale_doms = set(tx.loc[tx["is_sale_day"], "date"].dt.day)
    for d in remaining:
        rem_by_cat += by_dom.loc[d.day] if d.day in by_dom.index else overall
        exp_food_orders += float(n_by_dom.get(d.day, n_overall))
        spend = float(dom_totals.get(d.day, overall_daily))
        if overall_daily and spend > 1.5 * overall_daily:
            risky.append({"date": d, "expected_spend": spend,
                          "reason": "sale day" if d.day in sale_doms else "historically heavy spending"})

    monthly = hist.sum(axis=1).groupby(hist.index.to_period("M")).agg(["sum", "count"])
    full = monthly[monthly["count"] >= 25]["sum"]
    mtd = float(tx[tx["date"] >= month_start]["net_total"].sum())
    projected = mtd + float(rem_by_cat.sum())
    std_month = float(full.std(ddof=0)) if len(full) >= 2 else 0.15 * projected
    std_rem = max(std_month * np.sqrt(len(remaining) / max(month_end.day, 1)), 150.0, 0.03 * projected)

    imp = tx[tx["category"].isin(RETURN_CATEGORIES)]
    imp_total = float(imp["net_total"].sum())
    impulse_share = float(imp[imp["is_late_night"] | imp["is_sale_day"]]["net_total"].sum()) / imp_total if imp_total else 0.0
    return {
        "as_of": as_of, "month_end": month_end, "remaining_days": len(remaining), "mtd": mtd,
        "remaining_by_cat": rem_by_cat, "remaining_total": float(rem_by_cat.sum()), "projected": projected,
        "expected_food_orders": exp_food_orders,
        "avg_food_total": float(food["net_total"].mean()) if len(food) else 250.0,
        "impulse_share": impulse_share, "remaining_std": std_rem, "history_months": int(len(full)),
        "risky_days": risky,
    }
