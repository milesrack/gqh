"""One-contract marketable execution against observed top-of-book quotes."""

import numpy as np
import pandas as pd


def simulate(frame, predictions, books, cfg, fee, buffer, latency_ms=None, slippage=0):
    latency = pd.Timedelta(
        milliseconds=cfg["latency_ms"] if latency_ms is None else latency_ms
    )
    q = books["FDXS"]
    free_after = q.index[0] - pd.Timedelta(nanoseconds=1)
    trades = []
    realised = 0.0
    for t, forecast in zip(frame.index, predictions, strict=True):
        if realised <= -cfg.get("daily_loss_limit_eur", float("inf")):
            break
        if t <= free_after:
            continue
        threshold = frame.at[t, "spread_FDXS"] + 2 * (fee + slippage) + buffer
        side = 1 if forecast > threshold else -1 if forecast < -threshold else 0
        if side == 0:
            continue
        arrival = t + latency
        exit_arrival = t + pd.Timedelta(seconds=cfg["horizon_seconds"]) + latency
        entry_idx = q.index.searchsorted(arrival, side="left")
        close = pd.Timestamp(
            f"{t.tz_convert('Europe/Berlin').date()} {cfg.get('session_close', '23:59')}",
            tz="Europe/Berlin",
        ).tz_convert("UTC")
        if exit_arrival >= close:
            continue
        exit_idx = q.index.searchsorted(exit_arrival, side="left")
        if entry_idx >= len(q):
            continue
        entry = q.iloc[entry_idx]
        if not entry.valid or q.index[entry_idx] >= exit_arrival:
            continue
        if q.index[entry_idx] - arrival > pd.Timedelta(
            seconds=cfg["quote_age_seconds"]
        ):
            continue
        needed = "ask_size" if side == 1 else "bid_size"
        if entry[needed] < 1:
            continue
        entry_mid = entry.mid
        stop = cfg.get("position_stop_index_points", float("inf"))
        candidates = q.iloc[entry_idx:exit_idx]
        adverse = candidates[
            candidates.valid & (side * (candidates.mid - entry_mid) <= -stop)
        ]
        stop_triggered = not adverse.empty
        if stop_triggered:
            exit_arrival = adverse.index[0] + latency
            exit_idx = q.index.searchsorted(exit_arrival, side="left")
        # Once entered, an invalid exit triggers the next valid quote. Its
        # delay and adverse price are retained rather than deleting the trade.
        while exit_idx < len(q) and not q.iloc[exit_idx].valid:
            exit_idx += 1
        if exit_idx >= len(q):
            raise ValueError("Opened position has no valid exit; run cannot report P&L")
        exit_quote = q.iloc[exit_idx]
        exit_size = "bid_size" if side == 1 else "ask_size"
        if exit_quote[exit_size] < 1:
            raise ValueError("Exit displayed size is insufficient")
        entry_px = entry.ask if side == 1 else entry.bid
        exit_px = exit_quote.bid if side == 1 else exit_quote.ask
        gross = side * (exit_px - entry_px)
        trades.append(
            {
                "decision": t,
                "entry": q.index[entry_idx],
                "exit": q.index[exit_idx],
                "side": side,
                "forecast_ticks": forecast,
                "entry_price": entry_px,
                "exit_price": exit_px,
                "gross_eur": gross,
                "net_eur": gross - 2 * (fee + slippage),
                "stop_triggered": stop_triggered,
                "exit_delay_ms": (q.index[exit_idx] - exit_arrival).total_seconds()
                * 1000,
            }
        )
        realised += gross - 2 * (fee + slippage)
        free_after = q.index[exit_idx]
    return pd.DataFrame(trades)


def metrics(trades, days, capital=10000):
    daily = pd.Series(0.0, index=pd.Index(days, name="day"))
    if not trades.empty:
        grouped = trades.groupby(
            trades.decision.dt.tz_convert("Europe/Berlin").dt.strftime("%Y-%m-%d")
        ).net_eur.sum()
        daily.loc[grouped.index] = grouped
        equity = trades.net_eur.cumsum()
        drawdown = (equity.cummax().clip(lower=0) - equity).max()
        positive = trades.loc[trades.net_eur > 0, "net_eur"].sum()
        negative = -trades.loc[trades.net_eur < 0, "net_eur"].sum()
    else:
        drawdown = positive = negative = 0.0
    sd = daily.std(ddof=1)
    equity = capital + daily.cumsum()
    previous = equity.shift(1, fill_value=capital)
    returns = daily / previous
    turnover = (
        (trades.entry_price.abs().sum() + trades.exit_price.abs().sum()) / capital
        if len(trades)
        else 0
    )
    return {
        "trades": len(trades),
        "total_net_eur": daily.sum(),
        "mean_daily_eur": daily.mean(),
        "mean_trade_eur": trades.net_eur.mean() if len(trades) else None,
        "win_rate": (trades.net_eur > 0).mean() if len(trades) else None,
        "profit_factor": positive / negative if negative else None,
        "maximum_drawdown_eur": drawdown,
        "daily_pnl_sharpe": daily.mean() / sd * np.sqrt(252) if sd > 0 else None,
        "round_trip_contracts": len(trades),
        "reporting_capital_eur": capital,
        "annualised_return": float((equity.iloc[-1] / capital) ** (252 / len(days)) - 1)
        if equity.iloc[-1] > 0
        else None,
        "annualised_volatility": float(returns.std(ddof=1) * np.sqrt(252)),
        "annualised_turnover": float(turnover * 252 / len(days)),
        "maximum_drawdown_fraction": float(
            (
                (equity.cummax().clip(lower=capital) - equity)
                / equity.cummax().clip(lower=capital)
            ).max()
        ),
    }, daily
