"""Smoke test: run app.py and every page with stand-in Streamlit/Plotly modules (checks our own logic, not the real UI)."""
from __future__ import annotations

import os
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["Overview", "Money leaks", "Behaviour and prediction", "What-if simulator", "Privacy and data"]


def _wire(m):
    """Give any stand-in object (page, sidebar or column) realistic widget return values."""
    m.number_input.side_effect = lambda *a, **k: k.get("value", 0)
    m.slider.side_effect = lambda *a, **k: a[3] if len(a) > 3 else k.get("value")
    m.selectbox.side_effect = lambda label, options, **k: list(options)[0]
    m.checkbox.side_effect = lambda *a, **k: k.get("value", False)
    m.text_input.return_value = ""
    m.button.return_value = False
    m.file_uploader.return_value = None
    return m


def _fake_streamlit(page: str, state: dict):
    st = _wire(mock.MagicMock())
    _wire(st.sidebar)
    st.session_state = state
    st.stop.side_effect = SystemExit
    st.columns.side_effect = lambda n, *a, **k: [_wire(mock.MagicMock()) for _ in range(n if isinstance(n, int) else len(n))]
    st.tabs.side_effect = lambda labels: [_wire(mock.MagicMock()) for _ in labels]
    st.sidebar.radio.side_effect = lambda label, options, **kw: "Demo data (synthetic)" if label == "Data source" else page
    return st


class TestAppSmoke(unittest.TestCase):
    def test_every_page_renders(self):
        tmp = tempfile.mkdtemp()
        state: dict = {}
        with mock.patch.dict(os.environ, {"MONEYTWIN_DATA_DIR": tmp}):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            for page in PAGES:
                fake = _fake_streamlit(page, state)
                mods = {"streamlit": fake, "plotly": mock.MagicMock(), "plotly.graph_objects": mock.MagicMock(),
                        "plotly.express": mock.MagicMock()}
                for name in [m for m in sys.modules if m.startswith("moneytwin.views")]:
                    del sys.modules[name]
                with mock.patch.dict(sys.modules, mods):
                    runpy.run_path(str(ROOT / "app.py"), run_name="__main__")
                self.assertGreater(fake.title.call_count + fake.subheader.call_count, 0, page)
        self.assertTrue((Path(tmp) / "transactions.csv").exists())  # demo data generated on first run


if __name__ == "__main__":
    unittest.main()
