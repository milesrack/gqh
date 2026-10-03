---
name: financial-data
description: Inspect and validate unfamiliar market datasets before feature engineering or backtesting.
---

# Financial data

Pandas, NumPy, and PyArrow are available in `.venv` for inspecting released tabular or columnar data. Select readers only after confirming the actual format and schema; preserve nulls and source dtypes.

Inventory files, fields, units, instrument identifiers, ordering, and provenance before choosing a schema. Establish timestamp timezone, exchange calendar, interval meaning, and when each value became available. For OHLCV, check price/volume validity and bar construction; for trades, event ordering and corrections; for order books, side, depth, update semantics, and sequence gaps, as applicable. Profile missing values, duplicates, outliers, and relevant corporate actions or universe changes. Document resampling boundaries and whether returns are simple or log, adjusted or raw. Never silently forward-fill: describe and test every imputation or exclusion. Preserve raw inputs and a reproducible cleaning record.
