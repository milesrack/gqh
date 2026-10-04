# Gator Quant Hacks: Systematic Trading Track

Research for the [Gator Quant Hacks Systematic Trading competition](https://www.gqhacks.com/tracks/systematic-trading), 2–4 October 2026.

## Hypothesis

**MORTIMER: Multi-asset Optimisation with Risk Targeting, Integrated Macro Exposure, and Rebalancing** retains E6: a six-ETF equal-risk contribution portfolio with causal volatility scaling. The hypothesis is that persistent volatility permits lower portfolio risk after trading costs; see [the research specification](research/HYPOTHESIS.md).

## Data

Use QQQ, IWM, HYG, TLT, GLD, and DBC adjusted daily prices from Yahoo, with initial-release ALFRED DGS3MO observations for cash accrual. Restore the hash-bound inputs into ignored `data/`:

```sh
uv run --env-file .env --locked python tools/snowflake_store.py fetch --manifest research/archive/erc-control/erc-market-manifest.json --source data --path 'cache/erc/*'
uv run --env-file .env --locked python tools/snowflake_store.py fetch --manifest research/archive/erc-control/erc-market-manifest.json --source data --path 'cache/erc-final/*'
```

## Methodology

Estimate monthly constrained ERC weights from 126 sessions of Ledoit–Wolf covariance. Target 10% annual volatility using the larger of the 20- and 63-span EWMA forecasts, cap gross exposure at one, and rebalance exposure at a five percentage-point change. Execute close-derived orders at the following close and charge 5 bp on risky purchases and sales, with a 10 bp stress test.

## Results

| Net metric | Train | Reused validation | Recorded final |
| --- | ---: | ---: | ---: |
| Annualised return | 5.85% | 7.56% | 9.52% |
| Annualised volatility | 6.37% | 7.93% | 7.47% |
| Excess-return Sharpe | 0.859 | 0.660 | 0.714 |
| Maximum drawdown | −12.36% | −16.63% | −7.00% |
| Annual half-L1 turnover | 0.958 | 1.569 | 1.119 |

The final interval begins on 2 October 2024 and was previously accessed. These results reproduce the recorded E6 control; they do not constitute an untouched OOS test. Retain all prior trials in [the experiment ledger](research/experiments.csv) and [archived registry](research/archive/volatility-targeting-2/experiment_registry.csv).

## Risk and capacity

Use a 35% base weight limit per ETF, long-only positions, and gross exposure at most one. Volatility scaling reduces exposure when forecast risk rises; it does not impose a drawdown stop. Evaluate participation against lagged dollar volume and apply square-root impact scenarios before selecting capital.

## Reproduction

```sh
uv sync --locked
uv run --locked python tools/reproduce_e6.py
uv run --locked jupyter lab
```

Run [the research notebook](notebooks/e6_research.ipynb) after restoring the inputs. The reproduction command writes metrics, returns, exposures, and provenance to ignored `results/e6-submission/` without acquiring data or selecting parameters. Configure Snowflake credentials in ignored `.env` using `.env.example`; see [shared assets](docs/shared-assets.md).

## Repository

| Path | Contents |
| --- | --- |
| `notebooks/` | Self-contained E6 research notebook |
| `src/` | Frozen E6 strategy implementation |
| `tools/` | Acquisition, reproduction, and reporting commands |
| `data/` | Ignored observed inputs, reference material, and caches |
| `research/` | Specifications, provenance, frozen source, and trial ledger |
| `results/` | Ignored generated evidence and build outputs |
| `report/` | Quant note source, included assets, and `quant-note.pdf` |

## References

Read the [quant note](report/quant-note.pdf) for methodology, evidence, and source references. Volatility targeting and ERC are established methods; this experiment combines them under a fixed universe, bounded exposure, and explicit execution accounting.

## Contribute

Follow [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md). Keep additional worktrees outside this repository, inputs in ignored `data/`, generated evidence in `results/`, and credentials in ignored `.local/credentials/` or `.env`.

## Licence

Project code is available under the [MIT Licence](LICENSE). Market data and cited third-party materials retain their source terms.
