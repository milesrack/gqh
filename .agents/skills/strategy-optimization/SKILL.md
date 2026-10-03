---
name: strategy-optimization
description: Run controlled trading-parameter searches and judge robustness rather than a single peak result.
---

# Strategy optimization

Predefine parameter ranges, objective, search budget, split boundaries, and seeds. Search only training/validation data; never use final holdout performance to choose parameters. Save every attempted configuration and result, including failures. Inspect sensitivity surfaces and neighboring settings for stability, then test cost, slippage, and regime sensitivity. Prefer a robust region and simple rule over the single best score. Report the size of the search and the resulting selection bias risk.
