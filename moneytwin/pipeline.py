"""Wires the agents together into one Twin object."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from . import behaviour, consent, leaks
from .cleaning import (CleaningReport, attach_refunds, clean_autopay, clean_returns, clean_transactions, tag_recurring)
from .config import ALL_CATEGORIES
from .forecast import build_forecast
from .prediction import ReturnModel, confidence_label, fit_return_model, overspend_risk
from .twin_store import TwinStore


@dataclass
class Twin:
    profile: dict
    as_of: pd.Timestamp
    tx: pd.DataFrame
    returns: pd.DataFrame
    recurring: pd.DataFrame
    autopay: pd.DataFrame
    fees: pd.DataFrame
    return_loss: pd.DataFrame
    leaks: dict
    behaviour: dict
    return_model: ReturnModel
    forecast: dict
    risk: dict
    excluded: dict
    report: CleaningReport
    allowed: list
    factors: dict
    history_days: int
    confidence: str

    @property
    def risk_days_left(self) -> int:
        return int(self.forecast["remaining_days"])


def build_twin(tx_raw: pd.DataFrame, ret_raw: pd.DataFrame | None, ap_raw: pd.DataFrame | None,
               profile: dict, store: TwinStore, allowed: list[str] | None = None) -> Twin:
    """Run the full pipeline on the categories the user has allowed."""
    tx_all, report = clean_transactions(tx_raw, store.labels)
    ret_all = clean_returns(ret_raw, tx_all)
    tx_all = attach_refunds(tx_all, ret_all)
    allowed = list(ALL_CATEGORIES if allowed is None else allowed)
    tx, ret, declared = consent.apply_consent(tx_all, ret_all, clean_autopay(ap_raw), allowed)
    if tx.empty:
        raise ValueError("Every category is switched off, so the twin has nothing to learn from. Switch at least one on in Privacy & data.")
    tx, recurring = tag_recurring(tx)
    tx = behaviour.add_flags(tx, profile["payday_day"])
    as_of = tx["date"].max()
    fees = leaks.fee_breakdown(tx)
    rl = leaks.return_losses(ret)
    cal = leaks.autopay_calendar(recurring, declared, as_of)
    fc = build_forecast(tx, as_of)
    history_days = int((tx["date"].max() - tx["date"].min()).days) + 1
    return Twin(profile=profile, as_of=as_of, tx=tx, returns=ret, recurring=recurring, autopay=cal, fees=fees, return_loss=rl,
                leaks=leaks.summarise(fees, rl, cal, tx, ret), behaviour=behaviour.analyze(tx, profile["payday_day"]),
                return_model=fit_return_model(tx, ret, as_of), forecast=fc, risk=overspend_risk(tx, profile, as_of, fc),
                excluded=consent.excluded_summary(tx_all, allowed), report=report, allowed=allowed, factors=dict(store.factors),
                history_days=history_days, confidence=confidence_label(history_days))
