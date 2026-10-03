# SR3 curve revisions

## Hypothesis

Upward revisions to recent macroeconomic growth imply additional delayed policy tightening. Revision pressure predicts a rise in the twelve-month forward rate relative to the six-month forward rate over ten sessions. The null is zero incremental predictive slope and non-positive net trading P&L.

## Design

Use existing ALFRED and SR3 data only. Retain the vintage construction, next-session settlement entry and frozen quarterly contracts from the original experiment. Fix decay at 30 days, revision clipping at three standard deviations, tenors at 180 and 360 days and horizon at ten sessions. Pair only events with matching entry and exit dates and distinct contracts.

Estimate one revision-pressure coefficient plus an intercept. Standardise the predictor using fitting data only. Ridge penalties: 0, 1, 10 and 100; the intercept is unpenalised. Fit May 2018–December 2020, select the penalty by mean squared error in 2021–2022 against the fitting-sample mean forecast, then refit through December 2022. Selection never uses 2023–2024.

Positive curve forecasts imply short the far contract and long the near contract; negative forecasts reverse both legs. Thresholds are 0.5, 1 and 1.5 fitting-sample forecast standard deviations. Evaluate all penalties and thresholds without selecting another validation winner. One pair at a time; hold ten sessions. Costs are one basis point per leg round trip, with half paid at entry and half at exit. Capital is $100,000. Report daily marked P&L, forecast error against the constant baseline, trade count, Sharpe and drawdown.

## Interpretation

2023–2024 is reused validation, not a fresh test. January 2025 onwards remains excluded. This tests a curve mechanism and regularisation; it cannot rescue the original claim by selecting a favourable sign or validation winner. Settlement execution and simultaneous leg fills remain modelled.
