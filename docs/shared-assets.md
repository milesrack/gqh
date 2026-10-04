# Shared assets

Snowflake stores shared source files, market data and searchable context. Each contributor uses an individual user and private key. Keep account identifiers, credentials, host addresses and personal onboarding details in ignored local configuration.

```sh
uv sync --locked
uv run --env-file .env --locked python tools/snowflake_store.py manifest --collection market --manifest data/manifests/market.json
uv run --env-file .env --locked python tools/snowflake_store.py fetch --manifest data/manifests/market.json --source data --path '<required asset glob>'
uv run --env-file .env --locked python tools/snowflake_store.py search --query '<research question>'
```

Downloads verify SHA-256 and retain dataset names under ignored `data/`. Record the manifest and asset versions with each experiment. Use `--workers` to control parallel transfers. Publish changes from fresh inventories; coordinate edits to shared subjects.

Generate public-key bundles with `tools/team_keys.py <USERNAME>`. Send only the public bundle to the administrator. The administrator prepares registration SQL using `--bundle <path>`; individual usernames and keys remain outside Git.

Notebook servers bind to localhost. Use an individual Unix account, workspace and uv environment; connect through `tools/notebook_connect.py` using locally configured host, key and port.

Provider API keys and personal Snowflake keys stay outside GitHub Actions. Public connection defaults can use repository variables. Automated notebook deployment requires a dedicated SSH key scoped to a non-administrator deployment account.

CI checks Python and notebook structure without downloading data or running experiments. The manual `Upload notebooks` workflow uploads the selected Git revision as a source snapshot. It does not execute notebooks.

Configure `GQH_NOTEBOOK_HOST`, `GQH_DEPLOY_USER`, `GQH_NOTEBOOK_HOST_KEY` and `SNOWFLAKE_ACCOUNT` as GitHub repository variables. Store only the dedicated deployment key as `GQH_DEPLOY_SSH_KEY`. Personal Snowflake keys and provider API keys remain in local `.env` files.

## Publish assets

Use a dedicated source directory containing only the assets to share. Paths are relative to that directory; use unique dataset or subject names. Never inventory the repository root or a directory containing credentials.

```sh
uv run --locked python tools/snowflake_store.py inventory --collection market --source data --path 'my-dataset/*' --manifest data/manifests/upload.json
uv run --env-file .env --locked python tools/snowflake_store.py upload --source data --manifest data/manifests/upload.json
uv run --env-file .env --locked python tools/snowflake_store.py verify --manifest data/manifests/upload.json
```

Use collection `context` for documents and `results` for experiment evidence. Each upload publishes an immutable manifest after all files finish. Changed files receive new hashes and versions. Context uploads insert searchable passages; the administrator provisions the search service once with `index-context`. Upload requires `GQH_PUBLISHER`; each researcher receives this role during registration.
