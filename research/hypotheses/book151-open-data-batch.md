# Book screens: liquid crypto spot

Source: Kakushadze and Serur, 151 Trading Strategies, 17 August 2018. Full text and original SHA256 retained locally. These are book-derived implementations, not claims of novelty.

## Shared evaluation

Universe fixed before outcomes: Binance BTCUSDT and ETHUSDT spot. Official public daily OHLCV archives and provider checksums; cost $0. Quote currency USDT, not a risk-free USD asset. No shorts, leverage, funding or borrow. Cash earns zero.

Formal calendar history 1 January 2018–31 August 2026, 3,165 days. First 60% train: before 15 March 2023; next 20% validation: 15 March 2023–6 December 2024. Latest 20% holdout begins 7 December 2024 and remains inaccessible; do not download its daily observations. Missing development dates invalidate evaluation rather than change boundaries.

Signals use completed UTC daily bars. To avoid assuming the closing signal can trade the simultaneous next midnight open, execute at the following day's open after one full calendar day of delay. Decisions never use the entry day's prices. Mark returns open-to-next-open; liquidate before split boundaries. Small account scenario USDT10,000; maximum gross allocation100%, no fractional leverage.

Costs: 10 basis points fee and five basis points adverse execution per side, applied to absolute asset-weight turnover. Stress doubled total costs and one additional calendar day of signal delay. Track daily positions, gross/net returns, fees, turnover and trades. Benchmarks: equal-weight BTC/ETH with monthly rebalancing and identical costs; zero-return cash. Estimate daily benchmark-regression intercept with HAC20 and circular30-day block bootstrap2,000 draws, seed20261003. Report net Sharpe, drawdown and benchmark excess returns. Crypto market exposure alone is not alpha.

Each family has three fixed variants. Select its best training daily net Sharpe subject to positive net PnL, at least100 round trips or weight reallocations and75 invested days. Freeze at most one candidate per family before validation. Reject a family without validation if no candidate qualifies. Validate each frozen candidate once, alongside its two predeclared neighbours as sensitivity checks. Positive evidence requires net validation profitability, positive benchmark-regression alpha and95%/nine-candidate-adjusted intervals, plus profitability with doubled costs. Record all failures and the wider search count. Final holdout remains locked.

## B1: range-pressure reversal

Book§4.4, printed p64, PDFp65. Mechanism: temporary aggressive selling puts the close near the day's low; constrained sellers finish and liquidity replenishes. IBS=(close−low)/(high−low); zero-range days produce no entry. Allocate50% to each asset when IBS is below entry threshold {0.15,0.20,0.25}. Exit when IBS exceeds0.80 or after three held daily bars. Long only; unused capital cash. Null: delayed mean reversion does not pay transaction costs or improve on market exposure.

## B2: multi-asset trend

Book§4.6 printedp65/PDFp66 and§10.4 printedp96/PDFp97. Mechanism: gradual information incorporation and persistent institutional demand sustain trends. Lookback {60,120,240} days. Allocate50% to each asset with positive close-to-close lookback return; otherwise cash. Monthly target rebalancing using only known signals. Null: trend exposure adds no benchmark-adjusted return after costs. A profitable market-beta portfolio alone fails the edge criterion.

## B3: relative-value spot rotation

Adaptation of book§3.8 printedp45/PDFp46. Common crypto demand links Bitcoin and Ether; temporary relative-flow pressure can displace their price ratio. Compute z-score of log(BTC close/ETH close) against rolling {60,120,240}-day mean and standard deviation. z≤−1 allocates100% to BTC; z≥1 allocates100% to ETH; otherwise equal weights. Long only; daily target adjustment with delayed execution. No assumption of cointegration or fundamental parity: reject persistent relative trends if validation fails. Null: rotation has no net excess return over equal-weight exposure. Controls include the fixed equal-weight portfolio and the opposite rotation on identical signal times, not selectable as candidates.
