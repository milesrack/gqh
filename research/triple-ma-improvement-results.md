# Triple-MA improvement results

All 33 training jobs and the frozen development follow-ups completed or retained explicit failures. Final holdout access: none.

Nineteen of 27 neighbouring MA combinations had positive training P&L (70.4%); this fails the prespecified 80% stability gate. The three sizing variants failed the training participation constraint. Increasing notional caps is not an executable improvement under the unchanged liquidity policy; the relaxed-cap variant also failed the delayed development run. Both $5 million configurations failed base development execution.

The training-selected separation threshold was 1.0 times trailing daily price-change volatility. Development Sharpe declined from 0.870 to 0.824, CAGR from 2.48% to 2.36%, and net P&L from $59,096.88 to $56,127.50. Additional-delay Sharpe declined from 0.387 to 0.276. Incremental HAC20 alpha against the baseline was 0.11% annually, p=0.852, with a 199-training-trial adjusted interval of −2.04% to 2.26%. The filter does not establish improvement.

CL was held on 59 portfolio days versus 390 standalone days, with overlapping activity on all 59 portfolio days. Whole-contract portfolio sizing suppresses most CL positions; the strategy also depends on actual held position when deciding whether to retain a trend. Maximum absolute quantity was three contracts in both. The portfolio contribution reflects different exposure timing and state, not merely the sum of standalone signals. Gross portfolio CL P&L was $22,040; standalone net P&L was −$73,850. This decomposition does not establish beneficial diversification as a causal mechanism.

Decision: retain the original strategy as a baseline; these experiments do not justify promotion. Use training data for new mechanisms. The inspected development period is not fresh validation.

Outputs: `results/triple-ma-improvement-v1/improvement-summary.json`. The summary builder was corrected to join asynchronous results by job ID rather than completion order; saved evaluations were reused without retuning or rerunning market-data jobs.
