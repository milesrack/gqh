"""Free equity acquisition and a frozen ranked-DAX pilot; no paid downloads."""

import argparse
import hashlib
import itertools
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.batch_research import canonical, digest, write_json

CONFIG = ROOT / "research/configs/dax-ranked-pilot.json"
DATA = ROOT / ".agent-work/shared/data/dax-ranked-pilot"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen():
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    for path in [
        CONFIG,
        Path(__file__).resolve(),
        ROOT / "research/hypotheses/dax-ranked-pilot.md",
    ]:
        relative = path.relative_to(ROOT)
        if (
            subprocess.check_output(["git", "show", f"{commit}:{relative}"], cwd=ROOT)
            != path.read_bytes()
        ):
            raise ValueError(f"Commit {relative} before acquisition or evaluation")
    return commit


def prepare(cfg, commit):
    import yfinance as yf

    DATA.mkdir(parents=True, exist_ok=True)
    frames, failures = [], {}
    for number, ticker in enumerate(cfg["universe"], 1):
        file = DATA / f"{ticker}.parquet"
        if file.exists():
            frame = pd.read_parquet(file)
        else:
            try:
                frame = yf.download(
                    ticker,
                    start=cfg["equity_history_start"],
                    end=cfg["end"],
                    auto_adjust=True,
                    actions=True,
                    progress=False,
                    threads=False,
                    multi_level_index=False,
                )
                if frame.empty:
                    raise ValueError("Empty provider response")
                frame.to_parquet(file)
            except Exception as exc:  # noqa: BLE001 -- retain provider failures; fixed universe cannot shrink.
                failures[ticker] = str(exc)
                print(
                    f"[{number}/{len(cfg['universe'])}] {ticker}: FAILED {exc}",
                    flush=True,
                )
                continue
        frame = frame.copy()
        frame["ticker"] = ticker
        frame.index = pd.to_datetime(frame.index).tz_localize(None).normalize()
        frames.append(frame.rename_axis("date").reset_index())
        print(
            f"[{number}/{len(cfg['universe'])}] {ticker}: {len(frame)} bars", flush=True
        )
    write_json(
        DATA / "acquisition.json",
        {
            "provider": "Yahoo Finance via yfinance",
            "retrieved_at": pd.Timestamp.now(tz="UTC").isoformat(),
            "adjustment": "provider retrospective auto_adjust=True",
            "commit": commit,
            "config_sha256": sha(CONFIG),
            "failures": failures,
            "source_sha256": {
                p.name: sha(p)
                for p in DATA.glob("*.parquet")
                if p.name != "equities.parquet"
            },
        },
    )
    if failures or len(frames) != len(cfg["universe"]):
        raise ValueError(
            "Incomplete fixed universe; retry prepare, no silent symbol removal"
        )
    pd.concat(frames, ignore_index=True).to_parquet(
        DATA / "equities.parquet", index=False
    )
    manifest = json.loads((DATA / "acquisition.json").read_text())
    manifest["equities_sha256"] = sha(DATA / "equities.parquet")
    write_json(DATA / "manifest.json", manifest)


def metrics(net):
    equity = (1 + net).cumprod()
    annual_vol = net.std(ddof=1) * np.sqrt(252)
    return {
        "net_return": float(equity.iloc[-1] - 1),
        "cagr": float(equity.iloc[-1] ** (252 / len(net)) - 1),
        "sharpe": float(net.mean() * 252 / annual_vol) if annual_vol > 0 else None,
        "max_drawdown": float((equity / equity.cummax().clip(lower=1) - 1).min()),
        "annual_volatility": float(annual_vol),
        "sessions": len(net),
    }


def run(cfg, commit):
    manifest = json.loads((DATA / "manifest.json").read_text())
    if manifest["config_sha256"] != sha(CONFIG) or manifest["equities_sha256"] != sha(
        DATA / "equities.parquet"
    ):
        raise ValueError("Equity data/config hash changed")
    out = ROOT / "results" / cfg["batch_id"]
    out.mkdir(parents=True, exist_ok=True)
    panel = pd.read_parquet(DATA / "equities.parquet")
    close = panel.pivot(index="date", columns="ticker", values="Close").reindex(
        columns=cfg["universe"]
    )
    opens = panel.pivot(index="date", columns="ticker", values="Open").reindex_like(
        close
    )
    intraday = close / opens - 1
    paths = [ROOT / p for p in cfg["feature_files"]]
    quotes = pd.concat([pd.read_parquet(p) for p in paths]).sort_index()
    quotes = quotes.loc[~quotes.index.duplicated(keep="first")]
    quotes.index = pd.to_datetime(quotes.index, utc=True)
    quotes = quotes[
        (quotes.index >= pd.Timestamp(cfg["start"], tz="UTC"))
        & (quotes.index < pd.Timestamp(cfg["end"], tz="UTC"))
    ]
    local = quotes.index.tz_convert("Europe/Berlin")
    mask = (local.strftime("%H:%M:%S") >= "09:10:00") & (
        local.strftime("%H:%M:%S") <= "17:20:00"
    )
    quotes = quotes.loc[mask]
    quotes["observed_at"] = quotes.index
    quotes["date"] = (
        quotes.index.tz_convert("Europe/Berlin").tz_localize(None).normalize()
    )
    first = quotes.groupby("date").head(1).set_index("date")
    last = quotes.groupby("date").tail(1).set_index("date")
    # Keep identical complete sessions for every sleeve; reject short/stale sessions.
    dates = first.index.intersection(last.index).intersection(close.index).sort_values()
    complete = intraday.loc[dates].notna().sum(axis=1) >= cfg["minimum_equities"]
    entry_time = (
        first.loc[dates, "observed_at"]
        .dt.tz_convert("Europe/Berlin")
        .dt.strftime("%H:%M:%S")
    )
    exit_time = (
        last.loc[dates, "observed_at"]
        .dt.tz_convert("Europe/Berlin")
        .dt.strftime("%H:%M:%S")
    )
    dates = dates[complete & (entry_time <= "09:15:00") & (exit_time >= "17:15:00")]
    if len(dates) < 30:
        raise ValueError(
            "Fewer than 30 common pilot sessions; cannot split this experiment"
        )
    split = int(len(dates) * cfg["development_split_fraction"])
    train_dates = dates[:split]
    check_dates = dates[split:]
    identity = {
        "commit": commit,
        "config_sha256": sha(CONFIG),
        "equities_sha256": manifest["equities_sha256"],
        "feature_sha256": {str(p.relative_to(ROOT)): sha(p) for p in paths},
        "dates": [str(d.date()) for d in dates],
        "split_date": str(check_dates[0].date()),
        "final_holdout_access": False,
    }
    previous = out / "manifest.json"
    if previous.exists() and json.loads(previous.read_text()) != identity:
        raise ValueError("Existing batch differs; use a new batch ID")
    write_json(previous, identity)
    volume = panel.pivot(index="date", columns="ticker", values="Volume").reindex_like(
        close
    )
    lag_liquid = (volume * close).rolling(20, min_periods=20).mean().shift(1).loc[dates]
    daily = close.pct_change(fill_method=None)
    vol = daily.rolling(20, min_periods=20).std().shift(1).loc[dates]
    jobs = list(
        itertools.product(
            cfg["lookbacks"],
            cfg["quantiles"],
            cfg["families"],
            cfg["directions"],
            cfg["rebalance_days"],
            cfg["cost_multiples"],
        )
    )
    summary = []
    for number, (lookback, q, family, direction, rebalance, cost) in enumerate(jobs, 1):
        momentum = close.pct_change(lookback, fill_method=None).shift(1).loc[dates]
        score = momentum.copy()
        if family == "residual":
            market = daily.mean(axis=1)
            beta = (
                daily.rolling(60, min_periods=60)
                .cov(market)
                .div(market.rolling(60, min_periods=60).var(), axis=0)
                .shift(1)
                .loc[dates]
            )
            market_momentum = (1 + market).rolling(
                lookback, min_periods=lookback
            ).apply(np.prod, raw=True).shift(1).loc[dates] - 1
            score = score - beta.mul(market_momentum, axis=0)
        elif family == "vol_normalised":
            score = score / (vol * np.sqrt(lookback))
        score = score.replace([np.inf, -np.inf], np.nan)
        weights = pd.DataFrame(0.0, index=dates, columns=close.columns)
        leader = pd.Series(0.0, index=dates)
        breadth = leader.copy()
        for i, day in enumerate(dates):
            if i % rebalance and i:
                weights.loc[day] = weights.iloc[i - 1]
                leader.loc[day] = leader.iloc[i - 1]
                breadth.loc[day] = breadth.iloc[i - 1]
                continue
            valid = score.loc[day].dropna().sort_values(kind="stable")
            if len(valid) < cfg["minimum_equities"]:
                continue
            count = max(1, int(len(valid) * q))
            bottom = valid.iloc[:count]
            top = valid.iloc[-count:]
            weights.loc[day, top.index] = direction * 0.5 / count
            weights.loc[day, bottom.index] = -direction * 0.5 / count
            leader.loc[day] = direction * np.sign(
                top.mean() + bottom.mean() - 2 * valid.median()
            )
            breadth.loc[day] = direction * np.sign((valid > 0).mean() - 0.5)
        params = {
            "lookback": lookback,
            "quantile": q,
            "family": family,
            "direction": direction,
            "rebalance": rebalance,
            "cost_multiple": cost,
        }
        active = weights.abs().sum(axis=1)
        # Per-name participation cap uses lagged observed cash turnover.
        feasible = (
            (weights.abs() * cfg["capital_eur"] <= 0.01 * lag_liquid)
            .where(weights != 0, True)
            .all(axis=1)
        )
        gross = (weights * intraday.loc[dates]).sum(axis=1, min_count=1)
        stock_net = (
            gross
            - active * 2 * cfg["equity_side_bps"] / 10000 * cost
            - weights.clip(upper=0).abs().sum(axis=1) * cfg["annual_short_borrow"] / 252
        )
        observed = intraday.loc[dates].notna().where(weights != 0, True).all(axis=1)
        outcomes = [("equity_rank", stock_net, not bool((feasible & observed).all()))]
        for product, multiplier in [("FDAX", 25), ("FDXM", 5), ("FDXS", 1)]:
            mid0 = first.loc[dates, f"mid_{product}"]
            mid1 = last.loc[dates, f"mid_{product}"]
            spread0 = first.loc[dates, f"spread_{product}"]
            spread1 = last.loc[dates, f"spread_{product}"]
            valid = (
                np.isfinite(mid0)
                & np.isfinite(mid1)
                & np.isfinite(spread0)
                & np.isfinite(spread1)
                & (spread0 >= 0)
                & (spread1 >= 0)
            )
            for name, signal in [("leadership", leader), ("breadth", breadth)]:
                pnl = signal * (mid1 - mid0) * multiplier - signal.abs() * (
                    (spread0 + spread1) * multiplier / 2
                    + 2
                    * cost
                    * (
                        cfg["futures_side_fee_eur"]
                        + cfg["futures_slippage_points"] * multiplier
                    )
                )
                outcomes.append(
                    (
                        product + "_" + name,
                        pnl / cfg["capital_eur"],
                        not bool(valid.all()),
                    )
                )
        for sleeve, net, failed in outcomes:
            job = {"sleeve": sleeve, **params}
            job_id = digest(job)[:20]
            file = out / (job_id + ".csv")
            net.rename("return").rename_axis("date").to_csv(file)
            row = {
                **job,
                "job_id": job_id,
                "status": "failed"
                if failed or not np.isfinite(net).all()
                else "completed",
            }
            if row["status"] == "completed":
                row.update(
                    {"train_" + k: v for k, v in metrics(net.loc[train_dates]).items()}
                )
                row.update(
                    {
                        "development_" + k: v
                        for k, v in metrics(net.loc[check_dates]).items()
                    }
                )
            else:
                row["error"] = (
                    "Invalid quote/return or lagged stock participation exceeded"
                )
            summary.append(row)
        print(
            f"[{number}/{len(jobs)}] {params}; {len(summary)} sleeve trials", flush=True
        )
    import csv
    import fcntl

    ledger_path = ROOT / "research/experiments.csv"
    with ledger_path.open("r+", newline="") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        existing = {row["trial_id"] for row in reader}
        stream.seek(0, 2)
        writer = csv.DictWriter(stream, fieldnames=fields)
        for row in summary:
            trial = cfg["batch_id"] + "/" + row["job_id"]
            if trial in existing:
                continue
            writer.writerow(
                {
                    "trial_id": trial,
                    "timestamp_utc": pd.Timestamp.now(tz="UTC").isoformat(),
                    "hypothesis_commit": commit,
                    "code_commit": commit,
                    "data_sha256": digest(identity),
                    "config_sha256": sha(CONFIG),
                    "sample": "development",
                    "parameters": canonical(
                        {
                            k: row[k]
                            for k in [
                                "sleeve",
                                "lookback",
                                "quantile",
                                "family",
                                "direction",
                                "rebalance",
                                "cost_multiple",
                            ]
                        }
                    ),
                    "cost_model": "frozen pilot cost scenarios",
                    "result_path": str(
                        (out / (row["job_id"] + ".csv")).relative_to(ROOT)
                    ),
                    "status": row["status"],
                    "conclusion": canonical(row),
                    "holdout_access": "false",
                }
            )
    frame = pd.DataFrame(summary)
    frame.to_csv(out / "all-trials.csv", index=False)
    completed = frame[frame.status == "completed"]
    keys = ["sleeve", "cost_multiple"]
    selected = (
        completed.sort_values("train_sharpe", ascending=False).groupby(keys).head(1)
        if len(completed)
        else completed
    )
    selected.to_csv(out / "training-selected.csv", index=False)
    # Same-date passive controls; no ranking by development outcomes.
    intraday.loc[dates].mean(axis=1).rename("return").to_csv(
        out / "equity-equal-weight-gross-control.csv"
    )
    write_json(
        out / "summary.json",
        {
            "trials": len(frame),
            "completed": len(completed),
            "failed": len(frame) - len(completed),
            "selected": selected.replace({np.nan: None}).to_dict("records"),
            "interpretation": "Exploratory pilot; development outcomes previously inspected; no established alpha",
            "final_holdout_access": False,
        },
    )
    print("Finished. Results:", out, flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "run"])
    args = parser.parse_args()
    commit = frozen()
    cfg = json.loads(CONFIG.read_text())
    if cfg["end"] > "2025-07-28":
        raise ValueError("Locked DAX holdout boundary")
    if args.action == "prepare":
        prepare(cfg, commit)
    else:
        run(cfg, commit)


if __name__ == "__main__":
    main()
