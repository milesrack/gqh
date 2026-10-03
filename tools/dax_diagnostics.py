"""Secondary directed tests and training-only standardised disagreement."""

import argparse
import csv
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from statsmodels.stats.multitest import multipletests

from src.analysis import forecast_metrics
from src.signals import fit, predict


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", type=Path, required=True)
    args = p.parse_args()
    args.run_dir = args.run_dir.resolve()
    cfg = json.loads((args.run_dir / "config.json").read_text())
    train = pd.read_parquet(args.run_dir / "training-features.parquet")
    valid = pd.read_parquet(args.run_dir / "validation-features.parquet")
    products = cfg["products"]
    rows = []
    for target in products:
        baseline = [f"OF_{target}", f"BI_{target}"] + [f"R_{i}" for i in products]
        for predictor in products:
            if target == predictor:
                continue
            columns = baseline + [f"OF_{predictor}"]
            t = train.assign(Y=train[f"Y_{target}"]).dropna(subset=columns + ["Y"])
            v = valid.assign(Y=valid[f"Y_{target}"]).dropna(subset=columns + ["Y"])
            m0, m1 = fit(t, baseline), fit(t, columns)
            score, _ = forecast_metrics(
                v,
                predict(m0, v, baseline).to_numpy(),
                predict(m1, v, columns).to_numpy(),
                cfg,
            )
            rows.append(
                {
                    "predictor": predictor,
                    "target": target,
                    "p_value": float(m1.pvalues[f"OF_{predictor}"]),
                    "incremental_oos_r2": score["incremental_oos_r2"],
                    "observations": len(v),
                }
            )
    adjusted = multipletests([r["p_value"] for r in rows], method="holm")[1]
    for row, pvalue in zip(rows, adjusted, strict=True):
        row["holm_p_value"] = pvalue
    pd.DataFrame(rows).to_csv(
        args.run_dir / "secondary-direction-matrix.csv", index=False
    )
    # Standardisation never uses validation moments.
    flow = [f"OF_{i}" for i in products]
    mean = train[flow].mean()
    sd = train[flow].std(ddof=0)
    if (sd <= 0).any():
        raise ValueError("Undefined training flow standardisation")
    tz = (train[flow] - mean) / sd
    vz = (valid[flow] - mean) / sd
    t = train.assign(G=(tz.OF_FDAX + tz.OF_FDXM) / 2 - tz.OF_FDXS)
    v = valid.assign(G=(vz.OF_FDAX + vz.OF_FDXM) / 2 - vz.OF_FDXS)
    controls = ["OF_FDXS", "BI_FDXS", "R_FDXS", "R_FDAX", "R_FDXM"]
    m0, m1 = fit(t, controls), fit(t, controls + ["G"])
    score, _ = forecast_metrics(
        v,
        predict(m0, v, controls).to_numpy(),
        predict(m1, v, controls + ["G"]).to_numpy(),
        cfg,
    )
    result = {
        "standardisation_mean": mean.to_dict(),
        "standardisation_sd": sd.to_dict(),
        "disagreement_coefficient": float(m1.params["G"]),
        "p_value": float(m1.pvalues["G"]),
        "forecast": score,
        "scope": "secondary validation, not final holdout",
    }
    (args.run_dir / "disagreement-diagnostic.json").write_text(
        json.dumps(result, indent=2)
    )

    # A one-day shift keeps intraday ordering; exact same clock times only.
    def shifted(frame):
        days = sorted(frame.day.unique())
        previous = {day: days[i - 1] for i, day in enumerate(days)}
        result = frame.copy()
        clock = frame.index.strftime("%H:%M:%S")
        lookup = pd.DataFrame(
            {"day": frame.day, "clock": clock, "D": frame.OF_FDAX, "M": frame.OF_FDXM}
        )
        lookup = lookup.set_index(["day", "clock"])
        for field, name in [("OF_FDAX", "D"), ("OF_FDXM", "M")]:
            keys = pd.MultiIndex.from_arrays([frame.day.map(previous), clock])
            result[field] = lookup[name].reindex(keys).to_numpy()
        return result

    cols = controls + ["OF_FDAX", "OF_FDXM"]
    ts = shifted(train).dropna(subset=cols + ["Y"])
    vs = shifted(valid).dropna(subset=cols + ["Y"])
    pm = fit(ts, cols)
    bm = fit(ts, controls)
    placebo, _ = forecast_metrics(
        vs, predict(bm, vs, controls).to_numpy(), predict(pm, vs, cols).to_numpy(), cfg
    )
    real_train, real_valid = train.loc[ts.index], valid.loc[vs.index]
    real_m = fit(real_train, cols)
    real_b = fit(real_train, controls)
    matched_real, _ = forecast_metrics(
        real_valid,
        predict(real_b, real_valid, controls).to_numpy(),
        predict(real_m, real_valid, cols).to_numpy(),
        cfg,
    )
    (args.run_dir / "day-shift-placebo.json").write_text(
        json.dumps({"shifted": placebo, "unshifted_same_rows": matched_real}, indent=2)
    )
    root = Path(__file__).resolve().parents[1]
    provenance = json.loads((args.run_dir / "provenance.json").read_text())
    metadata = json.loads((args.run_dir / "metrics.json").read_text())
    ledger = root / "research/experiments.csv"
    with ledger.open() as stream:
        fields = next(csv.reader(stream))
    code = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    diagnostics = rows + [
        {"diagnostic": "disagreement", "result": result},
        {"diagnostic": "day_shift", "result": placebo},
    ]
    with ledger.open("a") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        for i, diagnostic in enumerate(diagnostics):
            writer.writerow(
                {
                    "trial_id": f"{args.run_dir.name}-secondary-{i}",
                    "timestamp_utc": datetime.now(UTC).isoformat(),
                    "hypothesis_commit": provenance["hypothesis_commit"],
                    "code_commit": code,
                    "config_sha256": hashlib.sha256(
                        (args.run_dir / "config.json").read_bytes()
                    ).hexdigest(),
                    "sample": metadata["stage"],
                    "parameters": json.dumps(diagnostic, default=float),
                    "cost_model": "forecast diagnostic only",
                    "result_path": str(args.run_dir.relative_to(root)),
                    "holdout_access": "false",
                    "status": "completed",
                    "data_sha256": metadata["data_identity"],
                    "conclusion": "secondary; primary unchanged",
                }
            )
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
