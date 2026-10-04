# Contributing

## Set up

Use Python 3.12 and uv.

```sh
uv sync --locked
cp .env.example .env
```

Supply only the credentials required for the selected provider. Keep keys, account identifiers and connection details in ignored local files. See [shared assets](docs/shared-assets.md) for versioned data and source access.

## Start work

```sh
git fetch origin
git switch -c feature/experiment-<hypothesis> origin/main
```

Use one experiment branch per economic hypothesis. Use `docs/`, `chore/`, `bugfix/`, `hotfix/` or `refactor/` for other work. Preserve unrelated changes. Declare dependencies on unmerged branches.

Read [AGENTS.md](AGENTS.md) before research. Check the hypothesis, trial ledger and holdout-access record before changing a strategy.

## Register an experiment

Commit the specification before inspecting results or running a backtest. Record:

- Market, universe, mechanism, counterparty and reason for persistence.
- Null, testable prediction, falsification criteria and frozen baseline.
- Data provenance, availability timestamps and cleaning rules.
- Signal, execution lag, sizing, risk limits and restoration rules.
- Commissions, spread, slippage, financing and capacity assumptions.
- Parameter grid, search budget, selection rule and chronological splits.

Compute the official holdout from the actual history: the latest 20% or latest two years, whichever is shorter. Keep it closed during development. Freeze the specification before its single evaluation. Record prior access and reused validation; changing a label does not remove contamination. Keep actual commit dates and evaluation timestamps.

## Implement and evaluate

Keep notebook acquisition, transformations, signals, simulation and analysis visible in cells. Define small functions in the notebook. Use observed market data; stop with an actionable error when data or entitlement is unavailable. Obtain approval before paid acquisition, substantial paid compute or live trading.

```sh
uv run --env-file .env --locked jupyter lab
```

Lag close-derived signals. Separate signals, fills, positions, gross returns, turnover, costs and net returns. Check timing and accounting with hand-computable cases. Fit preprocessing and choose parameters on development data only.

Append every candidate, failure and rejection to `research/experiments.csv`. Retain dataset hashes, resolved configuration, code revision, runtime versions and seeds. Report net IS and OOS metrics separately; include doubled costs, uncertainty, regimes, factor exposure and quantified liquidity/capacity. Record unavailable evidence directly.

Keep licensed inputs and notebook outputs untracked. Store generated evidence in `results/<run_id>/`. Generate the paper's numbers from recorded code and configuration.

## Write documentation

Use concise commands, tables and short declarative sentences in developer documentation. Define mathematical notation and technical terms in notebooks and the quant note. Use precise academic exposition; support empirical claims with tables, figures and primary sources.

Keep the note body within five pages, including figures and tables. Use at least 11-point type and standard margins. Put references and optional supporting material after the body; keep essential claims in the body.

## Check and submit

```sh
uv run --locked ruff check tools
uv run --locked ruff format --check tools
uv run --locked python -m compileall -q tools src
```

Run the experiment's documented tests and reproduction command. Validate notebooks and compile the quant note. Compare generated metrics with every reported number. Inspect the staged diff for credentials, licensed data and generated notebook output.

Use Conventional Commits with imperative summaries, for example `feat: add guarded ERC leverage experiment`. Use [.github/pull_request_template.md](.github/pull_request_template.md). Record checks actually run and unresolved limitations.

Push and open pull requests when authorised. Strategy adoption, merges, history rewrites and remote branch deletion require explicit approval. Never merge a strategy because its backtest is profitable.

Before competition submission, verify the PDF, public repository link, reproducible command, variant count and all four team members. Confirm the official deadline from the organiser's current announcement.
