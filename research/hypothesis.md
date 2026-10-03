# DAX cross-contract order flow

## Hypothesis

FDAX and FDXM signed trade flow adds information about five-second FDXS midpoint changes beyond FDXS flow, book imbalance and recent midpoint changes in all three contracts. Participant constraints may cause information to arrive at different times across economically equivalent books. Contract size does not identify participant type. Cross-contract arbitrage is the convergence mechanism and may eliminate the opportunity before execution.

Primary statistical null: the coefficients on FDAX and FDXM flow are jointly zero. Primary predictive null: cross-flow does not reduce out-of-sample squared forecast error relative to the nested baseline. Trading null: expected executable net daily P&L is non-positive.

The supplied [specification](specs/dax-cross-contract-order-flow.md) defines the research programme. The choices below complete the first implementation; all are fixed before outcomes are inspected.

## Data and timing

Use XEUR.EOBI MBP-1 and definitions, FDAX/FDXM/FDXS outrights with identical quarterly expiry. Select the nearest expiry whose third-Friday expiry is more than seven calendar days away; roll all products together at the session open. Verify definitions before processing.

Primary acquisition range: 10 March 2025 through 2 October 2026 inclusive, subject to actual coverage and authorised cost. Use common exchange sessions, 09:05–17:25 Europe/Berlin. Calendar dates, not observation counts, determine chronological 60/20/20 blocks. Final 20% is inaccessible to development commands. Missing data does not move the split. The 2–6 June 2025 development week is for pipeline validation and preliminary training/validation evidence; it cannot establish historical robustness.

Receive time governs all features, targets and execution. Exchange timestamps are retained for diagnostics; Eurex RequestTime/TransactTime differ by message type and are not a uniform execution clock. Quote updates require the end-of-event flag; trades are counted independently. Exclude off-market publishers, invalid prices and quality-flagged records. Valid quotes require positive sizes, bid <= ask, and age <= one second; missing quotes remain missing. Unknown trade side is excluded from signed volume and counted separately. No classified volume means missing flow, not zero.

Five-second lookback and target are primary. Decisions occur every second; windows are (t−5s,t]. Require valid current and lagged quotes for all contracts and a valid future target quote; labels cannot cross session or split boundaries. Never deduplicate trades merely because price and quantity match.

## Models

OLS baseline M0: intercept, FDXS flow, FDXS five-second return, FDXS book imbalance, FDAX five-second return, FDXM five-second return. M1 adds FDAX and FDXM flow. Fit on training only. Score both on exactly the same validation rows. Report rank/conditioning and refuse unidentified fits.

Report HAC joint flow-coefficient test (five lags on the one-second grid), MSE, MAE, directional accuracy including zero moves, R² versus the baseline, and daily forecast-loss differences. Bootstrap consecutive five-session blocks, 2,000 replicates, seed 20261003. Report sample counts, excluded rows and individual-day results. The development-week interval is descriptive and underpowered.

## Execution

Trade one FDXS contract when M1 predicted movement exceeds the observed spread plus round-trip fees/slippage and buffer. Primary latency is 100 ms; declared sensitivity is 0,10,50,100,250 ms. Zero latency is an upper bound. Buffer candidates are 0,0.5,1,2 ticks; select by validation mean daily net P&L, ties favour the larger buffer. No overlapping positions. Enter using the first valid observed quote at/after arrival; require displayed size >= position. Exit five seconds after decision, using the first valid quote at/after exit arrival. Entry must precede planned exit; forced exits retain realised adverse prices. Never silently discard an entered position whose exit quote is missing.

Fees must be supplied explicitly. Until verified, 0.5,1,2 EUR per side are illustrative scenarios, not a broker quote or a deployment claim. Slippage sensitivity: 0,0.5,1 tick per side. Tick value: FDXS EUR1, verified against definitions. Baseline M0 is evaluated with identical costs and threshold procedure. A profitable midpoint forecast alone is not alpha.

## Evaluation and access

Log every attempted model, parameter and failed run. No final holdout evaluation in this implementation task. A separate approved freeze records coefficients, buffer, fees, latency, data hashes, split dates and code commit before one final evaluation. No strategy-specific merge to main without Miles's approval. If selected, submit the hypothesis commit separately before implementation; retain the original dated hypothesis and all subsequent amendments.

Secondary work: disagreement z-scores fitted on training only, six directed pairs with Holm correction, L/H in {1,2,5,10}, day-shift placebos, delay/cost stress and regime breakdowns. Secondary variants never replace a failed primary result. New winning directions require fresh confirmation.
