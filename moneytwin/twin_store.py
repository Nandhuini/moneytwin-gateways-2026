"""Twin Profile Store: habits, goals, personal correction factors, decisions and feedback (JSON file)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .config import twin_path

DEFAULT_FACTORS = {
    "cook_adherence": 0.7,          # share of planned cooked nights the user actually keeps
    "wait_cancel_rate": 0.35,       # share of impulse purchases dropped after a 48h wait
    "save_first_elasticity": 0.4,   # share of an upfront saving that shows up as lower spending
    "leftover_saved_fraction": 0.6,  # share of "what is left" that really gets saved
}
LEVER_FACTOR = {"cook": "cook_adherence", "wait": "wait_cancel_rate", "save": "save_first_elasticity"}


def _fresh() -> dict:
    return {"profile": {}, "factors": dict(DEFAULT_FACTORS), "decisions": [], "labels": {}, "usage_log": []}


class TwinStore:
    """Small JSON-backed store. Works in memory if the disk is read-only."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else twin_path()
        self.state = self._load()
        self.persist_error = ""

    def _load(self) -> dict:
        state = _fresh()
        try:
            if self.path.exists():
                saved = json.loads(self.path.read_text())
                state.update({k: v for k, v in saved.items() if k in state})
                state["factors"] = {**DEFAULT_FACTORS, **state["factors"]}
        except (OSError, ValueError):
            pass
        return state

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.state, indent=2, default=str))
        except OSError as exc:
            self.persist_error = str(exc)

    @property
    def profile(self) -> dict:
        return self.state["profile"]

    @property
    def factors(self) -> dict:
        return self.state["factors"]

    @property
    def labels(self) -> dict:
        return self.state["labels"]

    def set_profile(self, profile: dict) -> None:
        self.state["profile"] = dict(profile)
        self.save()

    def label_merchant(self, raw_merchant: str, category: str) -> None:
        """Remember the user's category for an unknown merchant."""
        self.state["labels"][str(raw_merchant).strip().lower()] = category
        self.save()

    def log_usage(self, entry: dict) -> None:
        self.state["usage_log"] = (self.state["usage_log"] + [entry])[-50:]
        self.save()

    def record_feedback(self, scenario_name: str, levers: list[str], decision: str) -> None:
        """Accepted advice nudges the matching factors up; ignored advice pulls them down."""
        for lever in levers:
            key = LEVER_FACTOR.get(lever)
            if not key:
                continue
            f = self.state["factors"][key]
            self.state["factors"][key] = round(min(f + 0.05, 0.95) if decision == "accept" else max(f * 0.8, 0.05), 3)
        self.state["decisions"] = (self.state["decisions"] + [{
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"), "scenario": scenario_name,
            "levers": levers, "decision": decision}])[-200:]
        self.save()

    def delete_all(self) -> None:
        """Erase everything the twin has learned, including the file on disk."""
        self.state = _fresh()
        try:
            self.path.unlink(missing_ok=True)
        except OSError as exc:
            self.persist_error = str(exc)
