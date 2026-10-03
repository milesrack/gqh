import numpy as np
import pandas as pd
import pytest

from src.backtest import simulate
from src.signals import BASE, fit, flow, observed, quotes


def events():
    t = pd.Timestamp("2025-06-02 10:00", tz="UTC")
    return pd.DataFrame(
        {
            "ts_recv": [t + pd.Timedelta(seconds=s) for s in [0, 1, 2, 3, 4, 6]],
            "ts_event": [t] * 6,
            "publisher_id": [101] * 6,
            "action": ["T"] * 6,
            "side": ["B", "A", "B", "B", "B", "A"],
            "size": [1, 1, 2, 1, 1, 3],
            "flags": [128] * 6,
            "bid": [100, 100, 101, 101, 101, 103],
            "ask": [101, 101, 102, 102, 102, 104],
            "bid_size": [2] * 6,
            "ask_size": [2] * 6,
        }
    )


def test_window_excludes_left_boundary_and_future():
    e = events()
    t = e.ts_recv.iloc[4]
    of, total, count = flow(e, pd.DatetimeIndex([t]), 4)
    assert total[0] == 5 and count[0] == 4 and of[0] == pytest.approx(3 / 5)


def test_missing_activity_is_not_zero():
    e = events()
    t = e.ts_recv.iloc[0] - pd.Timedelta(seconds=1)
    of, _, _ = flow(e, pd.DatetimeIndex([t]), 5)
    assert np.isnan(of[0])


def test_invalid_book_blocks_prior_quote():
    e = events()
    e.loc[1, "bid"] = 105
    q = quotes(e)
    v = observed(
        q, pd.DatetimeIndex([e.ts_recv.iloc[1] + pd.Timedelta(milliseconds=100)]), 1
    )
    assert np.isnan(v.mid.iloc[0])


def test_receipt_time_stale_quote_and_future_quote():
    q = quotes(events())
    times = pd.DatetimeIndex(
        [
            q.index[0] - pd.Timedelta(milliseconds=1),
            q.index[-1] + pd.Timedelta(seconds=2),
        ]
    )
    assert observed(q, times, 1).mid.isna().all()


def test_rank_deficient_model_refused():
    frame = pd.DataFrame({name: np.ones(20) for name in BASE})
    frame["Y"] = 0
    with pytest.raises(ValueError, match="rank deficient"):
        fit(frame, BASE)


def test_latency_spread_and_no_overlap():
    q = quotes(events())
    t = q.index[0]
    frame = pd.DataFrame(
        {"spread_FDXS": [1, 1]}, index=[t, t + pd.Timedelta(seconds=1)]
    )
    cfg = {"latency_ms": 100, "horizon_seconds": 4, "quote_age_seconds": 1}
    trades = simulate(frame, [10, 10], {"FDXS": q}, cfg, fee=0.5, buffer=0)
    assert len(trades) == 1
    assert trades.entry.iloc[0] == t + pd.Timedelta(seconds=1)
    assert trades.net_eur.iloc[0] == 1  # buy101, sell103, fee1


def test_no_silent_deletion_of_open_position():
    q = quotes(events()).iloc[:3]
    t = q.index[0]
    frame = pd.DataFrame({"spread_FDXS": [1]}, index=[t])
    with pytest.raises(ValueError, match="no valid exit"):
        simulate(
            frame,
            [10],
            {"FDXS": q},
            {"latency_ms": 0, "horizon_seconds": 5, "quote_age_seconds": 1},
            0,
            0,
        )
