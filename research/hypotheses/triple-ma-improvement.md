# Triple moving-average improvement

Economic hypothesis: persistent demand can generate ordered trends across horizons; crossings smaller than ordinary price noise need not reflect persistent demand. Null: the entry-separation filter does not improve net returns over the unfiltered 5/20/60 rule. This extension does not establish a specific constrained counterparty or novelty.

Freeze 27 combinations of fast {4,5,6}, medium {16,20,24} and slow {48,60,72} days; three entry-separation cutoffs {0.25,0.5,1.0} times trailing 20-day same-contract point-change volatility; and three sizing diagnostics. New-entry thresholds preserve the existing exit rule. Keep all six markets, daily decisions, information delays, native contracts, costs and liquidity constraints unchanged.

Sizing diagnostics: $5 million capital with original caps; $1 million with root/gross/equity-index notional caps 50%/200%/70%; and both changes together. The 10% volatility target remains unchanged. Higher caps are diagnostic and not a deployment recommendation. No historical margin data is available, so funding feasibility remains unestablished.

Training: April 2016–18 January 2022. Report all 33 training jobs and the fraction of 27 neighbours with positive P&L. A stable region requires at least 80% positive neighbours. Rank filter thresholds on training Sharpe only. Run baseline, three sizing variants and the best training filter on the already-observed January 2022–May 2024 development period at base costs, doubled costs and an additional information-bar delay. No independent validation claim; final holdout locked. Compare the filtered winner directly with the unfiltered baseline and matched long controls using paired HAC20 inference, adjusting for 199 cumulative training trials. Do not broaden the grid after results.

Decompose CL portfolio and standalone trade dates, quantities and interventions. Explain sizing effects before assigning diversification credit.
