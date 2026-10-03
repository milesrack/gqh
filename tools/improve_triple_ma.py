"""Run frozen trend diagnostics; inspected validation is development evidence."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.batch_analysis import compare_returns
from src.batch_research import _stage, digest, run_plan, verify_plan, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-commit", required=True)
    args = parser.parse_args()
    path = ROOT / "research/configs/triple-ma-improvement-plan.json"
    run_plan(path, args.freeze_commit, workers=4, training_only=True)
    plan = verify_plan(path, args.freeze_commit)
    out = ROOT / "results" / plan["config"]["batch_id"]
    import json

    records = [
        json.loads(p.read_text())
        for p in (out / "jobs").glob("training-*-c1-d0/status.json")
    ]
    neighbours = [
        r
        for r in records
        if r["job"]["strategy"] == "triple_ma" and "risk" not in r["job"]
    ]
    filters = [
        r
        for r in records
        if r["job"]["strategy"] == "separated_triple_ma" and r["status"] == "completed"
    ]
    best = max(filters, key=lambda r: r["metrics"]["sharpe"]) if filters else None
    baseline = next(
        r["job"] for r in neighbours if r["job"]["params"]["lengths"] == [5, 20, 60]
    )
    jobs = (
        [baseline]
        + [j for j in plan["jobs"] if "risk" in j]
        + ([best["job"]] if best else [])
    )
    write_json(
        out / "development-selection.json",
        {
            "jobs": jobs,
            "selection": "fixed baseline, sizing diagnostics and training-best filter",
        },
    )
    base = _stage(plan, jobs, "validation", args.freeze_commit, 4)
    doubled = _stage(plan, jobs, "validation", args.freeze_commit, 4, multiple=2)
    delayed = _stage(plan, jobs, "validation", args.freeze_commit, 4, delay=1)
    controls = []
    for job in jobs:
        j = {**job, "strategy": "__long_control__", "params": {}}
        j.pop("id")
        j["id"] = digest(j)[:20]
        controls.append(j)
    benchmarks = _stage(
        plan,
        list({j["id"]: j for j in controls}.values()),
        "validation",
        args.freeze_commit,
        4,
    )
    bm = {r["job"]["id"]: r for r in benchmarks}

    def returns(r):
        return (
            out
            / "jobs"
            / r["trial_id"]
            / f"attempt-{r['attempt']}"
            / "daily-returns.csv"
        )

    baseline_record = next(r for r in base if r["job"]["id"] == baseline["id"])
    report = []
    for j in jobs:
        r = next(x for x in base if x["job"]["id"] == j["id"])
        control = next(
            c
            for c in controls
            if c["universe"] == j["universe"] and c.get("risk") == j.get("risk")
        )
        row = {
            "job": j,
            "base": r,
            "doubled": next(x for x in doubled if x["job"]["id"] == j["id"]),
            "delayed": next(x for x in delayed if x["job"]["id"] == j["id"]),
        }
        if r["status"] == bm[control["id"]]["status"] == "completed":
            row["matched_long"] = compare_returns(
                returns(r), returns(bm[control["id"]]), 199
            )
        if (
            j["strategy"] == "separated_triple_ma"
            and r["status"] == baseline_record["status"] == "completed"
        ):
            row["incremental_filter"] = compare_returns(
                returns(r), returns(baseline_record), 199
            )
        report.append(row)
    positive = sum(
        r["status"] == "completed" and r["metrics"]["net_pnl"] > 0 for r in neighbours
    )
    write_json(
        out / "improvement-summary.json",
        {
            "neighbours": len(neighbours),
            "positive_neighbours": positive,
            "stable_region": positive / len(neighbours) >= 0.8,
            "results": report,
            "independent_validation": False,
            "final_holdout_access": False,
        },
    )
    print("Finished:", out, flush=True)


if __name__ == "__main__":
    main()
