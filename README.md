# Gator Quant Hacks: Systematic Trading Track

Research for the [Gator Quant Hacks Systematic Trading competition](https://www.gqhacks.com/tracks/systematic-trading), 2–4 October 2026.

## Hypothesis

Develop each trading hypothesis on a separate experiment branch; adoption requires an approved research specification and implementation.

## Data

Restore versioned inputs through [shared assets](docs/shared-assets.md), keeping raw market data and credentials outside Git.

## Methodology

Preregister the rules and search budget, evaluate lagged signals after costs, and freeze the strategy before final evaluation.

## Results

Use each experiment branch's trial ledger, executed notebook, reproduction command, and quant note to review its evidence.

## Risk and capacity

Report exposure limits, adverse regimes, doubled costs, and trade participation, separating measured capacity from assumed impact.

## Reproduction

```sh
uv sync --locked
```

Copy `.env.example` to `.env`, add the selected provider's credentials, and load them with `uv run --env-file .env --locked`.

## Repository

| Path | Contents |
| --- | --- |
| `notebooks/` | Research experiments on hypothesis branches |
| `src/` | Reusable code and the selected strategy |
| `tools/` | Acquisition and experiment commands |
| `data/` | Ignored local caches; shared datasets reside in Snowflake |
| `research/` | Economic hypothesis, evaluation plan, and experiment ledger |
| `results/` | Generated run outputs, ignored |
| `report/` | Quant note source, required figure and table assets, and `quant-note.pdf` |

## References

Follow [asset access](docs/shared-assets.md) for shared data, source documents, and notebook compute.

## Contribute

Follow [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md).

## Licence

Project code is available under the [MIT Licence](LICENSE). Market data and cited third-party materials retain their source terms.
