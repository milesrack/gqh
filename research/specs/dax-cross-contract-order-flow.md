# DAX Cross-Contract Order-Flow Research Specification

## 1. Objective

Test whether order flow in DAX futures of different contract sizes contains **incremental information about the same underlying price**.

The three instruments are:

| Contract | Product | Exposure per DAX point | Minimum price change |
|---|---|---:|---:|
| FDAX | DAX Futures | €25 | 1 index point |
| FDXM | Mini-DAX Futures | €5 | 1 index point |
| FDXS | Micro-DAX Futures | €1 | 1 index point |

All three reference the DAX and can be matched on the **same quarterly expiry**. Because the economic exposure is the same apart from contract size, they should reflect the same underlying information. The research question is whether that information is incorporated into the three order books at exactly the same time.

The primary study is:

\[
\boxed{\text{FDAX and FDXM order flow} \rightarrow \text{future FDXS price movement}}
\]

The broader price-discovery study tests all six directed pairings among FDAX, FDXM and FDXS.

---

## 2. Economic hypothesis

### Core mechanism

The contracts share the same underlying and expiry, so they should be anchored to the same latent efficient futures price.

However, their participant mixes, liquidity, typical trade sizes, funding constraints and execution objectives may differ. If informed or urgent trading reaches one contract before another, its order flow may reveal information that has not yet been fully incorporated elsewhere.

Market efficiency supplies the convergence mechanism: any genuine information about the common DAX exposure should eventually be reflected across all three contracts.

The hypothesis is therefore **not** that larger contracts automatically contain "smart money" or that the Micro contract represents retail traders. Contract size alone does not identify trader type or informedness.

### Research hypothesis

> Order flow across DAX futures with different contract sizes may incorporate common information at different speeds. When their flows disagree, the contract carrying more informative flow should temporarily predict subsequent price adjustment in the others.

### Primary directional conjecture

> FDAX and FDXM flow may add predictive information for FDXS beyond information already contained in FDXS itself.

This direction is pre-specified as the primary test. The other directions are secondary tests designed to determine where price discovery actually occurs rather than assuming the answer.

---

## 3. Null and alternative hypotheses

Let \(Y^{S}_{t,H}\) be the future FDXS midprice change over horizon \(H\), and let \(OF^D_t\), \(OF^M_t\), and \(OF^S_t\) denote recent signed order-flow measures for FDAX, FDXM and FDXS.

The primary model is:

\[
Y^{S}_{t,H}
=
\alpha
+
\beta_S OF^S_t
+
\theta^\top X_t
+
\gamma_D OF^D_t
+
\gamma_M OF^M_t
+
\varepsilon_t
\]

where \(X_t\) contains a small set of pre-specified controls such as recent price movement and the current FDXS book state.

### Statistical null

\[
H_0:\gamma_D=\gamma_M=0
\]

FDAX and FDXM flow contain no incremental predictive information for future FDXS price movement after conditioning on information already observable at time \(t\).

### Statistical alternative

\[
H_A:(\gamma_D,\gamma_M)\neq(0,0)
\]

At least one larger-contract flow variable contains incremental predictive information.

A statistically significant rejection of \(H_0\) is **not sufficient** to claim a trading edge. The effect must also improve out-of-sample forecasts and survive realistic execution costs.

---

## 4. Data required

### Databento request

| Selection | Requirement |
|---|---|
| Dataset | `XEUR.EOBI` |
| Products | FDAX, FDXM, FDXS outright futures |
| Contracts | Same actual quarterly expiry across all three |
| Main schema | `mbp-1` |
| Reference schema | `definition` |
| Format | DBN, preferably compressed |
| History | Available from 10 March 2025 onward |

`mbp-1` provides every event that changes the best bid or offer, including trades, BBO prices, displayed sizes and aggressor-side information where supplied. It is sufficient for the primary study and a first-pass marketable-order execution model. Full MBO is unnecessary unless the project later studies queue position or passive fills.

Use the `definition` schema to resolve exact instruments, expiries, tick values and contract metadata.

### Development download

Start with **2-6 June 2025** or another small contiguous week and verify:

- FDAX, FDXM and FDXS are all present;
- the selected contracts have the identical expiry;
- trade-side fields behave as expected;
- timestamps are understood correctly;
- quotes can be reconstructed without crossed or stale states;
- off-market records can be identified;
- the full data request size and cost can be estimated.

Do not use the development week to choose a profitable-looking rule.

### Contract selection

Use a deterministic rule before examining results. For example:

1. select the nearest common quarterly expiry;
2. roll all three products together on a fixed pre-specified date before expiry;
3. never mix expiries in the same observation.

Do not choose expiries or roll dates after seeing which version produces the best backtest.

### Records to exclude

Exclude mechanically rather than subjectively:

- options, calendar spreads and combination instruments;
- off-market trades;
- invalid or crossed BBO states;
- periods where one required contract has no valid current quote;
- exchange halts or clearly invalid records;
- expiry/roll observations outside the pre-specified contract-selection rule.

Do **not** delete bad trading days merely because they hurt performance.

---

## 5. Time alignment and lookahead control

This is a high-frequency study, so timestamp handling is part of the research design rather than data-cleaning trivia.

For each decision time \(t\):

1. use only market information that would have been observable by \(t\);
2. construct each contract's most recent valid BBO using an as-of join;
3. compute signals only from events in the historical lookback window;
4. simulate execution only at a quote available **after** the assumed latency.

Databento provides nanosecond-resolution event and receive timestamps. `ts_event` represents exchange-side event timing, while `ts_recv` records when Databento's capture server received the message.

Use exchange time for studying economic sequencing, but use a receipt-time-aware simulation for claims about tradeability.

No signal may use:

- a future quote;
- the closing value of the interval in which the trade is supposedly entered;
- a fill at a quote that disappeared before the order could arrive;
- future volume, volatility or contract-selection information.

---

## 6. Variables

### Midprice

For contract \(i\):

\[
m_i(t)=\frac{bid_i(t)+ask_i(t)}{2}
\]

Use midprice rather than last trade price for the forecasting target because last trades contain bid-ask bounce.

### Signed trade-flow imbalance

For lookback \(L\):

\[
OF_i(t;L)
=
\frac{
\sum_{k\in(t-L,t]} s_k q_k
}{
\sum_{k\in(t-L,t]} q_k
}
\]

where:

- \(s_k=+1\) for buyer-initiated trades;
- \(s_k=-1\) for seller-initiated trades;
- \(q_k\) is contract quantity.

Thus \(OF_i\in[-1,1]\).

The **primary specification uses \(L=5\) seconds**. Other windows are sensitivity tests, not opportunities to hunt for the best-looking result.

### Book imbalance

For the target contract:

\[
BI_i(t)
=
\frac{Q^{bid}_i(t)-Q^{ask}_i(t)}
{Q^{bid}_i(t)+Q^{ask}_i(t)}
\]

This controls for immediately visible top-of-book pressure.

### Recent return

\[
R_i(t;L)
=
m_i(t)-m_i(t-L)
\]

Include recent price movement so cross-contract flow is not merely acting as a proxy for a price move that has already occurred elsewhere.

### Forecast target

Measure future movement in ticks:

\[
Y^j_{t,H}
=
\frac{m_j(t+H)-m_j(t)}
{\text{tick size}_j}
\]

The primary horizon is:

\[
H=5\text{ seconds}
\]

A secondary binary target may be used for interpretability:

\[
D^j_{t,H}=\operatorname{sign}(Y^j_{t,H})
\]

but continuous future price change remains the primary target.

---

## 7. Model design

Keep the primary model deliberately simple.

### Baseline model

For FDXS:

\[
M_0:
\quad
Y^S_{t,5}
=
\alpha
+
\beta_1 OF^S_t
+
\beta_2 R^S_t
+
\beta_3 BI^S_t
+
\beta_4 R^D_t
+
\beta_5 R^M_t
+
\varepsilon_t
\]

This represents what is already knowable from FDXS itself plus recent price movement in the parallel contracts.

### Cross-flow model

\[
M_1:
\quad
M_0
+
\gamma_D OF^D_t
+
\gamma_M OF^M_t
\]

The central question is whether \(M_1\) improves on \(M_0\).

This is stronger than merely showing that FDAX flow correlates with future FDXS returns. It asks whether FDAX/FDXM **flow itself adds information beyond the prices and state already visible across the market**.

Start with OLS. Do not introduce trees, neural networks or large feature sets unless the simple relationship is first demonstrated out of sample.

---

## 8. Disagreement signal

To describe the original intuition directly, standardise each flow measure using parameters estimated from the training set:

\[
z_i(t)=\frac{OF_i(t)-\mu_i}{\sigma_i}
\]

Define larger-contract flow:

\[
L_t=\frac{z_{FDAX}(t)+z_{FDXM}(t)}{2}
\]

and cross-contract disagreement:

\[
G_t=L_t-z_{FDXS}(t)
\]

Large positive \(G_t\) means the larger contracts are more buy-pressured than FDXS; large negative \(G_t\) means the reverse.

Use this as an interpretable secondary specification:

\[
Y^S_{t,5}
=
\alpha+\beta G_t+\theta^\top X_t+\varepsilon_t
\]

The corresponding null is:

\[
H_0:\beta=0
\]

Do not assume in advance that a larger \(|G_t|\) must be profitable. That is what the data must establish.

---

## 9. Trading rule

The research result and the trading rule are separate stages.

After the predictive model is frozen, let:

\[
\hat{Y}_{t,5}
\]

be the predicted FDXS midprice movement in ticks.

Let \(C_t\) be the estimated round-trip execution cost in ticks, including spread, exchange fees, broker/clearing fees and any slippage assumption. Let \(b\ge0\) be a safety buffer selected using validation data only.

Trade:

\[
\text{Position}_t=
\begin{cases}
+1, & \hat{Y}_{t,5}>C_t+b\\
-1, & \hat{Y}_{t,5}<-(C_t+b)\\
0, & \text{otherwise}
\end{cases}
\]

For the first implementation:

- use marketable execution;
- buy at the first executable ask after assumed latency;
- sell at the first executable bid after assumed latency;
- hold for the pre-specified horizon or until a separately pre-specified exit rule;
- allow at most one position per target contract at a time.

This prevents overlapping five-second signals from being counted as independent free trades.

The first strategy can trade FDXS because it is the primary target, but the research should not claim FDXS is the optimal execution vehicle until execution economics are compared.

---

## 10. Data split

Never randomise high-frequency observations.

Split by **whole trading days in chronological order**:

| Block | Purpose | Approx. share |
|---|---|---:|
| Training | Estimate coefficients and normalisation parameters | 60% |
| Validation | Freeze threshold, latency assumption and any permitted design choices | 20% |
| Final test | One untouched evaluation | 20% |

Procedure:

1. Build and debug the pipeline on the small development sample.
2. Fit the pre-specified models on training data.
3. Use validation data for the small number of choices explicitly allowed in advance.
4. Freeze the full specification.
5. Refit on training + validation if desired.
6. Run the final test **once**.

If the strategy is changed after inspecting final-test results, that test set is no longer out of sample. The revised strategy requires new forward data or a previously untouched reserve.

Because five-second labels overlap, individual observations are not independent. Use daily blocks for inference and resampling rather than pretending millions of neighbouring observations are millions of independent experiments.

---

## 11. Statistical testing

### 11.1 In-sample coefficient test

Test the primary joint restriction:

\[
H_0:\gamma_D=\gamma_M=0
\]

with a joint Wald/F test using heteroskedasticity- and autocorrelation-robust covariance estimates.

The purpose is evidence about the relationship, not strategy selection.

### 11.2 Out-of-sample forecast improvement

Compare \(M_1\) with \(M_0\) on validation and, after freezing, on the final test using:

- mean squared error;
- mean absolute error;
- out-of-sample \(R^2\);
- directional accuracy as a secondary descriptive measure.

Compute the difference in forecast loss by day and use a **block bootstrap over trading days** to obtain a confidence interval for the improvement.

A Diebold-Mariano-style test with autocorrelation-robust variance may be reported as a secondary check, but daily block resampling should remain the primary robustness method.

### 11.3 Economic test

For the frozen trading rule report net-of-cost:

- total P&L;
- mean P&L per trade;
- number of trades;
- win rate;
- profit factor;
- turnover;
- maximum drawdown;
- daily-P&L Sharpe ratio;
- bootstrap confidence interval for mean daily P&L.

Do not treat a high-frequency Sharpe ratio computed from overlapping five-second observations as meaningful.

### 11.4 Secondary directional matrix

Test all six directed pairings:

| Predictor | FDAX target | FDXM target | FDXS target |
|---|---:|---:|---:|
| FDAX flow | - | ✓ | ✓ |
| FDXM flow | ✓ | - | ✓ |
| FDXS flow | ✓ | ✓ | - |

These tests answer **where price discovery occurs**.

They are secondary, so correct their p-values for multiple testing, for example with Holm's method. Any newly discovered relationship should be treated as exploratory until confirmed on untouched data.

---

## 12. Execution model

A prediction is not an edge until it survives execution.

For every simulated trade:

1. compute the signal at the decision timestamp;
2. add assumed information-processing/order latency;
3. locate the first executable quote after that time;
4. enter at the ask for a buy or bid for a sell;
5. enforce displayed-size constraints;
6. exit using the same rules;
7. deduct exchange, broker and clearing fees;
8. record gross and net P&L separately.

Run a fixed latency sensitivity table, for example:

\[
0,\;10,\;50,\;100,\;250\text{ ms}
\]

Zero latency is an upper bound, not the headline result.

Also report performance under progressively less favourable slippage assumptions.

---

## 13. Guardrails against common backtest failures

### P-hacking / data snooping

**Failure:** testing many windows, thresholds and directions, then reporting the winner.

**Prevention:**

- declare the 5-second lookback and 5-second horizon as the primary specification;
- declare FDAX + FDXM \(\rightarrow\) FDXS as the primary direction;
- label other horizons and directions as secondary;
- use a locked final test;
- correct secondary hypothesis tests for multiplicity;
- report failed primary results even if a secondary variant looks better.

### Overfitting

**Failure:** too many features or parameters relative to the economic idea.

**Prevention:**

- begin with the nested linear models above;
- keep the feature set small and economically motivated;
- require any added model complexity to beat the simple baseline out of sample;
- never select features using the final test.

### Lookahead bias

**Failure:** allowing future information into the signal or fill.

**Prevention:**

- point-in-time/as-of joins only;
- signal inputs must have timestamps no later than the decision time;
- fills occur only after assumed latency;
- compute normalisation, volatility thresholds and similar quantities using past data only;
- never use future contract volume to decide today's contract.

### Survivorship / selection bias

Traditional equity survivorship is not the main issue here, but selection bias can enter through contract and session filtering.

**Prevention:**

- use all eligible common expiries under a fixed roll rule;
- include all qualifying sessions, including losing and stressed days;
- define exclusions mechanically before evaluating P&L;
- do not drop thin or volatile periods merely because results deteriorate.

### Ignoring costs

**Failure:** reporting mid-to-mid or gross returns as tradeable P&L.

**Prevention:**

- cross the actual historical spread;
- include exchange and broker/clearing fees;
- enforce latency;
- stress slippage;
- report gross and net results side by side.

### Leaking the test set

**Failure:** checking final results, changing the strategy, then calling the same data "out of sample".

**Prevention:**

- one locked final block;
- record the frozen specification before opening it;
- once inspected, that block becomes historical research data and cannot validate later revisions.

### Misleading Sharpe ratio

**Failure:** annualising heavily overlapping intraday observations or presenting one summary ratio without context.

**Prevention:**

- construct realised daily strategy P&L first;
- calculate Sharpe from daily P&L;
- accompany it with P&L, drawdown, turnover, trade count and confidence intervals;
- show monthly results rather than hiding concentration in one period.

### Regime dependence

**Failure:** all profits come from one month, volatility regime or market event.

**Prevention:**

Pre-specify descriptive breakdowns by:

- month/quarter;
- time of day;
- realised-volatility bucket formed using past information;
- contract expiry cycle.

The edge should not require one isolated episode to survive.

### Unrealistic capacity

**Failure:** assuming unlimited execution at the best quote.

**Prevention:**

- begin with one contract;
- respect displayed BBO size;
- test increasing order size against available depth/slippage assumptions;
- report a capacity curve rather than extrapolating one-contract P&L linearly.

---

## 14. Robustness and falsification tests

Run these only after the primary specification is frozen.

### Horizon sensitivity

Repeat the analysis at:

\[
L,H\in\{1,2,5,10\}\text{ seconds}
\]

Treat the 5-second/5-second result as primary. Do not redefine whichever combination wins as the original hypothesis.

### Reverse-direction tests

If larger contracts truly lead FDXS, the reverse relationship should be weaker after conditioning on available information.

Test:

\[
FDXS\rightarrow FDAX,\qquad
FDXS\rightarrow FDXM
\]

alongside the other directional relationships.

### Price-only placebo

Compare the cross-flow model against a model containing the parallel contracts' recent prices but **not** their flows.

If cross-contract flow adds nothing once cross-contract prices are known, the proposed order-flow mechanism is unsupported.

### Sign permutation / day shuffle

As a diagnostic, break the contemporaneous relationship between predictor flow and target returns by permuting or shifting entire daily blocks. The real specification should outperform these placebo versions.

---

## 15. Decision criteria

The hypothesis is supported only if the result survives all three levels.

### Level 1: statistical information

Cross-contract flow coefficients are jointly informative and the cross-flow model improves forecasts relative to the baseline.

### Level 2: out-of-sample stability

The improvement appears in the locked test and is not concentrated entirely in one short regime.

### Level 3: economic value

A rule based on the frozen model remains profitable after realistic spread, fees, latency and slippage assumptions.

A result that passes Level 1 but fails Level 3 is a **price-discovery finding**, not a trading strategy.

---

## 16. Research workflow

1. Download the small `XEUR.EOBI` development sample.
2. Validate instruments, expiries, timestamps, trade sides and BBO reconstruction.
3. Estimate the full historical request and freeze the contract-roll rule.
4. Build point-in-time 5-second features.
5. Create chronological train / validation / locked-test blocks.
6. Fit the FDXS baseline \(M_0\).
7. Add FDAX and FDXM flow to obtain \(M_1\).
8. Test the joint coefficient restriction and out-of-sample forecast improvement.
9. Freeze the execution rule and cost assumptions using validation data only.
10. Run the locked final test once.
11. Run the six-direction price-discovery matrix and pre-specified robustness checks.
12. Report statistical significance, forecast value and net trading performance separately.

---

## 17. What would constitute a meaningful result?

The strongest result would be:

> FDAX and/or FDXM order flow predicts subsequent FDXS midprice movement after controlling for FDXS's own flow, book imbalance, its recent price movement and recent price movement in the parallel contracts; the effect persists out of sample and remains positive after realistic execution costs.

A weaker but still useful result would be:

> Cross-contract flow reveals measurable lead-lag price discovery, but the adjustment is too fast or too small to trade after costs.

A clean null result is also informative:

> Once contemporaneous prices and FDXS's own state are known, FDAX and FDXM flow adds no reliable information about subsequent FDXS movement.

All three outcomes answer the research question. Only the first supports an implementable alpha claim.

---

## References

- Eurex, **DAX Futures contract specifications**: https://www.eurex.com/ex-en/markets/idx/dax/DAX-Futures-34642
- Eurex, **Micro-DAX Futures**: https://www.eurex.com/ex-en/markets/idx/dax/Micro-DAX-Futures-2615492
- Databento, **Eurex EOBI dataset (`XEUR.EOBI`)**: https://databento.com/datasets/XEUR.EOBI
- Databento, **MBP-1 schema**: https://databento.com/docs/schemas-and-data-formats/mbp-1
- Databento, **Eurex venue and timestamp documentation**: https://databento.com/docs/venues-and-datasets
- Databento, **Eurex historical availability announcement**: https://databento.com/blog/eurex-now-available

Databento states that `XEUR.EOBI` history begins on **10 March 2025**. Its Eurex launch announcement quoted usage-based historical pricing beginning at **$5/GB**; obtain a current portal estimate before purchasing because pricing can change.
