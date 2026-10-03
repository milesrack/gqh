"""Frozen identity, timing, and self-financing arithmetic checks.

The small price paths below are hand-computable unit-test inputs, not research.
"""

import ast
import hashlib
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.mortimer import E6_VARIANT, Variant, control, forecast, metrics, simulate
from tools.reproduce_mortimer import sample_masks, verify_files


class MortimerTests(unittest.TestCase):
    def test_extracted_function_bodies_match_immutable_source(self):
        old = ast.parse(
            Path(
                "research/frozen-source/mortimer/selected_engine_source.py"
            ).read_text()
        )
        new = ast.parse(Path("src/mortimer.py").read_text())
        names = {
            "Variant",
            "forecast",
            "allocation",
            "control",
            "simulate",
            "metrics",
            "load_data",
        }
        old_defs = {
            n.name: ast.dump(n, include_attributes=False)
            for n in old.body
            if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in names
        }
        new_defs = {
            n.name: ast.dump(n, include_attributes=False)
            for n in new.body
            if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in names
        }
        self.assertEqual(old_defs, new_defs)
        digest = hashlib.sha256(
            Path(
                "research/frozen-source/mortimer/selected_engine_source.py"
            ).read_bytes()
        ).hexdigest()
        self.assertEqual(
            digest, "8999a1a70e4068526608a579a92ff5eb0c5edf5dbc2969b3da3e061cc8cd4ffc"
        )

    def test_registered_identity_and_evidence(self):
        self.assertEqual(E6_VARIANT.cap, 1)
        self.assertEqual(E6_VARIANT.target, 0.10)
        self.assertEqual(E6_VARIANT.covariance_days, 126)
        provenance = json.loads(Path("research/mortimer-provenance.json").read_text())
        verify_files(provenance["scientific_source_sha256"])
        verify_files(provenance["recorded_sha256"])

    def test_forecast_second_moment_and_symmetric_event(self):
        history = pd.DataFrame({"A": [0.01] * 80})
        self.assertAlmostEqual(
            forecast(history, np.array([1.0]), E6_VARIANT), 0.01 * np.sqrt(252)
        )
        self.assertEqual(control(0.74, 0.75, E6_VARIANT, 0)[0], 0.75)
        self.assertEqual(control(0.60, 0.75, E6_VARIANT, 0)[0], 0.60)

    def test_next_close_fill_and_post_fee_accounting(self):
        dates = pd.date_range("2020-01-01", periods=4)
        prices = pd.DataFrame({"A": [100.0, 100.0, 110.0, 121.0]}, index=dates)
        rf = pd.Series(0.0, index=dates)
        closes = pd.Series(pd.to_datetime(dates, utc=True), index=dates)
        variant = Variant("unit", "unit", universe=("A",))
        result = simulate(
            prices,
            rf,
            closes,
            variant,
            overlay=False,
            start_position=0,
            forecast_engine=lambda *args: 0.10,
            allocation_engine=lambda *args: np.array([1.0]),
        )
        self.assertAlmostEqual(result.net_return.iloc[0], 0)
        self.assertAlmostEqual(result.net_return.iloc[1], 1 / 1.0005 - 1)
        self.assertAlmostEqual(result.net_return.iloc[2], 0.10)
        self.assertAlmostEqual(result.net_return.iloc[3], 0.10)
        orders = result.attrs["orders"]
        self.assertTrue((orders.signal_timestamp < orders.execution_timestamp).all())
        np.testing.assert_allclose(
            result.gross_return - result.transaction_cost, result.net_return, atol=1e-14
        )
        np.testing.assert_allclose(
            result.equity, (1 + result.net_return).cumprod(), atol=1e-14
        )

    def test_metric_sample_boundaries_and_initial_drawdown(self):
        dates = pd.to_datetime(["2018-12-31", "2019-01-02", "2024-10-01", "2024-10-02"])
        masks = sample_masks(dates, "2024-10-02")
        self.assertEqual(
            {k: int(v.sum()) for k, v in masks.items()},
            {"train": 1, "validation": 2, "oos_test": 1},
        )
        frame = pd.DataFrame(
            {
                "net_return": [-0.1, 0.0],
                "turnover": [0.0, 0.0],
                "transaction_cost": [0.0, 0.0],
            },
            index=dates[:2],
        )
        self.assertAlmostEqual(
            metrics(frame, pd.Series(0.0, index=frame.index))["max_drawdown"], -0.1
        )


if __name__ == "__main__":
    unittest.main()
