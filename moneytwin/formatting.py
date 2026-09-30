"""Small display helpers shared by the views and the advisor."""
from __future__ import annotations


def money(x: float) -> str:
    """Format a number as Indian rupees, e.g. Rs. 1,250."""
    return f"Rs. {float(x):,.0f}"


def pct(x: float) -> str:
    """Format a 0-1 fraction as a percentage."""
    return f"{float(x) * 100:.0f}%"
