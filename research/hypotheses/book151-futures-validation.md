# Futures validation

Freeze all 39 training-selected candidates in `research/configs/futures-validation.json`. Apply the existing training-positive doubled-cost gate before validation. Evaluate unchanged parameters from 19 January 2022 through 26 May 2024. The final holdout remains locked.

Compare each candidate with cash and a long-only control using the same universe, decision frequency, sizing, execution and risk limits. Evaluate base costs, doubled costs and one additional information-bar delay. Preserve failures and report every candidate; do not select new parameters from validation.

Report net returns, Sharpe, drawdown, paired 20-bar block-bootstrap intervals and HAC20 alpha against the control. Adjust inference for all 166 original trials. With 2,000 bootstrap draws, adjusted extreme-tail intervals have insufficient resolution; use adjusted HAC intervals for alpha and retain the bootstrap limitation. A surviving candidate requires positive net returns under both stresses and positive adjusted alpha against its matched control. Passing this screen does not establish novelty or final-holdout performance.
