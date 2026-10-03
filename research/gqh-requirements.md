# GQH requirements

Source: [Systematic Trading track](https://www.gqhacks.com/tracks/systematic-trading), supplied page text read 3 October 2026. Participant Brief and organiser announcements take precedence. Interactive examples and rubric-slider scores are illustrative.

| Requirement | Evidence or remaining work |
|---|---|
| Hypothesis before backtests | c5ce548; subsequent amendments precede outcome inspection |
| Economic mechanism and counterparty | Shared underlying, differentiated execution constraints; liquidity provider on opposite side. Persistence against arbitrage remains unproven |
| Innovation | Incremental cross-flow comparison and three matched books; prior-art comparison pending |
| Data provenance | Explicit requests, definitions, receipt/exchange timestamps, SHA256 manifests |
| Missing data and bias | No future fills; stale/crossed quotes invalid; unknown trade sides missing; fixed calendar/roll. Index constituent adjustments are not applied to outright futures |
| Final holdout | Latest 20% of selected pilot; locked from 28 July 2025; development runner refuses access |
| Trial disclosure | experiments.csv, per-run metadata, all declared sensitivity cells including failures |
| Realistic costs | Actual bid/ask crossings and delay; broker/clearing fees still unverified, scenarios labelled |
| Doubled costs | Required stress comparison; fees/slippage/spread components must be explicit |
| Parameter stability | Primary 5/5, supplied 16-cell horizon grid plus adjacent 4/5/6 grid; no winner replaces primary |
| Benchmarks | Nested own-state/price-only baseline; beta, momentum and factor diagnostics pending |
| Risk | One FDXS contract, no overlap, invalid-book abstention. Margin, capital, position-loss and daily de-risking specification pending |
| Capacity | Displayed-size checks; participation, impact and dollar-capacity curve pending |
| Required metrics | Separate IS/OOS annual return, volatility, Sharpe, drawdown, turnover and equity curve; capital-dependent metrics pending declared capital |
| Regime evidence | Month, volatility, time-of-day and roll-cycle breakdowns; six-month pilot cannot establish multi-year resilience |
| Reproducibility | uv lock; run_all.py; data acquisition separate; source/config/code/runtime hashes |
| Quant note | Existing 11pt template, standard margins; <=5 main pages. Write results only after strategy selection and approved freeze |
| Submission | Public code repo required; current repo private. Change visibility/publish sanitised submission only with authorisation |
| Secrets/data | Credentials excluded. Licensed raw data stays in separately authorised private context, never public submission |
| Team/deadline | Every member listed/explains work. Devpost 4 October 10:00 ET; final code 11:00 ET |

No claim of full rubric compliance or trading alpha until pending evidence is completed. No strategy changes merge to main without Miles's approval. If adopted, the hypothesis is staged separately before implementation; historical preregistration commits and trial ledger remain intact.
