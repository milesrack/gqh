"""Explicit cached acquisition of ALFRED vintages and CME settlement statistics."""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import databento as db
import numpy as np
import pandas as pd

from src.batch_research import file_hash, write_json


def fred(endpoint, params):
    query = {**params, "api_key": os.environ["FRED_API_KEY"], "file_type": "json"}
    url = (
        "https://api.stlouisfed.org/fred/"
        + endpoint
        + "?"
        + urllib.parse.urlencode(query)
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError):
            if attempt == 4:
                raise RuntimeError(
                    "FRED request failed; credentials and URL withheld"
                ) from None
            time.sleep(min(2**attempt, 10))


def acquire(cfg, root):
    for key in ["FRED_API_KEY", "DATABENTO_API_KEY"]:
        if not os.environ.get(key):
            raise ValueError(f"Missing {key} in ignored .env")
    raw = root / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    frames = []
    for series in cfg["series"]:
        folder = raw / "alfred" / series
        folder.mkdir(parents=True, exist_ok=True)
        dates_file = folder / "dates.json"
        if not dates_file.exists():
            write_json(
                dates_file,
                fred(
                    "series/vintagedates",
                    {
                        "series_id": series,
                        "realtime_start": cfg["macro_start"],
                        "realtime_end": str(
                            pd.Timestamp(cfg["holdout_start"]) - pd.Timedelta(days=1)
                        )[:10],
                        "limit": 10000,
                    },
                ),
            )
        dates = json.loads(dates_file.read_text())["vintage_dates"]
        for number, vintage in enumerate(dates, 1):
            file = folder / f"{vintage}.json"
            if not file.exists():
                lower = str(pd.Timestamp(vintage) - pd.DateOffset(months=16))[:10]
                write_json(
                    file,
                    fred(
                        "series/observations",
                        {
                            "series_id": series,
                            "realtime_start": vintage,
                            "realtime_end": vintage,
                            "observation_start": lower,
                            "observation_end": vintage,
                            "limit": 100000,
                            "units": "lin",
                        },
                    ),
                )
                time.sleep(0.15)
            rows = json.loads(file.read_text())["observations"]
            frames.extend(
                {
                    "series_id": series,
                    "vintage_date": vintage,
                    "observation_date": r["date"],
                    "value": r["value"],
                }
                for r in rows
            )
            print(f"ALFRED {series} [{number}/{len(dates)}] {vintage}", flush=True)
    pd.DataFrame(frames).to_parquet(root / "vintages.parquet", index=False)
    client = db.Historical()
    kwargs = {
        "dataset": "GLBX.MDP3",
        "symbols": ["SR3.FUT"],
        "stype_in": "parent",
        "start": cfg["sr3_start"],
        "end": cfg["holdout_start"],
    }
    quotes = {
        schema: float(client.metadata.get_cost(schema=schema, **kwargs))
        for schema in ["statistics", "definition"]
    }
    write_json(
        raw / "cost-estimate.json",
        {
            "requests": quotes,
            "total_usd": sum(quotes.values()),
            "cap_usd": cfg["max_download_cost_usd"],
            "parameters": kwargs,
        },
    )
    if sum(quotes.values()) > cfg["max_download_cost_usd"]:
        raise ValueError("SR3 quote exceeds authorised cap; no purchase")
    for schema, estimate in quotes.items():
        path = raw / f"{schema}.dbn.zst"
        if not path.exists():
            print(f"Databento {schema}: estimated ${estimate:.4f}", flush=True)
            client.timeseries.get_range(schema=schema, path=path, **kwargs)
        print(f"Cached SR3 {schema}", flush=True)
    prepare(cfg, root)
    paths = [p for p in root.rglob("*") if p.is_file() and p.name != "manifest.json"]
    write_json(
        root / "manifest.json",
        {
            "files": {str(p.relative_to(root)): file_hash(p) for p in paths},
            "end_exclusive": cfg["holdout_start"],
            "final_holdout_access": False,
        },
    )


def imm(year, month):
    start = pd.Timestamp(year=year, month=month, day=1, tz="UTC")
    return start + pd.Timedelta(days=(2 - start.weekday()) % 7 + 14)


def prepare(cfg, root):
    defs = db.DBNStore.from_file(root / "raw/definition.dbn.zst").to_df().reset_index()
    defs = defs[
        (defs.instrument_class == "F")
        & (defs.leg_count == 0)
        & defs.raw_symbol.str.match(r"^SR3[HMUZ]\d{1,2}$")
    ]
    stats = db.DBNStore.from_file(root / "raw/statistics.dbn.zst").to_df().reset_index()
    stats = stats[
        (stats.stat_type == 3)
        & (stats.update_action == 1)
        & ((stats.stat_flags.astype(int) & 3) == 3)
        & ((stats.stat_flags.astype(int) & 8) == 0)
    ].copy()
    if stats.ts_ref.isna().any():
        raise ValueError("Missing official settlement reference date")
    stats["trade_date"] = pd.to_datetime(stats.ts_ref, utc=True).dt.normalize()
    stats = stats[
        (stats.trade_date >= pd.Timestamp(cfg["sr3_start"], tz="UTC"))
        & (stats.trade_date < pd.Timestamp(cfg["holdout_start"], tz="UTC"))
    ]
    cutoff = (
        (stats.trade_date.dt.tz_localize(None) + pd.Timedelta(days=1, hours=6))
        .dt.tz_localize("America/Chicago")
        .dt.tz_convert("UTC")
    )
    stats = stats[
        (stats.ts_recv <= cutoff)
        & np.isfinite(stats.price)
        & (stats.price > 0)
        & (stats.price < 200)
    ]
    merged = pd.merge_asof(
        stats.sort_values("ts_recv"),
        defs[
            ["ts_recv", "instrument_id", "raw_symbol", "expiration", "activation"]
        ].sort_values("ts_recv"),
        on="ts_recv",
        by="instrument_id",
        direction="backward",
    )
    unmatched = int(merged.expiration.isna().sum())
    merged = merged.dropna(subset=["expiration", "raw_symbol"])
    if merged.empty:
        raise ValueError("No final actual settlements matched contract definitions")
    write_json(
        root / "settlement-coverage.json",
        {
            "unmatched_definitions": unmatched,
            "matched_rows": len(merged),
            "first_date": str(merged.trade_date.min()),
            "last_date": str(merged.trade_date.max()),
        },
    )
    merged["reference_end"] = [imm(x.year, x.month) for x in merged.expiration]
    merged["reference_start"] = [
        imm((x - pd.DateOffset(months=3)).year, (x - pd.DateOffset(months=3)).month)
        for x in merged.reference_end
    ]
    merged["contract"] = merged.reference_start.dt.strftime("SR3-%Y-%m")
    merged["midpoint"] = (
        merged.reference_start + (merged.reference_end - merged.reference_start) / 2
    )
    merged = merged.sort_values("ts_recv").drop_duplicates(
        ["trade_date", "contract"], keep="last"
    )
    merged[
        [
            "trade_date",
            "contract",
            "raw_symbol",
            "instrument_id",
            "price",
            "ts_recv",
            "stat_flags",
            "reference_start",
            "reference_end",
            "midpoint",
        ]
    ].to_parquet(root / "sr3_daily.parquet", index=False)
    print(
        "Prepared",
        len(merged),
        "actual final settlements; no OHLC substitution",
        flush=True,
    )
