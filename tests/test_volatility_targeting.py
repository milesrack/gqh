"""Isolated arithmetic and guard tests for the self-contained notebook cells."""

import ast
import hashlib
import itertools
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import nbformat
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def notebook_definitions():
    """Load definitions, imports and literal constants without running research."""
    nb = nbformat.read(
        ROOT / "notebooks/volatility_targeting_2_research.ipynb", as_version=4
    )
    module = types.ModuleType("volatility_notebook_test")
    sys.modules[module.__name__] = module
    nodes = []
    for cell in nb.cells:
        if cell.cell_type != "code":
            continue
        for node in ast.parse(cell.source).body:
            if isinstance(
                node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef)
            ):
                nodes.append(node)
            elif isinstance(node, ast.Assign):
                try:
                    ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    continue
                nodes.append(node)
    exec(  # noqa: S102 - execute parsed definitions from the trusted notebook
        compile(
            ast.Module(body=nodes, type_ignores=[]), "notebook definitions", "exec"
        ),
        module.__dict__,
    )
    return module.__dict__


NOTEBOOK = notebook_definitions()
Variant = NOTEBOOK["Variant"]
simulate = NOTEBOOK["simulate"]
metrics = NOTEBOOK["metrics"]
control = NOTEBOOK["control"]
allocation = NOTEBOOK["allocation"]
har_prediction = NOTEBOOK["har_prediction"]
variants = NOTEBOOK["variants"]


class AccountingTests(unittest.TestCase):
    def simulate(self, *args, **kwargs):
        # Fix the forecast to isolate execution/accounting from estimator warm-up.
        with patch.dict(NOTEBOOK, {"forecast": lambda *args, **kwargs: 0.1}):
            return simulate(*args, **kwargs)

    def fixture(self):
        dates = pd.date_range("2020-01-01", periods=7, freq="B")
        # Hand-computable toy inputs ONLY for isolated accounting tests.
        prices = pd.DataFrame(
            {
                "A": [100, 110, 99, 108.9, 108.9, 98.01, 107.811],
                "B": [100, 100, 100, 100, 100, 100, 100],
                "C": [100, 100, 100, 100, 100, 100, 100],
            },
            index=dates,
        )
        closes = pd.Series(
            dates.tz_localize("UTC") + pd.Timedelta(hours=21), index=dates
        )
        rf = pd.Series(0.0, index=dates)
        return prices, rf, closes

    def test_old_exposure_earns_execution_day_return(self):
        p, rf, c = self.fixture()
        v = Variant(
            "unit",
            "trailing",
            target=1.0,
            universe=("A", "B", "C"),
            lookback=2,
            control="monthly",
        )
        r = self.simulate(p, rf, c, v, cost_bps=0.0, overlay=False, start_position=1)
        self.assertEqual(r.net_return.iloc[2], 0.0)
        self.assertAlmostEqual(r.net_return.iloc[3], 0.1 / 3)
        self.assertEqual(r.attrs["orders"].iloc[0].signal_timestamp, c.iloc[1])
        self.assertEqual(r.attrs["orders"].iloc[0].execution_timestamp, c.iloc[2])
        self.assertEqual(
            r.attrs["orders"].iloc[0].first_return_end_timestamp, c.iloc[3]
        )

    def test_deployment_cost_self_finances(self):
        p, rf, c = self.fixture()
        v = Variant(
            "unit",
            "trailing",
            target=1.0,
            universe=("A", "B", "C"),
            lookback=2,
            control="monthly",
        )
        r = self.simulate(p, rf, c, v, cost_bps=5.0, overlay=False, start_position=1)
        expected_nav = 1 / 1.0005
        self.assertAlmostEqual(r.equity.iloc[2], expected_nav)
        self.assertAlmostEqual(r.transaction_cost.iloc[2], 1 - expected_nav)
        self.assertAlmostEqual(r.traded_notional.iloc[2], expected_nav)
        self.assertAlmostEqual(r.turnover.iloc[2], 1.0)
        np.testing.assert_allclose(
            r.net_return,
            r.risky_contribution
            + r.cash_contribution
            - r.financing_cost
            - r.transaction_cost,
            atol=1e-12,
        )

    def test_weights_drift_without_free_rebalancing(self):
        p, rf, c = self.fixture()
        v = Variant(
            "unit",
            "trailing",
            target=1.0,
            universe=("A", "B", "C"),
            lookback=2,
            control="monthly",
        )
        r = self.simulate(p, rf, c, v, cost_bps=0.0, overlay=False, start_position=1)
        self.assertAlmostEqual(r.attrs["weights"].iloc[3, 0], 1.1 / 3.1)
        self.assertEqual(r.traded_notional.iloc[3], 0.0)

    def test_leverage_pays_financing(self):
        p, rf, c = self.fixture()
        rf[:] = 0.0001
        v = Variant(
            "unit",
            "trailing",
            target=1.0,
            universe=("A", "B", "C"),
            lookback=2,
            control="monthly",
            cap=1.25,
        )
        r = self.simulate(
            p, rf, c, v, cost_bps=0.0, static_exposure=1.25, start_position=1
        )
        self.assertGreater(r.financing_cost.iloc[3], 0)
        self.assertEqual(r.cash_contribution.iloc[3], 0)
        self.assertAlmostEqual(
            r.financing_cost.iloc[3],
            0.25 * (0.0001 + 0.005 / 365 * (p.index[3] - p.index[2]).days),
        )

    def test_metrics_include_initial_loss_and_undefined_ratios(self):
        ix = pd.date_range("2020-01-01", periods=3)
        r = pd.DataFrame(
            {
                "net_return": [-0.1, 0.0, 0.0],
                "turnover": [0.0, 0.0, 0.0],
                "transaction_cost": [0.0, 0.0, 0.0],
            },
            index=ix,
        )
        m = metrics(r, pd.Series(0.0, index=ix))
        self.assertAlmostEqual(m["max_drawdown"], -0.1)
        self.assertTrue(m["unrecovered_at_end"])
        r.net_return = 0.0
        m = metrics(r, pd.Series(0.0, index=ix))
        self.assertTrue(np.isnan(m["sharpe"]))
        self.assertTrue(np.isnan(m["sortino"]))

    def test_asymmetric_five_session_restore_and_fast_cut(self):
        v = Variant("unit", "ensemble", control="asymmetric")
        current, streak = 0.5, 0
        for _ in range(4):
            current, streak = control(0.9, current, v, streak)
            self.assertEqual(current, 0.5)
        current, streak = control(0.9, current, v, streak)
        self.assertAlmostEqual(current, 0.6)
        current, streak = control(0.3, current, v, streak)
        self.assertEqual(current, 0.3)
        self.assertEqual(streak, 0)

    def test_prefix_invariance(self):
        p, rf, c = self.fixture()
        v = Variant(
            "unit",
            "trailing",
            target=0.08,
            universe=("A", "B", "C"),
            lookback=2,
            control="event",
        )
        a = self.simulate(p, rf, c, v, start_position=1)
        changed = p.copy()
        changed.iloc[-1] *= 2
        b = self.simulate(changed, rf, c, v, start_position=1)
        np.testing.assert_allclose(a.net_return.iloc[:-1], b.net_return.iloc[:-1])
        pd.testing.assert_frame_equal(
            a.attrs["weights"].iloc[:-1], b.attrs["weights"].iloc[:-1]
        )


class NotebookControls(unittest.TestCase):
    def test_no_project_imports_or_study_wrapper(self):
        nb = nbformat.read(
            ROOT / "notebooks/volatility_targeting_2_research.ipynb", as_version=4
        )
        for cell in nb.cells:
            if cell.cell_type != "code":
                continue
            for node in ast.walk(ast.parse(cell.source)):
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse(
                        (node.module or "").startswith("volatility_targeting")
                    )
                if isinstance(node, ast.Name):
                    self.assertNotEqual(node.id, "study")
                if isinstance(node, ast.ClassDef):
                    self.assertNotEqual(node.name, "Study")

    def test_registration_survives_appended_trial_records(self):
        # CSV records must compare by content, not pandas dtypes changed by log rows.
        NOTEBOOK["assert_registration"](ROOT)

    def test_calendar_boundary(self):
        b = NOTEBOOK["split"]()
        self.assertEqual(b["oos_start"], pd.Timestamp("2024-10-02"))
        self.assertEqual(
            b["oos_start"], max(b["twenty_percent_start"], b["two_year_start"])
        )
        with self.assertRaises(ValueError):
            NOTEBOOK["guard_dates"](pd.DatetimeIndex(["2024-10-02"]), b["oos_start"])

    def test_har_future_labels_are_not_fitted(self):
        ix = pd.date_range("2000-01-01", periods=650)
        r = pd.Series(np.tile([0.01, -0.02, 0.03, -0.01, 0.005], 130), index=ix)
        a = har_prediction(r, 600, {})
        r.iloc[601:] = 0.9
        self.assertAlmostEqual(a, har_prediction(r, 600, {}))
        self.assertTrue(np.isnan(har_prediction(r, 200, {})))

    def test_twelve_registered_candidates(self):
        self.assertEqual(len(variants()), 12)
        self.assertEqual(len({v.trial_id for v in variants()}), 12)

    def test_yahoo_hidden_timezone_request_is_bounded(self):
        session = NOTEBOOK["BoundedYahooSession"]("2008-01-02", "2008-01-10")
        url = "https://query2.finance.yahoo.com/v8/finance/chart/SPY"
        params = session.bounded_parameters(url, {"range": "1d", "interval": "1d"})
        self.assertNotIn("range", params)
        self.assertEqual(params["period2"], session.end_epoch)
        with self.assertRaises(ValueError):
            session.bounded_parameters(
                url, {"period1": session.start_epoch, "period2": session.end_epoch + 1}
            )
        with self.assertRaises(ValueError):
            session.bounded_parameters(
                "https://query2.finance.yahoo.com/v7/finance/quote", {}
            )
        session.close()

    def test_alfred_requests_partition_vintage_dates(self):
        # Empty mocked releases stop before Yahoo acquisition. No fabricated market data.
        with (
            tempfile.TemporaryDirectory() as d,
            patch.dict(
                NOTEBOOK,
                {
                    "get_json": lambda p: (
                        requests.append(p) or {"count": 0, "observations": []}
                    )
                },
            ),
        ):
            requests = []
            with (
                patch.dict("os.environ", {"FRED_API_KEY": "test-only-placeholder"}),
                self.assertRaisesRegex(RuntimeError, "No ALFRED"),
            ):
                NOTEBOOK["acquire"]("2024-10-02", d)
        self.assertEqual(len(requests), 18)
        for request in requests:
            self.assertEqual(request["output_type"], 4)
            span = pd.Timestamp(request["realtime_end"]) - pd.Timestamp(
                request["realtime_start"]
            )
            self.assertLessEqual(span.days, 398)
            self.assertLess(
                pd.Timestamp(request["realtime_end"]), pd.Timestamp("2024-10-02")
            )
        intervals = [
            (pd.Timestamp(p["observation_start"]), pd.Timestamp(p["observation_end"]))
            for p in requests
        ]
        for previous, current in itertools.pairwise(intervals):
            self.assertEqual(previous[1] + pd.Timedelta(days=1), current[0])

    def test_exclusive_final_gate_and_modified_source(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "research").mkdir()
            (root / "notebooks").mkdir()
            for name in ("pyproject.toml", "uv.lock"):
                (root / name).write_text("test")
            (root / "notebooks/volatility_targeting_2_research.ipynb").write_text(
                json.dumps({"cells": []})
            )
            (root / "research/experiment_registry.csv").write_text("test")
            for name in ("is-market", "is-rates"):
                (root / name).write_text("test")
            digest_file = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
            frozen = {
                "code_hash": NOTEBOOK["code_hash"](root),
                "hypothesis_hash": "test",
                "registry_hash": digest_file(root / "research/experiment_registry.csv"),
                "oos_start": "2024-10-02",
                "research_data": {
                    "paths": ["is-market", "is-rates"],
                    "market_sha256": digest_file(root / "is-market"),
                    "rates_sha256": digest_file(root / "is-rates"),
                },
            }
            path = root / "research/frozen_strategy.json"
            path.write_text(json.dumps(frozen))
            digest = digest_file(path)
            (root / "research/frozen_strategy.sha256").write_text(digest)
            flag = root / "research/oos_accessed.flag"
            with patch.dict(
                NOTEBOOK,
                {
                    "ROOT": root,
                    "MODE": "final",
                    "HYPOTHESIS_HASH": "test",
                    "OOS_FLAG": flag,
                    "RUN_ID": "unit-test",
                    "boundary": {"oos_start": pd.Timestamp("2024-10-02")},
                },
            ):
                with self.assertRaises(ValueError):
                    NOTEBOOK["unlock_final"]("wrong")
                self.assertFalse(flag.exists())
                NOTEBOOK["unlock_final"](digest)
                self.assertTrue(flag.exists())
                with self.assertRaises(RuntimeError):
                    NOTEBOOK["unlock_final"](digest)

    def test_paired_bootstrap(self):
        ix = pd.date_range("2000-01-01", periods=30)
        r = pd.DataFrame({"net_return": np.tile([0.01, -0.01, 0.02], 10)}, index=ix)
        intervals = NOTEBOOK["bootstrap"](
            r, r, pd.Series(0.0, index=ix), repetitions=10
        )
        np.testing.assert_allclose(intervals[["lower_95", "upper_95"]], 0.0)


if __name__ == "__main__":
    unittest.main()
