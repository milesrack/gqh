# Scheduled partial-market closures: pre-evaluation clarification

No strategy outcome has been evaluated. Preserve original specification b7672c9 and correction 90249ec. Their rule that scheduled no-trade holidays are non-events with positions held requires a portfolio calendar clarification.

The six-market raw archive contains precisely three UTC weekdays where CL and GC have no trades but all four financial roots do: 2015-04-03, 2021-04-02 and 2023-04-07. These are Good Friday dates. CME's 2023 holiday schedule explicitly shows energy and metals closed while interest rates, equities and FX have abbreviated sessions. Official 2015 Globex and 2021 delivery notices independently identify those dated Good Friday holidays. These are scheduled market closures, not unexplained instrument disappearances.

Use the common six-market weekday observation/execution calendar and treat only these three verified scheduled closure events as non-events. Every position remains held across the closure; the next common bar marks each same actual dated contract from its prior common open. The Friday financial movement therefore accrues into the next observed cash P&L rather than disappearing. No zero-return mark, interpolated quote, synthetic fill, contract substitution or discarded held loss is permitted. Features accumulate same-contract point changes between adjacent common weekday closes, retaining the complete closure gap. All raw Friday financial trades remain in evidence. Benchmarks and neighbouring trials use the identical calendar. Formal split dates and fixed annualisation remain unchanged.

Any other missing required actual held/replacement bar remains an experiment failure. This clarification neither changes the eight candidate choices nor allows a result-dependent calendar filter.

Primary sources:
- https://www.cmegroup.com/files/good-friday.pdf (dated 6–7 April 2023: energy/metals closed; financial markets abbreviated)
- https://www.cmegroup.com/tools-information/lookups/advisories/electronic-trading/20150330.html (dated 2015 Good Friday Globex notice)
- https://www.cmegroup.com/notices/clearing/2021/03/Chadv21-092.pdf (dated 2 April 2021 Good Friday delivery calendar)
