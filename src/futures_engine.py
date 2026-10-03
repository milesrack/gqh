"""Reusable causal forecast evaluation with dated-contract cash accounting."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.futures_data import FIXED_HOLDOUT_START, SPECS, FuturesInputs, native_tick, utc
from src.strategies.base import CausalMarketView


@dataclass
class EvaluationResult:
    metrics: dict
    returns: pd.DataFrame
    trades: pd.DataFrame
    positions: pd.DataFrame
    manifest: dict


def covariance_targets(signals, dollar_changes, equity, annual_target=0.10):
    x = np.asarray(dollar_changes, dtype=float)
    if x.ndim != 2 or len(x) < 63 or not np.isfinite(x).all():
        raise ValueError("Incomplete causal 63-bar covariance history")
    cov = np.atleast_2d(np.cov(x[-63:], rowvar=False, ddof=1))
    vol = np.sqrt(np.diag(cov))
    if np.any(vol <= 0):
        raise ValueError("Zero dollar volatility")
    cov = 0.5 * cov + 0.5 * np.diag(np.diag(cov))
    raw = np.asarray(signals, dtype=float) / vol
    risk = float(np.sqrt(raw @ cov @ raw))
    return raw * equity * annual_target / (np.sqrt(252) * risk) if risk else raw * 0


def cap_and_round(quantity, prices, roots, equity, root_cap=0.25):
    q = np.asarray(quantity, dtype=float)
    n = abs(q) * abs(np.asarray(prices)) * [SPECS[r].multiplier for r in roots]
    ratios = [1.0, equity / max(float(n.sum()), 1.0)]
    ratios.extend(root_cap * equity / max(float(v), 1.0) for v in n)
    ix = [i for i, r in enumerate(roots) if r in ("ES", "NQ")]
    ratios.append(0.35 * equity / max(float(n[ix].sum()), 1.0))
    return np.trunc(q * min(ratios)).astype(int)


def side_cost(root, quantity, execution_at, *, commission=2.5, ticks=1.0, multiple=1.0):
    return (
        abs(quantity)
        * (
            commission
            + ticks * native_tick(root, execution_at) * SPECS[root].multiplier
        )
        * multiple
    )


def mark_and_trade(
    root,
    old_quantity,
    old_mark,
    incumbent_open,
    target_quantity,
    replacement_open=None,
    *,
    execution_at="2020-01-01",
    costs=None,
):
    prices = [old_mark, incumbent_open] + (
        [] if replacement_open is None else [replacement_open]
    )
    if not np.isfinite(prices).all():
        raise ValueError("Missing observed held/replacement price")
    pnl = old_quantity * SPECS[root].multiplier * (incumbent_open - old_mark)
    sides = (
        abs(target_quantity - old_quantity)
        if replacement_open is None
        else abs(old_quantity) + abs(target_quantity)
    )
    return (
        pnl,
        side_cost(root, sides, execution_at, **(costs or {})),
        incumbent_open if replacement_open is None else replacement_open,
    )


def causal_view(inputs, day, roots, equity, held):
    lag = inputs.information_day(day)
    changes = inputs.point_changes.loc[:lag, list(roots)].copy(deep=True)
    ohlc = {}
    curves = []
    for root in roots:
        selected = inputs.selections[day][root]
        histories = getattr(inputs, "contract_histories", None)
        if histories is not None:
            bars = histories[(selected["symbol"], selected["instrument_id"])].loc[:lag]
        else:
            bars = (
                inputs.bars[
                    (inputs.bars.symbol == selected["symbol"])
                    & (inputs.bars.instrument_id == selected["instrument_id"])
                    & (inputs.bars.date <= lag)
                    & inputs.bars.date.isin(inputs.days)
                ]
                .set_index("date")
                .sort_index()
            )
        ohlc[root] = bars.copy(deep=True)
        pair = inputs.curves[day][root]
        if len(pair) == 2:
            a, b = pair
            curves.append(
                {
                    "root": root,
                    "near_price": float(inputs.row(lag, a["symbol"]).close),
                    "far_price": float(inputs.row(lag, b["symbol"]).close),
                    "near_expiry": a["expiry"],
                    "far_expiry": b["expiry"],
                }
            )
        else:
            curves.append(
                {
                    "root": root,
                    "near_price": np.nan,
                    "far_price": np.nan,
                    "near_expiry": pd.NaT,
                    "far_expiry": pd.NaT,
                }
            )
    return CausalMarketView(
        day,
        lag,
        roots,
        changes,
        changes * pd.Series({r: SPECS[r].multiplier for r in roots}),
        inputs.whole_root_volume.loc[:lag, list(roots)].copy(deep=True),
        ohlc,
        pd.DataFrame(curves).set_index("root"),
        inputs.notional_returns.loc[:lag, list(roots)].copy(deep=True),
        equity,
        pd.Series({r: held.get(r, {}).get("quantity", 0) for r in roots}, dtype=float),
    )


def metrics(frame, initial_capital=1_000_000.0):
    if frame.empty:
        return {"bars": 0, "missing_reason": "No eligible outcome observations"}
    r = frame["return"]
    sd = r.std(ddof=1)
    capacity = frame.capacity_equity.min()
    result = {
        "bars": len(frame),
        "mean": float(r.mean() * 252),
        "annual_volatility": float(sd * np.sqrt(252)),
        "sharpe": float(r.mean() / sd * np.sqrt(252)) if sd > 0 else None,
        "net_pnl": float(frame.equity.iloc[-1] - initial_capital),
        "cost": float(frame.cost.sum()),
        "max_drawdown": float(
            (frame.equity / frame.equity.cummax().clip(lower=initial_capital) - 1).min()
        ),
        "contracts_traded": int(frame.contracts_traded.sum()),
        "rolls": int(frame.rolls.sum()),
        "minimum_participation_capacity_equity": float(capacity)
        if np.isfinite(capacity)
        else None,
        "gap_cap_breach_bars": int(frame.gap_cap_breach.sum()),
    }
    result["missing_reasons"] = {}
    if result["sharpe"] is None:
        result["missing_reasons"]["sharpe"] = "Zero or insufficient return variance"
    if result["minimum_participation_capacity_equity"] is None:
        result["missing_reasons"]["minimum_participation_capacity_equity"] = (
            "No traded legs"
        )
    days = max(1, (frame.date.iloc[-1] - frame.date.iloc[0]).days)
    result["cagr"] = float(
        (frame.equity.iloc[-1] / initial_capital) ** (365.25 / days) - 1
    )
    return {
        k: (None if isinstance(v, float) and not np.isfinite(v) else v)
        for k, v in result.items()
    }


def evaluate(
    inputs: FuturesInputs,
    signal_fn,
    params,
    window,
    costs=None,
    frequency="monthly",
    output=None,
    universe=None,
    risk=None,
):
    start, end = map(utc, window)
    if start >= end or end > FIXED_HOLDOUT_START:
        raise ValueError("Evaluation window crosses locked boundary or is empty")
    roots = tuple(universe or inputs.roots)
    if (
        not roots
        or len(set(roots)) != len(roots)
        or not set(roots) <= set(inputs.roots)
    ):
        raise ValueError("Unknown, duplicate or empty evaluation universe")
    if frequency not in ("daily", "weekly", "monthly"):
        raise ValueError("Unsupported rebalance frequency")
    costs = {"commission": 2.5, "ticks": 1.0, "multiple": 1.0, **(costs or {})}
    risk = {
        "capital": 1_000_000.0,
        "annual_target": 0.10,
        "root_cap": 0.25,
        **(risk or {}),
    }
    if set(costs) != {"commission", "ticks", "multiple"} or set(risk) != {
        "capital",
        "annual_target",
        "root_cap",
    }:
        raise ValueError("Unknown execution/risk setting")
    if not all(np.isfinite(v) and v >= 0 for v in costs.values()) or not all(
        np.isfinite(v) and v > 0 for v in risk.values()
    ):
        raise ValueError("Invalid execution/risk settings")
    days = [d for d in inputs.selections if max(start, inputs.common_start) <= d < end]
    if not days:
        raise ValueError("No eligible outcome observations after common warm-up")
    equity = peak = risk["capital"]
    pause = 0
    liquidate = False
    breached = False
    resume = False
    gap_derisk = False
    held = {}
    daily = []
    legs = []
    positions = []
    last_period = None
    for k, day in enumerate(days):
        before = equity
        lag = inputs.information_day(day)
        view = causal_view(inputs, day, roots, equity, held)
        scores = signal_fn(view, dict(params))
        if (
            not isinstance(scores, pd.Series)
            or set(scores.index) != set(roots)
            or scores.index.has_duplicates
        ):
            raise ValueError("Plugin must return exactly one score per configured root")
        scores = scores.reindex(roots).astype(float)
        if not np.isfinite(scores).all():
            raise ValueError("Nonfinite plugin score")
        period = day.strftime(
            "%Y-%m"
            if frequency == "monthly"
            else "%G-%V"
            if frequency == "weekly"
            else "%Y-%m-%d"
        )
        rebal = period != last_period or resume
        resume = False
        if liquidate:
            pause = 5
            liquidate = False
        chosen = inputs.selections[day]
        forecast = [float(inputs.row(lag, chosen[r]["symbol"]).close) for r in roots]
        force_gap_exit = gap_derisk
        gap_derisk = False
        if k == len(days) - 1 or pause or force_gap_exit:
            target = np.zeros(len(roots), dtype=int)
        else:
            raw = (
                covariance_targets(
                    scores.values,
                    view.dollar_changes.tail(63).values,
                    equity,
                    risk["annual_target"],
                )
                if rebal
                else [held.get(r, {}).get("quantity", 0) for r in roots]
            )
            target = cap_and_round(raw, forecast, roots, equity, risk["root_cap"])
        contributions = {r: 0.0 for r in roots}
        cost = 0.0
        gross = 0.0
        traded = 0
        rolls = 0
        capacity = np.inf
        for j, root in enumerate(roots):
            new = chosen[root]
            old = held.get(root)
            new_open = float(inputs.row(day, new["symbol"]).open)
            if old is None:
                old = {
                    "symbol": new["symbol"],
                    "quantity": 0,
                    "mark": new_open,
                    "instrument_id": new["instrument_id"],
                }
            old_open = float(inputs.row(day, old["symbol"]).open)
            if (
                int(inputs.row(day, old["symbol"]).instrument_id)
                != old["instrument_id"]
            ):
                raise ValueError("Held cash ledger crossed instrument identity")
            roll = old["symbol"] != new["symbol"]
            q = int(target[j])
            pnl, c, new_mark = mark_and_trade(
                root,
                old["quantity"],
                old["mark"],
                old_open,
                q,
                new_open if roll else None,
                execution_at=day,
                costs=costs,
            )
            trade_legs = (
                [
                    (old["symbol"], -old["quantity"], old_open),
                    (new["symbol"], q, new_open),
                ]
                if roll
                else [(new["symbol"], q - old["quantity"], old_open)]
            )
            for symbol, quantity, price in trade_legs:
                if not quantity:
                    continue
                hist = inputs.volumes.loc[inputs.days[inputs.days <= lag][-20:], symbol]
                if len(hist) != 20 or hist.isna().any():
                    raise ValueError("Incomplete 20-bar traded-leg liquidity history")
                adv = float(hist.mean())
                capacity = min(capacity, before * 0.01 * adv / abs(quantity))
                if abs(quantity) > 0.01 * adv:
                    raise ValueError("Participation infeasible")
                legs.append(
                    {
                        "date": day,
                        "root": root,
                        "symbol": symbol,
                        "instrument_id": int(inputs.row(day, symbol).instrument_id),
                        "quantity": quantity,
                        "raw_open": price,
                        "information_asof": lag,
                        "commission": abs(quantity)
                        * costs["commission"]
                        * costs["multiple"],
                        "slippage": abs(quantity)
                        * native_tick(root, day)
                        * SPECS[root].multiplier
                        * costs["ticks"]
                        * costs["multiple"],
                        "native_tick": native_tick(root, day),
                        "multiplier": SPECS[root].multiplier,
                    }
                )
            positions.append(
                {
                    "date": day,
                    "root": root,
                    "information_asof": lag,
                    "score": float(scores.iloc[j]),
                    "forecast_close": forecast[j],
                    "prior_symbol": old["symbol"],
                    "prior_instrument_id": old["instrument_id"],
                    "prior_quantity": old["quantity"],
                    "prior_mark": old["mark"],
                    "incumbent_open": old_open,
                    "symbol": new["symbol"],
                    "instrument_id": new["instrument_id"],
                    "quantity": q,
                    "expiry": new.get("expiry"),
                    "metadata_known_at": new.get("known_at"),
                    "mark": new_mark,
                    "gross_pnl": pnl,
                    "cost": c,
                    "net_pnl": pnl - c,
                }
            )
            held[root] = {
                "symbol": new["symbol"],
                "instrument_id": new["instrument_id"],
                "quantity": q,
                "mark": new_mark,
            }
            contributions[root] = pnl - c
            gross += pnl
            cost += c
            traded += sum(abs(v[1]) for v in trade_legs)
            rolls += int(roll and old["quantity"] != 0)
        equity += gross - cost
        if equity <= 0:
            raise ValueError("Bankruptcy")
        peak = max(peak, equity)
        ret = (equity - before) / before
        below = equity / peak - 1 < -0.20
        if ret < -0.03 or (below and not breached):
            liquidate = True
        breached = below
        if pause:
            pause -= 1
            if pause == 0:
                resume = True
        notionals = np.array(
            [
                abs(held[r]["quantity"] * held[r]["mark"] * SPECS[r].multiplier)
                for r in roots
            ]
        )
        ix = [j for j, r in enumerate(roots) if r in ("ES", "NQ")]
        gap = bool(
            notionals.sum() / equity > 1 + 1e-12
            or (notionals / equity > risk["root_cap"] + 1e-12).any()
            or notionals[ix].sum() / equity > 0.35 + 1e-12
        )
        gap_derisk = gap
        if force_gap_exit and not pause:
            resume = True
        daily.append(
            dict(
                date=day,
                equity=equity,
                return_=ret,
                gross_pnl=gross,
                cost=cost,
                contracts_traded=traded,
                rolls=rolls,
                capacity_equity=capacity,
                realised_gross=float(notionals.sum() / equity),
                gap_cap_breach=gap,
                **{f"pnl_{r}": v for r, v in contributions.items()},
            )
        )
        last_period = period
    frame = pd.DataFrame(daily).rename(columns={"return_": "return"})
    manifest = {
        "window": [str(start), str(end)],
        "effective_sample_start": str(days[0]) if days else None,
        "effective_sample_end": str(days[-1]) if days else None,
        "sample_dates": [str(d) for d in days],
        "universe": list(roots),
        "params": dict(params),
        "frequency": frequency,
        "costs": costs,
        "risk": risk,
        "extra_information_bars": inputs.extra_information_bars,
        "selection_policy": getattr(inputs, "selection_policy", "synthetic"),
        "data": inputs.source_manifest,
        "gap_de_risk": "A realised cap breach forces flat at the next eligible decision; no additional fixed pause",
        "fill_assumption": "First reported daily trade plus explicit adverse tick cost; not a guaranteed executable auction fill",
    }
    result = EvaluationResult(
        metrics(frame, risk["capital"]),
        frame,
        pd.DataFrame(legs),
        pd.DataFrame(positions),
        manifest,
    )
    if output is not None:
        destination = Path(output)
        destination.mkdir(parents=True, exist_ok=True)
        for name, data in [
            ("daily-returns", result.returns),
            ("trades", result.trades),
            ("positions", result.positions),
        ]:
            data.to_csv(destination / f"{name}.csv", index=False)
        (destination / "metrics.json").write_text(
            json.dumps(result.metrics, indent=2, allow_nan=False) + "\n"
        )
        (destination / "manifest.json").write_text(
            json.dumps(manifest, indent=2, allow_nan=False) + "\n"
        )
    return result
