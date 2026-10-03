"""Run declared development sensitivity cells; never select a new primary."""

import argparse
import json
import os
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def plot_heatmap(data, index, columns, values, output, title):
    pivot = (
        data.pivot(index=index, columns=columns, values=values)
        .sort_index()
        .sort_index(axis=1)
    )
    fig, ax = plt.subplots(figsize=(6, 5))
    bound = max(float(pivot.abs().max().max()), 1e-8)
    image = ax.imshow(pivot, cmap="RdBu", aspect="auto", vmin=-bound, vmax=bound)
    ax.set_xticks(range(len(pivot.columns)), pivot.columns)
    ax.set_yticks(range(len(pivot.index)), pivot.index)
    ax.set_xlabel(columns)
    ax.set_ylabel(index)
    ax.set_title(title)
    for y in range(len(pivot.index)):
        for x in range(len(pivot.columns)):
            v = pivot.iloc[y, x]
            ax.text(
                x,
                y,
                f"{v:.3g}" if pd.notna(v) else "failed",
                ha="center",
                va="center",
                fontsize=8,
            )
    fig.colorbar(image, ax=ax)
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-prefix", required=True)
    parser.add_argument(
        "--stage", choices=["smoke", "development"], default="development"
    )
    args = parser.parse_args()
    cfg = json.loads((ROOT / "research/configs/dax.json").read_text())
    out = ROOT / "results" / args.run_prefix
    out.mkdir(exist_ok=False)
    declared = {(l, h) for l in [1, 2, 5, 10] for h in [1, 2, 5, 10]}
    declared |= {(l, h) for l in [4, 5, 6] for h in [4, 5, 6]}
    rows = []
    for lookback, horizon in sorted(declared):
        variant = dict(cfg, lookback_seconds=lookback, horizon_seconds=horizon)
        path = out / f"config-L{lookback}-H{horizon}.json"
        path.write_text(json.dumps(variant, indent=2))
        run_id = f"{args.run_prefix}-L{lookback}-H{horizon}"
        extra = [] if (lookback, horizon) == (5, 5) else ["--forecast-only"]
        proc = subprocess.run(
            [
                "uv",
                "run",
                "--locked",
                "python",
                "run_all.py",
                "--stage",
                args.stage,
                "--config",
                str(path),
                "--run-id",
                run_id,
            ]
            + extra,
            cwd=ROOT,
            env=dict(os.environ, UV_CACHE_DIR="/private/tmp/gqh-uv-cache"),
            check=False,
            capture_output=True,
            text=True,
        )
        (out / f"{run_id}.log").write_text(proc.stdout + proc.stderr)
        row = {
            "lookback_seconds": lookback,
            "horizon_seconds": horizon,
            "status": "failed",
            "incremental_oos_r2": None,
            "run_id": run_id,
        }
        result_path = ROOT / "results" / run_id / "metrics.json"
        if proc.returncode == 0:
            result = json.loads(result_path.read_text())
            row.update(
                status="completed",
                incremental_oos_r2=result["forecast"]["incremental_oos_r2"],
            )
        rows.append(row)
        pd.DataFrame(rows).to_csv(out / "horizon-grid.csv", index=False)
        print(run_id, row["status"], row["incremental_oos_r2"], flush=True)
    data = pd.DataFrame(rows)
    for name, values in [("local", [4, 5, 6]), ("declared", [1, 2, 5, 10])]:
        subset = data[
            data.lookback_seconds.isin(values) & data.horizon_seconds.isin(values)
        ]
        plot_heatmap(
            subset,
            "lookback_seconds",
            "horizon_seconds",
            "incremental_oos_r2",
            out / f"{name}-forecast-heatmap.png",
            "Validation forecast improvement; primary L=5,H=5",
        )
    primary = json.loads(
        (ROOT / "results" / f"{args.run_prefix}-L5-H5" / "metrics.json").read_text()
    )
    costs = pd.DataFrame([r for r in primary["execution"] if r["model"] == "M1"])
    costs.to_csv(out / "cost-buffer-grid.csv", index=False)
    plot_heatmap(
        costs,
        "fee_eur_per_side",
        "buffer_ticks",
        "mean_daily_eur",
        out / "cost-buffer-heatmap.png",
        "Validation daily net EUR; illustrative fees",
    )


if __name__ == "__main__":
    main()
