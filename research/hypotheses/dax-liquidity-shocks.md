# DAX liquidity shock and resiliency

## Mechanism

An execution programme can consume near-touch liquidity faster than other participants replenish it. A large one-sided move followed by opposing displayed depth indicates that liquidity suppliers have returned before the initiating programme has finished. Fade that transient pressure. Conversely, continued depth depletion can mark persistent aggressive execution: continuation is the competing mechanism. The counterparties are urgent liquidity takers and inventory-constrained dealers. Whether this persists beyond spread and fees is an empirical question.

## Signal

Use only FDXM, one-second receive-time decisions, 09:05–17:25 Europe/Berlin. Require valid quotes no older than one second at decision and 30 seconds earlier. Compute 30-second midpoint change, signed aggressive-volume imbalance and total aggressive volume. Set absolute-change threshold to the training 95th percentile and volume threshold to the training 75th percentile. Require non-zero change, absolute imbalance at least 0.7 and agreement between aggressive flow and price direction.

Replenishment: displayed book imbalance opposes price direction by at least 0.2. Enter against the price move. Depletion: displayed book imbalance agrees with price direction by at least 0.4. Enter with the price move.

## Trials and selection

Five training candidates: replenishment fade with 30, 60 or 120-second holding; depletion continuation with 60 or 120-second holding. Select once by highest mean net daily P&L across three chronological training blocks, requiring positive P&L in at least two blocks and at least 100 trades. If none qualifies, reject this menu without opening validation. Selection uses actual executable prices and base fees. Report all five failures and candidates.

One untouched validation assessment for the selected candidate. Four prespecified neighbours retain its holding period: change threshold 90th or 97.5th percentile; replenishment imbalance 0 or 0.4 (depletion 0.2 or 0.6). These assess stability, never replace the selected rule.

## Execution and inference

FDXM EUR5 per index point, one contract, no overlapping positions, no overnight holdings. Marketable entry at first valid top-of-book at or after 100 milliseconds; sufficient displayed size. Timed marketable exit includes 100 milliseconds. Retain delayed exits; an entered position without executable exit invalidates the run. Scenario fees EUR1 per side, then EUR2; doubled-cost stress doubles observed spread and fees. Broker fees and margin remain unverified.

Training 10 March–20 June 2025; validation 23 June–25 July; 28 July onward remains locked. Null: mean validation net daily P&L is non-positive. Five-session moving-block daily bootstrap, 2,000 draws, fixed seed 20261003. Require positive base and doubled-cost validation totals, a confidence interval excluding zero, neighbouring rules with the same sign, and sufficient observations. Results remain exploratory after five candidate trials.
