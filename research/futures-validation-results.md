# Futures validation

Period: 19 January 2022–26 May 2024. All 39 training-selected candidates passed the doubled-cost training gate. All validation and stress jobs completed. Ten candidates had positive base net P&L; nine remained profitable with doubled costs and an additional information-bar delay. No candidate passed the preregistered matched-control alpha test adjusted for 166 trials. Final holdout access: none.

The six-market 5/20/60 triple moving average produced validation Sharpe 0.870, CAGR 2.48% and maximum drawdown 3.43%. Net P&L on $1 million initial capital was $59,096.88, falling to $54,865.00 with doubled costs and $26,060.00 with the additional delay. HAC20 annual alpha against the matched long-only control was 1.92%; its adjusted interval was −3.26% to 7.09%. This is positive realised performance without established alpha.

Reproduce with `uv run --locked python tools/validate_futures.py` at the frozen validation commit f5b16dc. Outputs: `results/book151-futures-validation-v1/summary.json`. The 2,000-draw bootstrap cannot resolve the grid-adjusted extreme tails; the alpha gate uses adjusted HAC intervals.
