---
name: quant-visualization
description: Create transparent diagnostic charts for trading experiments and validation reports.
---

# Quant visualization

Matplotlib is available in `.venv` for reproducible diagnostic figures; pandas and NumPy may prepare the plotted series. Preserve the underlying values and axis conventions alongside each figure.

Plot equity curves with split boundaries and a baseline, drawdowns, rolling volatility, and rolling Sharpe when sample length supports it. Show turnover, exposure, parameter sensitivity, and regime performance where relevant. Label units, frequency, costs, dates, and sample size; distinguish gross from net results. Avoid truncated axes or smoothing that hides losses. Annotate unavailable or undefined metrics rather than fabricating curves. Save figure inputs and the config that produced them.
