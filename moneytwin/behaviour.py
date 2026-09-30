"""Behaviour Pattern Agent: when the user overspends and what triggers it."""
from __future__ import annotations

import pandas as pd

from .config import RETURN_CATEGORIES

BUCKETS = [(1, 5, "1-5"), (6, 10, "6-10"), (11, 15, "11-15"), (16, 20, "16-20"), (21, 25, "21-25"), (26, 31, "26-31")]
BANDS = ["Morning (5-11)", "Afternoon (12-16)", "Evening (17-21)", "Late night (22-4)"]


def time_band(hour: int) -> str:
    if hour >= 22 or hour < 5:
        return BANDS[3]
    if hour < 12:
        return BANDS[0]
    return BANDS[1] if hour < 17 else BANDS[2]


def dom_bucket(dom: int) -> str:
    return next(label for lo, hi, label in BUCKETS if lo <= dom <= hi)


def add_flags(tx: pd.DataFrame, payday_day: int) -> pd.DataFrame:
    """Add band, bucket, payday-window and sale-day flags (sale day = 3+ shopping/trend orders in one day)."""
    tx = tx.copy()
    tx["band"] = tx["hour"].map(time_band)
    tx["bucket"] = tx["dom"].map(dom_bucket)
    tx["is_payday_window"] = ((tx["dom"] - int(payday_day)) % 31) < 5
    shop = tx[tx["category"].isin(RETURN_CATEGORIES)]
    counts = shop.groupby("date").size()
    sale_dates = set(counts[counts >= 3].index)
    tx["is_sale_day"] = tx["date"].isin(sale_dates)
    return tx


def analyze(tx: pd.DataFrame, payday_day: int) -> dict:
    """Heatmap of net spend by time of month and time of day, plus personal triggers."""
    disc = tx[~tx["is_recurring"]]
    heat = disc.pivot_table(index="band", columns="bucket", values="net_total", aggfunc="sum", fill_value=0.0)
    heat = heat.reindex(index=BANDS, columns=[b[2] for b in BUCKETS], fill_value=0.0)
    total = float(disc["net_total"].sum()) or 1.0
    idx = pd.date_range(disc["date"].min(), disc["date"].max())
    daily = disc.groupby("date")["net_total"].sum().reindex(idx, fill_value=0.0)
    is_pay = pd.Series(((idx.day - int(payday_day)) % 31) < 5, index=idx)
    pay_avg, other_avg = float(daily[is_pay].mean() or 0), float(daily[~is_pay].mean() or 0)
    uplift = pay_avg / other_avg if other_avg else 0.0
    late = disc[disc["is_late_night"]]
    late_share = float(late["net_total"].sum()) / total
    fee_gap = float(late["fees"].mean() - disc[~disc["is_late_night"]]["fees"].mean()) if len(late) else 0.0
    shop = disc[disc["category"].isin(RETURN_CATEGORIES)]
    sale = shop[shop["is_sale_day"]]
    sale_share = float(sale["net_total"].sum()) / float(shop["net_total"].sum() or 1.0)
    triggers = [
        {"name": "Right after payday", "share": float(disc[disc["is_payday_window"]]["net_total"].sum()) / total, "uplift": uplift,
         "insight": f"You spend {uplift:.1f}x more per day in the first 5 days after money arrives."},
        {"name": "Late night (10pm-5am)", "share": late_share, "uplift": None,
         "insight": f"{late_share * 100:.0f}% of spending happens late at night, with about Rs. {fee_gap:.0f} more in fees per order."},
        {"name": "Sale days", "share": sale_share, "uplift": None,
         "insight": f"{sale_share * 100:.0f}% of shopping and trend spend lands on {sale['date'].nunique()} sale days."},
    ]
    stacked = heat.stack()
    peak = stacked.idxmax() if stacked.sum() > 0 else (BANDS[0], BUCKETS[0][2])
    return {"heatmap": heat, "triggers": triggers, "peak_band": peak[0], "peak_bucket": peak[1], "late_night_share": late_share}
