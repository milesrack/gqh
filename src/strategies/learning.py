"""Causal price/volume KNN and endpoint-only HP adaptations of §§3.17,8.1."""

import numpy as np
from scipy.sparse import diags, eye
from scipy.sparse.linalg import spsolve

from .base import scores, zeros


def knn(view, params):
    result = zeros(view.roots)
    neighbours = int(params["neighbours"])
    horizon, training = 5, 126
    for root in view.roots:
        bars = view.bars(root).tail(training + horizon + 20)
        if len(bars) < training + horizon + 20:
            continue
        close, volume = bars.close, bars.volume
        if (close <= 0).any() or (volume < 0).any():
            raise ValueError("KNN ratio labels require positive fixed-contract closes")
        features = np.column_stack(
            [
                close.rolling(5).mean(),
                close.rolling(20).mean(),
                volume.rolling(5).mean(),
            ]
        )
        target = close.shift(-horizon).to_numpy() / close.to_numpy() - 1
        # Each training label matures at or BEFORE information_asof. Last query
        # has no observed future label, and never participates in fitted scaling.
        candidates = np.arange(19, len(bars) - horizon)
        candidates = candidates[-training:]
        x, y = features[candidates], target[candidates]
        query = features[-1]
        if (
            not np.isfinite(x).all()
            or not np.isfinite(y).all()
            or not np.isfinite(query).all()
        ):
            raise ValueError("Invalid observed KNN features/labels")
        lower, upper = x.min(axis=0), x.max(axis=0)
        span = np.where(upper > lower, upper - lower, 1.0)
        scaled, point = (x - lower) / span, (query - lower) / span
        distance = ((scaled - point) ** 2).sum(axis=1)
        selected = np.argsort(distance, kind="stable")[:neighbours]
        result[root] = np.sign(y[selected].mean())
    return scores(result, view.roots)


def hp_ma(view, params):
    if "6E" not in view.roots:
        raise ValueError("FX HP adaptation requires purchased6E root")
    result = zeros(view.roots)
    close = view.bars("6E").close.tail(126)
    if len(close) < 126:
        return result
    if not np.isfinite(close).all():
        raise ValueError("Invalid HP observations")
    n = len(close)
    second = diags(
        [np.ones(n - 2), -2 * np.ones(n - 2), np.ones(n - 2)],
        [0, 1, 2],
        shape=(n - 2, n),
    )
    smooth = spsolve(
        (eye(n) + float(params["smoothing"]) * (second.T @ second)).tocsc(),
        close.to_numpy(),
    )
    # Refit ONLY the supplied past window at each decision; never full-sample HP.
    result["6E"] = np.sign(smooth[-10:].mean() - smooth[-30:].mean())
    return scores(result, view.roots)
