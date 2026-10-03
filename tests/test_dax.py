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


def test_end_to_end_features_use_only_available_flow():
    from src.signals import features

    e = events()
    e["ts_recv"] = pd.date_range(
        "2025-06-02 07:05:00", periods=len(e), freq="s", tz="UTC"
    )
    e["product"] = "FDXS"
    full = pd.concat(
        [e.assign(product=p) for p in ["FDAX", "FDXM", "FDXS"]], ignore_index=True
    )
    cfg = {
        "products": ["FDAX", "FDXM", "FDXS"],
        "timezone": "Europe/Berlin",
        "session_open": "09:05",
        "session_close": "09:05:06",
        "lookback_seconds": 1,
        "horizon_seconds": 1,
        "grid_seconds": 1,
        "quote_age_seconds": 1,
    }
    frame, _, audit = features(full, cfg, "2025-06-02")
    assert audit["eligible_rows"] > 0
    assert frame.OF_FDXS.iloc[0] == -1
    assert frame.Y.iloc[0] == 1


def test_trade_features_do_not_require_future_label():
    from src.signals import features

    e = events()
    e["ts_recv"] = pd.date_range(
        "2025-06-02 07:05:00", periods=len(e), freq="s", tz="UTC"
    )
    full = pd.concat(
        [e.assign(product=p) for p in ["FDAX", "FDXM", "FDXS"]], ignore_index=True
    )
    cfg = {
        "products": ["FDAX", "FDXM", "FDXS"],
        "timezone": "Europe/Berlin",
        "session_open": "09:05",
        "session_close": "09:05:07",
        "lookback_seconds": 1,
        "horizon_seconds": 1,
        "grid_seconds": 1,
        "quote_age_seconds": 0.5,
    }
    frame, _, _ = features(full, cfg, "2025-06-02")
    assert frame.Y.isna().any()
    assert frame.OF_FDXS.notna().all()


def test_unsigned_book_sizes_preserve_negative_imbalance():
    e = events()
    e["bid_size"] = np.array([1] * len(e), dtype=np.uint32)
    e["ask_size"] = np.array([3] * len(e), dtype=np.uint32)
    q = quotes(e)
    assert (q.bi == -0.5).all()
    assert q.bi.between(-1, 1).all()


def test_acquisition_recovers_existing_file_without_download(tmp_path, monkeypatch):
    import hashlib
    import json
    from data import download

    request = {"dataset": "XEUR.EOBI", "schema": "mbp-1", "start": "2025-03-10"}
    identity = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()[
        :20
    ]
    target = tmp_path / f"{identity}.dbn.zst"
    target.write_bytes(b"completed download before manifest write")
    monkeypatch.setattr(download, "DATA", tmp_path)
    monkeypatch.setattr(
        download, "quote", lambda r: [{"request": r[0], "estimated_usd": 1}]
    )
    monkeypatch.setattr(
        download, "client", lambda: pytest.fail("existing data must not be downloaded")
    )
    download.acquire({"requests": [{"request": request}]}, 2)
    row = json.loads((tmp_path / "manifest.jsonl").read_text())
    assert row["recovered_existing_file"]
    assert row["sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
    download.acquire({"requests": [{"request": request}]}, 2)
    assert len((tmp_path / "manifest.jsonl").read_text().splitlines()) == 1


def test_daily_loss_limit_stops_new_entries():
    q = quotes(events())
    t = q.index[0]
    frame = pd.DataFrame(
        {"spread_FDXS": [1, 1]}, index=[t, t + pd.Timedelta(seconds=4)]
    )
    cfg = {
        "latency_ms": 0,
        "horizon_seconds": 2,
        "quote_age_seconds": 1,
        "daily_loss_limit_eur": 0.5,
    }
    trades = simulate(frame, [-10, -10], {"FDXS": q}, cfg, fee=0, buffer=0)
    assert len(trades) == 1
    assert trades.net_eur.iloc[0] == -2


def test_holdout_files_are_excluded_before_opening(tmp_path):
    import json
    from src.market_data import prepare

    manifest = {
        "request": {"schema": "mbp-1", "start": "2025-07-28", "end": "2025-07-29"},
        "path": "does-not-exist.dbn.zst",
    }
    (tmp_path / "manifest.jsonl").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Both MBP-1 and definitions"):
        prepare(tmp_path, {"holdout_start": "2025-07-28"})


def test_mixed_holdout_file_is_rejected_before_opening(tmp_path):
    import json
    from src.market_data import prepare

    manifest = {
        "request": {"schema": "mbp-1", "start": "2025-07-27", "end": "2025-07-29"},
        "path": "does-not-exist.dbn.zst",
    }
    (tmp_path / "manifest.jsonl").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="locked holdout"):
        prepare(tmp_path, {"holdout_start": "2025-07-28"})
