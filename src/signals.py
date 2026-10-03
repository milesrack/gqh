"""Point-in-time flow features and nested linear forecasts."""

import numpy as np
import pandas as pd
import statsmodels.api as sm

BASE = ["OF_FDXS", "R_FDXS", "BI_FDXS", "R_FDAX", "R_FDXM"]
CROSS = BASE + ["OF_FDAX", "OF_FDXM"]


def quotes(events):
    # Only complete, on-market events update the observable book. Invalid
    # snapshots remain in the stream so they invalidate earlier quotes.
    q = events[(events.publisher_id == 101) & ((events["flags"] & 128) != 0)].copy()
    q = q.sort_values("ts_recv", kind="stable").drop_duplicates("ts_recv", keep="last")
    valid = ((q["flags"] & 12) == 0) & (q.bid > 0) & (q.ask >= q.bid)
    valid &= (q.bid < 1e8) & (q.ask < 1e8) & (q.bid_size > 0) & (q.ask_size > 0)
    q["valid"] = valid.fillna(False)
    q["mid"] = ((q.bid + q.ask) / 2).where(valid)
    q["bi"] = ((q.bid_size - q.ask_size) / (q.bid_size + q.ask_size)).where(valid)
    return q.set_index("ts_recv")


def observed(q, times, max_age):
    positions = q.index.searchsorted(times, side="right") - 1
    safe = np.maximum(positions, 0)
    values = q.iloc[safe].copy()
    ages = (times.as_unit("ns").asi8 - q.index.as_unit("ns").asi8[safe]) / 1e9
    valid = (positions >= 0) & (ages <= max_age) & values.valid.to_numpy()
    values.index = times
    values.loc[~valid, ["mid", "bi", "bid", "ask"]] = np.nan
    return values


def flow(events, times, lookback):
    trades = events[
        (events.publisher_id == 101)
        & (events.action == "T")
        & ((events["flags"] & 12) == 0)
    ].sort_values("ts_recv", kind="stable")
    classified = trades[trades.side.isin(["B", "A"])]
    tt = pd.DatetimeIndex(classified.ts_recv).as_unit("ns").asi8
    size = classified["size"].to_numpy(dtype=float)
    signed = size * np.where(classified.side == "B", 1, -1)
    right = np.searchsorted(tt, times.as_unit("ns").asi8, side="right")
    left = np.searchsorted(
        tt, times.as_unit("ns").asi8 - int(lookback * 1e9), side="right"
    )
    volume = np.r_[0, np.cumsum(size)]
    net = np.r_[0, np.cumsum(signed)]
    total = volume[right] - volume[left]
    imbalance = np.divide(
        net[right] - net[left], total, out=np.full(len(times), np.nan), where=total > 0
    )
    return imbalance, total, right - left


def features(events, cfg, day):
    start = pd.Timestamp(f"{day} {cfg['session_open']}", tz=cfg["timezone"]).tz_convert(
        "UTC"
    )
    end = pd.Timestamp(f"{day} {cfg['session_close']}", tz=cfg["timezone"]).tz_convert(
        "UTC"
    )
    grid = pd.date_range(
        start + pd.Timedelta(seconds=cfg["lookback_seconds"]),
        end - pd.Timedelta(seconds=cfg["horizon_seconds"]),
        freq=f"{cfg['grid_seconds']}s",
    )
    frame = pd.DataFrame(index=grid)
    books = {}
    for product in cfg["products"]:
        e = events[events["product"] == product]
        if e.empty:
            return frame.iloc[:0], books, {"missing_product": product}
        q = quotes(e)
        if q.empty:
            return frame.iloc[:0], books, {"missing_quotes": product}
        books[product] = q
        now = observed(q, grid, cfg["quote_age_seconds"])
        lag = observed(
            q,
            grid - pd.Timedelta(seconds=cfg["lookback_seconds"]),
            cfg["quote_age_seconds"],
        )
        of, volume, count = flow(e, grid, cfg["lookback_seconds"])
        frame[f"OF_{product}"] = of
        frame[f"R_{product}"] = now.mid.to_numpy() - lag.mid.to_numpy()
        frame[f"BI_{product}"] = now.bi.to_numpy()
        frame[f"volume_{product}"] = volume
        frame[f"trades_{product}"] = count
        frame[f"mid_{product}"] = now.mid.to_numpy()
        frame[f"spread_{product}"] = (now.ask - now.bid).to_numpy()
    # Label construction is separate from feature construction; the future
    # quote is never passed to model prediction or the execution decision.
    future = observed(
        books["FDXS"],
        grid + pd.Timedelta(seconds=cfg["horizon_seconds"]),
        cfg["quote_age_seconds"],
    )
    frame["Y"] = future.mid.to_numpy() - frame.mid_FDXS
    frame["day"] = day
    eligible = frame.dropna(subset=CROSS)
    audit = {
        "grid_rows": len(frame),
        "eligible_rows": len(eligible),
        "forecast_rows": int(eligible.Y.notna().sum()),
        "unknown_side_trades": int(
            ((events.action == "T") & ~events.side.isin(["B", "A"])).sum()
        ),
    }
    return eligible, books, audit


def fit(frame, columns):
    x = sm.add_constant(frame[columns], has_constant="add")
    if len(x) <= len(columns) + 1 or np.linalg.matrix_rank(x) < x.shape[1]:
        raise ValueError("OLS fit is underdetermined or rank deficient")
    return sm.OLS(frame.Y, x).fit(cov_type="HAC", cov_kwds={"maxlags": 5})


def predict(model, frame, columns):
    return model.predict(sm.add_constant(frame[columns], has_constant="add"))
