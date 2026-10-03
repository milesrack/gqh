# Passive liquidity premium with bounded inventory

## Mechanism

Urgent takers pay the spread to obtain immediate execution. A small liquidity provider can earn part of that premium by accepting brief inventory exposure, provided adverse selection and liquidation costs do not consume it. Quotes favour the side supported by moderate displayed depth rather than unusually aggressive flow. This is a separate passive-execution family, not a marketable shock reversal.

## Quotes

FDAX only, EUR25 per index point. One-second decisions, 09:05–17:25 Europe/Berlin. Require valid current quotes no older than one second, spread from one to four index points, and displayed book imbalance magnitude between 0.1 and 0.5. Positive imbalance submits one buy at the observed bid; negative imbalance submits one sell at the observed ask. No order exists while a position is open. Prices are exact observed bid/ask values; no assumed tick rounding.

The quote arrives after 100ms. Require a fresh valid quote at arrival and reject any entry limit that would already be marketable; record these rejected attempts. An exit limit that would be marketable on arrival uses that observed marketable price and is labelled as liquidation, never as a maker fill. It can fill only on the first subsequent on-market trade with the correct aggressor side, at least one contract and price strictly through the resting limit: seller-initiated below a buy limit; buyer-initiated above a sell limit. Touches never fill. Fill price is the submitted limit, with no price improvement. Order remains outstanding through its declared time-to-live; cancellation takes another 100ms, and trades during cancellation latency can fill.

After an entry fill, submit one opposite-side exit limit at the valid bid/ask observed at that fill; it arrives 100ms later. Strict trade-through proof also governs this exit. If inventory remains after the holding deadline, cancel the exit with 100ms latency, retain any intervening fill, then liquidate marketably at the next valid quote. A ten-index-point adverse midpoint stop triggers the same cancellation/liquidation sequence. Exit cannot be silently discarded. No overnight positions; stop opening entries five minutes before session close.

## Fixed menu and selection

Four training candidates: entry quote TTL one or five seconds, inventory holding deadline 30 or 60 seconds. All share the same filter, strict fill proof, stop and one-contract inventory bound. Select highest mean net daily P&L, requiring at least 100 completed trades, positive total, positive P&L in two of three chronological training blocks and a training 99.44% block-bootstrap interval above zero. If none qualifies, validation remains untouched.

Training 10 March–20 June 2025; validation 23 June–25 July; final holdout locked. Fee scenarios EUR1 and EUR2 per side; not verified broker rates. Stop new orders after realised daily loss reaches EUR250; a pending order is cancelled with latency and subsequent fills remain chargeable. Report maximum realised overshoot and mark-to-market inventory loss.

## Controls and uncertainty

Every unfilled and cancelled order is counted. Compare each candidate against an identical marketable entry/exit control at the same decision times and holding deadline, keeping separate inventory paths. The passive candidate never receives a midpoint fill. Stress fees EUR2/side, additional one-index-point slippage on forced liquidations, and 250ms order/cancellation latency, all with freshly simulated fills. Retain trade-through timing and opposing volume; at least one additional contract must trade strictly through in the queue stress scenario. Validation neighbours: TTL 0.5/2 seconds around selected one-second TTL, or 3/7 seconds around five; holds 20/40 around 30, or 45/75 around 60. Never select a replacement using validation.

Null: mean validation net daily P&L is non-positive. Five-session circular block bootstrap, 2,000 draws, seed 20261003; report 95% and the parent discovery-count-adjusted interval. Require positive conservative validation net P&L and cost/delay/queue stresses, a confidence interval above zero and consistent neighbouring signs. This is a conservative trade-through fill proxy, not a measurement of live queue position or fill economics. Margin and operational feasibility require separate verification.
