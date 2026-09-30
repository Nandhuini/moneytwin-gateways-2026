"""Core behaviour tests: run with `python -m pytest -q` or `python -m unittest discover -s tests`."""
from __future__ import annotations

import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

from moneytwin import advisor, cleaning, synthetic
from moneytwin.config import ALL_CATEGORIES
from moneytwin.prediction import predict_return
from moneytwin.simulator import Scenario, default_scenarios, parse_whatif, recommend, simulate
from tests.helpers import demo_data, fresh_store, make_twin

ROOT = Path(__file__).resolve().parent.parent


class TestDataGenerator(unittest.TestCase):
    def test_files_written(self):
        out = Path(tempfile.mkdtemp())
        synthetic.write_files(out)
        for name in ("transactions.csv", "returns.csv", "autopay.csv", "user_profile.json"):
            self.assertTrue((out / name).exists(), name)
        self.assertGreater(len(pd.read_csv(out / "transactions.csv")), 100)
        self.assertIn("monthly_savings_goal", json.loads((out / "user_profile.json").read_text()))

    def test_reproducible(self):
        a, b = synthetic.generate(), synthetic.generate()
        pd.testing.assert_frame_equal(a["transactions"], b["transactions"])


class TestCleaning(unittest.TestCase):
    def test_missing_column_message(self):
        with self.assertRaises(ValueError) as ctx:
            cleaning.clean_transactions(pd.DataFrame({"date": ["2026-01-01"], "total": [10]}))
        self.assertIn("order_id", str(ctx.exception))

    def test_duplicates_and_uncategorised(self):
        tx, rep = cleaning.clean_transactions(demo_data()["transactions"])
        self.assertEqual(rep.duplicates_removed, 1)
        self.assertEqual(rep.uncategorised, ["Local Chai Stall Kiosk 7"])
        self.assertIn("Zomato", set(tx["merchant"]))
        self.assertNotIn("ZOMATO LTD", set(tx["merchant"]))

    def test_user_label_is_remembered(self):
        store = fresh_store()
        store.label_merchant("Local Chai Stall Kiosk 7", "Other")
        tx, rep = cleaning.clean_transactions(demo_data()["transactions"], store.labels)
        self.assertEqual(rep.uncategorised, [])
        self.assertEqual(tx.loc[tx["raw_merchant"] == "Local Chai Stall Kiosk 7", "category"].iloc[0], "Other")

    def test_alternative_upload_schema(self):
        df = pd.DataFrame({"order_id": ["a", "b"], "date": ["2026-05-01", "2026-05-02"], "merchant": ["Swiggy", "Unknown Shop"],
                           "total": [300, 90], "fees": [40, 0]})
        tx, _ = cleaning.clean_transactions(df)
        self.assertEqual(list(tx["fees"]), [40.0, 0.0])
        self.assertEqual(list(tx["item_amount"]), [260.0, 90.0])
        self.assertEqual(tx["category"].tolist(), ["Food Delivery", "Uncategorised"])


class TestLeaks(unittest.TestCase):
    def setUp(self):
        self.twin, self.d, _ = make_twin()

    def test_hidden_fees_add_up(self):
        tx = self.twin.tx
        self.assertAlmostEqual(self.twin.leaks["total_fees"], float((tx["total"] - tx["item_amount"]).sum()), places=4)
        self.assertGreater(self.twin.leaks["total_fees"], 0)
        self.assertEqual(self.twin.leaks["top_fee_category"], "Food Delivery")

    def test_return_loss_and_pending(self):
        rl = self.twin.return_loss
        got = rl[rl["confirmed"]]
        self.assertTrue(((got["total"] - got["refund_amount"]).clip(lower=0) == got["loss"]).all())
        self.assertGreater(self.twin.leaks["pending_count"], 0)
        pend = rl[rl["status"] == "pending"]
        self.assertTrue((pend["loss"] == pend["fees"]).all())
        self.assertTrue((pend["pending_amount"] > 0).all())

    def test_unmatched_return_is_flagged_not_guessed(self):
        self.assertEqual(self.twin.leaks["unmatched_returns"], 1)
        self.assertNotIn("ORD-9999", set(self.twin.return_loss["order_id"]))

    def test_autopay(self):
        cal = self.twin.autopay.set_index("merchant")
        self.assertTrue({"Netflix", "Spotify", "Cult.fit", "YouTube Premium", "Coursera"} <= set(cal.index))
        self.assertEqual(cal.loc["Coursera", "source"], "declared, new (not charged yet)")
        self.assertEqual(cal.loc["YouTube Premium", "source"], "detected, not declared")
        self.assertTrue((cal["days_until"] >= 0).all())


class TestBehaviourAndPrediction(unittest.TestCase):
    def setUp(self):
        self.twin, _, _ = make_twin()

    def test_behaviour(self):
        heat = self.twin.behaviour["heatmap"]
        self.assertEqual(heat.shape, (4, 6))
        self.assertEqual(len(self.twin.behaviour["triggers"]), 3)
        self.assertGreater(self.twin.behaviour["triggers"][0]["uplift"], 1.0)
        self.assertTrue(self.twin.tx["is_sale_day"].any())

    def test_return_prediction(self):
        p = predict_return(self.twin.return_model, "Shopping", 900, 23, True, 40)
        self.assertTrue(0 <= p["low"] <= p["prob"] <= p["high"] <= 1)
        self.assertAlmostEqual(p["expected_loss"], p["prob"] * p["loss_if_returned"])
        self.assertIsNotNone(self.twin.return_model.pipe)

    def test_overspend_risk(self):
        r = self.twin.risk
        self.assertTrue(0 <= r["risk"] <= 1)
        self.assertEqual(r["budget"], 19000 - 3000)
        self.assertIn(r["level"], {"low", "medium", "high"})

    def test_cold_start_is_low_confidence(self):
        d = demo_data()
        tx = d["transactions"]
        early = tx[pd.to_datetime(tx["date"]) <= "2026-06-14"]
        twin, _, _ = make_twin(tx=early)
        self.assertEqual(twin.confidence, "low")
        p = predict_return(twin.return_model, "Shopping", 900, 23, False)
        self.assertEqual(p["confidence"], "low")
        self.assertTrue(0 <= p["low"] <= p["high"] <= 1)


class TestStoreAndSimulator(unittest.TestCase):
    def test_feedback_moves_factors(self):
        s = fresh_store()
        before = s.factors["cook_adherence"]
        s.record_feedback("Cook", ["cook"], "ignore")
        self.assertLess(s.factors["cook_adherence"], before)
        low = s.factors["cook_adherence"]
        s.record_feedback("Cook", ["cook"], "accept")
        self.assertGreater(s.factors["cook_adherence"], low)
        self.assertEqual(len(s.state["decisions"]), 2)

    def test_store_persists_and_deletes(self):
        s = fresh_store()
        s.record_feedback("Cook", ["cook"], "ignore")
        s.label_merchant("X Shop", "Other")
        again = type(s)(s.path)
        self.assertEqual(again.factors, s.factors)
        self.assertEqual(again.labels, {"x shop": "Other"})
        s.delete_all()
        self.assertFalse(s.path.exists())
        self.assertEqual(s.state["decisions"], [])

    def test_levers_change_outcomes(self):
        twin, d, store = make_twin()
        res = simulate(twin.forecast, d["profile"], twin.factors, default_scenarios()).set_index("scenario")
        base = res.loc["Keep current habits"]
        self.assertGreater(base["projected_spend"], 0)
        for name in res.index[1:]:
            self.assertLess(res.loc[name, "projected_spend"], base["projected_spend"] + 1e-6, name)
            self.assertGreaterEqual(res.loc[name, "projected_saved"], base["projected_saved"])
        self.assertGreater(res.loc["Combined plan", "projected_saved"], res.loc["Cook 3 nights a week", "projected_saved"])
        self.assertLess(res.loc["Combined plan", "goal_miss_risk"], base["goal_miss_risk"])

    def test_recommendation_and_feedback_loop(self):
        twin, d, store = make_twin()
        res = simulate(twin.forecast, d["profile"], twin.factors, default_scenarios())
        rec = recommend(res)
        self.assertGreater(rec["n_levers"], 0)
        store.record_feedback(rec["scenario"], list(rec["levers"]), "ignore")
        res2 = simulate(twin.forecast, d["profile"], store.factors, default_scenarios())
        rec2 = recommend(res2)
        self.assertLess(res2.set_index("scenario").loc[rec["scenario"], "projected_saved"],
                        res.set_index("scenario").loc[rec["scenario"], "projected_saved"])
        self.assertIsNotNone(rec2["scenario"])

    def test_goal_change_reruns_simulation(self):
        twin, d, store = make_twin()
        a = simulate(twin.forecast, d["profile"], twin.factors, default_scenarios())
        b = simulate(twin.forecast, {**d["profile"], "monthly_savings_goal": 6000}, twin.factors, default_scenarios())
        self.assertGreater(b["goal_miss_risk"].iloc[-1], a["goal_miss_risk"].iloc[-1])

    def test_parse_whatif(self):
        sc = parse_whatif("What if I cook 3 nights a week and move Rs. 1,000 to savings on day 1?")
        self.assertEqual((sc[1].cook_nights, sc[1].save_now), (3, 1000.0))
        self.assertTrue(parse_whatif("wait 48 hours")[1].wait_48h)
        self.assertIsNone(parse_whatif("hello there"))


class TestAdvisor(unittest.TestCase):
    def test_fallback_without_key(self):
        twin, d, _ = make_twin()
        res = simulate(twin.forecast, d["profile"], twin.factors, default_scenarios())
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            text, source = advisor.advise(twin, res, recommend(res))
        self.assertEqual(source, "template")
        self.assertIn("Recommendation", text)

    def test_llm_failure_falls_back(self):
        twin, d, _ = make_twin()
        res = simulate(twin.forecast, d["profile"], twin.factors, default_scenarios())
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "not-a-real-key"}), mock.patch.object(advisor, "_llm", return_value=None):
            _, source = advisor.advise(twin, res, recommend(res))
        self.assertEqual(source, "template")


class TestPrivacy(unittest.TestCase):
    def test_switched_off_category_vanishes_everywhere(self):
        allowed = [c for c in ALL_CATEGORIES if c != "Food Delivery"]
        twin, _, _ = make_twin(allowed=allowed)
        self.assertNotIn("Food Delivery", set(twin.tx["category"]))
        self.assertNotIn("Food Delivery", set(twin.fees["category"]))
        self.assertNotIn("Food Delivery", twin.forecast["remaining_by_cat"].index)
        self.assertIn("Food Delivery", twin.excluded)
        self.assertNotEqual(twin.leaks["top_fee_category"], "Food Delivery")

    def test_subscriptions_off_removes_autopay(self):
        twin, _, _ = make_twin(allowed=[c for c in ALL_CATEGORIES if c != "Subscriptions"])
        self.assertEqual(len(twin.autopay), 0)

    def test_all_off_gives_clear_error(self):
        with self.assertRaises(ValueError):
            make_twin(allowed=[])


class TestMinimalUpload(unittest.TestCase):
    def test_only_transactions_file(self):
        from moneytwin.pipeline import build_twin
        df = pd.DataFrame({"order_id": [f"o{i}" for i in range(6)],
                           "date": ["2026-05-02", "2026-05-09", "2026-05-15", "2026-05-20", "2026-05-25", "2026-05-28"],
                           "merchant": ["Swiggy", "Zomato", "Myntra", "Swiggy", "Blinkit", "Swiggy"],
                           "total": [320, 280, 1400, 350, 500, 300], "fees": [60, 50, 70, 60, 20, 55]})
        profile = {"monthly_allowance": 8000, "payday_day": 1, "monthly_savings_goal": 1000}
        twin = build_twin(df, None, None, profile, fresh_store())
        self.assertEqual(twin.confidence, "low")
        self.assertEqual(len(twin.return_loss), 0)
        self.assertEqual(len(twin.autopay), 0)
        res = simulate(twin.forecast, profile, twin.factors, default_scenarios())
        self.assertEqual(len(res), 5)


class TestRepoHygiene(unittest.TestCase):
    def test_requirements_and_secrets(self):
        reqs = (ROOT / "requirements.txt").read_text().lower()
        for pkg in ("streamlit", "pandas", "numpy", "scikit-learn", "plotly"):
            self.assertIn(pkg, reqs)
        self.assertIn(".env", (ROOT / ".gitignore").read_text())
        pattern = re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}")
        for path in ROOT.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".md", ".txt", ".toml", ".json", ".csv", ".example"} and ".git" not in path.parts:
                self.assertIsNone(pattern.search(path.read_text(errors="ignore")), str(path))

    def test_no_absolute_paths(self):
        for path in (ROOT / "moneytwin").rglob("*.py"):
            self.assertNotIn("/home/", path.read_text(), str(path))


if __name__ == "__main__":
    unittest.main()
