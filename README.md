# GQH Systematic Trading

Research for the [Gator Quant Hacks Systematic Trading competition](https://www.gqhacks.com/tracks/systematic-trading), 2–4 October 2026.

## Hypothesis

[DAX cross-contract order flow](research/hypothesis.md): test whether FDAX and FDXM flow improves FDXS forecasts and executable net returns.

## Data

Databento XEUR.EOBI, matched FDAX/FDXM/FDXS outrights, 10 March–29 August 2025. Raw data and manifests reside in the private context repository.

## Methodology

Nested OLS, chronological training/validation/locked holdout, dependence-aware uncertainty, observed-book execution and declared parameter sensitivity. [Specification and commands](research/dax-implementation.md).

## Results

Development: 0.0108% relative forecast-error reduction, interval includes zero; no executable trades. [Results](research/dax-development-results.md). Final holdout remains locked.

## Risk and capacity

## Reproduction

```sh
uv sync --locked
uv run --locked python run_all.py --stage development --run-id dax-development-reproduction
```

Copy `.env.example` to `.env` and supply the required provider credentials. Load them with `uv run --env-file .env --locked`.

## Repository

| Path | Contents |
| --- | --- |
| `src/` | Signals, portfolio construction, backtesting and analysis |
| `data/` | Acquisition code; datasets and manifests in the context repository |
| `research/` | Economic hypothesis, evaluation plan and experiment ledger |
| `results/` | Generated run outputs, ignored |
| `report/` | LaTeX quant note and selected figures and tables |

## References

[Private research context](https://github.com/milesrack/gqh-systematic-track-context)
