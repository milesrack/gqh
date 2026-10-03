"""Book §§3.11–3.15 and4.4; fixed dated-contract daily-price adaptations."""

from itertools import pairwise

import numpy as np

from .base import scores, zeros


def moving_average(view, params):
    result = zeros(view.roots)
    lengths = tuple(int(x) for x in params["lengths"])
    if sorted(lengths) != list(lengths) or len(set(lengths)) != len(lengths):
        raise ValueError("MA lengths must be strictly increasing")
    for root in view.roots:
        close = view.bars(root).close
        needed = max(lengths) + (len(lengths) == 1)
        if len(close) < needed:
            continue
        if not np.isfinite(close.tail(needed)).all():
            raise ValueError("Invalid observed close")
        if len(lengths) == 1:
            result[root] = np.sign(close.iloc[-1] - close.iloc[-needed:-1].mean())
        else:
            means = [close.tail(n).mean() for n in lengths]
            held = np.sign(view.positions.get(root, 0))
            result[root] = (
                1
                if all(a > b for a, b in pairwise(means))
                else (
                    -1
                    if all(a < b for a, b in pairwise(means))
                    else (
                        held
                        if len(lengths) == 3
                        and (
                            (held > 0 and means[0] > means[1])
                            or (held < 0 and means[0] < means[1])
                        )
                        else 0
                    )
                )
            )
    return scores(result, view.roots)


def channel(view, params):
    result = zeros(view.roots)
    length = int(params["lookback"])
    for root in view.roots:
        close = view.bars(root).close.tail(length + 1)
        if len(close) < length + 1:
            continue
        if not np.isfinite(close).all():
            raise ValueError("Invalid channel close")
        prior, current = close.iloc[:-1], close.iloc[-1]
        if prior.max() == prior.min():
            continue
        result[root] = np.sign(view.positions.get(root, 0))
        if current <= prior.min():
            result[root] = 1.0
        elif current >= prior.max():
            result[root] = -1.0
    return scores(result, view.roots)


def pivot(view, params):
    result = zeros(view.roots)
    for root in view.roots:
        bars = view.bars(root).tail(2)
        if len(bars) < 2:
            continue
        previous, current = bars.iloc[0], bars.close.iloc[-1]
        centre = (previous.high + previous.low + previous.close) / 3
        resistance, support = 2 * centre - previous.low, 2 * centre - previous.high
        # Daily snapshot adaptation; no intraday threshold fills.
        if centre < current < resistance:
            result[root] = 1.0
        elif support < current < centre:
            result[root] = -1.0
    return scores(result, view.roots)


def ibs(view, params):
    values = zeros(view.roots)
    for root in view.roots:
        bars = view.bars(root)
        if bars.empty:
            return zeros(view.roots)
        last = bars.iloc[-1]
        spread = last.high - last.low
        if spread <= 0:
            return zeros(view.roots)
        values[root] = (last.close - last.low) / spread
        if not 0 <= values[root] <= 1:
            raise ValueError("Close outside observed high/low")
    result = zeros(view.roots)
    if values.max() != values.min():
        # One winner/loser is the finite six-root top/bottom-decile adaptation.
        result[values.idxmin()], result[values.idxmax()] = 1.0, -1.0
    return scores(result, view.roots)
