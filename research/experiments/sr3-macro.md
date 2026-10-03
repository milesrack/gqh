# SR3 macro revisions

```sh
bash tools/run_sr3_macro.sh
```

Downloads cached ALFRED vintages and contract-level SR3 definitions and final settlements. Acquisition refuses Databento quotes above $20. The quoted total is $9.39. Credentials: root `.env`, `FRED_API_KEY` and `DATABENTO_API_KEY`.

Training: May 2018–December 2022. Validation: 2023–2024. Data from 2025 onwards is excluded.

The grid covers 288 event specifications and up to 5,184 trading cells. Each eligible event specification and split receives one million three-month block-bootstrap draws. Four workers run by default; set `SR3_WORKERS` between 1 and 8. Completion times depend on data coverage and hardware; the runner prints progress and an ETA. Completed bootstrap jobs and chunks resume on rerun.

```sh
uv run --locked python tools/sr3_macro_experiment.py status
tail -f results/sr3-macro-revisions-v1/run.log
```

Results: `results/sr3-macro-revisions-v1/`. `dashboard.html` shows equity and sensitivity plots; `REPORT.md`, `robustness_grid.csv`, `event_regressions.csv` and `bootstrap-results.json` contain the evidence. Data and vintage audits reside in `.agent-work/shared/data/sr3-macro-revisions/`.

Specification: `research/hypotheses/sr3-macro-revisions.md`. Grid: `research/configs/sr3-macro.json`. Settlement fills are modelled; positive results require an execution audit before deployment.
