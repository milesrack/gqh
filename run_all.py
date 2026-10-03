"""Explicit development evaluation; never downloads or opens the final holdout."""

import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis import block_interval, forecast_metrics
from src.backtest import metrics, simulate
from src.market_data import prepare
from src.signals import BASE, CROSS, features, fit, predict

ROOT = Path(__file__).resolve().parent


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def encode(value):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(type(value).__name__)


def run(args, cfg, output):
    if cfg.get("final_holdout_authorised"):
        raise ValueError("This development runner cannot evaluate a final holdout")
    paths, identity = prepare(args.data_dir, cfg, smoke=args.stage == "smoke")
    days = [
        p.stem
        for p in paths
        if (cfg["development_start"] if args.stage == "smoke" else cfg["history_start"])
        <= p.stem
        < cfg["development_end_exclusive"]
    ]
    if len(days) < 4:
        raise ValueError("At least four development sessions required")
    if args.stage == "smoke":
        cut = int(len(days) * 0.6)
        train_days, valid_days = days[:cut], days[cut:]
    else:
        train_days = [d for d in days if d < cfg["validation_start"]]
        valid_days = [
            d for d in days if cfg["validation_start"] <= d < cfg["holdout_start"]
        ]

    frames, books, audits = {}, {}, {}
    paths_by_day = {p.stem: p for p in paths}

    for day in days:
        path = paths_by_day[day]
        frame, book, audit = features(
            pd.read_parquet(path).sort_values("ts_recv", kind="stable"), cfg, day
        )
        frames[day], books[day], audits[day] = frame, book, audit

    train = pd.concat([frames[d] for d in train_days]).dropna(subset=["Y"])
    validation = pd.concat([frames[d] for d in valid_days]).dropna(subset=["Y"])
    if train.empty or validation.empty:
        raise ValueError("No eligible training or validation observations")
    m0, m1 = fit(train, BASE), fit(train, CROSS)
    p0, p1 = predict(m0, validation, BASE), predict(m1, validation, CROSS)
    score, losses = forecast_metrics(validation, p0.to_numpy(), p1.to_numpy(), cfg)
    wald = m1.wald_test("OF_FDAX = 0, OF_FDXM = 0", scalar=True)
    models = {
        "baseline": m0.params.to_dict(),
        "cross": m1.params.to_dict(),
        "cross_flow_wald_p": float(wald.pvalue),
        "condition_number": float(m1.condition_number),
    }
    execution = []
    for name, model, cols in (
        [] if args.forecast_only else [("M0", m0, BASE), ("M1", m1, CROSS)]
    ):
        for fee in cfg["fee_scenarios_eur_per_side"]:
            for buffer in cfg["buffer_ticks"]:
                trades = pd.concat(
                    [
                        simulate(
                            frames[d],
                            predict(model, frames[d], cols),
                            books[d],
                            cfg,
                            fee,
                            buffer,
                        )
                        for d in valid_days
                    ],
                    ignore_index=True,
                )
                summary, daily = metrics(
                    trades, valid_days, cfg["reporting_capital_eur"]
                )
                summary.update(
                    model=name,
                    fee_eur_per_side=fee,
                    buffer_ticks=buffer,
                    illustrative_fee=True,
                    daily_mean_ci=block_interval(daily, cfg),
                )
                execution.append(summary)
                stem = f"{name}-fee{fee}-buffer{buffer}"
                trades.to_csv(output / f"{stem}-trades.csv", index=False)
                daily.to_csv(output / f"{stem}-daily.csv")
    stress = []
    # Fixed five/five model, zero buffer; scenarios do not choose a winner.
    for latency in [] if args.forecast_only else cfg["latency_sensitivity_ms"]:
        for slippage in cfg["slippage_ticks_per_side"]:
            for multiplier in [1, 2]:
                trades = pd.concat(
                    [
                        simulate(
                            frames[d],
                            predict(m1, frames[d], CROSS),
                            books[d],
                            cfg,
                            fee=1 * multiplier,
                            buffer=0,
                            latency_ms=latency,
                            slippage=slippage * multiplier,
                            spread_multiplier=multiplier,
                        )
                        for d in valid_days
                    ],
                    ignore_index=True,
                )
                summary, daily = metrics(
                    trades, valid_days, cfg["reporting_capital_eur"]
                )
                summary.update(
                    latency_ms=latency,
                    slippage_index_points_per_side=slippage,
                    cost_multiplier=multiplier,
                    illustrative_fee=True,
                )
                stress.append(summary)
    pd.DataFrame(stress).to_csv(output / "execution-stress.csv", index=False)
    result = {
        "stage": args.stage,
        "holdout_access": False,
        "data_identity": identity,
        "train_days": train_days,
        "validation_days": valid_days,
        "forecast": score,
        "models": models,
        "execution": execution,
        "execution_stress": stress,
        "data_audit": audits,
        "capital_metrics_status": "EUR10000 scenario; broker margin and fees unverified",
        "deployment_status": "unvalidated; development evidence only",
    }
    losses.to_csv(output / "daily-forecast-loss.csv")
    (output / "metrics.json").write_text(
        json.dumps(result, indent=2, default=encode, allow_nan=False)
    )
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=ROOT / "research/configs/dax.json")
    p.add_argument(
        "--data-dir",
        type=Path,
        default=ROOT / ".agent-work/shared/data/dax-cross-contract-flow",
    )
    p.add_argument("--run-id", required=True)
    p.add_argument("--stage", choices=["smoke", "development"], default="development")
    p.add_argument("--forecast-only", action="store_true")
    args = p.parse_args()
    if "/" in args.run_id or args.run_id in [".", ".."]:
        p.error("run-id must be one directory name")
    cfg = json.loads(args.config.read_text())
    output = ROOT / "results" / args.run_id
    output.mkdir(exist_ok=False)
    hypothesis = git("log", "-1", "--format=%H", "--", "research/hypothesis.md")
    code = git("rev-parse", "HEAD")
    (output / "config.json").write_text(json.dumps(cfg, indent=2))
    versions = {
        k: importlib.metadata.version(k)
        for k in ["databento", "numpy", "pandas", "scipy", "statsmodels"]
    }
    (output / "provenance.json").write_text(
        json.dumps(
            {
                "hypothesis_commit": hypothesis,
                "code_commit": code,
                "dirty": bool(git("status", "--porcelain")),
                "python": platform.python_version(),
                "packages": versions,
            },
            indent=2,
        )
    )
    row = {
        "trial_id": args.run_id,
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "hypothesis_commit": hypothesis,
        "code_commit": code,
        "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
        "sample": args.stage,
        "parameters": json.dumps(
            {
                "config": str(args.config.relative_to(ROOT)),
                "forecast_only": args.forecast_only,
            }
        ),
        "cost_model": "illustrative fee scenarios; observed spread",
        "result_path": str(output.relative_to(ROOT)),
        "holdout_access": "false",
    }
    try:
        result = run(args, cfg, output)
        row.update(
            status="completed",
            data_sha256=result["data_identity"],
            conclusion=json.dumps(result["forecast"], default=encode),
        )
        print(json.dumps(result["forecast"], indent=2, default=encode))
    except Exception as error:
        row.update(status="failed", conclusion=f"{type(error).__name__}: {error}")
        (output / "failure.txt").write_text(row["conclusion"])
        raise
    finally:
        with (ROOT / "research/experiments.csv").open() as stream:
            fields = next(csv.reader(stream))
        with (ROOT / "research/experiments.csv").open("a") as stream:
            csv.DictWriter(stream, fieldnames=fields).writerow(row)
        with (output / "trial.json").open("w") as stream:
            json.dump(row, stream, indent=2)


if __name__ == "__main__":
    main()
