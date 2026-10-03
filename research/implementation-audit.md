# Implementation corrections

| Correction | Affected runs | Treatment |
| --- | --- | --- |
| DataFrame.product method collision | dax-smoke-001 | Failed before model fitting; retained |
| Future label availability filtered execution decisions | dax-smoke-002 | Forecast results unaffected; execution evidence invalidated |
| Unsigned book-size subtraction overflowed when ask size exceeded bid size | dax-smoke-002, dax-smoke-stability-*, dax-development-001 | Model and trading results invalidated; retained for provenance |

Signed-size correction: 970fb7a. The regression test requires unsigned sizes 1/3 to produce book imbalance −0.5. Corrected development runs use dax-development-stability-*; all declared cells are rerun, with 5/5 unchanged as primary.

Raw prices, request hashes and chronological boundaries are unchanged. Final holdout events remain unprocessed.
