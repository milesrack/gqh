---
name: experiment-runner
description: Make systematic trading experiments reproducible and comparable through configs and result metadata.
---

# Experiment runner

The research stack is declared in `requirements.txt` and installed in `.venv`. Record Python and direct package versions with each completed experiment; preserve a resolved package manifest when exact environment recreation is required.

Use a saved config for data version, split boundaries, hypothesis/baseline ID, parameters, execution assumptions, costs, slippage, and random seed where applicable. Record code version, run timestamp, status, and metric conventions. Write a standardized result record following `docs/experiment-contract.md`; retain failed runs and explicit missing-value reasons. Build comparable experiment tables using the same sample and metric definitions. Never substitute synthetic test fixtures for empirical evidence or alter the final test split after seeing results.
