# Fixed-sign reversal audit

User-requested falsification: determine whether previously rejected rules forecast adverse subsequent midpoint movement, rather than merely lose through spread and fees. The new prediction is that taking the opposite position on the exact original signals can capture that adverse movement after executable costs.

Retain original training 10 March–20 June and validation 23 June–25 July 2025. Final holdout remains inaccessible. No new data, thresholds, hours or features. Preserve all earlier trials.

Menus: reverse all twelve Micro dislocation rules (threshold {1,2,3,4}, hold {1,5,10}); six Mini round-level continuation rules (spacing {50,100}, hold {30,60,120}); six Mini failed-stop completion rules with identical spacing and hold menu. Original +17-point shifted-level placebos are retained as controls for the two Mini families, with their directions reversed. Discovery comprises 24 candidate rules plus twelve placebo controls.

Only trade direction changes. Keep decision times, signal eligibility, quote freshness, latency, fees and cooldown definitions. Recompute actual marketable entry and exit sides. For Mini families, re-evaluate the direction-dependent 20-point stop and €500 realised daily-loss gate. The Micro rules retain their original fixed-time exits. No overlapping positions or overnight exposure; preserve delayed exits and fail missing exits.

Primary latency 100 ms and fees €0.50 per side. Select the training rule with greatest mean daily net PnL among profitable candidates with at least 100 trades across 20 active days. Freeze exactly one rule before validation. Reject without validation if none qualifies. Controls cannot be selected as candidates.

Report original and reversed gross midpoint PnL, spread drag, fee drag, net PnL and trade count. For fixed trade times, opposite-direction net PnL equals negative original net PnL minus twice original spread-plus-fee cost. Path-dependent stops and loss limits require actual reruns rather than this identity.

For a selected rule, evaluate validation once, its original direction and pre-existing adjacent threshold/hold settings, plus reversed shifted-level control if applicable. Stress fees €1 and €2 per side; doubled spread plus doubled primary fee; 250 ms latency; 0.5 index point adverse slippage per side. Positive evidence requires profitable validation, positive five-session block-bootstrap daily-mean intervals after discovery adjustment, and survival of doubled costs and 250 ms latency. Use 2,000 bootstrap samples, seed 20261003; report 95% and 24-candidate adjusted intervals. Include the expanded experiment count when interpreting evidence. Reversal does not establish an independent economic mechanism or uncrowded alpha.
