"""Synthetic student spending data. No real people, banks or accounts are involved.

Run:  python -m moneytwin.synthetic
Writes transactions.csv, returns.csv, autopay.csv and user_profile.json into data/.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import data_dir

FOOD = ["ZOMATO LTD", "Swiggy*Order", "zomato", "SWIGGY"]
SHOP = ["AMAZON PAY IN", "Myntra Designs", "FLIPKART INTERNET", "Ajio Retail"]
TREND = ["Meesho", "Nykaa E-Retail", "Snitch Apparel", "boAt Lifestyle"]
GROC = ["BigBasket", "Blinkit", "Zepto"]
SUBS = [("Netflix", 199, 5), ("Spotify", 119, 12), ("Cult.fit Gym", 499, 20), ("YouTube Premium", 129, 27)]
SALE_DAYS = {10, 25}
PROFILE = {
    "name": "Demo Student",
    "monthly_allowance": 19000,
    "payday_day": 1,
    "monthly_savings_goal": 3000,
    "goal_label": "Laptop fund",
    "note": "Synthetic demo data only.",
}


def _hour(rng: np.random.Generator, late_p: float) -> int:
    if rng.random() < late_p:
        return int(rng.choice([22, 23, 0, 1]))
    return int(rng.choice([8, 9, 12, 13, 14, 17, 19, 20, 21]))


def generate(end: str = "2026-09-14", days: int = 106, seed: int = 393) -> dict:
    """Generate the demo dataset with planted, discoverable habits."""
    rng = np.random.default_rng(seed)
    end_d = pd.Timestamp(end)
    dates = pd.date_range(end=end_d, periods=days)
    tx: list[dict] = []
    ret: list[dict] = []
    counter = {"ORD": 0, "AP": 0}

    def add(d, merchant, cat, item, dl=0.0, pf=0.0, hf=0.0, sf=0.0, hour=12, prefix="ORD"):
        counter[prefix] += 1
        oid = f"{prefix}-{counter[prefix]:04d}"
        tx.append({
            "order_id": oid, "date": d.date().isoformat(), "time": f"{hour:02d}:{int(rng.integers(0, 60)):02d}",
            "merchant": merchant, "category": cat, "item_amount": item, "delivery_fee": dl,
            "platform_fee": pf, "handling_fee": hf, "surge_fee": sf, "total": item + dl + pf + hf + sf,
        })
        return oid

    def maybe_return(oid, item, d, p):
        if rng.random() >= p:
            return
        rd = d + pd.Timedelta(days=int(rng.integers(3, 9)))
        if rd > end_d:
            return
        fd = rd + pd.Timedelta(days=int(rng.integers(4, 9)))
        received = fd <= end_d
        restock = float(rng.choice([0, 0, 0, 50]))
        ret.append({
            "return_id": f"RET-{len(ret) + 1:04d}", "order_id": oid, "return_date": rd.date().isoformat(),
            "refund_amount": item - restock if received else "",
            "refund_status": "received" if received else "pending",
            "refund_date": fd.date().isoformat() if received else "",
        })

    for d in dates:
        dom = d.day
        payday = 1 <= dom <= 5
        weekend = d.dayofweek >= 4
        sale = dom in SALE_DAYS
        for _ in range(rng.poisson(0.50 * (2.4 if payday else 1.0) * (1.25 if weekend else 1.0))):
            hour = _hour(rng, 0.30)
            late = hour >= 22 or hour < 5
            item = float(np.clip(round(rng.lognormal(np.log(220), 0.35)), 90, 700))
            dl = 0.0 if rng.random() < 0.15 else float(rng.choice([25, 30, 35, 45]))
            sf = float(rng.choice([15, 20, 30])) if (late or rng.random() < 0.15) else 0.0
            add(d, rng.choice(FOOD), "Food Delivery", item, dl, float(rng.choice([5, 6, 8, 10])),
                float(rng.choice([3, 5, 7])), sf, hour)
        if rng.random() < 0.22:
            add(d, rng.choice(GROC), "Groceries", float(rng.integers(150, 600)),
                float(rng.choice([0, 0, 25])), 0.0, 5.0, 0.0, _hour(rng, 0.05))
        n_shop = 2 + rng.poisson(1.0) if sale else rng.poisson(0.06 * (2.0 if payday else 1.0))
        for _ in range(n_shop):
            hour = _hour(rng, 0.55 if sale else 0.30)
            late = hour >= 22 or hour < 5
            item = float(np.clip(round(rng.lognormal(np.log(600), 0.5)), 199, 3000))
            oid = add(d, rng.choice(SHOP), "Shopping", item, 0.0 if rng.random() < 0.6 else float(rng.choice([49, 79])),
                      float(rng.choice([0, 0, 7, 15])), float(rng.choice([0, 0, 10, 20])), 0.0, hour)
            maybe_return(oid, item, d, min(0.15 + 0.15 * late + 0.20 * sale, 0.8))
        for _ in range(rng.poisson(0.05 * (3.0 if payday else 1.0))):
            hour = _hour(rng, 0.30)
            late = hour >= 22 or hour < 5
            item = float(np.clip(round(rng.lognormal(np.log(600), 0.45)), 199, 2500))
            oid = add(d, rng.choice(TREND), "Trends", item, float(rng.choice([0, 49, 79])),
                      float(rng.choice([0, 7, 15])), float(rng.choice([0, 10])), 0.0, hour)
            maybe_return(oid, item, d, min(0.30 + 0.15 * late, 0.8))
        for name, amount, sub_dom in SUBS:
            if dom == sub_dom:
                add(d, name, "Subscriptions", float(amount), hour=3, prefix="AP")

    # Edge cases: an exact duplicate row, an unknown merchant, and a return with no matching order.
    tx.append(dict(tx[10]))
    tx.append({"order_id": "ORD-LOCAL-1", "date": (end_d - pd.Timedelta(days=2)).date().isoformat(), "time": "18:30",
               "merchant": "Local Chai Stall Kiosk 7", "category": "", "item_amount": 120.0, "delivery_fee": 0.0,
               "platform_fee": 0.0, "handling_fee": 0.0, "surge_fee": 0.0, "total": 120.0})
    ret.append({"return_id": "RET-9999", "order_id": "ORD-9999", "return_date": (end_d - pd.Timedelta(days=3)).date().isoformat(),
                "refund_amount": 499.0, "refund_status": "received", "refund_date": (end_d - pd.Timedelta(days=1)).date().isoformat()})

    autopay = pd.DataFrame([
        {"merchant": "Netflix", "amount": 199, "day_of_month": 5, "cycle": "monthly", "start_date": "2026-01-05"},
        {"merchant": "Spotify", "amount": 119, "day_of_month": 12, "cycle": "monthly", "start_date": "2026-01-12"},
        {"merchant": "Cult.fit Gym", "amount": 499, "day_of_month": 20, "cycle": "monthly", "start_date": "2026-02-20"},
        {"merchant": "Coursera Plus", "amount": 399, "day_of_month": 18, "cycle": "monthly", "start_date": "2026-09-01"},
    ])
    return {"transactions": pd.DataFrame(tx), "returns": pd.DataFrame(ret), "autopay": autopay, "profile": dict(PROFILE)}


def write_files(out_dir: Path | str | None = None, **kwargs) -> dict:
    """Generate the dataset and write the four demo files."""
    out = Path(out_dir) if out_dir else data_dir()
    out.mkdir(parents=True, exist_ok=True)
    data = generate(**kwargs)
    data["transactions"].to_csv(out / "transactions.csv", index=False)
    data["returns"].to_csv(out / "returns.csv", index=False)
    data["autopay"].to_csv(out / "autopay.csv", index=False)
    (out / "user_profile.json").write_text(json.dumps(data["profile"], indent=2))
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic MoneyTwin demo data.")
    parser.add_argument("--out", default=str(data_dir()))
    parser.add_argument("--seed", type=int, default=393)
    args = parser.parse_args()
    d = write_files(args.out, seed=args.seed)
    print(f"Wrote {len(d['transactions'])} transactions and {len(d['returns'])} returns to {args.out}")
