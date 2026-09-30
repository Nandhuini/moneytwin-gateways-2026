"""Consent & Intake Layer: only permitted categories enter the twin, and what was used is recorded."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from .config import ALL_CATEGORIES


def apply_consent(tx: pd.DataFrame, ret: pd.DataFrame, declared: pd.DataFrame, allowed: list[str]):
    """Drop every row belonging to a switched-off category, everywhere (orders, returns, autopay)."""
    allowed = set(allowed)
    tx_ok = tx[tx["category"].isin(allowed)].copy()
    ret_ok = ret[ret["order_id"].isin(tx_ok["order_id"]) | ~ret["matched"]].copy() if len(ret) else ret
    declared_ok = declared if "Subscriptions" in allowed else declared.iloc[0:0]
    return tx_ok, ret_ok, declared_ok


def excluded_summary(tx_all: pd.DataFrame, allowed: list[str]) -> dict:
    """What the twin could not consider because the user switched it off."""
    off = tx_all[~tx_all["category"].isin(set(allowed))]
    return {c: {"rows": int(len(g)), "amount": float(g["total"].sum())} for c, g in off.groupby("category")}


def describe_exclusions(excluded: dict) -> str:
    if not excluded:
        return ""
    parts = ", ".join(f"{c} ({v['rows']} orders)" for c, v in excluded.items())
    return f"Not considered because you switched them off: {parts}. Results may be incomplete."


def usage_entry(source: str, allowed: list[str], rows: int) -> dict:
    """One line of the 'data used' log."""
    return {"time": datetime.now().strftime("%Y-%m-%d %H:%M"), "source": source,
            "categories": list(allowed), "rows": int(rows),
            "switched_off": [c for c in ALL_CATEGORIES if c not in set(allowed)]}
