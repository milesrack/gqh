"""Rebuild MORTIMER result tables from hash-verified market and return files.

The default command checks recorded series and does not run the strategy.
--replay-development also verifies simulator arithmetic on development data.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import exchange_calendars as xc
import numpy as np
import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.mortimer import E6_VARIANT, MACRO, load_data, metrics, simulate


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_files(expected):
    for name, digest in expected.items():
        path = Path(name)
        if not path.is_file():
            raise FileNotFoundError(f"Restore the registered immutable asset: {path}")
        if file_hash(path) != digest:
            raise ValueError(f"Registered evidence hash differs: {path}")


def load_recorded_inputs():
    """Align prices, cash rates, and exchange closes on the observed calendar."""
    provenance = json.loads(Path("research/mortimer-provenance.json").read_text())
    verify_files(provenance["input_sha256"])
    panel, prices, rf, _, boundary, _ = load_data("data/cache/erc")
    final = pd.read_parquet("data/cache/erc-final/market.parquet")
    rates = pd.read_parquet("data/cache/erc-final/rates.parquet")
    cal = xc.get_calendar("XNYS", start="2007-01-01", end="2026-12-31")
    sessions = cal.sessions_in_range("2008-01-02", "2026-10-02").tz_localize(None)
    full = pd.concat(
        [prices, final.xs("Adj Close", axis=1, level=1)[list(MACRO)].loc[boundary:]]
    ).reindex(sessions)
    if full.isna().any().any() or full.index.has_duplicates:
        raise ValueError("Missing or duplicate recorded common price observations")
    rates["available"] = [
        sessions[sessions > max(d, r)][0] if (sessions > max(d, r)).any() else pd.NaT
        for d, r in zip(rates.date, rates.realtime_start)
    ]
    rates = (
        rates.dropna(subset=["available"])
        .sort_values(["available", "date"])
        .groupby("available")
        .tail(1)
    )
    final_sessions = sessions[sessions >= pd.Timestamp(boundary)]
    merged = pd.merge_asof(
        pd.DataFrame({"date": final_sessions}),
        rates.sort_values("available"),
        left_on="date",
        right_on="available",
    )
    if merged.value.isna().any():
        raise ValueError("Unavailable initial-release cash observations")
    yield_rate = pd.Series(merged.value.to_numpy() / 100, index=final_sessions)
    elapsed = sessions.to_series().diff().dt.days.loc[final_sessions]
    final_rf = (1 + yield_rate.shift().fillna(yield_rate.iloc[0])) ** (
        elapsed / 365
    ) - 1
    rf = pd.concat([rf, final_rf])
    closes = pd.Series([cal.session_close(d) for d in sessions], index=sessions)
    actual_boundary = max(
        sessions[int(len(sessions) * 0.8)],
        sessions[sessions >= sessions[-1] - pd.DateOffset(years=2)][0],
    )
    if actual_boundary != pd.Timestamp(boundary):
        raise ValueError("Recorded holdout boundary differs from observed history")
    full_panel = pd.concat([panel.loc[:, list(MACRO)], final.loc[boundary:]])
    return full_panel, full, rf, closes, boundary


def read_daily(path):
    return pd.read_csv(path, index_col=0, parse_dates=True)


def sample_masks(index, boundary):
    return {
        "train": index.year <= 2018,
        "validation": (index.year >= 2019) & (index < pd.Timestamp(boundary)),
        "oos_test": index >= pd.Timestamp(boundary),
    }


def reproduce(output=Path("results/mortimer-submission"), reuse=True):
    """Verify recorded series and rebuild deterministic result tables.

    The default path reads saved returns. Development replay checks arithmetic
    before the OOS boundary and never simulates the held-out period.
    """
    output = Path(output)
    provenance = json.loads(Path("research/mortimer-provenance.json").read_text())
    verify_files(provenance["input_sha256"])
    verify_files(provenance["recorded_sha256"])
    verify_files(provenance["scientific_source_sha256"])
    receipt = output / "reproduction-receipt.json"
    if reuse and receipt.exists():
        previous = json.loads(receipt.read_text())
        verify_files(previous["output_sha256"])
        if previous["provenance_sha256"] != file_hash(
            "research/mortimer-provenance.json"
        ):
            raise ValueError("Reproduction provenance changed")
    output.mkdir(parents=True, exist_ok=True)
    _panel, prices, rf, closes, boundary = load_recorded_inputs()
    rows, annual, datasets = [], [], {}
    for strategy in ("E6", "ERC"):
        dev = read_daily(f"results/archive/erc-guarded-v1/{strategy}-daily.csv")
        final = read_daily(f"results/archive/erc-final-v1/{strategy}-daily.csv")
        frame = pd.concat([dev, final])
        if frame.index.has_duplicates or not frame.index.equals(prices.index[550:]):
            raise ValueError("Recorded scoring sample differs from common warm-up")
        datasets[strategy] = frame
        frame.to_csv(output / f"{strategy}-daily.csv")
        for sample, mask in sample_masks(frame.index, boundary).items():
            current = frame.loc[mask]
            rows.append(
                dict(
                    strategy=strategy,
                    sample=sample,
                    cost_bps=5,
                    observations=len(current),
                    first=str(current.index[0].date()),
                    last=str(current.index[-1].date()),
                    **metrics(current, rf),
                )
            )
        for year, current in frame.groupby(frame.index.year):
            annual.append(dict(strategy=strategy, year=year, **metrics(current, rf)))
        for kind in ("weights", "base_weights", "trades", "orders"):
            # Individual-asset final holdings were not recorded in this archive.
            # Keep the development-only evidence explicitly bounded.
            recorded = Path(f"results/archive/erc-guarded-v1/{strategy}-{kind}.csv")
            (output / f"{strategy}-development-{kind}.csv").write_bytes(
                recorded.read_bytes()
            )
    performance = pd.DataFrame(rows)
    recorded_performance = pd.concat(
        [
            pd.read_csv("results/archive/erc-guarded-v1/performance.csv"),
            pd.read_csv("results/archive/erc-final-v1/performance.csv"),
        ]
    )
    recorded_performance["sample"] = recorded_performance["sample"].replace(
        {"reused_validation": "validation", "reused_final": "oos_test"}
    )
    for row in rows:
        registered = recorded_performance[
            (recorded_performance.strategy == row["strategy"])
            & (recorded_performance["sample"] == row["sample"])
        ].iloc[0]
        for metric in ("cagr", "volatility", "sharpe", "max_drawdown", "turnover"):
            if not np.isclose(row[metric], registered[metric], rtol=1e-10, atol=1e-12):
                raise ValueError(
                    f"Recorded metric mismatch: {row['strategy']} {row['sample']} {metric}"
                )
    performance.to_csv(output / "performance.csv", index=False)
    pd.DataFrame(annual).to_csv(output / "annual.csv", index=False)
    rf.rename("cash_return").to_csv(output / "cash-returns.csv")
    prices.to_csv(output / "market-adjusted-prices.csv")
    stress_rows = []
    original = Path("results/20261004T003708-e3127963")
    for strategy, filename in (
        ("E6", "E6-double_cost-3fc474039b.csv"),
        ("ERC", "E6-double_cost_base-811cdde690.csv"),
    ):
        stress = read_daily(original / filename).iloc[550:]
        stress.to_csv(output / f"{strategy}-10bp-development-daily.csv")
        for sample, mask in sample_masks(stress.index, boundary).items():
            if mask.any():
                stress_rows.append(
                    dict(
                        strategy=strategy,
                        sample=sample,
                        cost_bps=10,
                        **metrics(stress.loc[mask], rf),
                    )
                )
    pd.DataFrame(stress_rows).to_csv(output / "doubled-cost.csv", index=False)
    forecast_file = original / "tables/forecast_diagnostics.csv"
    forecast = pd.read_csv(forecast_file)
    forecast[forecast.trial_id == "E6"].to_csv(output / "forecast-ic.csv", index=False)
    if not reuse:
        dev_prices = prices.loc[:"2024-10-01"]
        replay = simulate(dev_prices, rf, closes, E6_VARIANT, start_position=550).iloc[
            550:
        ]
        saved = datasets["E6"].loc[:"2024-10-01"]
        np.testing.assert_allclose(
            replay.to_numpy(), saved.to_numpy(), rtol=1e-10, atol=1e-12, equal_nan=True
        )
    generated = [
        output / name
        for name in (
            "performance.csv",
            "annual.csv",
            "doubled-cost.csv",
            "forecast-ic.csv",
            "cash-returns.csv",
            "market-adjusted-prices.csv",
            "E6-daily.csv",
            "ERC-daily.csv",
            "E6-10bp-development-daily.csv",
            "ERC-10bp-development-daily.csv",
        )
    ]
    receipt.write_text(
        json.dumps(
            {
                "mode": "verified recorded evidence consolidation"
                if reuse
                else "recorded evidence plus development arithmetic replay",
                "provenance_sha256": file_hash("research/mortimer-provenance.json"),
                "scored_start": str(prices.index[550].date()),
                "boundary": boundary,
                "final_status": "held-out OOS test evaluated once after specification freeze",
                "final_10bp_status": "not recorded; no new final simulation",
                "output_sha256": {str(p): file_hash(p) for p in generated},
            },
            indent=2,
        )
        + "\n"
    )
    return performance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("results/mortimer-submission")
    )
    parser.add_argument("--replay-development", action="store_true")
    args = parser.parse_args()
    print(
        reproduce(args.output, reuse=not args.replay_development).to_string(index=False)
    )


if __name__ == "__main__":
    main()
