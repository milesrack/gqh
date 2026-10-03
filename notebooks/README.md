# Research notebooks

```sh
UV_CACHE_DIR=/private/tmp/gqh-uv-cache uv run --locked jupyter lab notebooks/sr3_research.ipynb
```

Select the project Python kernel and run all cells. The SR3 notebook reads cached data, displays diagnostics and runs the curve-revision experiment. Results, figures and trial records are saved automatically. No new data purchases or final-holdout access.

Use `experiment_console.ipynb` for other committed runners. Set `COMMAND` and `RESULTS`; its execution cell streams progress and saves the log. Strategy runners own configuration, costs, splits, manifests and trial recording.
