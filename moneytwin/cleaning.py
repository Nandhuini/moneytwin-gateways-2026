"""Cleaning & Categorisation Agent: standardise merchants, split fees, link returns, tag autopay."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import ALL_CATEGORIES, FEE_COLUMNS, LATE_NIGHT_END, LATE_NIGHT_START, UNCATEGORISED

MERCHANT_RULES = [
    (r"zomato", "Zomato", "Food Delivery"), (r"swiggy", "Swiggy", "Food Delivery"),
    (r"amazon", "Amazon", "Shopping"), (r"myntra", "Myntra", "Shopping"),
    (r"flipkart", "Flipkart", "Shopping"), (r"ajio", "Ajio", "Shopping"),
    (r"meesho", "Meesho", "Trends"), (r"nykaa", "Nykaa", "Trends"),
    (r"snitch", "Snitch", "Trends"), (r"boat", "boAt", "Trends"),
    (r"bigbasket", "BigBasket", "Groceries"), (r"blinkit", "Blinkit", "Groceries"),
    (r"zepto", "Zepto", "Groceries"),
    (r"netflix", "Netflix", "Subscriptions"), (r"spotify", "Spotify", "Subscriptions"),
    (r"cult\.?fit", "Cult.fit", "Subscriptions"), (r"youtube", "YouTube Premium", "Subscriptions"),
    (r"coursera", "Coursera", "Subscriptions"),
]
REQUIRED = ["order_id", "date", "merchant", "total"]
RETURN_COLS = ["return_id", "order_id", "return_date", "refund_amount", "refund_date", "status", "matched",
               "order_date", "merchant", "category", "item_amount", "fees", "total"]


@dataclass
class CleaningReport:
    rows_in: int = 0
    rows_out: int = 0
    duplicates_removed: int = 0
    invalid_rows: int = 0
    uncategorised: list = field(default_factory=list)


def standardise_merchant(raw: str, user_labels: dict | None = None) -> tuple[str, str | None]:
    """Return (canonical merchant name, category or None). User labels win over built-in rules."""
    text = re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9 .&'-]", " ", str(raw))).strip()
    key = str(raw).strip().lower()
    if user_labels and key in user_labels:
        return text, user_labels[key]
    for pattern, name, cat in MERCHANT_RULES:
        if re.search(pattern, key):
            return name, cat
    return text, None


def clean_transactions(df: pd.DataFrame, user_labels: dict | None = None) -> tuple[pd.DataFrame, CleaningReport]:
    """Validate and standardise a transactions table. Raises ValueError with a clear message if unusable."""
    out = df.copy()
    out.columns = [str(c).strip().lower() for c in out.columns]
    missing = [c for c in REQUIRED if c not in out.columns]
    if missing:
        raise ValueError(f"Transactions file is missing required column(s): {', '.join(missing)}. "
                         f"Expected at least: {', '.join(REQUIRED)}.")
    report = CleaningReport(rows_in=len(out))
    out = out.drop_duplicates().drop_duplicates(subset="order_id", keep="first")
    report.duplicates_removed = report.rows_in - len(out)
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["total"] = pd.to_numeric(out["total"], errors="coerce")
    before = len(out)
    out = out.dropna(subset=["date", "total"])
    report.invalid_rows = before - len(out)
    if out.empty:
        raise ValueError("No valid rows found. Check that 'date' and 'total' contain real dates and numbers.")

    for c in FEE_COLUMNS:
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0) if c in out.columns else 0.0
    if any(c in df.columns.str.lower() for c in FEE_COLUMNS):
        fees = out[FEE_COLUMNS].sum(axis=1)
    elif "fees" in out.columns:
        fees = pd.to_numeric(out["fees"], errors="coerce").fillna(0.0)
    elif "item_amount" in out.columns:
        fees = (out["total"] - pd.to_numeric(out["item_amount"], errors="coerce")).clip(lower=0).fillna(0.0)
    else:
        fees = pd.Series(0.0, index=out.index)
    out["fees"] = fees.clip(lower=0)
    out["other_fees"] = (out["fees"] - out[FEE_COLUMNS].sum(axis=1)).clip(lower=0)
    out["item_amount"] = (out["total"] - out["fees"]).clip(lower=0)

    times = out["time"].astype(str) if "time" in out.columns else pd.Series("12:00", index=out.index)
    out["hour"] = pd.to_numeric(times.str.extract(r"^(\d{1,2})")[0], errors="coerce").fillna(12).astype(int).clip(0, 23)

    std = [standardise_merchant(m, user_labels) for m in out["merchant"]]
    out["raw_merchant"] = out["merchant"]
    out["merchant"] = [s[0] for s in std]
    rule_cat = pd.Series([s[1] for s in std], index=out.index)
    given = out["category"] if "category" in out.columns else pd.Series(None, index=out.index, dtype=object)
    given = given.where(given.isin(ALL_CATEGORIES))
    out["category"] = rule_cat.fillna(given).fillna(UNCATEGORISED)

    out["dom"] = out["date"].dt.day
    out["dow"] = out["date"].dt.dayofweek
    out["month"] = out["date"].dt.strftime("%Y-%m")
    out["is_late_night"] = (out["hour"] >= LATE_NIGHT_START) | (out["hour"] < LATE_NIGHT_END)
    out["is_recurring"] = False
    out = out.sort_values(["date", "hour"]).reset_index(drop=True)
    report.rows_out = len(out)
    report.uncategorised = sorted(out.loc[out["category"] == UNCATEGORISED, "raw_merchant"].astype(str).unique())
    return out, report


def clean_returns(ret: pd.DataFrame | None, tx: pd.DataFrame) -> pd.DataFrame:
    """Link returns to their original orders. Status is received, pending or unmatched (never guessed)."""
    if ret is None or len(ret) == 0:
        return pd.DataFrame(columns=RETURN_COLS)
    r = ret.copy()
    r.columns = [str(c).strip().lower() for c in r.columns]
    if "order_id" not in r.columns:
        raise ValueError("Returns file needs an 'order_id' column to link returns to orders.")
    for c in ("return_id", "return_date", "refund_date"):
        if c not in r.columns:
            r[c] = None
    r["return_date"] = pd.to_datetime(r["return_date"], errors="coerce")
    r["refund_date"] = pd.to_datetime(r["refund_date"], errors="coerce")
    r["refund_amount"] = pd.to_numeric(r.get("refund_amount", 0), errors="coerce").fillna(0.0)
    if "refund_status" in r.columns:
        received = r["refund_status"].astype(str).str.lower().str.contains("receiv|credit|complete|done|success")
    else:
        received = r["refund_amount"] > 0
    r["status"] = np.where(received, "received", "pending")
    orders = tx[["order_id", "date", "merchant", "category", "item_amount", "fees", "total"]].rename(columns={"date": "order_date"})
    m = r.merge(orders, on="order_id", how="left")
    m["matched"] = m["total"].notna()
    m.loc[~m["matched"], "status"] = "unmatched"
    return m[RETURN_COLS].reset_index(drop=True)


def attach_refunds(tx: pd.DataFrame, ret: pd.DataFrame) -> pd.DataFrame:
    """Add refund, returned, refund_status and net_total (money out after refunds; pending refunds assumed coming)."""
    tx = tx.copy()
    tx["refund"], tx["returned"], tx["refund_status"] = 0.0, False, ""
    if ret is not None and len(ret):
        m = ret[ret["matched"]]
        est = pd.Series(np.where(m["status"] == "received", m["refund_amount"], m["item_amount"]), index=m["order_id"].to_numpy())
        tx["refund"] = tx["order_id"].map(est.groupby(level=0).sum()).fillna(0.0)
        tx["returned"] = tx["order_id"].isin(m["order_id"])
        tx["refund_status"] = tx["order_id"].map(m.groupby("order_id")["status"].first()).fillna("")
    tx["net_total"] = tx["total"] - tx["refund"]
    return tx


def clean_autopay(ap: pd.DataFrame | None) -> pd.DataFrame:
    """Standardise a declared-autopay table (optional input)."""
    cols = ["merchant", "amount", "day_of_month", "cycle", "start_date"]
    if ap is None or len(ap) == 0:
        return pd.DataFrame(columns=cols)
    a = ap.copy()
    a.columns = [str(c).strip().lower() for c in a.columns]
    if "merchant" not in a.columns or "amount" not in a.columns:
        raise ValueError("Autopay file needs 'merchant' and 'amount' columns.")
    a["merchant"] = [standardise_merchant(m)[0] for m in a["merchant"]]
    a["amount"] = pd.to_numeric(a["amount"], errors="coerce").fillna(0.0)
    a["day_of_month"] = pd.to_numeric(a.get("day_of_month", 1), errors="coerce").fillna(1).astype(int)
    a["cycle"] = a["cycle"].fillna("monthly") if "cycle" in a.columns else "monthly"
    a["start_date"] = pd.to_datetime(a.get("start_date"), errors="coerce")
    return a[cols].reset_index(drop=True)


def detect_recurring(tx: pd.DataFrame) -> pd.DataFrame:
    """Find merchants charged a fixed amount on a steady monthly or yearly rhythm."""
    rows = []
    for merchant, g in tx.groupby("merchant"):
        if len(g) < 2:
            continue
        g = g.sort_values("date")
        amounts = g["total"].to_numpy()
        if amounts.mean() == 0 or amounts.std() / amounts.mean() > 0.05:
            continue
        gaps = g["date"].diff().dt.days.dropna()
        if 26 <= gaps.median() <= 35 and gaps.std(ddof=0) <= 4:
            cycle = "monthly"
        elif 355 <= gaps.median() <= 375:
            cycle = "yearly"
        else:
            continue
        rows.append({"merchant": merchant, "amount": float(amounts[-1]), "cycle": cycle,
                     "last_charge": g["date"].iloc[-1], "charges": len(g)})
    return pd.DataFrame(rows, columns=["merchant", "amount", "cycle", "last_charge", "charges"])


def tag_recurring(tx: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Mark recurring payments in the transactions table and return the recurring summary."""
    recurring = detect_recurring(tx)
    tx = tx.copy()
    tx["is_recurring"] = tx["merchant"].isin(recurring["merchant"])
    return tx, recurring
