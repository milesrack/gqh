# Team access

Send [this prompt](../team-agent-prompt.md) to Nelson, Sean and Amir. Their agents generate individual keys and return `<name>-access.json`. It contains public keys only.

## Owner

For each returned bundle:

```sh
uv run --locked python tools/team_keys.py NELSON --bundle /path/to/nelson-access.json
```

Inspect `.agent-work/runs/nelson-register.sql` and execute it as ACCOUNTADMIN in Snowflake. Run the generated `nelson-ssh-user.sh` over the owner's SSH connection to the Vultr worker. Repeat for SEAN and AMIR.

`GQH_PUBLISHER` inherits read access and can ingest assets. The generated scripts refuse to overwrite existing users. Teammates receive no administrator, root or Vultr API credentials.

## Teammate

Keep the private keys and Snowflake settings in ignored local files. Retrieve a collection manifest and download the required assets:

```sh
uv run --env-file .env --locked python tools/snowflake_store.py manifest --collection market --manifest .agent-work/runs/market.json
uv run --env-file .env --locked python tools/snowflake_store.py fetch --manifest .agent-work/runs/market.json --source .agent-work/assets --path '*sr3_daily.parquet'
uv run --env-file .env --locked python tools/snowflake_store.py search --query 'participant constraints and forced trading'
```

Retain the manifest with the run. Downloads check SHA-256. Publish new collections from fresh inventories; original staged files are immutable. Check existing document hashes before editing and coordinate overlapping subjects.

## Notebook server

Each teammate connects by SSH to `140.82.47.196` under their lowercase name. Use a private home directory, own checkout, own uv environment and a Jupyter token. Bind the server to `127.0.0.1`. Assigned ports: Nelson 8889, Sean 8890, Amir 8891.

After `uv sync --locked`, create `~/.jupyter/jupyter_server_config.py` with a random token and mode 600. Start:

```sh
uv run --locked jupyter lab --no-browser --ip=127.0.0.1 --port=8889
```

From the teammate's laptop:

```sh
uv run --locked python tools/notebook_connect.py --host 140.82.47.196 --user nelson --key .agent-work/.secrets/nelson/notebooks --known-hosts .agent-work/.secrets/vultr-known-hosts --remote-port 8889
```

Server Ed25519 fingerprint: `SHA256:Ja30sGWILOoObxNgoGTO89pXl9DY/dgO97iBkvZt3ck`. Verify it before saving the host key. Never disable host-key checks or expose Jupyter publicly.
