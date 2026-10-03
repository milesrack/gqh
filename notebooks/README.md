# Research notebooks

```sh
UV_CACHE_DIR=/private/tmp/gqh-uv-cache uv run --locked jupyter lab notebooks/sr3_carry.ipynb
```

Select the project Python kernel and run all cells. The carry notebook audits the settlement calendar and walks through EDA, signals, chronological selection, validation, benchmarks, costs and uncertainty. `sr3_research.ipynb` retains the earlier revision experiments. Results, figures and trial records are saved automatically. No new data purchases or final-holdout access.

Use `experiment_console.ipynb` for other committed runners. Set `COMMAND` and `RESULTS`; its execution cell streams progress and saves the log. Strategy runners own configuration, costs, splits, manifests and trial recording.
