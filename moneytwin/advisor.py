"""Advisor Agent: explains results in plain language. Uses an LLM if a key is set, else a built-in template."""
from __future__ import annotations

import json
import os

import pandas as pd

from .config import LLM_MODEL
from .formatting import money, pct

SYSTEM_PROMPT = ("You are MoneyTwin's advisor for a student. Using ONLY the JSON facts given, write a short, plain-language "
                 "recommendation (under 140 words): state the recommended option, why, what it changes, one risky moment "
                 "to watch, and any assumption or missing data. Do not invent numbers.")


def build_summary(twin, results: pd.DataFrame, rec: pd.Series) -> dict:
    """Aggregate facts only. Raw transactions are never sent to the LLM."""
    base = results[results["n_levers"] == 0].iloc[0]
    upcoming = twin.autopay[twin.autopay["days_until"] <= (twin.risk_days_left)] if len(twin.autopay) else twin.autopay
    return {
        "recommended": rec["scenario"], "levers": list(rec["levers"]), "saved_if_followed": round(float(rec["projected_saved"])),
        "saved_if_unchanged": round(float(base["projected_saved"])), "goal_gap_if_followed": round(float(rec["goal_gap"])), "goal": round(float(rec["goal"])),
        "miss_risk_if_followed": round(float(rec["goal_miss_risk"]), 2), "miss_risk_if_unchanged": round(float(base["goal_miss_risk"]), 2),
        "top_fee_category": twin.leaks["top_fee_category"], "total_hidden_fees": round(twin.leaks["total_fees"]),
        "return_loss": round(twin.leaks["return_loss_confirmed"]),
        "autopay_due_this_month": [{"merchant": r.merchant, "amount": r.amount, "in_days": int(r.days_until)} for r in upcoming.itertuples()],
        "risky_days": [{"date": str(r["date"].date()), "reason": r["reason"]} for r in twin.risk["risky_days"][:3]],
        "confidence": twin.confidence, "not_considered": list(twin.excluded.keys()),
    }


def _template(s: dict) -> str:
    lines = [f"**Recommendation: {s['recommended']}.**" if s["levers"] else "**Your current habits already fit your plan.**"]
    if s["levers"]:
        lines.append(f"If you follow it, you finish the month with about {money(s['saved_if_followed'])} saved instead of "
                     f"{money(s['saved_if_unchanged'])}, against your goal of {money(s['goal'])}. The chance of missing the goal "
                     f"drops from {pct(s['miss_risk_if_unchanged'])} to {pct(s['miss_risk_if_followed'])}.")
    if s["levers"] and s["goal_gap_if_followed"] > 0:
        lines.append(f"Even then you would fall {money(s['goal_gap_if_followed'])} short this month, so consider a smaller goal or a bigger change.")
    if s["top_fee_category"]:
        lines.append(f"Your biggest hidden cost is fees on {s['top_fee_category']} ({money(s['total_hidden_fees'])} in fees overall), "
                     f"and returns have cost you {money(s['return_loss'])} in money that never came back.")
    if s["autopay_due_this_month"]:
        due = ", ".join(f"{a['merchant']} {money(a['amount'])} in {a['in_days']}d" for a in s["autopay_due_this_month"])
        lines.append(f"Autopay still due this month: {due}.")
    if s["risky_days"]:
        lines.append("Risky moments to watch: " + ", ".join(f"{d['date']} ({d['reason']})" for d in s["risky_days"]) + ".")
    lines.append(f"Confidence: {s['confidence']}." + (f" Not considered (switched off): {', '.join(s['not_considered'])}." if s["not_considered"] else ""))
    return "\n\n".join(lines)


def _llm(summary: dict) -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(model=LLM_MODEL, max_tokens=500, system=SYSTEM_PROMPT,
                                     messages=[{"role": "user", "content": json.dumps(summary, default=str)}])
        return msg.content[0].text
    except Exception:  # any LLM problem falls back to the template
        return None


def advise(twin, results: pd.DataFrame, rec: pd.Series, use_llm: bool = True) -> tuple[str, str]:
    """Return (advice text, source) where source is 'llm' or 'template'."""
    summary = build_summary(twin, results, rec)
    text = _llm(summary) if use_llm else None
    return (text, "llm") if text else (_template(summary), "template")
