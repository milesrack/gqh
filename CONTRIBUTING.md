# Contributing

## Set up

Use Python 3.12 and uv.

```sh
uv sync --locked
cp .env.example .env
```

Add only the selected provider's credentials, keeping keys, account identifiers, and connection details in ignored local files. Follow [shared assets](docs/shared-assets.md) for versioned inputs and source access.

## Start work

```sh
git fetch origin
git switch -c feature/experiment-<hypothesis> origin/main
```

Keep each economic hypothesis on its own experiment branch, and use `docs/`, `chore/`, `bugfix/`, `hotfix/`, or `refactor/` for other work. Preserve unrelated changes and declare dependencies on unmerged branches.

Before changing a strategy, read [AGENTS.md](AGENTS.md) and check its hypothesis, trial ledger, and holdout-access record.

## Register an experiment

Commit the specification before inspecting results or running a backtest. Record:

- Market, universe, mechanism, counterparty, and reason for persistence.
- Null, testable prediction, falsification criteria, and frozen baseline.
- Data provenance, availability timestamps, and cleaning rules.
- Signal, execution lag, sizing, risk limits, and restoration rules.
- Commissions, spread, slippage, financing, and capacity assumptions.
- Parameter grid, search budget, selection rule, and chronological splits.

Reserve the shorter of the latest 20% of actual history or the latest two years, and keep this holdout closed until the specification is frozen. Evaluate it once, retaining the result and access record. Describe the data split as training, validation, and held-out out-of-sample (OOS) test; document any deviations from this protocol with commit dates and evaluation timestamps.

## Implement and evaluate

Keep acquisition, transformations, signals, accounting, and analysis directly inspectable in notebook cells, using small local functions where needed. Use observed market data and raise an actionable error when inputs or entitlement are unavailable; paid acquisition, substantial paid compute, and live trading require approval.

```sh
uv run --env-file .env --locked jupyter lab
```

Lag close-derived signals and separate signals, fills, positions, gross returns, turnover, costs, and net returns. Verify timing and accounting with hand-computable cases, fitting preprocessing and selecting parameters only on development data.

Append every candidate, failure, and rejection to `research/experiments.csv`, retaining dataset hashes, resolved configuration, code revision, runtime versions, and seeds. Report net in-sample (IS) and out-of-sample (OOS) evidence separately, including doubled costs, uncertainty, regimes, factor exposure, and quantified liquidity/capacity; identify unavailable evidence directly.

Keep licensed inputs and notebook outputs untracked, store generated evidence in `results/<run_id>/`, and derive the paper's numbers from the recorded code and configuration.

## Write documentation

Preserve the README title and main-branch sections, placing the strategy title under Hypothesis and essential commands under Reproduction. Fill each section with the minimum content needed to understand or run the experiment.

Use concise, task-oriented developer documentation and fluent academic exposition in notebooks and the quant note. Connect related statements, define notation and technical terms at first use, and support empirical claims with tables, figures, and primary sources. Use Oxford commas in enumerations and commas, colons, or line breaks as separators.

Keep essential claims within the five-page note body, including figures and tables, with at least 11-point type and standard margins. Use a clearly larger, centred title and place references and optional supporting material after the body. Keep only the note source, assets it includes, and `quant-note.pdf` in `report/`; build intermediates elsewhere.

## Check and submit

```sh
uv run --locked ruff check tools src tests
uv run --locked ruff format --check tools src tests
uv run --locked python -m compileall -q tools src
```

Run the documented tests and reproduction command, validate the notebook, and compile the quant note. Compare every reported number with generated metrics, then inspect the staged diff for credentials, licensed inputs, and notebook outputs.

Inspect every exported figure at its intended size and in the final document, checking labels, legends, units, ticks, fonts, contrast, centring, and placement. Resolve clipping or overlap before recording the completed visual checks.

Use Conventional Commits with imperative summaries, such as `feat: add guarded ERC leverage experiment`, and submit through [.github/pull_request_template.md](.github/pull_request_template.md), recording completed checks and unresolved limitations.

Push and open pull requests when authorised. Strategy adoption, merges, history rewrites, and remote branch deletion require explicit approval. Never merge a strategy because its backtest is profitable.

Before competition submission, verify the PDF, public repository link, reproducible command, variant count, and all four team members. Confirm the official deadline from the organiser's current announcement.
