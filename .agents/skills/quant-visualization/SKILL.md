---
name: quant-visualization
description: Create transparent diagnostic charts for trading experiments and validation reports.
---

# Quant visualization

Use Matplotlib for diagnostic figures and pandas or NumPy to prepare series when required. Declare dependencies with `uv add` and run through `uv run --locked`. Preserve the underlying values and axis conventions alongside each figure.

Plot equity curves with split boundaries and a baseline, drawdowns, rolling volatility, and rolling Sharpe when sample length supports it. Show turnover, exposure, parameter sensitivity, and regime performance where relevant. Label units, frequency, costs, dates, and sample size; distinguish gross from net results. Avoid truncated axes or smoothing that hides losses. Annotate unavailable or undefined metrics rather than fabricating curves. Save figure inputs and the config that produced them.
