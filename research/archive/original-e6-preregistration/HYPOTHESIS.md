# Volatility targeting 2: frozen research contract

Specification date: 3 October 2026. No performance has been evaluated.

## Mechanism and null

Hypothesis: persistent variance, leverage constraints and slow institutional risk
adjustment make causal exposure sizing useful. Static allocators and benchmark
mandates retain exposure during rising risk. This is a risk-management hypothesis,
not a claim to forecast returns or a claim of novel volatility targeting.
Null: after financing and execution costs, dynamic sizing provides no robust
improvement over its matched unscaled and static-exposure portfolios.
Prediction: forecasts positively predict subsequent variance; net volatility,
CVaR and drawdown fall across multiple years without excessive CAGR drag.
Reject if forecast IC is non-positive, the benefit is isolated to one crisis,
turnover/costs erase it, neighbouring parameters collapse, or OOS contradicts it.
The claimed institutional mechanism remains conjecture until tested.

## Universe, timing and data

Fixed surviving ETFs: SPY/TLT/GLD; expanded QQQ/IWM/HYG/TLT/GLD/DBC.
This is a fixed instrument study, not historical constituent selection. Yahoo
adjusted closes include retrospectively adjusted distributions; raw OHLC, volume,
dividends and splits are preserved. No price filling. Parkinson uses raw high/low
with causal close-return correlations; it omits overnight variance, a limitation.
DGS3MO uses ALFRED initial releases and their availability dates, not revised FRED
history. Availability is conservatively the next NYSE session after release.
Require FRED_API_KEY locally; no fabricated or revised-rate fallback.
Calendar: XNYS sessions 2008-01-02 through 2026-10-02. Holdout is the shorter of
ceil(20% of planned sessions) and sessions in the latest two calendar years.
The last session is always included. Development ends 2018-12-31; validation
starts 2019-01-01. All comparisons use identical dates after a 550-session common warm-up.
Annual validation folds preserve causal estimation and trading state.

Close-t features produce a signal at the actual calendar close, execute at close
t+1 and affect returns starting the next close-to-close interval. Orders are
fixed before the execution close. Portfolio holdings drift between trades;
transaction costs use actual risky-asset dollars bought plus sold, 5 bp per
one-way notional, with 0/2/10 bp sensitivities. Half-L1 turnover includes cash;
it is reported separately and is NOT the fee base for risky cross-trades.
Initial deployment is at the raw target; subsequent changes use the registered control. Initial deployment costs are included from session 551. Cash accrues the available DGS3MO yield
on ACT/365; borrowing pays that rate plus 50 bp (0/100 bp diagnostics).
Rates are investment-basis yields used as a cash proxy, not total-return bills.
No fees on cash transfers. No discretionary stops or unsupported same-close fills.

## Search budget and variants

See experiment_registry.csv: 12 primary variants, immutable parameters. E0
monthly 63-session sample volatility, 8% target, equal-weight three-asset base.
E1 fast/slow EWMA squared returns (span 20/63, 63-session minimum), targets
9/10/11%, 5 percentage-point trigger. E2 expanding HAR with intercept,
1/5/21-session squared-return features, next-21-session average variance target,
504 minimum completed labels and monthly refits; targets must mature before fit.
Negative variance predictions are floored at 1e-8. E3 two Parkinson lookbacks
20/63, independently evaluated; this resolves the guide's conflicting max
ensemble and two-variant count in favour of its explicit 12-variant budget.
E4 minimum variance and E5 ERC use monthly 126-session Ledoit-Wolf covariance,
70% base caps; E6 expanded ERC uses 35% base caps. Overlays recompute historical
constant-current-base portfolio returns causally each session. E7 uses E1's
fixed 10% ensemble (no discretionary forecast selection), immediate 5 pp cuts,
10 pp restoration threshold sustained five days, maximum 10 pp daily increase.
E8 permits 1.25 gross, but caps at 1 if forecast exceeds target, 20-session base
drawdown is below -5%, or mean pairwise 20-session correlation exceeds its
expanding 80th percentile. Asset caps apply to BASE weights; scaled caps are
87.5% in the leveraged extension. E0/E1/E2/E3/E7/E8 bases rebalance monthly.

Diagnostics are logged as additional runs, never new candidate hypotheses:
0/2/5/10 bp costs; target +/-1 pp; lookback multiplier 0.8/1.2 (HAR uses 403/605 matured labels; diagnostics remain cash until labels mature); trigger 4/6 pp;
E8 financing 0/50/100 bp. No diagnostic may become the selected candidate.
Bootstrap paired daily net returns: 1,000 moving-block samples, seed 42,
block lengths 5/10/20, 95% percentile intervals; recompute each wealth path.
Static comparator exposure is estimated on development ONLY and then fixed.

## Validation and freeze

Against the matched unscaled base require >=10% volatility and drawdown reduction,
CVaR improvement, <=150 bp annual CAGR drag, <2 NAV annual half-L1 turnover,
and all these financial conditions at doubled costs. Require risk improvement
in a majority of complete annual validation folds (at least two); require
positive validation forecast rank IC, and neighbouring diagnostics to retain
risk improvement and <=150 bp CAGR drag. Reject unsupported optimisation.
Passing candidates rank by fixed mechanism complexity, then turnover, downside
risk and Sharpe. Ranking is advisory: Miles must select and explicitly freeze.
Freeze must bind full parameters, source/data hashes, code tree hash, specification
and registry hashes, development static exposure and result provenance. OOS mode
requires externally supplied expected freeze hash, exact code/specification and
an exclusive access flag written BEFORE any holdout request. Never repeat an
access or resume a failed request as if untouched. Any prior contamination must
be disclosed; this branch cannot certify team-wide untouched history.

## Sources and limitations

- Parkinson (1980), Journal of Business 53(1), 61–65,
  https://doi.org/10.1086/296071: variance = mean(log(H/L)^2)/(4 log(2)).
- Yahoo interface: https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html
- ALFRED initial-release semantics: https://fred.stlouisfed.org/docs/api/fred/series_observations.html
- Ledoit-Wolf implementation: https://scikit-learn.org/stable/modules/generated/sklearn.covariance.LedoitWolf.html
- Risk parity is conventional; constrained ERC can have unequal contributions.

Cost and square-root impact assumptions are transparent scenarios, not calibrated
execution evidence. Closing fills, distribution-adjusted historical prices,
limited crises, fixed surviving ETFs, cash proxy and same-day liquidity proxies
limit live claims. Capacity uses PREVIOUS-session median 20-day raw dollar volume
and daily volatility. AUM 1/10/100/500/1,000 million; impact Y=.25/.5/1;
report participations and net impact-adjusted performance. No research search,
paid acquisition, holdout access, strategy adoption or publication are authorised
by writing this implementation.

## Holdout provenance caveat

The implementation-time initial acquisition smoke used yfinance's default client
before its latest-chart timezone-discovery behaviour was identified. That call
may have fetched a current-day chart for metadata; no holdout metrics or strategy
selection were computed. The production adapter now bounds all chart calls and
blocks current-quote endpoints. Confirm this and any existing team-wide access
with Miles before asserting that final history is completely untouched.
