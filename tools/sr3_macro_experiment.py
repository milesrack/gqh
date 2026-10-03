"""Explicit acquisition, preparation and CPU-only heavy SR3 experiment."""

import argparse
import csv
import fcntl
import importlib.metadata
import itertools
import json
import platform
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.batch_research import canonical, digest, file_hash, write_json
from src.sr3_macro.bootstrap import compute
from src.sr3_macro.data import acquire
from src.sr3_macro.model import build, regression, revisions, trade

CONFIG = ROOT / "research/configs/sr3-macro.json"
DATA = ROOT / ".agent-work/shared/data/sr3-macro-revisions"


def frozen():
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    paths = [
        CONFIG,
        Path(__file__).resolve(),
        ROOT / "research/hypotheses/sr3-macro-revisions.md",
        ROOT / "pyproject.toml",
        ROOT / "uv.lock",
        *sorted((ROOT / "src/sr3_macro").glob("*.py")),
    ]
    for p in paths:
        if (
            subprocess.check_output(
                ["git", "show", f"{commit}:{p.relative_to(ROOT)}"], cwd=ROOT
            )
            != p.read_bytes()
        ):
            raise ValueError("Commit specification/code before evaluation")
    return commit, {str(p.relative_to(ROOT)): file_hash(p) for p in paths}


def prepare(cfg):
    manifest = json.loads((DATA / "manifest.json").read_text())
    for name, sha in manifest["files"].items():
        if file_hash(DATA / name) != sha:
            raise ValueError("Source data hash changed: " + name)
    rev, audit, benchmark = revisions(cfg, pd.read_parquet(DATA / "vintages.parquet"))
    if len(audit) < 5:
        raise ValueError("Fewer than five auditable historical revision dates")
    rev.to_parquet(DATA / "revision_events.parquet", index=False)
    write_json(DATA / "vintage-audit.json", audit)
    write_json(DATA / "benchmark-exclusions.json", benchmark)
    prices = pd.read_parquet(DATA / "sr3_daily.parquet")
    if prices.trade_date.max() >= pd.Timestamp(cfg["holdout_start"], tz="UTC"):
        raise ValueError("Holdout leaked into source")
    cases = build(cfg, rev, prices)
    write_json(
        DATA / "prepared-manifest.json",
        {
            "source_manifest_sha256": file_hash(DATA / "manifest.json"),
            "revision_events_sha256": file_hash(DATA / "revision_events.parquet"),
            "sr3_daily_sha256": file_hash(DATA / "sr3_daily.parquet"),
            "case_count": len(cases),
            "config_sha256": file_hash(CONFIG),
            "final_holdout_access": False,
        },
    )
    print(
        "Prepared",
        len(cases),
        "event-study cases; five-date audit:",
        DATA / "vintage-audit.json",
        flush=True,
    )
    return cases, prices


def run(cfg, commit, hashes, workers):
    cases, prices = prepare(cfg)
    out = ROOT / "results" / cfg["batch_id"]
    out.mkdir(parents=True, exist_ok=True)
    lock = open(out / "run.lock", "w")  # noqa: SIM115 -- process-lifetime advisory lock
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise ValueError("Experiment already running") from None
    identity = {
        "commit": commit,
        "sources": hashes,
        "data": file_hash(DATA / "prepared-manifest.json"),
        "config": cfg,
    }
    previous = out / "manifest.json"
    if previous.exists():
        saved = json.loads(previous.read_text())
        if any(saved[k] != identity[k] for k in ["sources", "data", "config"]):
            raise ValueError("Batch manifest changed; new batch ID required")
        identity = saved
        commit = saved["commit"]
    write_json(previous, identity)
    write_json(
        out / "runtime.json",
        {
            "python": platform.python_version(),
            "packages": {
                name: importlib.metadata.version(name)
                for name in [
                    "numpy",
                    "pandas",
                    "statsmodels",
                    "databento",
                    "matplotlib",
                ]
            },
            "started_at": pd.Timestamp.now(tz="UTC").isoformat(),
            "workers": workers,
        },
    )
    boundaries = {
        "training": (
            pd.Timestamp(cfg["sr3_start"], tz="UTC"),
            pd.Timestamp(cfg["train_end"], tz="UTC"),
        ),
        "validation": (
            pd.Timestamp(cfg["train_end"], tz="UTC"),
            pd.Timestamp(cfg["holdout_start"], tz="UTC"),
        ),
    }
    regressions = []
    trials = []
    tasks = []
    paths = {}
    primary = None
    for params, frame in cases:
        case_id = digest(params)[:20]
        folder = out / "cases" / case_id
        folder.mkdir(parents=True, exist_ok=True)
        if frame.empty:
            write_json(
                folder / "failure.json",
                {"params": params, "reason": "no_complete_contract_paths"},
            )
            continue
        frame.to_parquet(folder / "events.parquet", index=False)
        for split, (start, end) in boundaries.items():
            sample = frame[(frame.entry >= start) & (frame.exit < end)]
            result = {
                **params,
                "case_id": case_id,
                "split": split,
                **regression(sample, params["horizon"]),
            }
            regressions.append(result)
            if len(sample) >= 30:
                records = (
                    sample[["entry", "raw_signal", "target_bp"]]
                    .assign(entry=lambda x: x.entry.astype(str))
                    .to_dict("records")
                )
                tasks.append(
                    (params, split, records, cfg, str(folder / split / "bootstrap"))
                )
            for threshold, cost in itertools.product(
                cfg["thresholds"], cfg["costs_bp"]
            ):
                job = {
                    **params,
                    "threshold": threshold,
                    "cost_bp": cost,
                    "split": split,
                }
                job_id = digest(job)[:20]
                target = out / "trials" / job_id
                target.mkdir(parents=True, exist_ok=True)
                metrics, returns, trades = trade(
                    cfg, frame, prices, threshold, cost, start, end
                )
                returns.to_csv(target / "returns.csv", index=False)
                pd.DataFrame(trades).to_csv(target / "trades.csv", index=False)
                row = {**job, "job_id": job_id, "status": "completed", **metrics}
                trials.append(row)
                paths[job_id] = target
                write_json(target / "metrics.json", row)
                if (
                    all(
                        params[k] == cfg["primary"][k]
                        for k in ["decay", "tenor", "horizon", "clip"]
                    )
                    and len(params["series"]) == 3
                    and threshold == cfg["primary"]["threshold"]
                    and cost == cfg["primary"]["cost_bp"]
                    and split == "validation"
                ):
                    primary = (row, returns, trades, frame)
        print("Built case", len(regressions) // 2, "/", len(cases), params, flush=True)
    pd.DataFrame(regressions).to_csv(out / "event_regressions.csv", index=False)
    tab = pd.DataFrame(trials)
    tab.to_csv(out / "robustness_grid.csv", index=False)
    if tab.empty:
        raise ValueError("No complete contract paths; inspect cases/*/failure.json")
    training = tab[
        (tab.split == "training")
        & (tab.cost_bp == 1)
        & (tab.series.apply(len) == 3)
        & tab.sharpe.notna()
    ]
    selected = training.sort_values(["sharpe", "job_id"], ascending=[False, True]).head(
        1
    )
    selected.to_csv(out / "training-selected.csv", index=False)
    ledger = ROOT / "research/experiments.csv"
    with ledger.open("r+", newline="") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        existing = {r["trial_id"] for r in reader}
        stream.seek(0, 2)
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        for row in trials:
            tid = cfg["batch_id"] + "/" + row["job_id"]
            if tid in existing:
                continue
            writer.writerow(
                {
                    "trial_id": tid,
                    "timestamp_utc": pd.Timestamp.now(tz="UTC").isoformat(),
                    "hypothesis_commit": commit,
                    "code_commit": commit,
                    "data_sha256": identity["data"],
                    "config_sha256": file_hash(CONFIG),
                    "sample": row["split"],
                    "parameters": canonical(
                        {
                            k: row[k]
                            for k in [
                                "series",
                                "clip",
                                "decay",
                                "tenor",
                                "horizon",
                                "threshold",
                            ]
                        }
                    ),
                    "cost_model": f"{row['cost_bp']} bp round trip",
                    "result_path": str(paths[row["job_id"]].relative_to(ROOT)),
                    "status": "completed",
                    "conclusion": canonical(row),
                    "holdout_access": "false",
                }
            )
    figs(out, tab, primary)
    print(
        "Heavy inference:",
        len(tasks),
        "jobs ×",
        cfg["bootstrap_draws"],
        "bootstrap draws; checkpoints every",
        cfg["bootstrap_chunk"],
        flush=True,
    )
    started = time.monotonic()
    done = 0
    bootstrap = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(compute, t): t for t in tasks}
        for future in as_completed(futures):
            task = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001 -- retain independent worker failures
                result = {
                    "params": task[0],
                    "split": task[1],
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            bootstrap.append(result)
            done += 1
            elapsed = time.monotonic() - started
            eta = elapsed / done * (len(tasks) - done)
            write_json(
                out / "progress.json",
                {
                    "stage": "bootstrap",
                    "completed": done,
                    "total": len(tasks),
                    "elapsed_seconds": elapsed,
                    "eta_seconds": eta,
                    "updated_at": pd.Timestamp.now(tz="UTC").isoformat(),
                },
            )
            print(
                f"[{done}/{len(tasks)}] {result['status']}; ETA {eta / 60:.1f} min",
                flush=True,
            )
    write_json(out / "bootstrap-results.json", bootstrap)
    report(out, tab, selected, primary, bootstrap)
    write_json(
        out / "summary.json",
        {
            "trading_trials": len(trials),
            "event_cases": len(cases),
            "bootstrap_jobs": len(tasks),
            "bootstrap_completed": sum(x["status"] == "completed" for x in bootstrap),
            "bootstrap_failed": sum(x["status"] == "failed" for x in bootstrap),
            "holdout_access": False,
            "report": "REPORT.md",
        },
    )
    lock.close()
    print("Finished. Results:", out, flush=True)


def figs(out, tab, primary):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    folder = out / "figures"
    folder.mkdir(exist_ok=True)
    if primary:
        _row, returns, trades, frame = primary
        fig, axes = plt.subplots(2, 1, figsize=(9, 6))
        axes[0].plot(pd.to_datetime(returns.date), returns.equity)
        axes[0].set_ylabel("Equity ($), validation")
        axes[1].scatter(frame.raw_signal, frame.target_bp, s=6, alpha=0.4)
        axes[1].set(xlabel="Revision pressure", ylabel="Subsequent rate change (bp)")
        fig.tight_layout()
        fig.savefig(folder / "primary.png", dpi=160)
        plt.close(fig)
        yearly = pd.DataFrame(trades)
        if len(yearly):
            yearly["year"] = pd.to_datetime(yearly.entry, utc=True).dt.year
            yearly.groupby("year").net_pnl.sum().to_csv(
                out / "primary-year-contributions.csv"
            )
    subset = tab[
        (tab.split == "validation")
        & (tab.threshold == 1)
        & (tab.cost_bp == 1)
        & tab.series.apply(lambda x: len(x) == 3)
        & tab["clip"].isna()
    ]
    for horizon, group in subset.groupby("horizon"):
        grid = group.pivot(index="decay", columns="tenor", values="net_pnl")
        fig, ax = plt.subplots()
        im = ax.imshow(grid.to_numpy())
        ax.set_xticks(range(len(grid.columns)), grid.columns)
        ax.set_yticks(range(len(grid.index)), grid.index)
        ax.set(
            xlabel="Tenor days",
            ylabel="Decay days",
            title=f"Validation net P&L, holding {horizon} sessions",
        )
        fig.colorbar(im, ax=ax)
        fig.tight_layout()
        fig.savefig(folder / f"sensitivity-{horizon}.png", dpi=140)
        plt.close(fig)


def report(out, tab, selected, primary, bootstrap):
    lines = [
        "# SR3 macro-revision experiment",
        "",
        "Final holdout untouched. Training-selected specification and fixed primary are reported separately. Settlement fills, margin and event-time availability remain modelling limitations.",
        "",
    ]
    if primary:
        row = primary[0]
        lines += [
            "## Fixed primary",
            "",
            f"Validation trades: {row['trades']}; net P&L: ${row['net_pnl']:.2f}; Sharpe: {row['sharpe']}; maximum drawdown: {100 * abs(row['max_drawdown']):.2f}%.",
            "",
        ]
    if len(selected):
        winner = selected.iloc[0]
        keys = ["series", "clip", "decay", "tenor", "horizon", "threshold", "cost_bp"]
        matches = tab.split.eq("validation")
        for key in keys:
            if key == "clip":
                matches &= (
                    tab[key].isna()
                    if pd.isna(winner[key])
                    else tab[key].eq(winner[key])
                )
            elif key == "series":
                matches &= tab[key].apply(lambda x: x == winner["series"])
            else:
                matches &= tab[key].eq(winner[key])
        lines += [
            "## Training selection",
            "",
            str(winner[keys].to_dict()),
            "",
            tab[matches][["trades", "net_pnl", "sharpe", "max_drawdown"]].to_csv(
                index=False
            ),
            "",
        ]
    lines += [
        "## Evidence",
        "",
        "Inspect event_regressions.csv and bootstrap-results.json for expected-positive slopes and adjusted intervals. Inspect robustness_grid.csv for nearby horizons/tenors, costs and series exclusions. Trading uses one non-overlapping contract; event-study targets may overlap.",
        "",
        "Figures are in figures/. Raw ALFRED vintages, benchmark exclusions and five-date audit remain in the context dataset. No final-test alpha claim is made.",
    ]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n")
    images = "".join(
        f'<h3>{p.stem}</h3><img width="900" src="figures/{p.name}">'
        for p in sorted((out / "figures").glob("*.png"))
    )
    (out / "dashboard.html").write_text(
        '<html><meta charset="utf-8"><title>SR3 macro revisions</title><body><h1>SR3 macro revisions</h1><p>Full tables: robustness_grid.csv and event_regressions.csv. Final holdout untouched.</p>'
        + images
        + "</body></html>"
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["acquire", "prepare", "run", "status"])
    p.add_argument("--workers", type=int, default=4)
    args = p.parse_args()
    cfg = json.loads(CONFIG.read_text())
    if args.action == "status":
        out = ROOT / "results" / cfg["batch_id"]
        progress = out / "progress.json"
        print(
            progress.read_text()
            if progress.exists()
            else "No completed bootstrap jobs yet. Read run.log and cases/*/*/bootstrap/progress.json."
        )
        return
    commit, hashes = frozen()
    if not 1 <= args.workers <= 8:
        raise ValueError("workers must be 1–8")
    if args.action == "acquire":
        acquire(cfg, DATA)
    elif args.action == "prepare":
        prepare(cfg)
    else:
        run(cfg, commit, hashes, args.workers)


if __name__ == "__main__":
    main()
