"""Estimate explicit Databento requests before downloading them."""

import argparse
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import databento as db

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / ".agent-work/shared/data/dax-cross-contract-flow"


def client():
    return db.Historical(os.environ["DATABENTO_API_KEY"])


def quote(requests):
    def one(r):
        api = client()
        return {
            "request": r,
            "estimated_usd": api.metadata.get_cost(**r),
            "estimated_bytes": api.metadata.get_billable_size(**r),
        }

    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(one, requests))


def acquire(plan, max_usd):
    """Reprice; explicit caller cap is required, never an implicit download."""
    estimates = quote([item["request"] for item in plan["requests"]])
    total = sum(item["estimated_usd"] for item in estimates)
    if total > max_usd:
        raise ValueError(f"Request estimate ${total:.2f} exceeds cap ${max_usd:.2f}")
    DATA.mkdir(parents=True, exist_ok=True)
    manifest = DATA / "manifest.jsonl"

    recorded = (
        {json.loads(line)["path"] for line in manifest.read_text().splitlines()}
        if manifest.exists()
        else set()
    )

    def fetch(item):
        request = item["request"]
        identity = hashlib.sha256(
            json.dumps(request, sort_keys=True).encode()
        ).hexdigest()[:20]
        target = DATA / f"{identity}.dbn.zst"
        relative = target.relative_to(DATA.parent).as_posix()
        if target.exists() and relative in recorded:
            return None
        partial = target.with_suffix(".partial")
        if partial.exists():
            raise FileExistsError(f"Prior partial request needs review: {partial.name}")
        recovered = target.exists()
        if not recovered:
            client().timeseries.get_range(**request, path=partial)
            partial.rename(target)
        with target.open("rb") as stream:
            sha = hashlib.file_digest(stream, "sha256").hexdigest()
        return dict(
            item,
            path=relative,
            recovered_existing_file=recovered,
            sha256=sha,
            downloaded_utc=datetime.now(UTC).isoformat(),
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(fetch, item) for item in estimates]
        for future in as_completed(futures):
            record = future.result()
            if record:
                with manifest.open("a") as stream:
                    stream.write(json.dumps(record) + "\n")
    return estimates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["metadata", "estimate", "download"])
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--max-usd", type=float)
    args = parser.parse_args()
    if args.command == "metadata":
        api = client()
        result = {
            "range": api.metadata.get_dataset_range("XEUR.EOBI"),
            "schemas": api.metadata.list_schemas("XEUR.EOBI"),
            "publishers": api.metadata.list_publishers(),
            "symbols": api.symbology.resolve(
                dataset="XEUR.EOBI",
                symbols=["FDAX.FUT", "FDXM.FUT", "FDXS.FUT"],
                stype_in="parent",
                stype_out="instrument_id",
                start_date="2025-06-02",
                end_date="2025-06-07",
            ),
        }
        DATA.mkdir(parents=True, exist_ok=True)
        (DATA / "metadata.json").write_text(json.dumps(result, indent=2, default=str))
        print(json.dumps(result, default=str))
    else:
        plan = json.loads(args.plan.read_text())
        if args.command == "estimate":
            print(json.dumps(quote([r["request"] for r in plan["requests"]]), indent=2))
        else:
            if args.max_usd is None or args.max_usd <= 0:
                parser.error("download requires a positive --max-usd")
            print(json.dumps(acquire(plan, args.max_usd), indent=2))


if __name__ == "__main__":
    main()
