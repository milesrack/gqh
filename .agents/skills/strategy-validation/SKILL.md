---
name: strategy-validation
description: Independently validate a trading result for out-of-sample robustness, costs, and leakage.
---

# Strategy validation

Use SciPy, statsmodels or scikit-learn for checks and train-only preprocessing when required. Declare dependencies with `uv add` and run through `uv run --locked`. Respect chronological splits when using estimator or cross-validation helpers.

Keep train, validation, and final test boundaries explicit and chronological. Fit preprocessing and tune parameters only on permitted earlier data; never optimize using the final holdout. Use walk-forward evaluation when the sample permits. Probe parameter neighborhoods, cost and slippage sensitivity, regime performance, sample size, and uncertainty. Audit feature availability, labels, universe membership, revisions, and split boundaries for leakage. Compare with the prespecified baseline and report failures as plainly as successes. The Validator and Critic should reach conclusions independently of strategy development.
