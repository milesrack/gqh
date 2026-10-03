"""Pure forecasts over an engine-supplied, information-cut view.

No view builder may expose bars after asof. Point changes must compare the same
instrument on both dates. OHLC histories must use one fixed dated instrument per
root, never concatenated unadjusted contracts. Execution and risk stay in engine.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from itertools import pairwise
from numbers import Integral, Real

import numpy as np
import pandas as pd

ROOTS = ("ES", "NQ", "ZN", "CL", "GC", "6E")


@dataclass(frozen=True)
class CausalMarketView:
    decision_at: pd.Timestamp
    information_asof: pd.Timestamp
    roots: tuple[str, ...]
    point_changes: pd.DataFrame
    dollar_changes: pd.DataFrame
    whole_root_volume: pd.DataFrame | None = None
    ohlc: Mapping[str, pd.DataFrame] = field(default_factory=dict)
    curve: pd.DataFrame | None = None
    notional_returns: pd.DataFrame | None = None
    equity: float = 0.0
    positions: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))

    @property
    def asof(self):
        return self.information_asof

    def history(self, name: str) -> pd.DataFrame:
        data = getattr(self, name)
        if data is None:
            raise ValueError(f"Missing required input: {name}")
        if not isinstance(data.index, pd.DatetimeIndex):
            raise TypeError(f"{name} requires a dated index")
        if not data.index.is_monotonic_increasing or data.index.has_duplicates:
            raise ValueError(f"{name} must have unique increasing dates")
        if len(data) and data.index[-1] > self.asof:
            raise ValueError(f"{name} exposes information after asof")
        if not set(self.roots).issubset(data.columns):
            raise ValueError(f"{name} must contain configured roots")
        return data.loc[:, list(self.roots)]

    def bars(self, root: str) -> pd.DataFrame:
        if root not in self.ohlc:
            raise ValueError(f"Missing fixed-contract OHLC: {root}")
        data = self.ohlc[root]
        if (
            not data.index.is_monotonic_increasing
            or data.index.has_duplicates
            or (len(data) and data.index[-1] > self.asof)
        ):
            raise ValueError("OHLC violates information order/cutoff")
        if "instrument_id" in data and data.instrument_id.nunique() > 1:
            raise ValueError("OHLC mixes dated instrument identities")
        return data


StrategyView = CausalMarketView


def zeros(roots=ROOTS) -> pd.Series:
    return pd.Series(0.0, index=roots)


def scores(values, roots=ROOTS) -> pd.Series:
    result = pd.Series(values, index=roots, dtype=float)
    if not np.isfinite(result).all():
        raise ValueError("Non-finite strategy score")
    return result


def window(view, name, length):
    data = view.history(name).tail(length)
    if len(data) < length:
        return None
    if not np.isfinite(data.to_numpy()).all():
        raise ValueError(f"Invalid observed {name}")
    return data


@dataclass(frozen=True)
class StrategySpec:
    id: str
    book_sections: tuple[str, ...]
    printed_pages: tuple[int, ...]
    mechanism: str
    required_inputs: tuple[str, ...]
    default_grid: tuple[Mapping[str, object], ...]
    signal: Callable[[StrategyView, Mapping[str, object]], pd.Series]
    adaptation: str
    min_roots: int = 1
    supported_roots: tuple[str, ...] = ROOTS
    null: str = ""
    falsifier: str = ""

    @property
    def grid(self):
        return self.default_grid

    @property
    def sections(self):
        return self.book_sections

    def validate_params(self, params):
        keys = set(self.default_grid[0])
        if set(params) != keys:
            raise ValueError(f"{self.id} expects parameters {sorted(keys)}")
        for key, value in params.items():
            if key in {"lookback", "ma", "neighbours", "skip"}:
                minimum = 0 if key == "skip" else 1
                if (
                    isinstance(value, bool)
                    or not isinstance(value, Integral)
                    or value < minimum
                ):
                    raise ValueError(f"{key} must be an integer >= {minimum}")
                if key == "neighbours" and value > 126:
                    raise ValueError("Neighbours cannot exceed126 training labels")
                if (
                    key == "lookback"
                    and self.id in {"low_volatility", "skewness"}
                    and value < 3
                ):
                    raise ValueError("Moment estimation needs at least3 bars")
            elif key in {"cutoff", "smoothing"}:
                if (
                    isinstance(value, bool)
                    or not isinstance(value, Real)
                    or not np.isfinite(value)
                    or value <= 0
                ):
                    raise ValueError(f"{key} must be finite and positive")
            elif key == "lengths":
                expected = {"single_ma": 1, "double_ma": 2, "triple_ma": 3}[self.id]
                if len(value) != expected or any(
                    isinstance(x, bool) or not isinstance(x, Integral) or x <= 0
                    for x in value
                ):
                    raise ValueError(
                        "MA lengths must be positive integers of the declared count"
                    )
                if any(a >= b for a, b in pairwise(value)):
                    raise ValueError("MA lengths must be strictly increasing")
            elif key == "pair":
                if (
                    len(value) != 2
                    or len(set(value)) != 2
                    or not set(value).issubset(self.supported_roots)
                ):
                    raise ValueError("Pair must contain two distinct supported roots")
            elif key == "filter":
                expected = {
                    "rotation": "none",
                    "rotation_ma": "own_ma",
                    "dual_rotation": "broad_ma",
                }[self.id]
                if value != expected:
                    raise ValueError("Filter must match registered strategy")

    def validate_universe(self, roots):
        if len(set(roots)) != len(roots) or len(roots) < self.min_roots:
            raise ValueError(f"{self.id} requires >= {self.min_roots} distinct roots")
        if not set(roots).issubset(self.supported_roots):
            raise ValueError(f"{self.id} contains unsupported roots")
        if self.id == "dual_rotation" and not {"ES", "GC"}.issubset(roots):
            raise ValueError("Dual rotation requires ES broad proxy and GC fallback")
