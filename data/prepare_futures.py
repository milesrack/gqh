"""Normalise authorised local futures archives; never acquire data.

Run with ``uv run --locked python -m data.prepare_futures``. Relative source
paths resolve under GQH_CONTEXT_DIR (default .agent-work/shared); outputs are
explicit generated derivatives, separate from immutable source archives.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

import databento as db

from src.futures_data import CALENDAR_CLOSURES, FIXED_HOLDOUT_START, file_hash, utc

ROOT = Path(__file__).resolve().parents[1]


def prepare(source_dir, output_dir):
    source_dir, output_dir = Path(source_dir), Path(output_dir)
    raw_manifest = json.loads((source_dir / "raw-manifest.json").read_text())
    if utc(raw_manifest["period"]["end_exclusive"]) > FIXED_HOLDOUT_START:
        raise ValueError("Source manifest crosses locked final period; no DBN parsed")
    if utc(raw_manifest["holdout_start"]) != FIXED_HOLDOUT_START:
        raise ValueError("Fixed final boundary mismatch")
    stores = {}
    sources = []
    for item in raw_manifest["files"]:
        path = (source_dir / item["path"]).resolve()
        if not path.is_relative_to(source_dir.resolve()):
            raise ValueError("Raw source escaped canonical dataset directory")
        if file_hash(path) != item["sha256"]:
            raise ValueError(f"Immutable source checksum mismatch: {path.name}")
        store = db.DBNStore.from_file(path)
        if store.metadata.end is None or utc(store.metadata.end) > FIXED_HOLDOUT_START:
            raise ValueError(
                "DBN header includes locked period; no price records decoded"
            )
        sources.append(
            {"path": os.path.relpath(path, output_dir), "sha256": item["sha256"]}
        )
        if "parent-bars" in path.name:
            stores["bars"] = store
        elif "outright-definitions" in path.name:
            stores["definitions"] = store
    if set(stores) != {"bars", "definitions"}:
        raise ValueError(
            "Parent prices and complete sparse outright definitions required"
        )
    if output_dir.exists() and (output_dir / "prepared-manifest.json").exists():
        prior = json.loads((output_dir / "prepared-manifest.json").read_text())
        if prior["sources"] != sources:
            raise ValueError("Prepared output belongs to different immutable sources")
        for item in prior["files"].values():
            if file_hash(output_dir / item["path"]) != item["sha256"]:
                raise ValueError("Existing prepared derivative checksum mismatch")
        return prior
    output_dir.mkdir(parents=True, exist_ok=True)
    bars = stores["bars"].to_df().reset_index()
    outright = bars.symbol.map(
        lambda s: bool(re.fullmatch(r"(ES|NQ|ZN|CL|GC|6E)[FGHJKMNQUVXZ]\d{1,4}", s))
    )
    bars = bars.loc[outright].copy()
    bars["root"] = bars.symbol.str.extract(r"^(ES|NQ|ZN|CL|GC|6E)")
    bars["date"] = bars.ts_event.dt.normalize()
    if (bars.date >= FIXED_HOLDOUT_START).any() or bars.duplicated(
        ["date", "symbol"]
    ).any():
        raise ValueError("Locked price or ambiguous raw-symbol/date identity")
    definitions = stores["definitions"].to_df().reset_index()
    if not definitions.instrument_class.eq("F").all():
        raise ValueError("Sparse definition archive contains a non-outright instrument")
    files = {}
    for role, frame, name in [
        ("bars", bars, "outright-bars.parquet"),
        ("definitions", definitions, "outright-definitions.parquet"),
    ]:
        path = output_dir / name
        frame.to_parquet(path, index=False)
        files[role] = {"path": name, "sha256": file_hash(path), "rows": len(frame)}
    manifest = {
        "version": 1,
        "period": raw_manifest["period"],
        "fixed_holdout_start": str(FIXED_HOLDOUT_START.date()),
        "sources": sources,
        "files": files,
        "roots": raw_manifest["roots"],
        "calendar_closures": list(CALENDAR_CLOSURES),
        "prepared_at": datetime.now(UTC).isoformat(),
        "databento_version": db.__version__,
        "price_adjustment": "none",
        "strategy_outcomes_evaluated": False,
    }
    (output_dir / "prepared-manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", default="data/futures-daily-development")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    context = Path(os.environ.get("GQH_CONTEXT_DIR", ROOT / ".agent-work/shared"))
    source = Path(args.source_dir)
    if not source.is_absolute():
        source = context / source
    manifest = prepare(source, Path(args.output_dir).resolve())
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
