# Ranked DAX pilot

30 fixed German large-cap stocks; 4,536 sleeve trials across rank families, lookbacks, quantiles, signs, rebalance frequencies and costs. Stock baskets and FDAX/FDXM/FDXS breadth and leadership sleeves are evaluated separately. This is an exploratory subset, not a historical DAX membership reconstruction.

```sh
export UV_CACHE_DIR=/private/tmp/gqh-uv-cache
uv sync --locked
uv run --locked python tools/dax_ranked_pilot.py prepare
uv run --locked python tools/dax_ranked_pilot.py run
```

Preparation downloads free Yahoo equity bars, retains provider failures and refuses an incomplete universe. Evaluation reads the existing local futures feature files and performs no downloads. Final DAX prices from 28 July 2025 stay locked. No Databento purchase.

Live progress prints each grid combination. Outputs: `results/dax-ranked-pilot-v1/all-trials.csv`, `training-selected.csv`, per-trial daily returns, manifest and summary. The trial ledger records all outcomes. Selection uses the first 80% of common pilot sessions; the remaining 20% is an inspected development segment, not fresh validation. Do not call a profitable grid cell alpha.

Data: `.agent-work/shared/data/dax-ranked-pilot/`. Existing futures features must be present at the two paths in the configuration. Teammates can retrieve the original DAX feature artefacts from the context repository; do not regenerate or download the locked holdout.

The model assumes €2 per futures side, one point extra slippage and 10 bp per equity side, with doubled-cost scenarios. Fees, borrow availability, margin and capacity require validation before promotion. Universe and adjusted prices are retrospective.

Older frozen plans require their original implementation/dependency checkout; adding yfinance changes the dependency hash.
