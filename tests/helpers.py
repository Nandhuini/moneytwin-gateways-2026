"""Shared test fixtures (plain functions so tests run with unittest or pytest)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd

from moneytwin import synthetic
from moneytwin.pipeline import build_twin
from moneytwin.twin_store import TwinStore

_CACHE: dict = {}


def demo_data() -> dict:
    if "d" not in _CACHE:
        _CACHE["d"] = synthetic.generate()
    return {k: (v.copy() if hasattr(v, "copy") else dict(v)) for k, v in _CACHE["d"].items()}


def fresh_store() -> TwinStore:
    return TwinStore(Path(tempfile.mkdtemp()) / "twin.json")


def make_twin(allowed=None, tx=None, store=None):
    d = demo_data()
    store = store or fresh_store()
    return build_twin(d["transactions"] if tx is None else tx, d["returns"], d["autopay"], d["profile"], store, allowed), d, store
