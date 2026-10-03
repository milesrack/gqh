"""Synthetic plugin/API checks; no market files, acquisition or engine imports."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from src.strategies import STRATEGIES, CausalMarketView, get_strategy
from src.strategies.base import ROOTS


def view(roots=ROOTS, periods=400):
    dates = pd.bdate_range("2018-01-01", periods=periods, tz="UTC")
    rng = np.random.default_rng(151)
    common = rng.normal(0, 1, periods)
    changes = pd.DataFrame(
        {r: common + rng.normal(0, 0.2, periods) for r in ROOTS}, index=dates
    )
    bars = {}
    for i, root in enumerate(ROOTS):
        close = 100 + i * 20 + changes[root].cumsum()
        bars[root] = pd.DataFrame(
            {
                "close": close,
                "high": close + 2,
                "low": close - 1,
                "volume": 100 + np.arange(periods),
                "instrument_id": i,
            },
            index=dates,
        )
    curve = pd.DataFrame(
        {
            "near_price": [101.0, 100.0],
            "far_price": [100.0, 101.0],
            "near_expiry": [dates[-1] + pd.Timedelta(days=60)] * 2,
            "far_expiry": [dates[-1] + pd.Timedelta(days=90)] * 2,
        },
        index=["CL", "GC"],
    )
    return CausalMarketView(
        decision_at=dates[-1] + pd.Timedelta(days=2),
        information_asof=dates[-1],
        roots=tuple(roots),
        point_changes=changes,
        dollar_changes=changes * 50,
        whole_root_volume=pd.DataFrame(100.0, index=dates, columns=ROOTS),
        ohlc=bars,
        curve=curve,
        notional_returns=changes / 100,
        positions=pd.Series(0.0, index=roots),
    )


@pytest.mark.parametrize("strategy_id", STRATEGIES)
def test_declared_grids_return_finite_ordered_scores_without_mutation(strategy_id):
    spec = get_strategy(strategy_id)
    roots = spec.supported_roots
    if strategy_id == "dual_rotation":
        roots = ROOTS
    data = view(roots)
    before = data.point_changes.copy(deep=True)
    for params in spec.grid:
        output = spec.signal(data, params)
        assert tuple(output.index) == roots
        assert np.isfinite(output).all()
    pd.testing.assert_frame_equal(before, data.point_changes)


def test_custom_values_and_json_arrays_are_accepted_beyond_defaults():
    get_strategy("trend").validate_params({"lookback": 77})
    get_strategy("double_ma").validate_params({"lengths": [7, 31]})
    get_strategy("volume_reversal").validate_params({"cutoff": 1.7})
    with pytest.raises(ValueError, match="strictly increasing"):
        get_strategy("double_ma").validate_params({"lengths": [31, 7]})
    with pytest.raises(ValueError, match="integer"):
        get_strategy("trend").validate_params({"lookback": True})
    with pytest.raises(ValueError, match="expects parameters"):
        get_strategy("trend").validate_params({"lookback": 77, "future": 1})


def test_univariate_and_cross_sectional_universe_contract():
    data = view(("ES",))
    assert get_strategy("trend").signal(data, {"lookback": 77}).index.tolist() == ["ES"]
    with pytest.raises(ValueError, match="distinct roots"):
        get_strategy("reversal").signal(data, {"lookback": 5})
    with pytest.raises(ValueError, match="unsupported roots"):
        get_strategy("carry").signal(view(("ES", "NQ")), {})


def test_reversal_normalises_before_demeaning_and_volume_does_not_redemean():
    data = view()
    history = data.point_changes.tail(63)
    change = history.tail(5).sum() / history.std(ddof=1)
    expected = -(change - change.mean())
    pd.testing.assert_series_equal(
        get_strategy("reversal").signal(data, {"lookback": 5}), expected
    )
    volume = data.whole_root_volume.copy()
    volume.loc[volume.index[-5:], ["ES", "NQ"]] = 200
    output = get_strategy("volume_reversal").signal(
        replace(data, whole_root_volume=volume), {"cutoff": 1.5}
    )
    pd.testing.assert_series_equal(
        output, expected * pd.Series([1, 1, 0, 0, 0, 0], index=ROOTS)
    )


def test_information_after_cutoff_and_identity_mixes_fail():
    data = view()
    future = replace(
        data, information_asof=data.information_asof - pd.Timedelta(days=1)
    )
    with pytest.raises(ValueError, match="after asof"):
        get_strategy("trend").signal(future, {"lookback": 60})
    bars = {r: b.copy() for r, b in data.ohlc.items()}
    bars["ES"].iloc[-1, bars["ES"].columns.get_loc("instrument_id")] = 999
    with pytest.raises(ValueError, match="instrument identities"):
        get_strategy("single_ma").signal(replace(data, ohlc=bars), {"lengths": [20]})


def test_channel_is_contrarian_and_carry_is_actual_curve_signal():
    data = view(("ES",))
    bars = dict(data.ohlc)
    bars["ES"] = bars["ES"].copy()
    bars["ES"].iloc[-1, bars["ES"].columns.get_loc("close")] = (
        bars["ES"].close.iloc[-21:-1].max() + 1
    )
    assert (
        get_strategy("channel").signal(replace(data, ohlc=bars), {"lookback": 20})["ES"]
        == -1
    )
    carry = get_strategy("carry").signal(view(("CL", "GC")), {})
    assert carry.CL > 0 and carry.GC < 0
    assert abs(carry.sum()) < 1e-12


def test_knn_labels_and_hp_use_only_cut_history():
    data = view(("6E",))
    cutoff = data.ohlc["6E"].index[-2]
    bars = {"6E": data.ohlc["6E"].loc[:cutoff].copy()}
    earlier = replace(data, information_asof=cutoff, ohlc=bars)
    for strategy_id, params in [
        ("knn", {"neighbours": 7}),
        ("hp_ma", {"smoothing": 5000.0}),
    ]:
        expected = get_strategy(strategy_id).signal(earlier, params)
        future_bars = data.ohlc["6E"].copy()
        future_bars.iloc[-1, future_bars.columns.get_loc("close")] = 999999
        # Future modifications cannot enter a cut view; uncut future is rejected.
        np.testing.assert_array_equal(
            expected, get_strategy(strategy_id).signal(earlier, params)
        )
        with pytest.raises(ValueError, match="information order/cutoff"):
            get_strategy(strategy_id).signal(
                replace(earlier, ohlc={"6E": future_bars}), params
            )
