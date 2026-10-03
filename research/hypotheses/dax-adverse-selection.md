# Aggressive pressure against opposing displayed liquidity

## Hypothesis revision

Immediate fading of large FDXM aggressive-flow shocks failed in training. Opposing displayed depth may represent stale or adversely selected liquidity suppliers rather than informed resistance. Aggressive takers who continue executing can consume that apparently replenished depth. Continue the shock direction specifically when the book appears to oppose it. This rule is motivated by observed training failures and counts as another discovery family.

## Fixed rule

Retain the original training-defined 30-second shock: absolute midpoint change above its training 95th percentile, classified aggressive volume above its training 75th percentile, absolute signed imbalance at least 0.7 agreeing with the price move. Displayed book imbalance must oppose the move by at least 0.2. Enter with the price move; hold 60 seconds. No training selection among horizons. Training must have positive total P&L, at least 100 trades and positive P&L in two of three chronological blocks before validation is opened.

## Evidence

Same FDXM-only receive-time inputs, fresh valid quotes, one-second decisions, one contract EUR5/point, 100ms executable latency, actual marketable bid/ask and EUR1/side scenario fees. Double observed spread and fees as stress. No overlap or overnight; entered positions cannot be discarded for delayed exits. Training 10 March–20 June, validation 23 June–25 July, final holdout locked.

Validation neighbours, without selecting a replacement: holds 30/120 seconds and opposing depth imbalance 0/0.4. Report 95%, 98.33% and 99.17% five-session block-bootstrap intervals with 2,000 draws and seed 20261003; parent also adjusts for any expanded discovery count. Null is non-positive validation mean net P&L. Evidence must survive doubled costs and consistent neighbouring signs. No alpha claim from reversing a losing training strategy alone.
