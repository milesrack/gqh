# Shared research storage

Snowflake stores source files, market tables and searchable context. Vultr runs Python notebooks. Git stores hypotheses, code, manifests and selected evidence.

## Authentication

Keep credentials in ignored `.env`. Each teammate uses their own Snowflake user and RSA key. Grant `GQH_RESEARCHER` for retrieval and `GQH_PUBLISHER` for ingestion. Never distribute an administrator private key.

Set `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_ROLE` and `SNOWFLAKE_PRIVATE_KEY_FILE`. Restore dependencies with `uv sync --locked`.

## Initialise

Run `uv run --env-file .env --locked python tools/snowflake_store.py setup` as ACCOUNTADMIN. Grant the publisher role to the ingestion user. The warehouse suspends after 60 seconds; its daily resource monitor suspends at five credits. Cortex charges require separate monitoring.

## Publish and retrieve

```sh
uv run --env-file .env --locked python tools/snowflake_store.py inventory --collection market --manifest .agent-work/runs/market.json
uv run --env-file .env --locked python tools/snowflake_store.py upload --manifest .agent-work/runs/market.json
uv run --env-file .env --locked python tools/snowflake_store.py verify --manifest .agent-work/runs/market.json
uv run --env-file .env --locked python tools/snowflake_store.py fetch --manifest .agent-work/runs/market.json --source .agent-work/downloads
```

Repeat for `context` and `results`. Share manifests through Git. Uploads preserve originals and SHA-256 hashes. Fetch verifies downloaded bytes. Parquet assets are also queryable in `GQH.MARKET.OBSERVATIONS`; DBN files remain intact in the stage.

After context ingestion, run `index-context`, then `search --query 'participant inventory constraints'`. Retrieve the cited source and read its passage before making claims.

## Migration

Retain the context checkout and existing tools until every collection has been uploaded, downloaded into a fresh directory and hash-verified. Verify cited search results and teammate retrieval before retiring the old repository.

## Notebook compute

The Vultr worker uses four CPUs, 8 GB RAM and 160 GB disk: $0.055/hour, $1.32 per 24 hours. Bind Jupyter to localhost and connect through an SSH tunnel. Each teammate uses a separate Unix account and SSH key. Keep notebook outputs and cached datasets outside Git; record parameters, data hashes, trials and runtime with each experiment.

Run large experiments when required by the hypothesis. Estimate memory, runtime and cloud spend before launching. Save checkpoints and progress logs; preserve the final holdout.

Connect to the current worker:

```sh
uv run --locked python tools/notebook_connect.py --host 140.82.47.196 --key .agent-work/.secrets/vultr-notebooks --known-hosts .agent-work/.secrets/vultr-known-hosts
```

Keep the tunnel running while using Jupyter. The connector reads the existing token over SSH and opens the browser without printing it. Experiments are available under `/srv/gqh/experiments`; restore that checkout with its own `uv sync --locked` and register its kernel before running existing notebooks.

## Team access

1. Create an individual Snowflake user through the account administrator.
2. Generate an RSA-2048 key locally; register only its public key with that user.
3. Grant `GQH_RESEARCHER`; add `GQH_PUBLISHER` only for ingestion responsibilities.
4. Configure ignored `.env`, pull the published manifest and use `fetch` or `search`.
5. Add each teammate’s SSH public key to their own Vultr Unix account. Start a separate Jupyter process and forward its localhost port.

For the first 24 hours, reserve $30 of Snowflake trial usage for ingestion, queries and context indexing. Actual cost depends on active warehouse time and Cortex usage. The five-credit daily warehouse monitor does not cap Cortex. Check account billing before enabling continuous indexing. Stop or destroy the Vultr worker when finished; powering it off continues billing.
