# GQH Systematic Trading

Research for the [Gator Quant Hacks Systematic Trading competition](https://www.gqhacks.com/tracks/systematic-trading), 2–4 October 2026.

## Hypothesis

## Data

## Methodology

## Results

## Risk and capacity

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
| `data/` | Ignored local caches; paid datasets remain in private context |
| `research/` | Economic hypothesis, evaluation plan and experiment ledger |
| `results/` | Generated run outputs, ignored |
| `report/` | LaTeX quant note and selected figures and tables |

## References

[Private research context](https://github.com/milesrack/gqh-systematic-track-context)
