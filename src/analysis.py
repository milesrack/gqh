"""Daily forecast-loss inference and dependence-aware uncertainty."""

import numpy as np
import pandas as pd


def block_interval(values, cfg):
    a = np.asarray(values, dtype=float)
    if len(a) < 2:
        return None
    rng = np.random.default_rng(cfg["seed"])
    block = min(cfg["bootstrap_block_days"], max(1, len(a) // 2))
    starts = rng.integers(
        0, len(a), size=(cfg["bootstrap_replicates"], int(np.ceil(len(a) / block)))
    )
    indices = (starts[..., None] + np.arange(block)) % len(a)
    draws = a[indices.reshape(len(starts), -1)[:, : len(a)]].mean(axis=1)
    return {
        "lower": float(np.quantile(draws, 0.025)),
        "upper": float(np.quantile(draws, 0.975)),
        "days": len(a),
        "block_days": block,
        "underpowered": len(a) < 20,
    }


def forecast_metrics(frame, baseline, cross, cfg):
    y = frame.Y.to_numpy()
    errors0 = (y - baseline) ** 2
    errors1 = (y - cross) ** 2
    daily = (
        pd.DataFrame(
            {"day": frame.day.to_numpy(), "loss_improvement": errors0 - errors1}
        )
        .groupby("day")
        .mean()
    )
    result = {
        "observations": len(y),
        "baseline_mse": np.mean(errors0),
        "cross_mse": np.mean(errors1),
        "baseline_mae": np.mean(np.abs(y - baseline)),
        "cross_mae": np.mean(np.abs(y - cross)),
        "incremental_oos_r2": 1 - np.mean(errors1) / np.mean(errors0)
        if np.mean(errors0)
        else None,
        "directional_accuracy_including_zero": np.mean(np.sign(y) == np.sign(cross)),
        "zero_move_fraction": np.mean(y == 0),
        "daily_loss_improvement_ci": block_interval(daily.loss_improvement, cfg),
    }
    return result, daily
