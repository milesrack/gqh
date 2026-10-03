"""Evaluate the frozen training selection without changing strategy parameters."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd

from src.batch_analysis import compare_returns
from src.batch_research import _stage, digest, file_hash, verify_plan, write_json


def main():
    specification = ROOT / "research/configs/futures-validation.json"
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    for relative in [
        "research/configs/futures-validation.json",
        "tools/validate_futures.py",
        "research/hypotheses/book151-futures-validation.md",
    ]:
        if (
            subprocess.check_output(["git", "show", f"{commit}:{relative}"])
            != (ROOT / relative).read_bytes()
        ):
            raise ValueError("Validation specification and runner must be committed")
    cfg = json.loads(specification.read_text())
    plan = verify_plan(ROOT / cfg["training_plan"], cfg["training_commit"])
    selection = json.loads(
        (ROOT / "results/book151-futures-v1/selection.json").read_text()
    )
    if selection != cfg["selection"] or selection["plan_sha256"] != digest(plan):
        raise ValueError("Training selection differs from frozen validation selection")
    jobs = selection["jobs"]
    plan["config"]["batch_id"] = cfg["batch_id"]
    plan["validation_specification_sha256"] = file_hash(specification)
    plan["validation_runner_sha256"] = file_hash(Path(__file__))
    out = ROOT / "results" / cfg["batch_id"]
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "plan.json", plan)
    gate = _stage(plan, jobs, "training", commit, 4, multiple=2)
    passing = {
        r["job"]["id"]
        for r in gate
        if r["status"] == "completed" and r["metrics"]["net_pnl"] > 0
    }
    finalists = [j for j in jobs if j["id"] in passing]
    write_json(
        out / "selection.json",
        {"jobs": finalists, "gate": "training positive after doubled costs"},
    )
    base = _stage(plan, finalists, "validation", commit, 4)
    doubled = _stage(plan, finalists, "validation", commit, 4, multiple=2)
    delayed = _stage(plan, finalists, "validation", commit, 4, delay=1)
    controls = {}
    for job in finalists:
        control = {**job, "strategy": "__long_control__", "params": {}}
        control.pop("id")
        control["id"] = digest(control)[:20]
        controls[job["id"]] = control
    unique = {j["id"]: j for j in controls.values()}
    benchmarks = _stage(plan, list(unique.values()), "validation", commit, 4)
    benchmark_map = {r["job"]["id"]: r for r in benchmarks}
    stress = {r["job"]["id"]: r for r in doubled}
    delay = {r["job"]["id"]: r for r in delayed}

    def returns(record):
        return (
            out
            / "jobs"
            / record["trial_id"]
            / f"attempt-{record['attempt']}"
            / "daily-returns.csv"
        )

    rows = []
    for record in base:
        job = record["job"]
        identity = job["id"]
        row = {
            "job": job,
            "base": record,
            "doubled": stress[identity],
            "delayed": delay[identity],
            "passes": False,
        }
        control = benchmark_map[controls[identity]["id"]]
        if record["status"] == control["status"] == "completed":
            row["matched_long"] = compare_returns(
                returns(record),
                returns(control),
                cfg["trials"],
                draws=cfg["bootstrap_draws"],
            )
            cash = returns(record).with_name("cash-control.csv")
            frame = pd.read_csv(returns(record))
            frame["return"] = 0.0
            frame.to_csv(cash, index=False)
            row["cash"] = compare_returns(
                returns(record), cash, cfg["trials"], draws=cfg["bootstrap_draws"]
            )
            hac = row["matched_long"]["hac"]
            row["passes"] = bool(
                hac
                and hac["alpha_ci_grid_adjusted_annual"][0] > 0
                and all(
                    r["status"] == "completed" and r["metrics"]["net_pnl"] > 0
                    for r in [record, stress[identity], delay[identity]]
                )
            )
        rows.append(row)
        print(
            job["strategy"],
            job["universe"],
            "PASS" if row["passes"] else "FAIL",
            flush=True,
        )
    write_json(
        out / "summary.json",
        {
            "candidates": len(jobs),
            "training_gate_passed": len(finalists),
            "results": rows,
            "survivors": [r["job"] for r in rows if r["passes"]],
            "final_holdout_access": False,
        },
    )
    print("Finished. Results:", out, flush=True)


if __name__ == "__main__":
    main()
