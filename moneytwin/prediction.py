"""Prediction Agent: chance a purchase is returned (scikit-learn) and risk of overspending."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .config import LOW_CONFIDENCE_DAYS, RETURN_CATEGORIES, RETURN_WINDOW_DAYS
from .forecast import build_forecast

MIN_ROWS_FOR_ML = 25  # fit the classifier from this many past orders
LOW_CONFIDENCE_ROWS = 40


@dataclass
class ReturnModel:
    pipe: object = None
    n: int = 0
    base_rate: float = 0.2
    cat_rates: dict = field(default_factory=dict)
    avg_fees: dict = field(default_factory=dict)
    avg_extra: float = 0.0
    avg_lag_days: float = 0.0
    confidence: str = "low"


def _features(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "trend": (df["category"] == "Trends").astype(int), "late": df["is_late_night"].astype(int),
        "sale": df["is_sale_day"].astype(int), "payday": df["is_payday_window"].astype(int),
        "log_amt": np.log1p(df["item_amount"]),
    })


def confidence_label(history_days: int, n: int = 999) -> str:
    if history_days < LOW_CONFIDENCE_DAYS or n < LOW_CONFIDENCE_ROWS:
        return "low"
    return "medium" if history_days < 90 or n < 150 else "high"


def fit_return_model(tx: pd.DataFrame, returns: pd.DataFrame, as_of: pd.Timestamp) -> ReturnModel:
    """Learn which purchases tend to come back. Falls back to category base rates when data is thin."""
    data = tx[tx["category"].isin(RETURN_CATEGORIES) & (tx["date"] <= as_of - pd.Timedelta(days=RETURN_WINDOW_DAYS))]
    history_days = int((tx["date"].max() - tx["date"].min()).days) + 1
    model = ReturnModel(n=len(data), confidence=confidence_label(history_days, len(data)))
    if len(data):
        model.base_rate = (data["returned"].sum() + 1) / (len(data) + 2)
        model.cat_rates = {c: (g["returned"].sum() + 1) / (len(g) + 2) for c, g in data.groupby("category")}
        model.avg_fees = data.groupby("category")["fees"].mean().to_dict()
    if len(returns):
        got = returns[(returns["status"] == "received") & returns["matched"]]
        if len(got):
            model.avg_extra = float((got["item_amount"] - got["refund_amount"]).clip(lower=0).mean())
            lag = (got["refund_date"] - got["return_date"]).dt.days.dropna()
            model.avg_lag_days = float(lag.mean()) if len(lag) else 0.0
    if len(data) >= MIN_ROWS_FOR_ML and data["returned"].nunique() == 2:
        model.pipe = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500))
        model.pipe.fit(_features(data), data["returned"].astype(int))
    return model


def predict_return(model: ReturnModel, category: str, amount: float, hour: int, is_sale_day: bool,
                   fees: float | None = None, is_payday_window: bool = False) -> dict:
    """Probability (with a range) that this purchase is returned, and the expected money lost if it is."""
    late = hour >= 22 or hour < 5
    if model.pipe is not None:
        row = pd.DataFrame([{"category": category, "is_late_night": late, "is_sale_day": is_sale_day,
                             "is_payday_window": is_payday_window, "item_amount": amount}])
        p = float(model.pipe.predict_proba(_features(row))[0, 1])
    else:
        p = float(model.cat_rates.get(category, model.base_rate))
    se = math.sqrt(p * (1 - p) / max(model.n, 1))
    z = 2.5 if model.confidence == "low" else 1.64
    low, high = max(0.0, p - z * se), min(1.0, p + z * se)
    fee = fees if fees is not None else model.avg_fees.get(category, float(np.mean(list(model.avg_fees.values()))) if model.avg_fees else 30.0)
    loss_if_returned = fee + model.avg_extra
    return {"prob": p, "low": low, "high": high, "confidence": model.confidence, "loss_if_returned": loss_if_returned,
            "expected_loss": p * loss_if_returned, "expected_loss_low": low * loss_if_returned,
            "expected_loss_high": high * loss_if_returned, "refund_lag_days": model.avg_lag_days}


def overspend_risk(tx: pd.DataFrame, profile: dict, as_of: pd.Timestamp, fc: dict | None = None) -> dict:
    """Chance that this month's spending breaks the budget (allowance minus savings goal)."""
    fc = fc or build_forecast(tx, as_of)
    budget = float(profile["monthly_allowance"]) - float(profile["monthly_savings_goal"])
    z = (budget - fc["projected"]) / fc["remaining_std"]
    risk = 1 - 0.5 * (1 + math.erf(z / math.sqrt(2)))
    history_days = int((tx["date"].max() - tx["date"].min()).days) + 1
    return {"budget": budget, "spent_mtd": fc["mtd"], "expected_remaining": fc["remaining_total"],
            "projected": fc["projected"], "risk": risk, "level": "low" if risk < 0.25 else "medium" if risk < 0.6 else "high",
            "risky_days": fc["risky_days"], "history_months": fc["history_months"],
            "confidence": confidence_label(history_days)}
