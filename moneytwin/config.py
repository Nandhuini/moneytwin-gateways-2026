"""Central settings. No secrets live here; the optional LLM key is read from the environment."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    """Folder for demo data and the saved twin. Override with MONEYTWIN_DATA_DIR."""
    return Path(os.environ.get("MONEYTWIN_DATA_DIR", ROOT / "data"))


def twin_path() -> Path:
    return data_dir() / "twin_profile.json"


CATEGORIES = ["Food Delivery", "Shopping", "Trends", "Groceries", "Subscriptions", "Other"]
UNCATEGORISED = "Uncategorised"
ALL_CATEGORIES = CATEGORIES + [UNCATEGORISED]
RETURN_CATEGORIES = ["Shopping", "Trends"]
FEE_COLUMNS = ["delivery_fee", "platform_fee", "handling_fee", "surge_fee"]

LATE_NIGHT_START = 22  # 22:00 onwards
LATE_NIGHT_END = 5     # until 04:59
COOK_COST_PER_MEAL = 90.0
RETURN_WINDOW_DAYS = 10
LOW_CONFIDENCE_DAYS = 30
LLM_MODEL = os.environ.get("MONEYTWIN_LLM_MODEL", "claude-sonnet-5-5")
