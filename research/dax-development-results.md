# DAX development results

Primary run: `dax-development-stability-L5-H5`. Training: 72 populated sessions, 10 March–20 June 2025. Validation: 25 sessions, 23 June–25 July. Final holdout: locked, 28 July–29 August.

| Measure | Result |
| --- | ---: |
| Forecast observations | 141,153 |
| Baseline MSE | 5.748098 |
| Cross-flow MSE | 5.747478 |
| Relative MSE reduction | 0.0108% |
| Daily MSE improvement, 95% five-session-block interval | −0.000736 to 0.002439 |
| Training joint flow test, HAC p-value | 0.001976 |
| Model condition number | 26.09 |
| Trades in each cost/buffer scenario | 0 |
| Net P&L | EUR0 |
| Sharpe | Undefined |

The predictive interval includes zero. Training significance does not establish validation benefit. Forecasts fail to exceed the observed spread plus the minimum illustrative round-trip fee. Median spread is two index points; the 99th percentile absolute forecast is 0.662 points. Zero-delay and doubled-cost scenarios also produce no trades.

## Parameter stability

All nine neighbouring 4/5/6-second cells have positive incremental forecast R², ranging from 0.000066 to 0.000129. Every daily block-bootstrap interval includes zero. The effect is locally consistent in sign but too small to establish an edge. All 24 declared cells completed; no cell replaces the primary.

## Secondary diagnostics

The preregistered standardised disagreement diagnostic reduces validation MSE by 0.0337%; its unadjusted daily loss-improvement interval is 0.001004–0.003476. This is a small secondary predictive association, not demonstrated net alpha; its interval is not adjusted for the complete trial family.

Six directed tests use Holm-adjusted training p-values. FDXM→FDAX is significant in training but worsens validation MSE. FDXM→FDXS is significant in training but improves validation MSE by only 0.000155%. The matched-sample day-shift comparison does not establish useful contemporaneous cross-flow information.

Descriptive regime splits show negative incremental forecast R² in June, afternoon hours and the highest lagged-move group. Positive aggregate improvement is not uniform across these conditions; no regime is used to retune entries.

The primary fails the executable-alpha gate. Capacity, capital adequacy and broker execution remain unestablished. Keep the holdout locked; do not select a different horizon from the sensitivity grid to rescue this hypothesis.

[Implementation audit](implementation-audit.md) identifies invalidated earlier results. The [trial ledger](experiments.csv) retains all attempts. Full evidence resides in the private context data branch.
