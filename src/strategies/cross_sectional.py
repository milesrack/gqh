"""Book price-only cross-sectional rules, labelled as futures adaptations."""

import numpy as np

from .base import scores, window, zeros


def rank_sides(values, roots):
    result = zeros(roots)
    if values.max() != values.min():
        result[values.idxmax()], result[values.idxmin()] = 1.0, -1.0
    return result


def momentum(view, params):
    n, skip = int(params["lookback"]), int(params.get("skip", 0))
    data = window(view, "notional_returns", n + skip)
    if data is None:
        return zeros(view.roots)
    formation = data.iloc[:n]
    return scores(rank_sides(formation.sum(), view.roots), view.roots)


def low_volatility(view, params):
    data = window(view, "notional_returns", int(params["lookback"]))
    return (
        zeros(view.roots)
        if data is None
        else scores(-rank_sides(data.std(ddof=1), view.roots), view.roots)
    )


def pair_reversal(view, params):
    data = window(view, "notional_returns", max(63, int(params["lookback"])))
    if data is None:
        return zeros(view.roots)
    roots = list(params["pair"])
    if not set(roots).issubset(view.roots):
        raise ValueError("Configured universe omits fixed pair")
    correlation = data[roots].tail(63).corr().iloc[0, 1]
    if not np.isfinite(correlation) or correlation < 0.5:
        return zeros(view.roots)
    result = zeros(view.roots)
    pair = data[roots].tail(int(params["lookback"])).sum()
    result.loc[roots] = -(pair - pair.mean())
    return scores(result, view.roots)


def rotation(view, params):
    n = int(params["lookback"])
    data = window(view, "notional_returns", n)
    if data is None:
        return zeros(view.roots)
    winner = data.sum().idxmax()
    result = zeros(view.roots)
    mode = params.get("filter", "none")
    if mode == "none":
        result[winner] = 1.0
    elif mode == "own_ma":
        from .technical import moving_average

        passing = moving_average(view, {"lengths": (int(params["ma"]),)})
        result[winner] = float(passing[winner] > 0)
    elif mode == "broad_ma":
        from .technical import moving_average

        passing = moving_average(view, {"lengths": (int(params["ma"]),)})
        # ES is a declared broad-equity proxy; GC fallback is not uncorrelated proof.
        result[winner if passing["ES"] > 0 else "GC"] = 1.0
    else:
        raise ValueError("Unknown rotation filter")
    return scores(result, view.roots)
