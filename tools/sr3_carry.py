"""Staged SR3 carry research with a repaired settlement calendar."""

import csv
import fcntl
import json
import subprocess
import sys
from pathlib import Path

import databento as db
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.batch_research import canonical, file_hash, write_json
from src.sr3_macro.model import trade

DATA = ROOT / ".agent-work/shared/data/sr3-macro-revisions"
CFG = {
    "pairs": [[180, 360], [270, 540], [360, 720]],
    "horizons": [10, 20, 40],
    "thresholds": [5, 15, 30],
    "costs": [0.5, 1, 2],
    "capital": 100000,
    "bootstrap_draws": 10000,
    "seed": 8304,
}


def initialise(run_id):
    if Path(run_id).name != run_id or run_id in {".", ".."}:
        raise ValueError("Use a simple run directory name")
    out = ROOT / "results" / run_id
    out.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    for p in [
        Path(__file__).resolve(),
        ROOT / "research/hypotheses/sr3-curve-carry.md",
    ]:
        if (
            subprocess.check_output(
                ["git", "show", f"{commit}:{p.relative_to(ROOT)}"], cwd=ROOT
            )
            != p.read_bytes()
        ):
            raise ValueError(
                "Commit the specification and implementation before running"
            )
    write_json(
        out / "manifest.json",
        {
            "config": CFG,
            "commit": commit,
            "hypothesis_commit": "ae1d6a3",
            "holdout_access": False,
            "validation_reused": True,
            "raw_statistics_sha256": file_hash(DATA / "raw/statistics.dbn.zst"),
            "original_prices_sha256": file_hash(DATA / "sr3_daily.parquet"),
            "code_sha256": file_hash(Path(__file__)),
            "dependencies_sha256": file_hash(ROOT / "uv.lock"),
        },
    )
    return out


def figure(fig, out, name):
    (out / "figures").mkdir(exist_ok=True)
    fig.tight_layout()
    fig.savefig(out / "figures" / f"{name}.png", dpi=150)
    plt.show()


def load_prices(out):
    cached = out / "settlements.parquet"
    if cached.exists():
        return pd.read_parquet(cached)
    old = pd.read_parquet(DATA / "sr3_daily.parquet")
    if (old.groupby("instrument_id").contract.nunique() > 1).any():
        raise ValueError("Instrument IDs reused; dated definitions required")
    meta = old[
        ["instrument_id", "contract", "reference_start", "reference_end", "midpoint"]
    ].drop_duplicates("instrument_id")
    print("Reading cached raw settlements; no download", flush=True)
    s = db.DBNStore.from_file(DATA / "raw/statistics.dbn.zst").to_df().reset_index()
    s = s[
        (s.stat_type == 3)
        & (s.update_action == 1)
        & ((s.stat_flags.astype(int) & 3) == 3)
        & ((s.stat_flags.astype(int) & 8) == 0)
    ].copy()
    s["trade_date"] = pd.to_datetime(s.ts_ref, utc=True).dt.normalize()
    next_day = (
        s.trade_date.dt.tz_localize(None) + pd.offsets.BDay(1) + pd.Timedelta(hours=6)
    )
    cutoff = next_day.dt.tz_localize("America/Chicago").dt.tz_convert("UTC")
    s = s[
        (s.ts_recv <= cutoff)
        & (s.trade_date >= pd.Timestamp("2018-05-07", tz="UTC"))
        & (s.trade_date < pd.Timestamp("2025-01-01", tz="UTC"))
        & s.price.between(0, 200, inclusive="neither")
    ]
    unknown = int((~s.instrument_id.isin(meta.instrument_id)).sum())
    s = s[["trade_date", "instrument_id", "price", "ts_recv"]].merge(
        meta, on="instrument_id", validate="many_to_one"
    )
    s = s.sort_values("ts_recv").drop_duplicates(
        ["trade_date", "contract"], keep="last"
    )
    s.to_parquet(cached, index=False)
    days = s[["trade_date"]].drop_duplicates()
    audit = pd.DataFrame(
        {
            "old_days": old[["trade_date"]]
            .drop_duplicates()
            .trade_date.dt.day_name()
            .value_counts(),
            "repaired_days": days.trade_date.dt.day_name().value_counts(),
        }
    ).fillna(0)
    audit.to_csv(out / "weekday-coverage.csv")
    write_json(
        out / "data-audit.json",
        {
            "unmapped_records_excluded": unknown,
            "first_day": str(days.trade_date.min()),
            "last_day": str(days.trade_date.max()),
            "days": len(days),
            "fridays": int((days.trade_date.dt.weekday == 4).sum()),
            "settlement_sha256": file_hash(cached),
            "holdout_access": False,
        },
    )
    if not (days.trade_date.dt.weekday == 4).any():
        raise ValueError("Friday calendar still missing")
    return s


def events(prices, out):
    days = pd.DatetimeIndex(sorted(prices.trade_date.unique()))
    entries = [i for i in range(1, len(days)) if days[i].month != days[i - 1].month]
    lookup = prices.set_index(["trade_date", "contract"]).sort_index().price
    rows = []
    skips = []
    spreads = {}
    business = CustomBusinessDay(calendar=USFederalHolidayCalendar())
    for near, far in CFG["pairs"]:
        for horizon in CFG["horizons"]:
            for i in entries:
                if i + horizon >= len(days):
                    continue
                decision, entry, exit = days[i - 1], days[i], days[i + horizon]
                eligible = prices[
                    (prices.trade_date == decision) & (prices.reference_start > entry)
                ]
                chosen = []
                for target in [near, far]:
                    distance = (
                        eligible.midpoint - (entry + pd.Timedelta(days=target))
                    ).abs()
                    if distance.empty or distance.min() > pd.Timedelta(days=60):
                        break
                    chosen.append(eligible.loc[distance.idxmin()])
                reason = None
                if len(chosen) != 2 or chosen[0].contract == chosen[1].contract:
                    reason = "no_distinct_pair_within_60_days"
                if reason is None:
                    n, f = chosen
                    missing = pd.date_range(entry, exit, freq=business).difference(days)
                    if len(missing):
                        reason = "missing_nonholiday_weekday"
                    else:
                        pair = n.contract + "|" + f.contract
                        spread = (
                            lookup.xs(f.contract, level="contract")
                            - lookup.xs(n.contract, level="contract")
                        ).dropna()
                        dates = days[i : i + horizon + 1]
                        marks = spread.reindex(dates)
                        if marks.isna().any():
                            reason = "missing_contract_settlement"
                        else:
                            spreads[pair] = pd.DataFrame(
                                {
                                    "trade_date": spread.index,
                                    "contract": pair,
                                    "price": spread.to_numpy(),
                                }
                            )
                            carry = float((n.price - f.price) * 100)
                            rows.append(
                                {
                                    "near": near,
                                    "far": far,
                                    "horizon": horizon,
                                    "decision": decision,
                                    "entry": entry,
                                    "exit": exit,
                                    "contract": pair,
                                    "carry_bp": carry,
                                    "signal": -carry,
                                    "target_bp": float(
                                        -100 * (marks.iloc[-1] - marks.iloc[0])
                                    ),
                                }
                            )
                if reason:
                    skips.append(
                        {
                            "near": near,
                            "far": far,
                            "horizon": horizon,
                            "entry": str(entry),
                            "reason": reason,
                        }
                    )
    frame = pd.DataFrame(rows)
    frame.to_csv(out / "events.csv", index=False)
    pd.DataFrame(skips).to_csv(out / "skipped-paths.csv", index=False)
    if frame.empty:
        raise ValueError("No complete monthly contract paths")
    pair_prices = pd.concat(spreads.values(), ignore_index=True)
    pair_prices.to_parquet(out / "pair-prices.parquet", index=False)
    print(f"{len(frame)} event paths; {len(skips)} exclusions", flush=True)
    return frame, pair_prices


def evaluate(frame, prices, out, sample):
    if sample not in ["training", "inner", "reused_validation"]:
        raise ValueError("Unknown sample")
    start, end = {
        "training": ("2018-05-07", "2023-01-01"),
        "inner": ("2021-01-01", "2023-01-01"),
        "reused_validation": ("2023-01-01", "2025-01-01"),
    }[sample]
    start, end = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC")
    rows = []
    for (near, far, horizon), f in frame.groupby(["near", "far", "horizon"]):
        for threshold in CFG["thresholds"]:
            for cost in CFG["costs"]:
                key = f"{near}-{far}-h{horizon}-t{threshold}-c{cost}-{sample}"
                m, r, t = trade(CFG, f, prices, threshold, 2 * cost, start, end)
                exposure = pd.Series(0.0, index=pd.DatetimeIndex(r.date))
                for tr in t:
                    exposure.loc[
                        (exposure.index >= pd.Timestamp(tr["entry"]))
                        & (exposure.index < pd.Timestamp(tr["exit"]))
                    ] = 2
                r["exposure"] = exposure.to_numpy()
                r["drawdown"] = (
                    r.equity / r.equity.cummax().clip(lower=CFG["capital"]) - 1
                )
                r["rolling_sharpe_126"] = (
                    r["return"].rolling(126).mean()
                    / r["return"].rolling(126).std()
                    * np.sqrt(252)
                )
                r.to_csv(out / f"returns-{key}.csv", index=False)
                pd.DataFrame(t).to_csv(out / f"trades-{key}.csv", index=False)
                row = {
                    "job_id": key,
                    "near": int(near),
                    "far": int(far),
                    "horizon": int(horizon),
                    "threshold": threshold,
                    "cost_bp_per_leg": cost,
                    "sample": sample,
                    "turnover_contracts": 4 * len(t),
                    "mean_exposure": float(exposure.mean()),
                    **m,
                }
                rows.append(row)
                print(
                    f"[{len(rows)}/81] {key}: {m['trades']} trades, ${m['net_pnl']:.0f}",
                    flush=True,
                )
    table = pd.DataFrame(rows)
    table.to_csv(out / f"metrics-{sample}.csv", index=False)
    ledger = ROOT / "research/experiments.csv"
    with ledger.open("r+", newline="") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        existing = {r["trial_id"] for r in reader}
        stream.seek(0, 2)
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        for row in rows:
            tid = out.name + "/" + row["job_id"]
            if tid in existing:
                continue
            writer.writerow(
                {
                    "trial_id": tid,
                    "timestamp_utc": str(pd.Timestamp.now(tz="UTC")),
                    "hypothesis_commit": "ae1d6a3",
                    "code_commit": json.loads((out / "manifest.json").read_text())[
                        "commit"
                    ],
                    "data_sha256": file_hash(out / "settlements.parquet"),
                    "config_sha256": file_hash(out / "manifest.json"),
                    "sample": sample,
                    "parameters": canonical(
                        {k: row[k] for k in ["near", "far", "horizon", "threshold"]}
                    ),
                    "cost_model": f"{row['cost_bp_per_leg']} bp per leg round trip",
                    "result_path": str(out.relative_to(ROOT)),
                    "status": "completed",
                    "conclusion": canonical(row),
                    "holdout_access": "false",
                }
            )
    return table


def select(inner, out):
    eligible = inner[
        (inner.cost_bp_per_leg == 1) & (inner.trades >= 6) & inner.sharpe.notna()
    ]
    if eligible.empty:
        raise ValueError("No inner-selection cell with six trades")
    row = eligible.sort_values(["sharpe", "job_id"], ascending=[False, True]).iloc[0]
    selected = {k: int(row[k]) for k in ["near", "far", "horizon", "threshold"]}
    write_json(
        out / "selection.json",
        {
            "sample": "2021-2022",
            "parameters": selected,
            "positive_inner_edge": bool(row.net_pnl > 0),
            "frozen_before_validation": True,
        },
    )
    return selected


def diagnostics(frame, table, selected, out):
    fixed = {"near": 270, "far": 540, "horizon": 20, "threshold": 15}
    fig, axes = plt.subplots(3, 2, figsize=(15, 11))
    ic = []
    for label, params in [("fixed", fixed), ("inner_selected", selected)]:
        key = f"{params['near']}-{params['far']}-h{params['horizon']}-t{params['threshold']}-c1-reused_validation"
        r = pd.read_csv(out / f"returns-{key}.csv")
        d = pd.to_datetime(r.date)
        for ax, col in zip(
            axes[:, 0], ["equity", "drawdown", "rolling_sharpe_126"], strict=True
        ):
            ax.plot(d, r[col], label=label)
        f = frame[
            (frame.near == params["near"])
            & (frame.far == params["far"])
            & (frame.horizon == params["horizon"])
        ]
        for sample, start, end in [
            ("training", "2018-05-07", "2023-01-01"),
            ("reused_validation", "2023-01-01", "2025-01-01"),
        ]:
            z = f[
                (f.entry >= pd.Timestamp(start, tz="UTC"))
                & (f.exit < pd.Timestamp(end, tz="UTC"))
            ]
            ic.append(
                {
                    "specification": label,
                    "sample": sample,
                    "events": len(z),
                    "IC": (-z.carry_bp).corr(z.target_bp),
                    "rank_IC": (-z.carry_bp).corr(z.target_bp, method="spearman"),
                }
            )
        if label == "fixed":
            axes[0, 1].hist(r["return"], bins=40)
            axes[0, 1].set(xlabel="Daily net return", ylabel="Sessions")
            axes[1, 1].plot(d, r.exposure)
            axes[1, 1].set(ylabel="Gross contracts")
            values = r["return"].to_numpy()
            rng = np.random.default_rng(CFG["seed"])
            means = []
            for _ in range(100):
                starts = rng.integers(
                    0, len(values), (100, int(np.ceil(len(values) / 20)), 1)
                )
                indices = ((starts + np.arange(20)) % len(values)).reshape(100, -1)[
                    :, : len(values)
                ]
                means.extend(values[indices].mean(axis=1))
            ci = np.quantile(means, [0.025, 0.975])
            pd.DataFrame({"daily_mean_return": means}).to_csv(
                out / "primary-bootstrap.csv", index=False
            )
            write_json(
                out / "primary-uncertainty.json",
                {
                    "daily_mean_ci95": ci.tolist(),
                    "draws": len(means),
                    "block_sessions": 20,
                    "selection_adjusted": False,
                },
            )
    for ax, label in zip(
        axes[:, 0],
        ["Equity ($), 1 bp/leg", "Drawdown (fraction)", "126-session Sharpe"],
        strict=True,
    ):
        ax.set(ylabel=label)
        ax.legend()
    heat = table[
        (table.near == 270) & (table.far == 540) & (table.cost_bp_per_leg == 1)
    ].pivot(index="horizon", columns="threshold", values="net_pnl")
    image = axes[2, 1].imshow(heat.to_numpy(), cmap="RdYlGn")
    fig.colorbar(image, ax=axes[2, 1], label="Net P&L ($)")
    axes[2, 1].set_xticks(range(len(heat.columns)), heat.columns)
    axes[2, 1].set_yticks(range(len(heat.index)), heat.index)
    axes[2, 1].set(xlabel="Threshold (bp)", ylabel="Holding sessions")
    figure(fig, out, "validation-diagnostics")
    pd.DataFrame(ic).to_csv(out / "IC.csv", index=False)
    return pd.DataFrame(ic)


def benchmarks(frame, prices, out):
    f = frame[(frame.near == 270) & (frame.far == 540) & (frame.horizon == 20)].copy()
    f = f[f.carry_bp.abs() >= 15]
    f["signal"] = -100.0
    m, r, t = trade(
        CFG,
        f,
        prices,
        15,
        2,
        pd.Timestamp("2023-01-01", tz="UTC"),
        pd.Timestamp("2025-01-01", tz="UTC"),
    )
    r.to_csv(out / "benchmark-fixed-long.csv", index=False)
    pd.DataFrame(t).to_csv(out / "benchmark-fixed-long-trades.csv", index=False)
    write_json(
        out / "benchmark.json",
        {
            "fixed_long_spread": m,
            "cash_net_pnl": 0,
            "matching_primary_eligible_events": True,
        },
    )
    return m, r


def finish(table, selected, out):
    rows = []
    for label, p in [
        ("fixed", {"near": 270, "far": 540, "horizon": 20, "threshold": 15}),
        ("inner_selected", selected),
    ]:
        mask = table.cost_bp_per_leg.eq(1)
        for k, v in p.items():
            mask &= table[k].eq(v)
        row = table[mask].copy()
        row["specification"] = label
        rows.append(row)
    summary = pd.concat(rows, ignore_index=True)
    summary.to_csv(out / "selected-results.csv", index=False)
    (out / "REPORT.md").write_text(
        "# SR3 curve carry\n\n"
        + summary.to_string(index=False)
        + "\n\nCalendar repaired from raw final settlements. 2023–2024 is reused validation. Settlement fills are modelled. Holdout untouched. Bootstrap is pointwise, not selection-adjusted.\n"
    )
    write_json(
        out / "summary.json",
        {
            "completed_validation_cells": len(table),
            "holdout_access": False,
            "selection": selected,
            "validation_reused": True,
        },
    )
    return summary
