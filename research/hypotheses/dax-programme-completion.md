# Programme completion after liquidity pressure

## Mechanism

Immediate shock fades failed in training. Displayed replenishment does not establish the end of aggressive execution. This second family waits for aggressive trading intensity to collapse and for the price to stop extending. Dealers can then unwind inventory acquired from a completed execution programme. The observable constraint is execution urgency; the proposed persistence is dealer inventory adjustment after that urgency ends.

## Rule

FDXM only, one-second decisions. A shock occurs over (t−40s,t−10s]: signed aggressive imbalance magnitude at least 0.7; absolute midpoint move above its training 95th percentile; volume above its training 75th percentile; direction agrees with aggressive flow. Over (t−10s,t], per-second aggressive volume must be below 25% of shock intensity. Midpoint must not extend the shock direction by more than one index point, and must retrace less than half the preceding move. Enter against the shock direction.

## Fixed trials

Holding periods 60, 120 and 300 seconds. Select highest training mean daily net P&L, requiring positive total, at least 100 trades and positive P&L in two of three chronological training blocks. Reject before validation if none qualifies. Four validation neighbours preserve the chosen horizon: intensity ratio 0.15/0.35; shock quantile 90%/97.5%. Retain every candidate; never select from validation.

## Evaluation

Same training 10 March–20 June 2025 and validation 23 June–25 July; final holdout remains locked. Actual marketable FDXM bid/ask, one contract at EUR5 per point, 100ms latency, no overlap or overnight. EUR1/side scenario and doubled observed spread/fees stress. Entry requires fresh valid displayed liquidity; delayed executable exits remain in P&L. Null: validation mean net daily P&L is non-positive. Five-session moving-block bootstrap, 2,000 draws, seed 20261003. Require positive doubled-cost performance, confidence interval above zero, and neighbours with consistent sign. This is a training-informed second family, not independent confirmation of the first.

Intensity is classified aggressive volume divided by window length. A window with no classified prints has zero observed classified intensity; no directional imbalance is imputed. Missing or invalid midpoint observations invalidate the signal. Report uncertainty about unclassified trades. Compare exhaustion-qualified signals with the same shock/retrace condition without the intensity filter on training only. Report 98.33% and 95% daily bootstrap intervals; extended discovery includes six families and remains exploratory.
