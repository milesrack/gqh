"""Resumable three-calendar-month bootstrap of event-study slopes."""

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from src.batch_research import digest, write_json


def compute(task):
    params, split, records, cfg, folder = task
    path = Path(folder)
    path.mkdir(parents=True, exist_ok=True)
    final = path / "result.json"
    identity = digest(
        {
            "params": params,
            "split": split,
            "data": records,
            "draws": cfg["bootstrap_draws"],
            "block": cfg["block_months"],
            "seed": cfg["seed"],
        }
    )
    if final.exists():
        result = json.loads(final.read_text())
        if result["identity"] != identity:
            raise ValueError("Bootstrap checkpoint differs")
        return result
    frame = pd.DataFrame(records)
    frame["entry"] = pd.to_datetime(frame.entry, utc=True)
    months = frame.entry.dt.tz_localize(None).dt.to_period("M")
    calendar = pd.period_range(months.min(), months.max(), freq="M")
    if len(frame) < 30 or len(calendar) < 12:
        result = {
            "identity": identity,
            "params": params,
            "split": split,
            "status": "insufficient_events_or_months",
            "events": len(frame),
            "months": len(calendar),
        }
        write_json(final, result)
        return result
    x = frame.raw_signal.to_numpy()
    y = frame.target_bp.to_numpy()
    data = (
        pd.DataFrame({"n": 1.0, "x": x, "y": y, "xx": x * x, "xy": x * y}, index=months)
        .groupby(level=0)
        .sum()
        .reindex(calendar, fill_value=0)
        .to_numpy()
    )
    count = len(calendar)
    blocks = int(np.ceil(count / cfg["block_months"]))
    offset = np.arange(cfg["block_months"])
    chunk = cfg["bootstrap_chunk"]
    draws = cfg["bootstrap_draws"]
    started = time.monotonic()
    finished = 0
    for i in range(int(np.ceil(draws / chunk))):
        output = path / f"chunk-{i:05d}.npy"
        size = min(chunk, draws - i * chunk)
        if not output.exists():
            seed = int(identity[:16], 16) ^ cfg["seed"] ^ i
            rng = np.random.default_rng(seed)
            indices = (
                (rng.integers(0, count, (size, blocks, 1)) + offset) % count
            ).reshape(size, -1)[:, :count]
            sums = data[indices].sum(axis=1)
            n, sx, sy, sxx, sxy = sums.T
            denom = sxx - sx * sx / n
            slope = np.divide(
                sxy - sx * sy / n, denom, out=np.full(size, np.nan), where=denom > 1e-12
            )
            tmp = output.with_suffix(".tmp")
            with tmp.open("wb") as stream:
                np.save(stream, slope, allow_pickle=False)
            tmp.replace(output)
        finished += size
        write_json(
            path / "progress.json",
            {
                "draws": finished,
                "total": draws,
                "elapsed_seconds": time.monotonic() - started,
                "params": params,
                "split": split,
            },
        )
    samples = np.concatenate(
        [np.load(p, allow_pickle=False) for p in sorted(path.glob("chunk-*.npy"))]
    )
    valid = samples[np.isfinite(samples)]
    alpha = 0.05 / 288
    result = {
        "identity": identity,
        "params": params,
        "split": split,
        "status": "completed",
        "draws": len(samples),
        "finite_draws": len(valid),
        "events": len(frame),
        "months": len(calendar),
        "beta_ci95": np.quantile(valid, [0.025, 0.975]).tolist()
        if len(valid)
        else None,
        "beta_ci_grid_adjusted": np.quantile(valid, [alpha / 2, 1 - alpha / 2]).tolist()
        if len(valid)
        else None,
        "bootstrap_probability_beta_positive": float(np.mean(valid > 0))
        if len(valid)
        else None,
        "elapsed_seconds": time.monotonic() - started,
    }
    write_json(final, result)
    for p in path.glob("chunk-*.npy"):
        p.unlink()
    return result
