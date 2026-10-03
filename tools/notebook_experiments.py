"""Notebook diagnostics and a frozen, regularised curve experiment."""

import csv
import fcntl
import importlib.metadata
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.batch_research import canonical, digest, file_hash, write_json
from src.sr3_macro.model import trade

DATA = ROOT / ".agent-work/shared/data/sr3-macro-revisions"
ORIGINAL = ROOT / "results/sr3-macro-revisions-v1"


def save_figure(fig, out, name):
    (out / "figures").mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out / "figures" / f"{name}.png", dpi=150)
    plt.show()


def correlations(frame, x="raw_signal", y="target_bp"):
    usable = frame[[x, y]].dropna()
    return {
        "events": len(usable),
        "IC": usable[x].corr(usable[y]),
        "rank_IC": usable[x].corr(usable[y], method="spearman"),
    }


def case(tenor):
    params = {
        "series": ["PAYEMS", "RSAFS", "INDPRO"],
        "clip": 3.0,
        "decay": 30,
        "tenor": tenor,
        "horizon": 10,
    }
    return pd.read_parquet(ORIGINAL / "cases" / digest(params)[:20] / "events.parquet")


def original_eda(out):
    out.mkdir(parents=True, exist_ok=True)
    rev = pd.read_parquet(DATA / "revision_events.parquet")
    frame = case(360)
    frame["sample"] = np.where(
        frame.exit < pd.Timestamp("2023-01-01", tz="UTC"),
        "training",
        "reused_validation",
    )
    frame = frame[
        (frame.entry < pd.Timestamp("2023-01-01", tz="UTC"))
        == (frame.exit < pd.Timestamp("2023-01-01", tz="UTC"))
    ]
    frame.to_csv(out / "eda-events.csv", index=False)
    rev.to_csv(out / "eda-revisions.csv", index=False)
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    for ax, name in zip(axes[0], ["PAYEMS", "RSAFS", "INDPRO"], strict=True):
        values = rev.loc[rev.series.eq(name), "z"].dropna()
        ax.hist(values, bins=40)
        ax.set(
            title=f"{name}, n={len(values)}",
            xlabel="Prior-history revision z-score",
            ylabel="Count",
        )
    for ax, col in zip(axes[1, :2], ["raw_signal", "target_bp"], strict=True):
        for sample, f in frame.groupby("sample"):
            ax.hist(f[col], bins=25, alpha=0.5, label=f"{sample}, n={len(f)}")
        ax.set(xlabel=col, ylabel="Events")
        ax.legend()
    for sample, f in frame.groupby("sample"):
        axes[1, 2].scatter(f.raw_signal, f.target_bp, s=15, label=sample, alpha=0.6)
    axes[1, 2].set(xlabel="Revision pressure", ylabel="10-session rate change (bp)")
    axes[1, 2].legend()
    save_figure(fig, out, "histograms-scatter")
    rows = [{"sample": s, **correlations(f)} for s, f in frame.groupby("sample")]
    ic = pd.DataFrame(rows)
    ic.to_csv(out / "IC.csv", index=False)
    frame["month"] = frame.entry.dt.strftime("%Y-%m")
    monthly = pd.DataFrame(
        [
            {"month": m, **correlations(f)}
            for m, f in frame.groupby("month")
            if len(f) >= 5
        ]
    )
    monthly.to_csv(out / "monthly-IC.csv", index=False)
    fig, ax = plt.subplots(figsize=(12, 3))
    if len(monthly):
        ax.plot(
            pd.to_datetime(monthly.month),
            monthly.rank_IC,
            label="Monthly rank IC; at least 5 events",
        )
        ax.legend()
    ax.axhline(0, color="black", lw=0.7)
    ax.set(ylabel="Rank IC", title="Overlapping event targets; descriptive IC")
    save_figure(fig, out, "monthly-IC")
    grid = pd.read_csv(ORIGINAL / "robustness_grid.csv")
    grid.to_csv(out / "original-grid.csv", index=False)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    base = grid[(grid.cost_bp == 1) & (grid.trades >= 10)]
    for sample, f in base.groupby("split"):
        axes[0].hist(f.sharpe.dropna(), bins=40, alpha=0.5, label=sample)
    axes[0].legend()
    axes[0].set(xlabel="Net annualised Sharpe", ylabel="Cells with at least 10 trades")
    sensitivity = grid[
        (grid.split == "validation")
        & (grid.threshold == 1)
        & (grid.horizon == 10)
        & (grid.cost_bp == 1)
        & (grid["clip"] == 3)
        & (grid.series == str(["PAYEMS", "RSAFS", "INDPRO"]))
    ]
    heat = sensitivity.pivot(index="decay", columns="tenor", values="net_pnl")
    if not heat.empty:
        image = axes[1].imshow(heat.to_numpy(), cmap="RdYlGn")
        fig.colorbar(image, ax=axes[1], label="Net P&L ($)")
        axes[1].set_xticks(range(len(heat.columns)), heat.columns)
        axes[1].set_yticks(range(len(heat.index)), heat.index)
    axes[1].set(
        xlabel="Tenor (days)",
        ylabel="Decay (days)",
        title="Reused-validation parameter sensitivity",
    )
    save_figure(fig, out, "selection-sensitivity")
    return ic


def fit_ridge(train, alpha):
    mean = float(train.raw_signal.mean())
    sd = float(train.raw_signal.std(ddof=0))
    if not np.isfinite(sd) or sd <= 0 or len(train) < 30:
        raise ValueError("Insufficient training variation/events")
    x = (train.raw_signal.to_numpy() - mean) / sd
    y = train.target_bp.to_numpy()
    intercept = float(y.mean())
    beta = float(x @ (y - intercept) / (x @ x + alpha))
    scale = float(np.std(intercept + beta * x))
    return {
        "mean": mean,
        "sd": sd,
        "intercept": intercept,
        "beta": beta,
        "forecast_sd": scale,
    }


def forecast(frame, fit):
    return fit["intercept"] + fit["beta"] * (frame.raw_signal - fit["mean"]) / fit["sd"]


def curve_experiment(out):
    out.mkdir(parents=True, exist_ok=True)
    near, far = case(180), case(360)
    paired = near.merge(
        far,
        on=["event_date", "entry", "exit"],
        suffixes=("_near", "_far"),
        validate="one_to_one",
    )
    paired = paired[paired.contract_near != paired.contract_far].copy()
    paired["contract"] = paired.contract_near + "|" + paired.contract_far
    paired["raw_signal"] = paired.raw_signal_near
    paired["target_bp"] = paired.target_bp_far - paired.target_bp_near
    paired = paired.sort_values("entry")
    train = paired[paired.exit < pd.Timestamp("2023-01-01", tz="UTC")]
    initial = train[train.exit < pd.Timestamp("2021-01-01", tz="UTC")]
    inner = train[train.entry >= pd.Timestamp("2021-01-01", tz="UTC")]
    valid = paired[paired.entry >= pd.Timestamp("2023-01-01", tz="UTC")]
    if initial.empty or inner.empty or valid.empty:
        raise ValueError(
            "Missing chronological fitting, inner-selection or validation sample"
        )
    prices = pd.read_parquet(DATA / "sr3_daily.parquet")
    if prices.trade_date.max() >= pd.Timestamp("2025-01-01", tz="UTC"):
        raise ValueError("Holdout data present")
    market = prices.set_index(["trade_date", "contract"]).price
    synthetic = []
    for pair, g in paired.groupby("contract"):
        n, f = g.iloc[0][["contract_near", "contract_far"]]
        spread = (
            market.xs(f, level="contract") - market.xs(n, level="contract")
        ).dropna()
        synthetic.append(
            pd.DataFrame(
                {
                    "trade_date": spread.index,
                    "contract": pair,
                    "price": spread.to_numpy(),
                }
            )
        )
    pair_prices = pd.concat(synthetic, ignore_index=True)
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    spec = ROOT / "research/hypotheses/sr3-curve-revisions.md"
    for p in [spec, Path(__file__).resolve()]:
        if (
            subprocess.check_output(
                ["git", "show", f"{commit}:{p.relative_to(ROOT)}"], cwd=ROOT
            )
            != p.read_bytes()
        ):
            raise ValueError("Commit hypothesis and implementation before running")
    config = {
        "alphas": [0, 1, 10, 100],
        "thresholds": [0.5, 1, 1.5],
        "costs_bp_per_leg": [0.5, 1, 2],
        "capital": 100000,
        "holdout_access": False,
        "validation_reused": True,
    }
    source_paths = [
        DATA / "sr3_daily.parquet",
        DATA / "revision_events.parquet",
        ORIGINAL / "manifest.json",
        ROOT / "uv.lock",
        spec,
        Path(__file__).resolve(),
    ]
    manifest = {
        "commit": commit,
        "config": config,
        "hashes": {str(p.relative_to(ROOT)): file_hash(p) for p in source_paths},
        "python_packages": {
            n: importlib.metadata.version(n) for n in ["numpy", "pandas", "matplotlib"]
        },
    }
    write_json(out / "manifest.json", manifest)
    paired.to_csv(out / "paired-events.csv", index=False)
    selection = []
    forecasts = []
    metrics = []
    curves = {}
    jobs = 0
    for alpha in config["alphas"]:
        fitted = fit_ridge(initial, alpha)
        pred = forecast(inner, fitted)
        selection.append(
            {
                "alpha": alpha,
                "inner_MSE": float(np.mean((pred - inner.target_bp) ** 2)),
                "constant_MSE": float(
                    np.mean((fitted["intercept"] - inner.target_bp) ** 2)
                ),
                "inner_events": len(inner),
            }
        )
        fitted = fit_ridge(train, alpha)
        for sample, f in [("training", train), ("reused_validation", valid)]:
            pred = forecast(f, fitted)
            prediction = f.copy()
            prediction["forecast_bp"] = pred
            prediction["signal"] = (
                pred / fitted["forecast_sd"] if fitted["forecast_sd"] > 1e-12 else 0.0
            )
            prediction.to_csv(out / f"forecasts-{alpha}-{sample}.csv", index=False)
            forecasts.append(
                {
                    "alpha": alpha,
                    "sample": sample,
                    "beta": fitted["beta"],
                    "MSE": float(np.mean((pred - f.target_bp) ** 2)),
                    "constant_MSE": float(
                        np.mean((fitted["intercept"] - f.target_bp) ** 2)
                    ),
                    **correlations(prediction, "forecast_bp", "target_bp"),
                }
            )
            begin, end = (
                (
                    pd.Timestamp("2018-05-07", tz="UTC"),
                    pd.Timestamp("2023-01-01", tz="UTC"),
                )
                if sample == "training"
                else (
                    pd.Timestamp("2023-01-01", tz="UTC"),
                    pd.Timestamp("2025-01-01", tz="UTC"),
                )
            )
            for threshold in config["thresholds"]:
                for cost in config["costs_bp_per_leg"]:
                    key = f"a{alpha}-t{threshold}-c{cost}-{sample}"
                    m, r, t = trade(
                        config, prediction, pair_prices, threshold, 2 * cost, begin, end
                    )
                    exposure = pd.Series(0.0, index=pd.to_datetime(r.date))
                    for tr in t:
                        exposure.loc[
                            (exposure.index >= pd.Timestamp(tr["entry"]))
                            & (exposure.index < pd.Timestamp(tr["exit"]))
                        ] = 2
                    r["gross_contract_exposure"] = exposure.to_numpy()
                    r["drawdown"] = (
                        r.equity / r.equity.cummax().clip(lower=config["capital"]) - 1
                    )
                    r["rolling_sharpe_126"] = (
                        r["return"].rolling(126).mean()
                        / r["return"].rolling(126).std()
                        * np.sqrt(252)
                    )
                    r.to_csv(out / f"returns-{key}.csv", index=False)
                    pd.DataFrame(t).to_csv(out / f"trades-{key}.csv", index=False)
                    metrics.append(
                        {
                            "job_id": key,
                            "alpha": alpha,
                            "threshold": threshold,
                            "cost_bp_per_leg": cost,
                            "sample": sample,
                            "mean_gross_contract_exposure": float(exposure.mean()),
                            "turnover_contracts": 4 * len(t),
                            **m,
                        }
                    )
                    if threshold == 1 and cost == 1:
                        curves[(alpha, sample)] = r
                    jobs += 1
                    print(
                        f"[{jobs}/72] {key}: trades={m['trades']}, net=${m['net_pnl']:.2f}",
                        flush=True,
                    )
    pd.DataFrame(selection).to_csv(out / "inner-selection.csv", index=False)
    chosen = min(selection, key=lambda r: (r["inner_MSE"], r["alpha"]))["alpha"]
    pd.DataFrame(forecasts).to_csv(out / "forecast-metrics.csv", index=False)
    table = pd.DataFrame(metrics)
    table.to_csv(out / "metrics.csv", index=False)
    ledger = ROOT / "research/experiments.csv"
    with ledger.open("r+", newline="") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        existing = {r["trial_id"] for r in reader}
        stream.seek(0, 2)
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        for row in metrics:
            tid = out.name + "/" + row["job_id"]
            if tid in existing:
                continue
            writer.writerow(
                {
                    "trial_id": tid,
                    "timestamp_utc": pd.Timestamp.now(tz="UTC").isoformat(),
                    "hypothesis_commit": "bf416ab",
                    "code_commit": commit,
                    "data_sha256": digest(manifest["hashes"]),
                    "config_sha256": digest(config),
                    "sample": row["sample"],
                    "parameters": canonical(
                        {k: row[k] for k in ["alpha", "threshold"]}
                    ),
                    "cost_model": f"{row['cost_bp_per_leg']} bp per leg round trip",
                    "result_path": str(out.relative_to(ROOT)),
                    "status": "completed",
                    "conclusion": canonical(row),
                    "holdout_access": "false",
                }
            )
    fig, axes = plt.subplots(3, 2, figsize=(14, 11))
    for (alpha, sample), r in curves.items():
        if sample != "reused_validation":
            continue
        d = pd.to_datetime(r.date)
        for ax, col in zip(
            axes[:, 0], ["equity", "drawdown", "rolling_sharpe_126"], strict=True
        ):
            ax.plot(d, r[col], label=f"alpha={alpha}")
    for ax, label in zip(
        axes[:, 0],
        ["Equity ($), 1 bp/leg", "Drawdown (fraction)", "126-session rolling Sharpe"],
        strict=True,
    ):
        ax.set(ylabel=label)
        ax.legend()
    chosen_returns = curves[(chosen, "reused_validation")]
    axes[0, 1].hist(chosen_returns["return"], bins=40)
    axes[0, 1].set(xlabel="Daily net return", ylabel="Sessions")
    axes[1, 1].plot(
        pd.to_datetime(chosen_returns.date), chosen_returns.gross_contract_exposure
    )
    axes[1, 1].set(ylabel="Gross contract exposure")
    heat = table[
        (table["sample"] == "reused_validation") & (table.cost_bp_per_leg == 1)
    ].pivot(index="alpha", columns="threshold", values="net_pnl")
    im = axes[2, 1].imshow(heat.to_numpy(), cmap="RdYlGn")
    fig.colorbar(im, ax=axes[2, 1], label="Net P&L ($)")
    axes[2, 1].set_xticks(range(len(heat.columns)), heat.columns)
    axes[2, 1].set_yticks(range(len(heat.index)), heat.index)
    axes[2, 1].set(xlabel="Threshold", ylabel="Ridge alpha")
    save_figure(fig, out, "curve-diagnostics")
    selected = table[
        (table.alpha == chosen) & (table.threshold == 1) & (table.cost_bp_per_leg == 1)
    ]
    (out / "REPORT.md").write_text(
        "# SR3 curve revisions\n\nInner-selected ridge penalty: "
        + str(chosen)
        + "\n\n"
        + selected.to_string(index=False)
        + "\n\n2023–2024 is reused validation. Holdout untouched. Event targets overlap; IC is descriptive. Fills and two-leg execution are modelled.\n"
    )
    write_json(
        out / "summary.json",
        {
            "completed": jobs,
            "selected_alpha": chosen,
            "holdout_access": False,
            "validation_reused": True,
        },
    )
    return table, pd.DataFrame(forecasts), pd.DataFrame(selection)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="sr3-curve-notebook-v1")
    args = parser.parse_args()
    if Path(args.run_id).name != args.run_id or args.run_id in {".", ".."}:
        raise ValueError("run-id must be a directory name")
    output = ROOT / "results" / args.run_id
    original_eda(output)
    curve_experiment(output)
