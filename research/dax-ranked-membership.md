# DAX historical membership pilot

Full 40-member universe verified for 10 March–27 July 2025. No membership changes occur inside this window. Coverage CSV: `research/configs/dax-membership-2025-pilot.csv`. Membership outside that window is rejected.

```sh
export UV_CACHE_DIR=/private/tmp/gqh-uv-cache
uv run --locked python tools/dax_ranked_membership.py prepare &&
uv run --locked python tools/dax_ranked_membership.py run
```

Preparation reuses the original stock files and downloads only missing names. Outputs: `results/dax-ranked-membership-v1/`. Data: `.agent-work/shared/data/dax-ranked-membership/`. Original experiment files and outputs are preserved. The grid has 4,536 sleeve trials; no paid request or final-holdout access.

Source records: context `sources/dax-membership-2025/`. The CSV bounds describe this verified pilot window; they are not admission dates. This removes the arbitrary subset for the pilot, while retrospective price adjustments and prior inspection of development outcomes remain limitations.
