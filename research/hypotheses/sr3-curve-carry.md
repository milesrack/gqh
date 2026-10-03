# SR3 curve carry

## Hypothesis

A steep forward-rate curve creates mechanical roll-down for a fixed forward contract as its reference period approaches. If compensation for policy uncertainty exceeds adverse curve repricing and costs, buying the far contract and selling the near contract when the forward curve slopes upward earns positive net returns. Reverse both legs for a downward curve. The null is non-positive net returns and no predictive relation between initial curve slope and subsequent curve flattening.

## Frozen experiment

Use cached contract-level settlements only. Restore Friday observations from the original raw statistics: final actual settlements must be published by 06:00 Chicago on the next business day. Join the existing unambiguous instrument definitions; count unmatched instruments. Do not alter the original dataset or its previous results.

At each month's first observed session, use the previous session's published settlements to select unstarted quarterly contracts nearest reference midpoints 180/360, 270/540 or 360/720 days ahead. Reject either tenor error above 60 days. Enter at that session's settlement, freeze both contracts and hold 10, 20 or 40 exchange sessions. No overlapping pairs. Reject paths with missing weekday settlements; exchange holidays follow the US federal calendar approximation and are disclosed. Signal is far implied rate minus near implied rate, in basis points. Thresholds: 5, 15 and 30 bp. Long far/short near when positive; reverse when negative. One contract per leg; capital $100,000. Costs: 0.5, 1 and 2 bp per leg round trip, charged half at entry and exit.

Training: May 2018–2022. Inner selection: fit-screen through 2020, choose the parameter cell using 2021–2022 net Sharpe at 1 bp per leg, at least six trades; freeze the selected cell before calculating 2023–2024 results. Fixed primary: 270/540 days, 20 sessions, 15 bp, 1 bp per leg. Compare fixed long-spread and cash benchmarks on the same events. Save every cell, skipped path, data audit, IC, returns and trades. Use a 20-session moving-block bootstrap of daily net returns for the primary mean-return interval; 10,000 draws.

## Boundaries

2023–2024 is reused validation. No 2025+ data. Settlement fills and simultaneous two-leg fills are modelled. Carry is an established strategy family; this screen makes no novelty claim. A surviving result requires fresh validation and execution analysis.
