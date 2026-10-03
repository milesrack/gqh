# SR3 revision screens

## Original outright hypothesis

5,184 trading cells; 576 completed bootstrap jobs, no bootstrap failures. Fixed primary validation: eight trades, −$2,462.50, Sharpe −1.329. Training-selected specification: 16 training trades, +$4,712.50, Sharpe 1.294; seven validation trades, −$1,450.00, Sharpe −0.819. No grid-adjusted bootstrap slope interval excluded zero.

## Regularised curve hypothesis

72 completed trading cells. Fixed six-/twelve-month curve, ten-session horizon, 30-day decay, clipped revisions. Chronological inner selection chose ridge penalty zero. Training rank IC: +0.315 across 136 events. Reused-validation rank IC: −0.160 across 56 events. Validation MSE: 204.95 versus 180.42 for the constant forecast. Penalty 100 reduced MSE to 192.63, still worse than the baseline.

The revision mechanism failed both screens. January 2025 onwards remains untouched. Event targets overlap; correlation counts are not independent observations. Two-leg settlement execution is modelled.

## Reproduction

Run `notebooks/sr3_research.ipynb`. Results and executed notebook: `results/sr3-curve-notebook-v1/`. The original outputs remain in `results/sr3-macro-revisions-v1/`. No acquisition is performed by the notebook.
