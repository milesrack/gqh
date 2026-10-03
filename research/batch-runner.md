# Futures batch runner

Signals: `src/strategies/`. Execution: `src/futures_engine.py`. Grid and queue: `src/batch_research.py`. Coverage: `research/book-strategies.csv`.

## Run

```sh
uv run --locked python tools/batch_research.py run \
  --plan research/configs/futures-grid-plan.json \
  --freeze-commit PLAN_COMMIT --workers 4
```

The terminal prints completed jobs, net P&L, Sharpe, failures and estimated remaining time. Run the same command to resume. Completed outputs are checked and retained; failed jobs require `--retry-failed`. Each attempt is recorded in `research/experiments.csv`.

```sh
uv run --locked python tools/batch_research.py status --batch book151-futures-v1
```

Outputs: `results/book151-futures-v1/`. Each job saves metrics, daily returns, trades, positions and hashes. `training-grid.csv` retains the full grid; sensitivity figures preserve missing cells. The default batch searches training only. Validation and final holdout are separate.

## Configure

Edit `research/configs/futures-grid.json`; use a new `batch_id`. Select plugins, universes, frequencies and parameter grids:

```json
{
  "id": "trend",
  "grid": {"lookback": {"start": 20, "stop": 241, "step": 20}},
  "universes": [["ES"], ["NQ"], ["ES", "NQ", "ZN", "CL", "GC", "6E"]],
  "frequencies": ["weekly", "monthly"]
}
```

Ranges exclude `stop`; lists specify exact values. Omit `grid` to use the plugin's declared defaults. Compound parameters use lists, such as `"lengths": [[5, 20], [10, 40]]`.

```sh
uv run --locked python tools/batch_research.py plan \
  --config research/configs/futures-grid.json \
  --output research/configs/futures-grid-plan.json
git add research/configs/futures-grid.json research/configs/futures-grid-plan.json
git commit -m "research: freeze futures parameter grid"
```

Run with that commit SHA. The runner checks committed plan bytes, implementation, dependencies and dataset hashes before evaluation. It performs no downloads. `GQH_CONTEXT_DIR` selects the private data checkout.

## Add a strategy

Implement `signal(view, params)` returning a score for each configured root; register its `StrategySpec`. Include source sections, mechanism, null, inputs and parameter validation. The view contains only information available before execution. The engine owns sizing, fills, rolls, costs and risk.
