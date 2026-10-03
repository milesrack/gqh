# Failed DAX stop cascades

Mechanism: concentrated protective stops create finite demand around salient prices. Once that demand ends, replenished opposing liquidity can return price through the trigger level. Observe completion before fading: recrossing and an aggressive-flow sign reversal. Counterparty is the trader exiting at a clustered stop price; persistent informed execution falsifies the proposed recovery.

This follows rejected training experiments in executable book dislocation and immediate round-level continuation. It is a new exploratory hypothesis; those failures contribute to the total trial count. No validation or final holdout outcomes have been inspected by this agent.

Use the existing FDXM/FDAX matched outrights. Training 10 March–20 June 2025; validation 23 June–25 July. Final holdout 28 July–29 August remains locked. Receipt-time snapshots, complete on-market books, maximum quote age one second, one-second grid.

Initial event: Mini crosses a 50- or 100-point lattice with a one-point or larger return, same-sign Large return, Mini one-second signed-volume imbalance at least 0.6 in the crossing direction and classified volume above the previously frozen training 90th percentile. Exactly five seconds later, price must have returned to the previous side of that crossed level and the latest one-second Mini imbalance must have the opposite sign. Enter opposite to the initial crossing. No future outcome determines eligibility. Ten-minute cooldown per crossed level and direction.

Finite menu: spacing {50,100} × holding {30,60,120} seconds after the completion observation. Six shifted-lattice placebos use +17 points. Select only the best profitable real-round training variant with at least 100 trades across 20 active days. Freeze it before validation. Reject without validation if no candidate qualifies.

Execution and risk: one Mini contract, €5 per point, marketable fills after 100 ms latency, entry delay at most one second. Exit after the declared hold plus latency or 20-point adverse midpoint stop plus latency. No overlap or overnight exposure. Stop new entries after €500 realised daily loss. Retain delayed exits and adverse fills; missing exits invalidate the run. Fee scenarios €0.50, €1 and €2 per side; doubled spread and doubled primary fee; 250 ms latency; 0.5 point adverse slippage per side.

Null: non-positive validation daily net PnL or no positive round-minus-placebo difference. Report 95% and six-family 99.17% five-session circular bootstrap intervals, 2,000 samples, seed 20261003. A positive finding must survive €1/€2 fees, doubled costs, 250 ms latency and neighbouring declared holdings, with both net-PnL and round-minus-placebo intervals above zero. Validation is exploratory, not final OOS evidence.
