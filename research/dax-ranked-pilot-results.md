# Ranked DAX pilot results

All 4,536 trials completed; zero failed. Saved data/config hashes match. Seventy training sessions and eighteen development sessions. All fourteen training-selected sleeve/cost candidates lost money in development. No final holdout access.

Base-cost FDAX leadership: training return +13.71%, Sharpe 5.28; development return −1.90%, Sharpe −5.29. FDXM and FDXS leadership similarly reversed. Leadership selections used three-day raw momentum, 30% tails, contrarian direction and daily rebalancing. The selected equity rank sleeve lost in both segments: −3.83% training and −1.16% development. Higher modelled costs deepened losses.

The fixed 30-stock subset and retrospective Yahoo adjustments prevent point-in-time constituent-alpha claims. The development segment was already inspected. Short samples and 4,536 variants prevent treating large annualised training metrics as alpha evidence. Quote freshness/depth, borrow availability and margin feasibility are not independently established. The higher-cost scenario doubles futures fees and added slippage, not observed spread or equity borrow charges.

Full results are preserved in the private context data bundle `data/experiment-results/dax-ranked-pilot-v1.tar.gz`. Run the separate historical 40-member experiment to diagnose subset dependence; do not select a new model using these development outcomes.
