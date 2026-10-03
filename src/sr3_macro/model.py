"""Causal revisions, frozen-contract outcomes and non-overlapping trades."""

import itertools

import numpy as np
import pandas as pd
import statsmodels.api as sm


def revisions(cfg, vintages):
    rows = []
    audits = []
    benchmark = []
    vintages = vintages.copy()
    vintages["value"] = pd.to_numeric(vintages.value, errors="coerce")
    for name, series in vintages.groupby("series_id"):
        previous = None
        history = []
        for vintage, group in series.groupby("vintage_date", sort=True):
            current = group.set_index("observation_date").value.dropna().sort_index()
            if previous is None:
                previous = current
                continue
            shared = previous.index.intersection(current.index).sort_values()
            if len(shared) < 4:
                previous = current
                continue
            changed = (current.loc[shared] - previous.loc[shared]).abs() > 1e-9
            old_changes = int(changed.iloc[:-3].sum())
            if old_changes > 12:
                benchmark.append(
                    {"series": name, "date": vintage, "older_changes": old_changes}
                )
                previous = current
                continue
            before = (
                previous.diff()
                if name == "PAYEMS"
                else previous.pct_change(fill_method=None) * 100
            )
            after = (
                current.diff()
                if name == "PAYEMS"
                else current.pct_change(fill_method=None) * 100
            )
            selected = shared[-cfg["recent_months"] :]
            delta = (after.loc[selected] - before.loc[selected]).dropna()
            delta = delta[delta.abs() > 1e-9]
            prior = np.asarray(history, dtype=float)
            mean = prior.mean() if len(prior) else 0
            sd = prior.std(ddof=1) if len(prior) > 1 else 0
            for month, value in delta.items():
                z = (
                    (value - mean) / sd
                    if len(prior) >= cfg["warmup_revisions"] and sd > 0
                    else np.nan
                )
                row = {
                    "series": name,
                    "date": vintage,
                    "observation_date": month,
                    "revision": float(value),
                    "z": float(z),
                    "before_growth": float(before.loc[month]),
                    "after_growth": float(after.loc[month]),
                    "prior_count": len(prior),
                }
                rows.append(row)
                if (
                    len(audits) < 5
                    and np.isfinite(z)
                    and vintage >= cfg["sr3_start"]
                    and not any(a["date"] == vintage for a in audits)
                ):
                    audits.append(
                        {
                            **row,
                            "brand_new_observation_excluded": True,
                            "latest_previous_observation": str(shared[-1]),
                        }
                    )
            history.extend(delta.tolist())
            previous = current
    return pd.DataFrame(rows), audits, benchmark


def build(cfg, rev, prices):
    days = pd.DatetimeIndex(sorted(prices.trade_date.unique()))
    lookup = prices.set_index(["trade_date", "contract"]).sort_index()
    subsets = [tuple(cfg["series"])] + [
        tuple(s for s in cfg["series"] if s != drop) for drop in cfg["series"]
    ]
    cases = []
    for subset, clip, decay, tenor, horizon in itertools.product(
        subsets, cfg["clips"], cfg["decays"], cfg["tenors"], cfg["horizons"]
    ):
        r = rev[rev.series.isin(subset) & rev.z.notna()].copy()
        if clip is not None:
            r["z"] = r.z.clip(-clip, clip)
        event = (
            r.groupby(["date", "series"]).z.mean().groupby("date").mean().sort_index()
        )
        state = 0.0
        previous = None
        prior = []
        observations = []
        for date, score in event.items():
            vintage = pd.Timestamp(date, tz="UTC")
            state = (
                state * np.exp(-(vintage - previous).days / decay) + score
                if previous is not None
                else score
            )
            scale = np.std(prior, ddof=1) if len(prior) > 1 else np.nan
            signal = state / scale if len(prior) >= 36 and scale > 0 else np.nan
            prior.append(state)
            previous = vintage
            if vintage < pd.Timestamp(cfg["sr3_start"], tz="UTC"):
                continue
            at = days.searchsorted(vintage) + cfg["entry_delay_sessions"]
            if at + horizon >= len(days) or not np.isfinite(signal):
                continue
            entry = days[at]
            exit = days[at + horizon]
            if entry < pd.Timestamp(cfg["sr3_start"], tz="UTC"):
                continue
            available = prices[
                (prices.trade_date == entry) & (prices.reference_start > entry)
            ].copy()
            if available.empty:
                continue
            available["distance"] = (
                available.midpoint - (entry + pd.Timedelta(days=tenor))
            ).abs()
            contract = available.sort_values(["distance", "contract"]).iloc[0].contract
            path = lookup.loc[(slice(entry, exit), contract), :].copy().reset_index()
            if len(path) != horizon + 1 or not pd.DatetimeIndex(path.trade_date).equals(
                days[at : at + horizon + 1]
            ):
                continue
            first = float(path.price.iloc[0])
            last = float(path.price.iloc[-1])
            new = r[r.date == date]
            observations.append(
                {
                    "event_date": date,
                    "entry": entry,
                    "exit": exit,
                    "contract": contract,
                    "signal": signal,
                    "raw_signal": state,
                    "target_bp": -100 * (last - first),
                    "entry_price": first,
                    "exit_price": last,
                    "positive_revisions": int((new.revision > 0).sum()),
                    "negative_revisions": int((new.revision < 0).sum()),
                }
            )
        frame = pd.DataFrame(observations)
        params = {
            "series": list(subset),
            "clip": clip,
            "decay": decay,
            "tenor": tenor,
            "horizon": horizon,
        }
        cases.append((params, frame))
    return cases


def regression(frame, horizon):
    if len(frame) < 30 or frame.raw_signal.nunique() < 3:
        return {"status": "insufficient_events", "events": len(frame)}
    fit = sm.OLS(frame.target_bp, sm.add_constant(frame.raw_signal)).fit(
        cov_type="HAC", cov_kwds={"maxlags": max(20, horizon), "use_correction": True}
    )
    ci = fit.conf_int().iloc[1]
    return {
        "status": "completed",
        "events": len(frame),
        "beta": float(fit.params.iloc[1]),
        "beta_p": float(fit.pvalues.iloc[1]),
        "beta_ci95": ci.tolist(),
        "r_squared": float(fit.rsquared),
        "intercept": float(fit.params.iloc[0]),
    }


def trade(cfg, frame, prices, threshold, cost, start, end):
    calendar = pd.DatetimeIndex(sorted(prices.trade_date.unique()))
    dates = calendar[(calendar >= start) & (calendar < end)]
    pnl = pd.Series(0.0, index=dates)
    busy = None
    trades = []
    lookup = prices.set_index(["trade_date", "contract"]).sort_index().price
    for row in frame.sort_values("entry").itertuples():
        if (
            row.entry < start
            or row.exit >= end
            or (busy is not None and row.entry <= busy)
            or abs(row.signal) < threshold
        ):
            continue
        direction = -np.sign(row.signal)
        path_dates = calendar[(calendar >= row.entry) & (calendar <= row.exit)]
        marks = lookup.reindex(pd.MultiIndex.from_product([path_dates, [row.contract]]))
        if marks.isna().any():
            raise ValueError("Missing held settlement; never forward fill")
        changes = np.diff(marks.to_numpy()) * direction * 2500
        pnl.loc[path_dates[1:]] += changes
        pnl.loc[row.entry] -= cost * 25 / 2
        pnl.loc[row.exit] -= cost * 25 / 2
        net = float(changes.sum() - cost * 25)
        trades.append(
            {
                "entry": str(row.entry),
                "exit": str(row.exit),
                "contract": row.contract,
                "direction": float(direction),
                "net_pnl": net,
                "net_bp": net / 25,
            }
        )
        busy = row.exit
    equity = cfg["capital"] + pnl.cumsum()
    returns = pnl / equity.shift(1).fillna(cfg["capital"])
    vol = returns.std(ddof=1) * np.sqrt(252)
    gross_gain = sum(max(t["net_pnl"], 0) for t in trades)
    loss = -sum(min(t["net_pnl"], 0) for t in trades)
    result = {
        "trades": len(trades),
        "net_pnl": float(pnl.sum()),
        "mean_trade": float(np.mean([t["net_pnl"] for t in trades]))
        if trades
        else None,
        "win_rate": float(np.mean([t["net_pnl"] > 0 for t in trades]))
        if trades
        else None,
        "profit_factor": gross_gain / loss if loss else None,
        "sharpe": float(returns.mean() * 252 / vol) if vol > 0 else None,
        "max_drawdown": float(
            (equity / equity.cummax().clip(lower=cfg["capital"]) - 1).min()
        ),
        "annual_volatility": float(vol),
    }
    return (
        result,
        pd.DataFrame(
            {
                "date": dates,
                "pnl": pnl.to_numpy(),
                "return": returns.to_numpy(),
                "equity": equity.to_numpy(),
            }
        ),
        trades,
    )
