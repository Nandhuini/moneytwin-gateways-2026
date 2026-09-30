"""Leak Detector Agent: hidden fees, unrecovered return costs, autopay calendar."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .cleaning import standardise_merchant
from .config import FEE_COLUMNS


def fee_breakdown(tx: pd.DataFrame) -> pd.DataFrame:
    """Per category: product value, each fee type, total fees and fees as % of product value."""
    cols = ["item_amount"] + FEE_COLUMNS + ["other_fees", "fees", "total"]
    g = tx.groupby("category")[cols].sum()
    g["fee_pct"] = np.where(g["item_amount"] > 0, g["fees"] / g["item_amount"] * 100, 0.0)
    return g.sort_values("fees", ascending=False).reset_index()


def return_losses(returns: pd.DataFrame) -> pd.DataFrame:
    """Money not recovered per return. Pending refunds are estimates (fees only) and flagged as unconfirmed."""
    if returns is None or returns.empty:
        return pd.DataFrame(columns=["return_id", "order_id", "merchant", "category", "return_date", "status",
                                     "total", "refund_amount", "loss", "confirmed", "pending_amount", "month"])
    r = returns[returns["matched"]].copy()
    r["loss"] = np.where(r["status"] == "received", (r["total"] - r["refund_amount"]).clip(lower=0), r["fees"])
    r["confirmed"] = r["status"] == "received"
    r["pending_amount"] = np.where(r["status"] == "pending", r["item_amount"], 0.0)
    r["month"] = r["return_date"].dt.strftime("%Y-%m")
    return r


def _next_due(last: pd.Timestamp, cycle: str, as_of: pd.Timestamp) -> pd.Timestamp:
    step = pd.DateOffset(months=1) if cycle == "monthly" else pd.DateOffset(years=1)
    nxt = last + step
    while nxt < as_of:
        nxt += step
    return nxt


def _declared_next(day: int, start: pd.Timestamp | None, as_of: pd.Timestamp) -> pd.Timestamp:
    base = max(as_of, start) if pd.notna(start) else as_of
    for offset in (0, 1):
        month = (base + pd.DateOffset(months=offset)).replace(day=1)
        cand = month.replace(day=min(day, month.days_in_month))
        if cand >= base:
            return cand
    return base


def autopay_calendar(recurring: pd.DataFrame, declared: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """Upcoming recurring debits, from detected patterns and any autopay the user declared."""
    rows, seen = [], set()
    have_declared = declared is not None and len(declared) > 0
    declared_names = set(declared["merchant"]) if have_declared else set()
    for _, r in recurring.iterrows():
        seen.add(r["merchant"])
        nxt = _next_due(r["last_charge"], r["cycle"], as_of)
        source = "detected" if not have_declared else ("detected + declared" if r["merchant"] in declared_names else "detected, not declared")
        rows.append({"merchant": r["merchant"], "amount": r["amount"], "cycle": r["cycle"],
                     "last_charge": r["last_charge"], "next_due": nxt, "source": source})
    if have_declared:
        for _, d in declared.iterrows():
            if d["merchant"] in seen:
                continue
            rows.append({"merchant": d["merchant"], "amount": d["amount"], "cycle": d["cycle"], "last_charge": pd.NaT,
                         "next_due": _declared_next(int(d["day_of_month"]), d["start_date"], as_of),
                         "source": "declared, new (not charged yet)"})
    cal = pd.DataFrame(rows, columns=["merchant", "amount", "cycle", "last_charge", "next_due", "source"])
    if cal.empty:
        cal["days_until"] = []
        return cal
    cal["days_until"] = (cal["next_due"] - as_of).dt.days
    return cal.sort_values("next_due").reset_index(drop=True)


def summarise(fees: pd.DataFrame, rl: pd.DataFrame, cal: pd.DataFrame, tx: pd.DataFrame, returns: pd.DataFrame) -> dict:
    """Headline leak numbers for the dashboard and the advisor."""
    item_total = float(fees["item_amount"].sum()) if len(fees) else 0.0
    total_fees = float(fees["fees"].sum()) if len(fees) else 0.0
    monthly_auto = 0.0
    if len(cal):
        monthly_auto = float(cal.apply(lambda r: r["amount"] / (12 if r["cycle"] == "yearly" else 1), axis=1).sum())
    upcoming = cal[cal["days_until"] <= 30] if len(cal) else cal
    top = fees.iloc[0] if len(fees) else None
    return {
        "total_fees": total_fees,
        "fee_pct_of_item": (total_fees / item_total * 100) if item_total else 0.0,
        "fees_by_type": {c: float(fees[c].sum()) for c in FEE_COLUMNS + ["other_fees"]} if len(fees) else {},
        "return_loss_confirmed": float(rl.loc[rl["confirmed"], "loss"].sum()) if len(rl) else 0.0,
        "return_loss_expected": float(rl.loc[~rl["confirmed"], "loss"].sum()) if len(rl) else 0.0,
        "pending_refund_amount": float(rl["pending_amount"].sum()) if len(rl) else 0.0,
        "pending_count": int((rl["status"] == "pending").sum()) if len(rl) else 0,
        "returns_count": int(len(rl)),
        "unmatched_returns": int((returns["status"] == "unmatched").sum()) if len(returns) else 0,
        "monthly_autopay": monthly_auto,
        "upcoming_autopay_30d": float(upcoming["amount"].sum()) if len(upcoming) else 0.0,
        "top_fee_category": None if top is None else str(top["category"]),
        "top_fee_amount": 0.0 if top is None else float(top["fees"]),
    }
