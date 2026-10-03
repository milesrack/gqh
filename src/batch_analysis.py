"""Paired uncertainty and training-grid reports; never select validation winners."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm


def _returns(path):
    frame = pd.read_csv(path)
    if not {"date", "return"}.issubset(frame):
        raise ValueError("Return CSV requires date and net return columns")
    dates = pd.DatetimeIndex(pd.to_datetime(frame.date, utc=True, errors="raise"))
    if dates.hasnans or dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError("Dates must be unique and strictly ordered")
    values = pd.to_numeric(frame["return"], errors="raise").to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError(
            "Returns must be finite; no missing observations may be dropped"
        )
    return dates, values


def compare_returns(
    strategy_csv, control_csv, trials, block_size=20, draws=2000, seed=151
):
    """Arithmetic annual252 inference; paired circular blocks, bounded draw memory.

    Nulls indicate unidentified estimates. Bonferroni percentile intervals are
    exploratory when their tails are below the bootstrap's Monte Carlo resolution.
    """
    for name, value, minimum in [
        ("trials", trials, 1),
        ("block_size", block_size, 1),
        ("draws", draws, 100),
    ]:
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValueError(f"{name} must be an integer >= {minimum}")
    dates, strategy = _returns(strategy_csv)
    control_dates, control = _returns(control_csv)
    if not dates.equals(control_dates):
        raise ValueError(
            "Strategy and control must have exactly the same ordered observations"
        )
    n = len(strategy)
    excess = strategy - control
    reasons = []
    result = {
        "observations": n,
        "annualisation": 252,
        "trials": trials,
        "block_size": block_size,
        "draws": draws,
        "seed": seed,
        "date_start": dates[0].isoformat() if n else None,
        "date_end": dates[-1].isoformat() if n else None,
        "net_mean": float(strategy.mean() * 252) if n else None,
        "control_mean": float(control.mean() * 252) if n else None,
        "excess_mean": float(excess.mean() * 252) if n else None,
        "bootstrap": None,
        "hac": None,
        "reasons": reasons,
    }
    if n and np.all(strategy == 0):
        reasons.append("strategy_is_cash")
    if n and np.all(control == 0):
        reasons.append("control_is_cash")
    constant_control = n < 2 or np.ptp(control) <= np.finfo(float).eps * max(
        1.0, np.max(np.abs(control), initial=0)
    )
    if constant_control:
        reasons.append("constant_control_alpha_beta_unidentified")
    if n < max(2 * block_size, 22):
        reasons.append("insufficient_data_for_fixed_block_and_HAC20")
        return result
    rng = np.random.default_rng(seed)
    # One O(N) resample at a time, not draws-by-N; retain only two scalar arrays.
    sampled = np.empty((draws, 2))
    blocks = int(np.ceil(n / block_size))
    offsets = np.arange(block_size)
    for draw in range(draws):
        starts = rng.integers(0, n, size=blocks)
        indices = ((starts[:, None] + offsets) % n).reshape(-1)[:n]
        sampled[draw] = (strategy[indices].mean() * 252, excess[indices].mean() * 252)
    alpha = 0.05 / trials
    result["adjusted_tail_resolved"] = draws * alpha / 2 >= 1
    if not result["adjusted_tail_resolved"]:
        reasons.append("adjusted_bootstrap_tail_below_Monte_Carlo_resolution")
    result["bootstrap"] = {}
    for column, name in enumerate(("net", "excess")):
        result["bootstrap"][name] = {
            "ci95": np.quantile(sampled[:, column], [0.025, 0.975]).tolist(),
            "ci_grid_adjusted": np.quantile(
                sampled[:, column], [alpha / 2, 1 - alpha / 2]
            ).tolist(),
            "grid_confidence": 1 - alpha,
        }
    if not constant_control:
        fit = sm.OLS(strategy, sm.add_constant(control, has_constant="add")).fit(
            cov_type="HAC",
            cov_kwds={"maxlags": 20, "use_correction": True},
            use_t=False,
        )
        ci = fit.conf_int(alpha=0.05)
        adjusted = fit.conf_int(alpha=alpha)
        result["hac"] = {
            "lags": 20,
            "alpha_daily": float(fit.params[0]),
            "alpha_annual": float(fit.params[0] * 252),
            "beta": float(fit.params[1]),
            "alpha_p": float(fit.pvalues[0]),
            "beta_p": float(fit.pvalues[1]),
            "alpha_ci95_annual": (ci[0] * 252).tolist(),
            "beta_ci95": ci[1].tolist(),
            "alpha_ci_grid_adjusted_annual": (adjusted[0] * 252).tolist(),
        }
        # Perfect fits can make inference numerically unidentified, never JSON NaN.
        if not all(np.isfinite(value).all() for value in result["hac"].values()):
            result["hac"] = None
            reasons.append("HAC_inference_numerically_unidentified")
    json.dumps(result, allow_nan=False)
    return result


def _flatten(value, prefix=""):
    if isinstance(value, dict):
        result = {}
        for key, item in sorted(value.items()):
            result.update(_flatten(item, f"{prefix}.{key}" if prefix else str(key)))
        return result
    if isinstance(value, (list, tuple)):
        result = {}
        for index, item in enumerate(value):
            result.update(_flatten(item, f"{prefix}.{index}"))
        return result
    return {prefix: value}


def summarise_grid(records, outdir):
    """Keep every training failure; observed cells only, no interpolation/selection."""
    destination = Path(outdir)
    destination.mkdir(parents=True, exist_ok=True)
    rows = []
    for record in records:
        if record.get("stage", "training") != "training":
            raise ValueError("Training-grid report accepts training records only")
        job = record.get("job", record)
        row = {
            "trial_id": record.get("trial_id", job.get("id", "")),
            "strategy": job["strategy"],
            "universe": json.dumps(job["universe"], separators=(",", ":")),
            "frequency": job["frequency"],
            "status": record.get("status", "completed"),
            "error": record.get("error", ""),
            "costs": json.dumps(record.get("costs", {}), sort_keys=True),
            "delay": record.get("delay", 0),
        }
        row.update(
            {f"param.{k}": v for k, v in _flatten(job.get("params", {})).items()}
        )
        row.update(
            {f"metric.{k}": v for k, v in _flatten(record.get("metrics", {})).items()}
        )
        rows.append(row)
    frame = pd.DataFrame(rows)
    csv_path = destination / "training-grid.csv"
    frame.to_csv(csv_path, index=False)
    charts = []
    if frame.empty:
        return {"csv": str(csv_path), "charts": charts, "records": 0}
    for group_key, group in frame.groupby(
        ["strategy", "universe", "frequency", "costs", "delay"], dropna=False, sort=True
    ):
        numeric = []
        for column in sorted(c for c in group if c.startswith("param.")):
            values = group[column].dropna()
            if len(values) and not values.map(lambda x: isinstance(x, bool)).any():
                converted = pd.to_numeric(values, errors="coerce")
                if np.isfinite(converted).all() and converted.nunique() > 1:
                    numeric.append(column)
        metric = "metric.sharpe" if "metric.sharpe" in group else "metric.mean"
        if not numeric or metric not in group:
            continue
        axes = numeric[:2]
        other = [c for c in group if c.startswith("param.") and c not in axes]
        # Facet remaining dimensions: never average different parameter settings.
        facets = (
            [((), group)]
            if not other
            else group.groupby(other, dropna=False, sort=True)
        )
        for facet_key, facet in facets:
            identity = hashlib.sha256(
                repr((group_key, axes, facet_key)).encode()
            ).hexdigest()[:16]
            fig, ax = plt.subplots(figsize=(6, 4), layout="constrained")
            observed = facet[facet.status == "completed"].copy()
            observed[metric] = pd.to_numeric(observed[metric], errors="coerce")
            observed = observed[np.isfinite(observed[metric])]
            if observed.duplicated(axes).any():
                plt.close(fig)
                raise ValueError(
                    "Duplicate observed parameter cells; no silent averaging"
                )
            if len(axes) == 1:
                x = sorted(group[axes[0]].dropna().unique())
                values = observed.set_index(axes[0])[metric].reindex(x)
                ax.plot(x, values.to_numpy(), marker="o")
                ax.set_xlabel(axes[0].removeprefix("param."))
                ax.set_ylabel(metric.removeprefix("metric."))
            else:
                x = sorted(group[axes[0]].dropna().unique())
                y = sorted(group[axes[1]].dropna().unique())
                cells = np.full((len(y), len(x)), np.nan)
                for _, row in observed.iterrows():
                    cells[y.index(row[axes[1]]), x.index(row[axes[0]])] = row[metric]
                heat = ax.imshow(
                    np.ma.masked_invalid(cells),
                    origin="lower",
                    aspect="auto",
                    interpolation="none",
                )
                ax.set_xticks(range(len(x)), x)
                ax.set_yticks(range(len(y)), y)
                ax.set_xlabel(axes[0].removeprefix("param."))
                ax.set_ylabel(axes[1].removeprefix("param."))
                fig.colorbar(heat, ax=ax, label=metric.removeprefix("metric."))
            ax.set_title(
                f"{group_key[0]} {group_key[1]} {group_key[2]}\nTraining only; missing/failed cells blank"
            )
            if other:
                labels = facet_key if isinstance(facet_key, tuple) else (facet_key,)
                fig.supxlabel(
                    ", ".join(
                        f"{key.removeprefix('param.')}={value}"
                        for key, value in zip(other, labels, strict=True)
                    )
                )
            output = destination / f"grid-{identity}.png"
            fig.savefig(output, dpi=150)
            plt.close(fig)
            charts.append(str(output))
    return {"csv": str(csv_path), "charts": charts, "records": len(frame)}
