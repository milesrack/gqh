# Book-derived futures screen

Test published price, volume and curve mechanisms on ES, NQ, ZN, CL, GC and EUR futures. Strategy metadata identifies source sections, economic mechanism, null, falsifier and adaptations. Strategies requiring unavailable inputs remain excluded in `research/book-strategies.csv`.

Resolve every parameter combination, market universe and frequency from `research/configs/futures-grid.json` into a committed plan before evaluation. Default grids are finite examples; configured values and ranges replace them. Record all jobs, costs, failures and interruptions. Parameter grids run on training only; rank net results without calling profitable exposure alpha.

Training: 1 April 2016–19 January 2022 exclusive. Validation: 19 January 2022–27 May 2024 exclusive. Final prices from 27 May 2024 remain locked. The initial batch does not open validation. Any later validation selection uses training evidence and is frozen before evaluation.

Actual dated contracts, delayed information, shared calendar, native ticks, whole contracts, costs and risk follow the separately committed futures operational policy. All markets use the same requested evaluation window. Executable contract selection and feature histories are causal. Acquisition is separate; the runner never downloads data.

The one-job harness check uses ES 120-bar trend over 2020. It checks execution and outputs; it is not a strategy-selection result.
