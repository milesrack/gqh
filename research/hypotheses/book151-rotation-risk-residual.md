# Book screens: rotation, risk and residual demand

Next exploratory batch; not evaluated. Earlier book range reversal and ratio mean reversion failed training; fixed240-day trend failed validation alpha despite positive market-exposure returns. Count all prior families and attempts. New strategies use the same free BTCUSDT/ETHUSDT spot archives, costs, timing and locked final holdout. Current fixed asset selection has survivorship bias.

## Shared specification

Source Kakushadze/Serur2018, original and searchable text retained. Training before15 March2023; validation15 March2023–6 December2024. Final holdout7 December2024 onward inaccessible and absent from raw files. No paid data.

Completed UTC daily bars only. One full calendar day between signal completion and entry at a subsequent daily open. Long-only unlevered spot; cash zero yield; USDT10,000 account scenario. Primary10bp fee+5bp adverse execution per side. Costs applied to actual target-weight turnover against drifted existing holdings; post-fee holdings must be self-financing. Stress30bp per side and one further day of delay. Benchmark monthly-rebalanced equal-weight BTC/ETH with identical costs and execution delay in every scenario.

Three fixed variants per family; no extra filters. Freeze best training net Sharpe per family among profitable candidates with at least30 actual asset-weight reallocations, at least three calendar years each with100 invested days and at least two profitable calendar years. Monthly-frequency strategies need not reach100 trades. Reject a family without validation if none qualifies. Do not select on validation outcomes.

For each frozen candidate, report validation net return, annualised Sharpe365, drawdown, gross exposure, turnover, yearly distributions, paired benchmark-excess and benchmark-regression alpha. HAC20 and30-day circular block bootstrap2,000 draws, seed20261003. Report95% and nine-new-candidate-adjusted intervals plus cumulative discovery count. A positive finding requires positive net profit and positive alpha/excess intervals, profitability under doubled costs, and positive net return of both declared neighbouring variants. Market exposure or mechanical volatility reduction alone is insufficient. No final holdout access.

## C1: dual relative momentum rotation

Book§4.1/§4.1.2, printedpp61–62/PDFpp62–63, crypto adaptation. Persistent heterogeneous investor demand can favour one asset within a common market. Lookback {60,120,240} completed daily closes. At each month end, invest100% in the asset with stronger lookback return if that return is positive; otherwise cash. Ties use equal weights. Retain the selected allocation until the next delayed monthly rebalance. Null: relative selection adds no net alpha over equal-weight crypto exposure; avoid calling established momentum new or uncrowded.

## C2: volatility-managed exposure

Book§6.5 printedp80/PDFp81, spot adaptation. Investor leverage constraints and volatility feedback can make high-volatility exposure less attractive; forecast volatility before scaling risk. Rolling volatility window {20,40,60} days of close returns, sample standard deviation annualised365. Daily weight per asset is0.5×min(1,0.20/forecast volatility). Missing estimates imply cash. No leverage or trend filter. Null: variable exposure has no positive net alpha after costs and market-beta adjustment. Reduced drawdown is a risk benefit, not standalone alpha.

## C3: residual momentum rotation

Book§3.7 printedp44/PDFp45, two-asset adaptation. Asset-specific demand may persist after removing a common crypto-market shock. Define daily market return as equal-weight BTC/ETH close returns. Estimate each asset beta from the previous252 completed daily returns, excluding the current return. Daily residual is asset return minus that known beta times market return. Formation window {60,120,240} days; score is cumulative residual divided by its formation-window standard deviation. Require complete beta and formation histories. At month end allocate100% to the asset with higher positive score; otherwise cash. Ties equal weights. Null: residual demand adds no net alpha beyond the common crypto exposure. No fundamentals, sentiment or future factor estimates enter the signal.
