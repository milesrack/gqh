---
name: experiment-runner
description: Make systematic trading experiments reproducible and comparable through configs and result metadata.
---

# Experiment runner

Use `uv sync --locked` to restore the Python 3.12 environment from `pyproject.toml` and `uv.lock`; run experiments with `uv run --locked`. Add required packages through `uv add`, and commit the project metadata and lockfile together. Record Python and direct package versions with each completed experiment.

Use a saved config for data version, split boundaries, hypothesis/baseline ID, parameters, execution assumptions, costs, slippage, and random seed where applicable. Record code version, run timestamp, status, and metric conventions. Write run artefacts to `results/<run_id>/` and record each trial in `research/experiments.csv`; retain failed runs and explicit missing-value reasons. Build comparable experiment tables using the same sample and metric definitions. Never substitute synthetic test fixtures for empirical evidence or alter the final test split after seeing results.
