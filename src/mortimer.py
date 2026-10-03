"""Implement MORTIMER allocation, exposure control, and return accounting."""

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path

import exchange_calendars as xc
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf

CORE = ("SPY", "TLT", "GLD")
MACRO = ("QQQ", "IWM", "HYG", "TLT", "GLD", "DBC")


@dataclass(frozen=True)
class Variant:
    trial_id: str
    family: str
    target: float = 0.10
    base: str = "equal"
    universe: tuple = CORE
    lookback: int = 63
    threshold: float = 0.05
    cap: float = 1.0
    control: str = "event"
    covariance_days: int = 126
    har_train_min: int = 504

    def parameters(self):
        return asdict(self)


def forecast(history, base, variant, high=None, low=None, state=None):
    portfolio = history @ base
    fast = portfolio.pow(2).ewm(span=20, adjust=False, min_periods=63).mean().iloc[-1]
    slow = portfolio.pow(2).ewm(span=63, adjust=False, min_periods=63).mean().iloc[-1]
    return float(np.sqrt(252 * max(fast, slow)))


def allocation(history, kind, cap):
    n = history.shape[1]
    if kind == "equal":
        return np.full(n, 1 / n)
    covariance = LedoitWolf().fit(history.to_numpy()).covariance_
    scale = max(np.trace(covariance), 1e-12)
    covariance = covariance / scale

    def objective(w):
        if kind == "minvar":
            return float(w @ covariance @ w)
        contribution = w * (covariance @ w)
        return float(np.sum((contribution - contribution.mean()) ** 2))

    fit = minimize(
        objective,
        np.full(n, 1 / n),
        method="SLSQP",
        bounds=[(0, cap)] * n,
        constraints={"type": "eq", "fun": lambda w: w.sum() - 1},
        options={"ftol": 1e-12, "maxiter": 1000},
    )
    if not fit.success or abs(fit.x.sum() - 1) > 1e-07 or (fit.x > cap + 1e-07).any():
        raise RuntimeError(f"Unsupported {kind} allocation: {fit.message}")
    return fit.x


def control(raw, current, variant, streak):
    if variant.control == "monthly":
        return (raw, 0)
    if variant.control == "event":
        return (raw if abs(raw - current) >= variant.threshold else current, 0)
    if raw - current <= -variant.threshold:
        return (raw, 0)
    streak = streak + 1 if raw - current >= 0.1 - 1e-12 else 0
    if streak >= 5:
        return (min(raw, current + 0.1), 0)
    return (current, streak)


def simulate(
    prices,
    rf,
    closes,
    variant,
    high=None,
    low=None,
    cost_bps=5.0,
    borrow_bps=50.0,
    overlay=True,
    static_exposure=None,
    start_position=504,
    guard_returns=None,
    forecast_engine=None,
    allocation_engine=None,
    control_engine=None,
):
    """Close orders execute one session after formation, after that day's return.

    Weights are post-cost NAV fractions. Costs are solved self-consistently
    against drifted dollar holdings, so the cash account and fees reconcile.
    """
    forecast_engine = forecast_engine or forecast
    allocation_engine = allocation_engine or allocation
    control_engine = control_engine or control
    prices = prices.loc[:, list(variant.universe)]
    if (
        prices.isna().any().any()
        or not prices.index.is_monotonic_increasing
        or prices.index.has_duplicates
    ):
        raise ValueError(
            "Invalid price history: missing, duplicate or unordered observations"
        )
    returns = prices.pct_change(fill_method=None)
    returns.iloc[0] = 0.0
    rf = rf.reindex(prices.index)
    if rf.isna().any() or (prices <= 0).any().any():
        raise ValueError("Missing available risk-free rate or invalid prices")
    n = prices.shape[1]
    holdings = np.zeros(n)
    cash = 1.0
    base = np.full(n, 1 / n)
    pending = None
    exposure = 0.0
    streak = 0
    har_state = {}
    rows, orders = [], []
    weight_rows, base_rows, trade_rows, forecast_weight_rows = [], [], [], []
    previous_month = None
    for t, date in enumerate(prices.index):
        old_nav = holdings.sum() + cash
        risky = float(holdings @ returns.iloc[t].to_numpy())
        cash_pnl = cash * rf.iloc[t] if cash >= 0 else 0.0
        financing = (
            -cash
            * (
                rf.iloc[t]
                + borrow_bps / 10000 / 365 * (date - prices.index[t - 1]).days
            )
            if cash < 0 and t
            else 0.0
        )
        holdings *= 1 + returns.iloc[t].to_numpy()
        cash += cash_pnl - financing
        before_fee = holdings.sum() + cash
        trade = np.zeros(n)
        fee = turnover = 0.0
        if pending is not None:
            desired, signal_date, signal_base, signal_exposure = pending
            # Solve fee = c * sum(abs(post_fee_nav*target - drifted_holdings)).
            after_fee = before_fee
            for _ in range(50):
                updated = (
                    before_fee
                    - cost_bps / 10000 * np.abs(after_fee * desired - holdings).sum()
                )
                if abs(updated - after_fee) < 1e-14:
                    break
                after_fee = updated
            after_fee = updated
            trade = after_fee * desired - holdings
            fee = before_fee - after_fee
            old_weights = np.r_[holdings / before_fee, cash / before_fee]
            holdings = after_fee * desired
            cash = after_fee - holdings.sum()
            new_weights = np.r_[desired, 1 - desired.sum()]
            turnover = 0.5 * np.abs(new_weights - old_weights).sum()
            exposure = signal_exposure
            base = signal_base
            effective = closes.iloc[t + 1] if t + 1 < len(prices) else pd.NaT
            assert closes.loc[signal_date] < closes.loc[date]
            orders.append(
                {
                    "signal_timestamp": closes.loc[signal_date],
                    "feature_timestamp": closes.loc[signal_date],
                    "execution_timestamp": closes.loc[date],
                    "effective_from_timestamp": closes.loc[date],
                    "first_return_end_timestamp": effective,
                    "exposure": exposure,
                }
            )
            pending = None
        nav = holdings.sum() + cash
        if nav <= 0:
            raise RuntimeError("Insolvent simulation")
        rows.append(
            {
                "net_return": nav / old_nav - 1,
                "gross_return": (risky + cash_pnl - financing) / old_nav,
                "risky_contribution": risky / old_nav,
                "cash_contribution": cash_pnl / old_nav,
                "financing_cost": financing / old_nav,
                "transaction_cost": fee / old_nav,
                "traded_notional": np.abs(trade).sum() / before_fee,
                "turnover": turnover,
                "equity": nav,
                "exposure": holdings.sum() / nav,
                "forecast": np.nan,
                "raw_exposure": np.nan,
            }
        )
        weight_rows.append(holdings / nav)
        base_rows.append(base.copy())
        forecast_weight_rows.append(base.copy())
        trade_rows.append(trade / before_fee)
        if t < start_position or t == len(prices) - 1:
            continue
        month = date.to_period("M")
        # Monthly signal on last actual NYSE session of month, not first session.
        month_end = prices.index[t + 1].to_period("M") != month
        first = previous_month is None
        base_change = first or month_end
        next_base = (
            allocation_engine(
                returns.iloc[max(1, t - variant.covariance_days + 1) : t + 1],
                variant.base,
                0.35 if n == 6 else 0.70,
            )
            if base_change
            else base
        )
        history = returns.iloc[1 : t + 1]
        # HAR is only registered for the constant equal-weight base.
        vol = forecast_engine(
            history,
            next_base,
            variant,
            None if high is None else high.loc[:date, prices.columns],
            None if low is None else low.loc[:date, prices.columns],
            har_state,
        )
        rows[-1]["forecast"] = vol
        forecast_weight_rows[-1] = next_base.copy()
        if not np.isfinite(vol) or vol <= 0:
            continue
        raw = min(variant.cap, variant.target / vol) if overlay else 1.0
        if static_exposure is not None:
            raw = static_exposure
        if variant.cap > 1 and overlay and static_exposure is None:
            trailing = guard_returns.loc[:date].tail(252)
            if len(trailing) < 252 or (1 + trailing).prod() <= 1:
                raw = min(raw, 1.0)
        rows[-1]["raw_exposure"] = raw
        if variant.control == "monthly" and not (base_change or first):
            continue
        actual = holdings.sum() / nav
        desired_exposure, streak = (
            control_engine(raw, actual, variant, streak)
            if overlay and static_exposure is None
            else (raw, 0)
        )
        if first:
            desired_exposure, streak = raw, 0
        # Hard leverage ceiling overrides slow restoration/ordinary hysteresis.
        if variant.cap > 1 and raw <= 1 and actual > 1:
            desired_exposure = min(desired_exposure, 1.0)
        if first or base_change or abs(desired_exposure - actual) > 1e-10:
            desired_exposure = min(variant.cap, max(0.0, desired_exposure))
            pending = (next_base * desired_exposure, date, next_base, desired_exposure)
        previous_month = month
    result = pd.DataFrame(rows, index=prices.index)
    result.attrs["orders"] = pd.DataFrame(orders)
    result.attrs["weights"] = pd.DataFrame(
        weight_rows, index=prices.index, columns=prices.columns
    )
    result.attrs["base_weights"] = pd.DataFrame(
        base_rows, index=prices.index, columns=prices.columns
    )
    result.attrs["forecast_weights"] = pd.DataFrame(
        forecast_weight_rows, index=prices.index, columns=prices.columns
    )
    result.attrs["trades"] = pd.DataFrame(
        trade_rows, index=prices.index, columns=prices.columns
    )
    return result


def metrics(result, rf):
    r = result.net_return
    if len(r) < 2:
        raise ValueError("Insufficient metric observations")
    excess = r - rf.reindex(r.index)
    wealth = pd.concat(
        [pd.Series([1.0]), (1 + r).cumprod().reset_index(drop=True)], ignore_index=True
    )
    dd = wealth / wealth.cummax() - 1
    cagr = float(wealth.iloc[-1] ** (252 / len(r)) - 1)
    vol = float(r.std(ddof=1) * np.sqrt(252))
    downside = float(np.sqrt(np.mean(np.minimum(excess, 0) ** 2)) * np.sqrt(252))
    var = float(r.quantile(0.05))
    tail = r[r <= var]
    durations, duration = [], 0
    for value in dd:
        duration = duration + 1 if value < -1e-12 else 0
        durations.append(duration)
    return {
        "cagr": cagr,
        "volatility": vol,
        "sharpe": excess.mean() * 252 / vol if vol else np.nan,
        "sortino": excess.mean() * 252 / downside if downside else np.nan,
        "max_drawdown": float(dd.min()),
        "calmar": cagr / abs(dd.min()) if dd.min() < 0 else np.nan,
        "var_95": var,
        "cvar_95": float(tail.mean()),
        "worst_1d": float(r.min()),
        "worst_5d": float((1 + r).rolling(5).apply(np.prod, raw=True).min() - 1),
        "worst_20d": float((1 + r).rolling(20).apply(np.prod, raw=True).min() - 1),
        "turnover": result.turnover.sum() * 252 / len(r),
        "implementation_cost": result.transaction_cost.sum() * 252 / len(r),
        "terminal_wealth": float(wealth.iloc[-1]),
        "recovery_sessions": max(durations),
        "unrecovered_at_end": bool(dd.iloc[-1] < -1e-12),
    }


def load_data(cache):
    cache = Path(cache)
    market = cache / "market-20080102-20241002.parquet"
    rates_path = cache / "rates-20080102-20241002.parquet"
    expected_hashes = [
        "e5f957a2b78b4a08cede2183cd59012f73beaffc38f0821d43bb458df08be222",
        "5eb2ada6d8d007969c111064ae6c5de089e8bd61c0156cb49cc98484cea2b5d9",
    ]
    for path, digest in zip([market, rates_path], expected_hashes):
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Data hash differs: {path.name}")
    panel = pd.read_parquet(market)
    rates = pd.read_parquet(rates_path)
    cal = xc.get_calendar("XNYS", start="2007-01-01", end="2026-12-31")
    planned = cal.sessions_in_range("2008-01-02", "2026-10-02").tz_localize(None)
    boundary = max(
        planned[int(len(planned) * 0.8)],
        planned[planned >= pd.Timestamp("2024-10-02")][0],
    )
    sessions = planned[planned < boundary]
    assert panel.index.max() < boundary
    prices = panel.xs("Adj Close", axis=1, level=1)[list(MACRO)].reindex(sessions)
    assert not prices.isna().any().any() and not prices.index.has_duplicates
    releases = rates.sort_values(["realtime_start", "date"]).copy()
    releases["available"] = [
        planned[planned > max(d, r)][0]
        for d, r in zip(releases.date, releases.realtime_start)
    ]
    releases = releases.groupby("available").tail(1)
    merged = pd.merge_asof(
        pd.DataFrame({"date": sessions}),
        releases.sort_values("available"),
        left_on="date",
        right_on="available",
    )
    assert merged.value.notna().all()
    rate = pd.Series(merged.value.to_numpy() / 100, index=sessions)
    elapsed = sessions.to_series().diff().dt.days.fillna(1)
    rf = (1 + rate.shift().fillna(rate.iloc[0])) ** (elapsed / 365) - 1
    closes = pd.Series([cal.session_close(d) for d in sessions], index=sessions)
    return panel, prices, rf, closes, str(boundary.date()), expected_hashes


E6_VARIANT = Variant("ERC", "ensemble", base="erc", universe=MACRO)
