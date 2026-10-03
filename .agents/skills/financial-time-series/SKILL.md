---
name: financial-time-series
description: Construct and inspect causal financial time-series features and statistical diagnostics.
---

# Financial time series

Pandas and NumPy are available in `.venv` for indexed lag and rolling operations; SciPy and statsmodels are available for statistical diagnostics. Make shifts, window endpoints, missing-value handling, and train-only fitting explicit rather than relying on library defaults.

Build lagged features and rolling statistics from observations available by the decision time. Document window endpoints, warm-up handling, missing observations, and resampling rules. Consider autocorrelation, nonstationarity, structural breaks, and appropriate regression assumptions before interpreting estimates. Fit normalization and model parameters on training data only. Check that shifted labels, centered windows, revised values, or global statistics do not move future information into features. Use synthetic alignment tests for non-obvious transformations.
