# Triple-MA experiment handoff

Branch: `feature/dax-edge-hunt`. PR: https://github.com/milesrack/gqh-systematic-track/pull/7. Do not merge strategy work without approval.

Frozen improvement implementation and plan: `7ac4dd5d8d84c89063f5e0d9ad41900d553f1fb9`. Economic specification: `research/hypotheses/triple-ma-improvement.md`.

```sh
UV_CACHE_DIR=/private/tmp/gqh-uv-cache uv run --locked python tools/improve_triple_ma.py --freeze-commit 7ac4dd5d8d84c89063f5e0d9ad41900d553f1fb9
tail -f results/triple-ma-improvement-v1/run.log
```

The runner executes 33 training jobs, then baseline, three sizing diagnostics and the training-selected entry filter on the inspected development period with cost/delay stress and matched controls. Outputs: `results/triple-ma-improvement-v1/improvement-summary.json`. Resume only after confirming no active run; completed job hashes are checked. The final holdout remains locked. No data purchase is required.

Existing results: `research/futures-validation-results.md` and `research/futures-standalone-exploration-results.md`. Canonical datasets are published on context branch `feature/dax-pilot-data`, PR https://github.com/milesrack/gqh-systematic-track-context/pull/7. Routine outputs remain ignored; record completed experiment outcomes and commit ledger rows before handoff.
