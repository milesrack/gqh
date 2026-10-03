# Teammate agent prompt

```text
Set up my GQH research workspace using milesrack/gqh-systematic-track.

My name is <Nelson | Sean | Amir>. Use the matching Snowflake username NELSON, SEAN or AMIR.

1. Inspect Git state. Fetch current main without overwriting local work. Read AGENTS.md and deployment/snowflake/README.md. Use uv and Python 3.12.
2. Run uv sync --locked, then uv run --locked python tools/team_keys.py <USERNAME>.
3. Give me only .agent-work/runs/<name>-access.json to send to Miles. It contains public keys. Keep .agent-work/.secrets/ and .env private and ignored. Never print or transmit private keys, tokens or provider credentials.
4. Stop access-dependent work until Miles confirms provisioning. Continue inspecting the project locally.
5. Set my ignored .env to SNOWFLAKE_ACCOUNT=qmsodrr-dec70778, SNOWFLAKE_USER=<USERNAME>, SNOWFLAKE_ROLE=GQH_PUBLISHER and SNOWFLAKE_PRIVATE_KEY_FILE=<absolute path to my snowflake.p8>. Preserve existing values.
6. Verify Snowflake access with tools/snowflake_store.py sql --query 'SELECT CURRENT_USER(), CURRENT_ROLE()'. Use manifest to retrieve completed collection inventories, fetch only the assets required for my experiment, and verify hashes. Search shared context with search --query, then read the cited source passage. Never clone the old context repo or install QMD.
7. Connect to Vultr at 140.82.47.196 using my Unix username and my own SSH key. Miles will provide my Jupyter port and server host fingerprint. Bind Jupyter to localhost and use tools/notebook_connect.py with the assigned remote port. Use my own workspace and experiment environment; do not modify another teammate's environment.
8. Start each economic hypothesis on a new feature/experiment-<hypothesis> branch from current main. Commit its mechanism, null, executable rules, costs, grid and chronological evaluation plan before backtesting. Work in a research notebook and save progress, configuration, hashes, trials and results. Preserve the final holdout. Use cloud compute when justified by the experiment and authorised budget.
9. Publish new assets through the shared store, retaining source paths and hashes. Check current shared versions before editing a note; coordinate overlapping edits. Record the immutable collection versions used in each run.
10. Open PRs using the repository template. No strategy-specific merge to main without Miles's approval. Remove merged branches after confirming they contain no subsequent work.
```
