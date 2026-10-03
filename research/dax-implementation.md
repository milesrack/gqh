# DAX experiment

Source and evaluation design: [hypothesis](hypothesis.md), [supplied specification](specs/dax-cross-contract-order-flow.md), [GQH requirements](gqh-requirements.md).

```sh
uv sync --locked
uv run --env-file .env --locked python data/download.py metadata
uv run --env-file .env --locked python data/download.py estimate --plan research/configs/dax-pilot-download.json
uv run --env-file .env --locked python data/download.py download --plan research/configs/dax-pilot-download.json --max-usd 180
uv run --locked python run_all.py --stage smoke --run-id dax-smoke-001
uv run --locked python run_all.py --stage development --run-id dax-development-001
uv run --locked python tools/dax_sensitivity.py --run-prefix dax-stability
```

Downloads are explicit and cost-capped; existing requests are not charged again. Data resides in the private context checkout. Development never reads the locked price events. Definitions, source hashes and rejected-row counts accompany results. Model targets and buffers are in index points pending historical tick reconciliation.

Smoke runs use three June sessions for training and two for validation. Full development uses the fixed pilot training/validation boundaries. Fees and EUR10,000 capital are labelled scenarios until broker terms are verified. The final holdout requires a separate approved freeze and evaluation entry point.

Each run saves configuration, source identity, Python/package versions, hypothesis/code commits, metrics, daily forecast losses and trades in results/. Every attempted run is logged in research/experiments.csv. Reusing a run ID fails; acquisition never occurs inside evaluation.

No strategy-specific merge without approval. If adopted, land the hypothesis before implementation and preserve every amendment and trial. Code-only submission excludes the private context and credentials.
