"""Describe primary validation errors by month, clock hour and lagged move."""

import argparse
import json
from pathlib import Path

import pandas as pd

from src.analysis import forecast_metrics
from src.signals import BASE, CROSS, fit, predict


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    root = parser.parse_args().run_dir.resolve()
    cfg = json.loads((root / "config.json").read_text())
    train = pd.read_parquet(root / "training-features.parquet")
    valid = pd.read_parquet(root / "validation-features.parquet")
    p0 = predict(fit(train, BASE), valid, BASE)
    p1 = predict(fit(train, CROSS), valid, CROSS)
    edges = train.R_FDAX.abs().quantile([1 / 3, 2 / 3]).to_numpy()
    level = pd.cut(
        valid.R_FDAX.abs(),
        [-float("inf"), *edges, float("inf")],
        labels=["low", "medium", "high"],
    )
    rows = []
    groups = [
        ("month", valid.index.strftime("%Y-%m")),
        ("Berlin hour", valid.index.tz_convert("Europe/Berlin").hour),
        ("lagged move regime", level),
    ]
    for name, group in groups:
        for label in pd.Series(group, index=valid.index).dropna().unique():
            mask = group == label
            score, _ = forecast_metrics(
                valid.loc[mask], p0.loc[mask].to_numpy(), p1.loc[mask].to_numpy(), cfg
            )
            rows.append(
                {
                    "group": name,
                    "label": str(label),
                    "observations": score["observations"],
                    "incremental_oos_r2": score["incremental_oos_r2"],
                    "interval": json.dumps(score["daily_loss_improvement_ci"]),
                }
            )
    pd.DataFrame(rows).to_csv(root / "forecast-regimes.csv", index=False)
    (root / "regime-definition.json").write_text(
        json.dumps(
            {
                "lagged_abs_FDAX_move_training_tertiles": edges.tolist(),
                "scope": "secondary descriptive; no retuning",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
