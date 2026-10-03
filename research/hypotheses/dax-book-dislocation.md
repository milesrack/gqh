# DAX executable book dislocation

Mechanism: fragmented contract liquidity leaves Micro quotes temporarily cheap or dear relative to simultaneous Large and Mini quotes. Marketable Micro orders buy from stale liquidity and unwind after alignment. Receipt-time snapshots must be fresh; the Large and Mini markets must agree within two index points.

Null: executable relative-value trades have non-positive expected daily net PnL after spread, fees and 100 ms latency.

Universe: matched FDAX, FDXM and FDXS outright maturities; existing cached sessions only. Training 10 March–20 June 2025; validation 23 June–25 July. Final holdout 28 July–29 August inaccessible.

Signal: consensus midpoint is the arithmetic mean of Large and Mini midpoints. Buy when consensus minus Micro ask exceeds threshold; sell when Micro bid minus consensus exceeds threshold. All three quotes must be no older than one second. One-second decisions, 09:05–17:25 Europe/Berlin.

Limited grid: thresholds 1, 2, 3 and 4 index points; holdings 1, 5 and 10 seconds. One Micro contract, one position at a time, marketable entry at first valid quote at or after decision plus 100 ms. Exit at first valid quote at or after decision plus holding plus 100 ms. Missing exits invalidate the run rather than discard losing trades. No overnight positions. Primary fees €0.50 per side; cost stress €1 and €2 per side, doubled spreads, 250 ms latency and 0.5 point adverse slippage per side.

Selection: rank the twelve training variants by mean daily net PnL, subject to at least 100 trades across 20 trading days. Freeze one candidate before validation. Report every training variant. Validate the selected candidate once, along with its immediately neighbouring thresholds and holdings as declared sensitivity checks. Five-session moving-block bootstrap, 2,000 samples, seed 20261003. Positive finding requires positive validation daily net PnL, a 95% interval above zero and profitability with doubled costs and 250 ms latency. Exploratory validation is not final OOS evidence.
