"""Shared view helpers: colours, banners and small utilities."""
from __future__ import annotations

import streamlit as st

from ..consent import describe_exclusions

PRIMARY, ACCENT, NEUTRAL = "#1f6f8b", "#d1495b", "#9aa5b1"


def banners(twin) -> None:
    """Notices that apply to every page: cold start and switched-off data."""
    if twin.confidence == "low":
        st.warning(f"Low confidence: only {twin.history_days} days of history, so predictions are shown as wide ranges "
                   "and will improve as more data arrives.")
    note = describe_exclusions(twin.excluded)
    if note:
        st.info(note)
    flash = st.session_state.pop("flash", None)
    if flash:
        st.success(flash)
