"""Book strategy plugins, independent of acquisition and execution."""

from .base import CausalMarketView, StrategySpec, StrategyView
from .registry import STRATEGIES, get_strategy

__all__ = [
    "STRATEGIES",
    "CausalMarketView",
    "StrategySpec",
    "StrategyView",
    "get_strategy",
]
