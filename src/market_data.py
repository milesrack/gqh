"""Validate DBN definitions and normalise receipt-time events."""

import hashlib
import json
from pathlib import Path

import databento as db
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

COLUMNS = [
    "ts_recv",
    "ts_event",
    "publisher_id",
    "instrument_id",
    "action",
    "side",
    "price",
    "size",
    "flags",
    "bid_px_00",
    "ask_px_00",
    "bid_sz_00",
    "ask_sz_00",
    "symbol",
]


def validate_matched_expiry(events, day, cfg):
    symbols = events["symbol"].drop_duplicates()
    pieces = symbols.str.split()
    expiries = pd.to_datetime(pieces.str[2], format="%Y%m%d")
    if expiries.nunique() != 1 or set(pieces.str[0]) != set(cfg["products"]):
        raise ValueError("Session does not contain three matched outright contracts")
    date = pd.Timestamp(day)
    expiry = expiries.iloc[0]
    if (expiry - date).days <= cfg["roll_days"]:
        raise ValueError("Session uses a contract inside the declared roll window")
    # The next eligible quarterly third Friday is fixed by the calendar.
    candidates = []
    for year in [date.year, date.year + 1]:
        for month in [3, 6, 9, 12]:
            first = pd.Timestamp(year=year, month=month, day=1)
            third_friday = first + pd.Timedelta(days=(4 - first.weekday()) % 7 + 14)
            if (third_friday - date).days > cfg["roll_days"]:
                candidates.append(third_friday)
    if expiry != min(candidates):
        raise ValueError("Session does not use the nearest eligible quarterly expiry")


def prepare(directory, cfg, smoke=False):
    directory = Path(directory)
    manifest = [
        json.loads(line)
        for line in (directory / "manifest.jsonl").read_text().splitlines()
    ]
    allowed = []
    for item in manifest:
        r = item["request"]
        day = r["start"][:10]
        if r["schema"] == "definition":
            if not smoke or cfg["development_start"] <= day < "2025-06-07":
                allowed.append(item)
        elif smoke:
            if cfg["development_start"] <= day < "2025-06-07":
                allowed.append(item)
        elif day < cfg["holdout_start"]:
            # Reject mixed-period files rather than parsing held-out events.
            if r["end"][:10] > cfg["holdout_start"]:
                raise ValueError("Raw file crosses the locked holdout boundary")
            allowed.append(item)
    manifest = allowed
    definitions = []
    paths = []
    for item in manifest:
        path = directory.parent / item["path"]
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != item["sha256"]:
                raise ValueError(f"Data checksum mismatch: {path.name}")
        if item["request"]["schema"] == "definition":
            definitions.append(db.DBNStore.from_file(path).to_df())
        elif item["request"]["schema"] == "mbp-1":
            paths.append(path)
    if not definitions or not paths:
        raise ValueError("Both MBP-1 and definitions are required")
    definition = pd.concat(definitions)
    outright = definition[
        definition.raw_symbol.str.match(r"^(FDAX|FDXM|FDXS) SI \d{8} CS$")
    ]
    required = set(cfg["products"])
    if set(outright.raw_symbol.str.split().str[0]) != required:
        raise ValueError("Missing matched product definitions")
    # Check every recorded definition, not just the last instrument snapshot.
    if not (outright.min_price_increment > 0).all():
        raise ValueError("Undefined or non-positive native price increment")
    if (
        not outright.raw_symbol.str.split()
        .str[2]
        .eq(outright.expiration.dt.strftime("%Y%m%d"))
        .all()
    ):
        raise ValueError("Raw symbol and definition expiry disagree")
    source_identity = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()
    ).hexdigest()
    caches = (
        Path(__file__).resolve().parents[1] / ".agent-work/.cache/dax" / source_identity
    )
    caches.mkdir(parents=True, exist_ok=True)
    marker = caches / "source.json"
    if (
        marker.exists()
        and json.loads(marker.read_text())["source_identity"] == source_identity
    ):
        return sorted(caches.glob("*.parquet")), source_identity
    if list(caches.glob("*.parquet")):
        raise ValueError("Normalised cache belongs to different raw sources")
    writers = {}
    try:
        for path in paths:
            store = db.DBNStore.from_file(path)
            mapping = {}
            for symbol, intervals in store.mappings.items():
                for interval in intervals:
                    instrument = int(interval["symbol"])
                    if instrument in mapping and mapping[instrument] != symbol:
                        raise ValueError(
                            "Instrument id reused within raw file; dated mapping required"
                        )
                    mapping[instrument] = symbol
            for chunk in store.to_df(count=250000, map_symbols=False):
                chunk = chunk.reset_index()
                chunk["symbol"] = chunk.instrument_id.map(mapping)
                if chunk.symbol.isna().any():
                    raise ValueError("Unmapped instrument id")
                e = chunk[COLUMNS].rename(
                    columns={
                        "bid_px_00": "bid",
                        "ask_px_00": "ask",
                        "bid_sz_00": "bid_size",
                        "ask_sz_00": "ask_size",
                    }
                )
                e["product"] = e.symbol.map({s: s.split()[0] for s in mapping.values()})
                e = e[e.symbol.isin(outright.raw_symbol)]
                e["day"] = e.ts_recv.dt.tz_convert(cfg["timezone"]).dt.floor("D")
                for day, group in e.groupby("day"):
                    day = day.strftime("%Y-%m-%d")
                    group = group.assign(day=day)
                    if day >= cfg["holdout_start"]:
                        raise ValueError("Refuse to normalise final holdout")
                    table = pa.Table.from_pandas(group, preserve_index=False)
                    if day not in writers:
                        writers[day] = pq.ParquetWriter(
                            caches / f"{day}.parquet", table.schema
                        )
                    writers[day].write_table(table)
    finally:
        for writer in writers.values():
            writer.close()
    marker.write_text(json.dumps({"source_identity": source_identity}))
    return sorted(caches.glob("*.parquet")), source_identity
