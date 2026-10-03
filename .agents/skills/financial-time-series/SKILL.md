---
name: financial-time-series
description: Construct and inspect causal financial time-series features and statistical diagnostics.
---

# Financial time series

Use pandas and NumPy for indexed operations, and SciPy or statsmodels for diagnostics when required. Declare dependencies with `uv add` and run through `uv run --locked`. Make shifts, window endpoints, missing-value handling and train-only fitting explicit rather than relying on library defaults.

Build lagged features and rolling statistics from observations available by the decision time. Document window endpoints, warm-up handling, missing observations, and resampling rules. Consider autocorrelation, nonstationarity, structural breaks, and appropriate regression assumptions before interpreting estimates. Fit normalization and model parameters on training data only. Check that shifted labels, centered windows, revised values, or global statistics do not move future information into features. Use synthetic alignment tests for non-obvious transformations.
