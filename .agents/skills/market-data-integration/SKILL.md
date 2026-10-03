---
name: market-data-integration
description: Integrate a newly released market-data API or provider behind a provider-neutral adapter.
---

# Market data integration

First inspect official provider documentation and sample responses; do not guess authentication, endpoints, rate limits, or schema. Keep credentials outside the repository. Isolate provider requests and parsing in an adapter that emits documented, validated records for downstream research. Preserve source timestamps, timezone, availability time, instrument identifiers, and provenance. Handle pagination, retries, gaps, duplicates, and revisions according to actual provider behavior. Test the adapter with sanitized fixtures before connecting strategy code; do not put vendor-specific fields in signal logic.
