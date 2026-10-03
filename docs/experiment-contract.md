# Experiment contract

Every completed strategy experiment should retain a reproducible config and a result record. Use `null` with an explanation when a field is inapplicable; do not silently omit failed or unrun evaluations.

Record: hypothesis and baseline; data source/version and sample period; timestamp timezone and availability rule; universe; train, validation, and untouched test boundaries; feature, signal, portfolio, and execution rules; strategy parameters; random seed when applicable; cost and slippage assumptions; annualization factor and risk-free/target-return convention; code version; Python and direct dependency versions (plus a resolved package manifest if exact environment recreation is required); and run time.

Report, when applicable: cumulative and annualized return, annualized volatility, Sharpe, Sortino, maximum drawdown, turnover, number of trades, hit rate, average exposure, and performance by split/regime. Distinguish interval hit rate from closed-trade hit rate. Include sample count and uncertainty or sensitivity evidence. Results on synthetic unit-test data are never strategy evidence.

For the scaffold's `metrics.py`, returns are simple net interval returns; annualization uses a caller-supplied periods-per-year value; volatility is population standard deviation; Sharpe uses zero risk-free return; Sortino uses zero target return and downside root-mean-square deviation; drawdown uses starting wealth 1; turnover is mean absolute position change per interval; and hit rate is the fraction of nonzero-exposure intervals with positive net return. These are explicit defaults, not competition rules.
