# Gator Quant Hacks: Systematic Trading Track

Research for the [Gator Quant Hacks Systematic Trading competition](https://www.gqhacks.com/tracks/systematic-trading), 2–4 October 2026.

## Hypothesis

Develop and test systematic trading hypotheses on separate experiment branches. No strategy has been adopted.

## Data

Restore versioned inputs from [shared assets](docs/shared-assets.md). Keep raw market data and credentials outside Git.

## Methodology

Preregister rules and search budgets. Lag signals, include costs and freeze the strategy before final evaluation.

## Results

Each experiment branch contains its trial ledger, notebook, reproduction command and quant note.

## Risk and capacity

Report exposure limits, adverse regimes, doubled costs and trade participation. Distinguish measured capacity from assumed impact.

## Reproduction

```sh
uv sync --locked
```

Copy `.env.example` to `.env` and supply the required provider credentials. Load them with `uv run --env-file .env --locked`.

## Repository

| Path | Contents |
| --- | --- |
| `notebooks/` | Research experiments on hypothesis branches |
| `src/` | Reusable code and the selected strategy |
| `tools/` | Acquisition and experiment commands |
| `data/` | Ignored local caches; shared datasets reside in Snowflake |
| `research/` | Economic hypothesis, evaluation plan and experiment ledger |
| `results/` | Generated run outputs, ignored |
| `report/` | LaTeX quant note and selected figures and tables |

## References

Shared data and context: [asset access](docs/shared-assets.md). Notebook compute uses SSH tunnels.

## Contribute

Follow [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md).

## Licence

Project code is available under the [MIT Licence](LICENSE). Market data and cited third-party materials retain their source terms.
