"""Book §§9.1,10.3–10.4; fixed risk-unit futures adaptations."""

import numpy as np

from .base import scores, window, zeros


def trend(view, params):
    history = window(view, "point_changes", max(int(params["lookback"]), 63))
    if history is None:
        return zeros(view.roots)
    return scores(np.sign(history.tail(int(params["lookback"])).sum()), view.roots)


def reversal(view, params):
    history = window(view, "point_changes", max(int(params["lookback"]), 63))
    if history is None:
        return zeros(view.roots)
    volatility = history.tail(63).std(ddof=1)
    if (volatility <= 0).any():
        return zeros(view.roots)
    # The frozen engine normalises BEFORE cross-sectional demeaning.
    change = history.tail(int(params["lookback"])).sum() / volatility
    return scores(-(change - change.mean()), view.roots)


def volume_reversal(view, params):
    base = reversal(view, {"lookback": 5})
    volume = window(view, "whole_root_volume", 10)
    if volume is None:
        return zeros(view.roots)
    previous = volume.iloc[:5].sum()
    if (volume < 0).any().any() or (previous <= 0).any():
        raise ValueError("Invalid reported volume or zero prior denominator")
    result = base * (volume.iloc[5:].sum() / previous >= float(params["cutoff"]))
    return (
        scores(result, view.roots)
        if np.count_nonzero(result) >= 2
        else zeros(view.roots)
    )


def carry(view, params):
    if view.curve is None:
        raise ValueError("Missing dated futures curve")
    result = zeros(view.roots)
    roots = ["CL", "GC"]
    curve = view.curve.loc[roots]
    near, far = curve.near_price, curve.far_price
    days = (curve.far_expiry - curve.near_expiry).dt.total_seconds() / 86400
    if (near <= 0).any() or (far <= 0).any() or (days <= 0).any():
        raise ValueError("Carry requires positive prices and ordered maturities")
    values = 365 * (near - far) / (near.abs() * days)
    result.loc[roots] = values - values.mean()
    return scores(result, view.roots)


def skewness(view, params):
    history = window(view, "notional_returns", int(params["lookback"]))
    if history is None:
        return zeros(view.roots)
    # Only purchased commodity roots; two-asset rank is concentrated.
    commodity = history[["CL", "GC"]]
    centred = commodity - commodity.mean()
    values = (centred**3).mean() / commodity.std(ddof=1) ** 3
    result = zeros(view.roots)
    if np.isfinite(values).all() and values.iloc[0] != values.iloc[1]:
        result.loc[values.idxmin()] = 1.0
        result.loc[values.idxmax()] = -1.0
    return result


def commodity_long(view, params):
    result = zeros(view.roots)
    result.loc[["CL", "GC"]] = 1.0
    return result
