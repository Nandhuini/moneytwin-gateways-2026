"""Twin Profile Store: habits, goals, personal correction factors, decisions and feedback (JSON file)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .config import twin_path

DEFAULT_FACTORS = {
    "cook_adherence": 0.7,
    "wait_cancel_rate": 0.35,
    "save_first_elasticity": 0.4,
    "leftover_saved_fraction": 0.6,
}

LEVER_FACTOR = {
    "cook": "cook_adherence",
    "wait": "wait_cancel_rate",
    "save": "save_first_elasticity",
}

_FACTOR_MIN = 0.05
_FACTOR_MAX = 0.95


def _clamp_factor(value: object, default: float) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = default

    if value != value:
        value = default

    return round(max(_FACTOR_MIN, min(value, _FACTOR_MAX)), 3)


def _fresh() -> dict:
    return {
        "profile": {},
        "factors": dict(DEFAULT_FACTORS),
        "decisions": [],
        "labels": {},
        "usage_log": [],
    }


class TwinStore:
    """Small JSON-backed store. Works in memory if the disk is read-only."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else twin_path()
        self.persist_error = ""
        self.state = self._load()

    def _load(self) -> dict:
        state = _fresh()

        try:
            if self.path.exists():
                saved = json.loads(self.path.read_text())

                if not isinstance(saved, dict):
                    return state

                profile = saved.get("profile", {})
                factors = saved.get("factors", {})
                decisions = saved.get("decisions", [])
                labels = saved.get("labels", {})
                usage_log = saved.get("usage_log", [])

                state["profile"] = (
                    dict(profile) if isinstance(profile, dict) else {}
                )

                if isinstance(factors, dict):
                    for key, default in DEFAULT_FACTORS.items():
                        state["factors"][key] = _clamp_factor(
                            factors.get(key, default),
                            default,
                        )

                state["decisions"] = (
                    list(decisions)[-200:]
                    if isinstance(decisions, list)
                    else []
                )

                state["labels"] = (
                    dict(labels) if isinstance(labels, dict) else {}
                )

                state["usage_log"] = (
                    list(usage_log)[-50:]
                    if isinstance(usage_log, list)
                    else []
                )

        except (OSError, ValueError, TypeError):
            return _fresh()

        return state

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self.state, indent=2, default=str)
            )
            self.persist_error = ""
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
        self.state["profile"] = (
            dict(profile) if isinstance(profile, dict) else {}
        )
        self.save()

    def label_merchant(self, raw_merchant: str, category: str) -> None:
        """Remember the user's category for an unknown merchant."""
        self.state["labels"][str(raw_merchant).strip().lower()] = str(category)
        self.save()

    def log_usage(self, entry: dict) -> None:
        self.state["usage_log"] = (
            self.state["usage_log"] + [entry]
        )[-50:]
        self.save()

    def record_feedback(
        self,
        scenario_name: str,
        levers: list[str],
        decision: str,
    ) -> None:
        """Accepted advice nudges matching factors up; ignored advice pulls them down."""

        if decision not in {"accept", "ignore"}:
            raise ValueError("decision must be 'accept' or 'ignore'")

        if not isinstance(levers, list):
            levers = []

        for lever in levers:
            key = LEVER_FACTOR.get(lever)
            if not key:
                continue

            current = _clamp_factor(
                self.state["factors"].get(key),
                DEFAULT_FACTORS[key],
            )

            if decision == "accept":
                updated = min(current + 0.05, _FACTOR_MAX)
            else:
                updated = max(current * 0.8, _FACTOR_MIN)

            self.state["factors"][key] = round(updated, 3)

        self.state["decisions"] = (
            self.state["decisions"]
            + [{
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "scenario": str(scenario_name),
                "levers": list(levers),
                "decision": decision,
            }]
        )[-200:]

        self.save()

    def delete_all(self) -> None:
        """Erase everything the twin has learned, including the file on disk."""
        self.state = _fresh()
        self.persist_error = ""

        try:
            self.path.unlink(missing_ok=True)
        except OSError as exc:
            self.persist_error = str(exc)