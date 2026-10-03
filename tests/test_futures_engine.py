"""Independent dated-contract, availability and cash-accounting regressions."""

import json

import numpy as np
import pandas as pd
import pytest

from src import futures_data
from src.futures_data import FuturesInputs, native_tick, select_liquid_contract


def candidate(symbol, expiry, adv=100, observed_bars=20):
    return {
        "symbol": symbol,
        "expiry": pd.Timestamp(expiry, tz="UTC"),
        "adv": adv,
        "observed_bars": observed_bars,
    }


def test_selection_requires_complete_liquid_history_and_40_days():
    day = pd.Timestamp("2015-01-01", tz="UTC")
    rows = [
        candidate("short", "2015-02-09", 1000),
        candidate("partial", "2015-03-01", 1000, 19),
        candidate("thin", "2015-04-01", 99.99),
        candidate("eligible", "2015-02-10"),
    ]
    assert select_liquid_contract(rows, day)["symbol"] == "eligible"
    with pytest.raises(ValueError, match="No forward"):
        select_liquid_contract(rows[:3], day)


def test_nearest_two_precedes_forward_filter_and_ties_retain_incumbent():
    day = pd.Timestamp("2015-01-01", tz="UTC")
    rows = [
        candidate("near", "2015-03-01", 200),
        candidate("second", "2015-06-01", 200),
        candidate("distant", "2015-09-01", 10000),
        candidate("later", "2015-12-01", 20000),
    ]
    assert select_liquid_contract(rows, day, "near")["symbol"] == "near"
    assert select_liquid_contract(rows, day)["symbol"] == "second"
    with pytest.raises(ValueError, match="No forward"):
        select_liquid_contract(rows, day, "distant")
    with pytest.raises(ValueError, match="metadata disappeared"):
        select_liquid_contract(rows, day, "missing")


@pytest.mark.parametrize(
    "root,tick,multiplier",
    [
        ("ES", 0.25, 50),
        ("NQ", 0.25, 20),
        ("ZN", 1 / 64, 1000),
        ("CL", 0.01, 1000),
        ("GC", 0.1, 100),
        ("6E", 0.00005, 125000),
    ],
)
def test_native_units(root, tick, multiplier):
    assert native_tick(root, "2016-01-11") == tick
    assert futures_data.SPECS[root].multiplier == multiplier


def test_euro_tick_changes_on_announced_execution_date():
    assert native_tick("6E", "2016-01-08") * 125000 == 12.5
    assert native_tick("6E", "2016-01-11") * 125000 == 6.25


def manifest(tmp_path, **overrides):
    value = {
        "period": {"end_exclusive": "2024-05-27"},
        "fixed_holdout_start": "2024-05-27",
        "files": {
            "bars": {"path": "bars.parquet", "sha256": "unused"},
            "definitions": {"path": "definitions.parquet", "sha256": "unused"},
        },
    }
    value.update(overrides)
    (tmp_path / "prepared-manifest.json").write_text(json.dumps(value))


@pytest.mark.parametrize(
    "overrides,kwargs,match",
    [
        ({"period": {"end_exclusive": "2024-05-28"}}, {}, "crosses locked"),
        ({"fixed_holdout_start": "2025-01-01"}, {}, "different locked"),
        ({}, {"holdout_start": "2025-01-01"}, "cannot be overridden"),
    ],
)
def test_locked_boundary_refused_before_any_price_file_access(
    tmp_path, monkeypatch, overrides, kwargs, match
):
    manifest(tmp_path, **overrides)
    monkeypatch.setattr(
        futures_data, "file_hash", lambda p: pytest.fail("price opened")
    )
    monkeypatch.setattr(pd, "read_parquet", lambda *a, **k: pytest.fail("price parsed"))
    with pytest.raises(ValueError, match=match):
        FuturesInputs.from_directory(tmp_path, **kwargs)


def test_escaped_manifest_path_refused_before_open(tmp_path, monkeypatch):
    manifest(
        tmp_path,
        files={
            "bars": {"path": "../outside.parquet", "sha256": "unused"},
            "definitions": {"path": "definitions.parquet", "sha256": "unused"},
        },
    )
    monkeypatch.setattr(
        futures_data, "file_hash", lambda p: pytest.fail("escaped file opened")
    )
    with pytest.raises(ValueError, match="escaped"):
        FuturesInputs.from_directory(tmp_path)


def synthetic_frames():
    days = pd.bdate_range("2015-01-01", periods=300, tz="UTC")
    bars = pd.DataFrame(
        {
            "date": days,
            "root": "ES",
            "symbol": "ESH7",
            "instrument_id": 1,
            "open": 2000 + np.arange(len(days)),
            "close": 2000.5 + np.arange(len(days)),
            "volume": 1000,
        }
    )
    definitions = pd.DataFrame(
        {
            "ts_recv": [pd.Timestamp("2014-12-31", tz="UTC")],
            "ts_event": [pd.Timestamp("2014-12-31", tz="UTC")],
            "raw_symbol": ["ESH7"],
            "instrument_id": [1],
            "instrument_class": ["F"],
            "min_price_increment": [0.25],
            "expiration": ["2017-03-17"],
            "maturity_year": [2017],
            "maturity_month": [3],
            "unit_of_measure_qty": [50],
        }
    )
    return bars, definitions


def test_received_identity_not_event_time_governs_volume_coverage():
    bars, definitions = synthetic_frames()
    definitions["ts_recv"] = pd.Timestamp("2015-01-02", tz="UTC")
    with pytest.raises(ValueError, match="causally received identity"):
        FuturesInputs(bars, definitions, roots=("ES",))


def test_reused_symbol_cannot_borrow_another_instrument_definition():
    bars, definitions = synthetic_frames()
    bars.loc[0, "instrument_id"] = 2
    with pytest.raises(ValueError, match="causally received identity"):
        FuturesInputs(bars, definitions, roots=("ES",))


def test_information_clock_has_full_calendar_day_and_optional_bar_delay():
    bars, definitions = synthetic_frames()
    normal = FuturesInputs(bars, definitions, roots=("ES",))
    delayed = FuturesInputs(bars, definitions, roots=("ES",), extra_information_bars=1)
    monday = pd.Timestamp("2015-02-09", tz="UTC")
    assert normal.information_day(monday) == pd.Timestamp("2015-02-06", tz="UTC")
    assert delayed.information_day(monday) == pd.Timestamp("2015-02-05", tz="UTC")
    # Frozen Good Friday closure retains both actual weekday price increments.
    gap = pd.Timestamp("2015-04-06", tz="UTC")
    assert normal.point_changes.loc[gap, "ES"] == 2
    assert (normal.point_changes.drop(index=gap).ES == 1).all()
    assert normal.common_start > normal.point_changes.index[239]


def test_missing_required_selected_bar_fails_instead_of_dropping_date():
    bars, definitions = synthetic_frames()
    second = bars.copy().assign(symbol="ESM7", instrument_id=2, volume=100)
    definitions = pd.concat(
        [
            definitions,
            definitions.assign(
                raw_symbol="ESM7",
                instrument_id=2,
                expiration="2017-06-16",
                maturity_month=6,
            ),
        ],
        ignore_index=True,
    )
    # Whole-root presence remains: only the actual selected contract vanishes.
    bars = pd.concat([bars.drop(index=100), second], ignore_index=True)
    with pytest.raises(ValueError, match="Missing required actual-contract bar"):
        FuturesInputs(bars, definitions, roots=("ES",))


def test_future_price_changes_do_not_change_prior_features_or_selection():
    bars, definitions = synthetic_frames()
    baseline = FuturesInputs(bars, definitions, roots=("ES",))
    cutoff = bars.date.iloc[280]
    altered = bars.copy()
    altered.loc[altered.date > cutoff, ["open", "close"]] *= 10
    perturbed = FuturesInputs(altered, definitions, roots=("ES",))
    pd.testing.assert_frame_equal(
        baseline.point_changes.loc[:cutoff], perturbed.point_changes.loc[:cutoff]
    )
    assert {d: v for d, v in baseline.selections.items() if d <= cutoff} == {
        d: v for d, v in perturbed.selections.items() if d <= cutoff
    }


def test_checksum_failure_precedes_parquet_parsing(tmp_path, monkeypatch):
    manifest(tmp_path)
    (tmp_path / "bars.parquet").write_bytes(b"tampered source")
    monkeypatch.setattr(
        pd, "read_parquet", lambda *a, **k: pytest.fail("parsed before hash")
    )
    with pytest.raises(ValueError, match="bars checksum mismatch"):
        FuturesInputs.from_directory(tmp_path)


def test_valid_local_loader_needs_no_network(tmp_path, monkeypatch):
    import socket

    bars, definitions = synthetic_frames()
    files = {}
    for role, frame in (("bars", bars), ("definitions", definitions)):
        path = tmp_path / f"{role}.parquet"
        frame.to_parquet(path, index=False)
        files[role] = {"path": path.name, "sha256": futures_data.file_hash(path)}
    manifest(tmp_path, files=files)
    monkeypatch.setattr(
        socket.socket, "connect", lambda *a, **k: pytest.fail("network access")
    )
    inputs = FuturesInputs.from_directory(tmp_path, roots=("ES",))
    assert len(inputs.point_changes) >= 240
    assert inputs.source_manifest["files"] == files


def rolled_inputs():
    """Observed old/new contracts with a deliberately large roll price gap."""
    bars, definitions = synthetic_frames()
    second = bars.assign(
        symbol="ESM7",
        instrument_id=2,
        volume=100,
        open=bars.open + 200,
        close=bars.close + 200,
    )
    definitions = pd.concat(
        [
            definitions,
            definitions.assign(
                raw_symbol="ESM7",
                instrument_id=2,
                expiration="2017-06-16",
                maturity_month=6,
            ),
        ],
        ignore_index=True,
    )
    bars = pd.concat([bars, second], ignore_index=True)
    fill_days = pd.to_datetime(["2016-02-19", "2016-02-22", "2016-02-23"], utc=True)
    for symbol, prices in (("ESH7", [4000, 4010, 4020]), ("ESM7", [4190, 4200, 4195])):
        for day, price in zip(fill_days, prices, strict=True):
            bars.loc[(bars.date == day) & (bars.symbol == symbol), "open"] = price
    inputs = FuturesInputs(bars, definitions, roots=("ES",))
    for day in fill_days[1:]:
        inputs.selections[day]["ES"] = inputs.curves[day]["ES"][1]
    return inputs


@pytest.mark.parametrize("multiple,expected_net", [(1, 190), (2, 130)])
def test_evaluate_replays_actual_cash_positions_roll_legs_and_costs(
    monkeypatch, multiple, expected_net
):
    from src import futures_engine as engine

    inputs = rolled_inputs()
    monkeypatch.setattr(engine, "covariance_targets", lambda *a, **k: np.array([1.0]))
    clocks = []

    def signal(view, params):
        clocks.append((view.decision_at, view.information_asof))
        assert view.point_changes.index.max() <= view.information_asof
        assert view.bars("ES").index.max() <= view.information_asof
        return pd.Series({"ES": 1.0})

    result = engine.evaluate(
        inputs,
        signal,
        {},
        ("2016-02-19", "2016-02-24"),
        frequency="daily",
        costs={"multiple": multiple},
    )
    assert len(result.returns) == 3
    assert result.metrics["net_pnl"] == expected_net
    assert result.metrics["rolls"] == 1
    assert result.metrics["contracts_traded"] == 4
    assert result.returns.gross_pnl.tolist() == [0, 500, -250]
    assert result.returns.cost.tolist() == [15 * multiple, 30 * multiple, 15 * multiple]
    assert all(d - a >= pd.Timedelta(days=2) for d, a in clocks)
    positions = result.positions
    independent_gross = (
        positions.prior_quantity
        * 50
        * (positions.incumbent_open - positions.prior_mark)
    )
    np.testing.assert_array_equal(independent_gross, positions.gross_pnl)
    np.testing.assert_allclose(positions.gross_pnl - positions.cost, positions.net_pnl)
    np.testing.assert_allclose(result.returns.pnl_ES, positions.net_pnl)
    independent_fees = result.trades.commission + result.trades.slippage
    assert independent_fees.sum() == result.returns.cost.sum()
    assert result.trades.quantity.tolist() == [1, -1, 1, -1]
    assert positions.iloc[-1].quantity == 0
    np.testing.assert_allclose(
        (1 + result.returns["return"]).cumprod() * 1_000_000, result.returns.equity
    )


def test_evaluation_holdout_guard_precedes_plugin_and_price_access():
    from src.futures_engine import evaluate

    def forbidden(*args):
        pytest.fail("plugin or price access before locked-window guard")

    inputs = type("NoPrices", (), {"row": forbidden})()
    with pytest.raises(ValueError, match="locked boundary"):
        evaluate(inputs, forbidden, {}, ("2024-05-01", "2024-05-28"))


def test_base_and_clock_stress_use_identical_effective_observations(monkeypatch):
    from src import futures_engine as engine

    bars, definitions = synthetic_frames()
    base = FuturesInputs(bars, definitions, roots=("ES",))
    delayed = FuturesInputs(bars, definitions, roots=("ES",), extra_information_bars=1)
    monkeypatch.setattr(engine, "covariance_targets", lambda *a, **k: np.array([1.0]))

    def signal(view, params):
        return pd.Series({"ES": 1.0})

    results = [
        engine.evaluate(
            inputs, signal, {}, ("2015-01-01", "2016-02-25"), frequency="daily"
        )
        for inputs in (base, delayed)
    ]
    pd.testing.assert_series_equal(results[0].returns.date, results[1].returns.date)


def test_reported_fill_gap_cap_breach_derisks_at_next_decision(monkeypatch):
    from src import futures_engine as engine

    inputs = rolled_inputs()
    fill_days = pd.to_datetime(["2016-02-19", "2016-02-22", "2016-02-23"], utc=True)
    for symbol, price in (("ESH7", 6000), ("ESM7", 6200)):
        for day in fill_days:
            inputs.prices.loc[(day, symbol), "open"] = price
    monkeypatch.setattr(engine, "covariance_targets", lambda *a, **k: np.array([1.0]))
    result = engine.evaluate(
        inputs,
        lambda view, params: pd.Series({"ES": 1.0}),
        {},
        ("2016-02-19", "2016-02-24"),
        frequency="daily",
    )
    assert result.returns.iloc[0].gap_cap_breach
    assert result.positions.iloc[0].quantity == 1
    assert result.positions.iloc[1].quantity == 0
    assert not result.returns.iloc[1].gap_cap_breach


def test_drawdown_pause_is_five_bars_then_rearms_without_flat_day_reset(monkeypatch):
    from src import futures_engine as engine

    bars, definitions = synthetic_frames()
    days = bars.loc[
        (bars.date >= pd.Timestamp("2016-02-01", tz="UTC"))
        & (bars.date < pd.Timestamp("2016-02-19", tz="UTC")),
        "date",
    ]
    bars.loc[bars.date.isin(days), "open"] = 890.0
    bars.loc[bars.date == days.iloc[0], "open"] = 4900.0
    inputs = FuturesInputs(bars, definitions, roots=("ES",))
    monkeypatch.setattr(engine, "covariance_targets", lambda *a, **k: np.array([1.0]))
    result = engine.evaluate(
        inputs,
        lambda view, params: pd.Series({"ES": 1.0}),
        {},
        ("2016-02-01", "2016-02-19"),
        frequency="monthly",
    )
    assert result.returns.iloc[1]["return"] < -0.20
    assert result.positions.quantity.iloc[2:7].tolist() == [0] * 5
    assert result.positions.quantity.iloc[7] == 1
    assert result.metrics["max_drawdown"] < -0.20


def test_window_without_warmed_observations_is_an_explicit_failure():
    from src.futures_engine import evaluate

    bars, definitions = synthetic_frames()
    inputs = FuturesInputs(bars, definitions, roots=("ES",))
    with pytest.raises(ValueError, match="(?i)(eligible|observations|warm)"):
        evaluate(
            inputs,
            lambda view, params: pytest.fail("unwarmed plugin called"),
            {},
            ("2015-01-01", "2015-01-31"),
        )
