"""Frozen parameter grids, resumable local jobs and chronological evaluation."""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import os
import platform
import re
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import UTC, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOLDOUT = "2024-05-27"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_hash(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def timestamp():
    return datetime.now(UTC).isoformat()


def expand_values(value):
    if isinstance(value, list):
        if not value:
            raise ValueError("Grid values must be a nonempty list")
        canonical(value)
        if len({canonical(x) for x in value}) != len(value):
            raise ValueError("Duplicate grid values")
        return value
    if not isinstance(value, dict) or set(value) != {"start", "stop", "step"}:
        raise ValueError("Use a list or {start, stop, step}; stop is exclusive")
    if any(
        isinstance(x, bool) or not isinstance(x, (int, float)) for x in value.values()
    ):
        raise ValueError("Range limits must be numeric")
    start, stop, step = (Decimal(str(value[k])) for k in ("start", "stop", "step"))
    if not all(x.is_finite() for x in (start, stop, step)) or step == 0:
        raise ValueError("Range limits must be finite and step nonzero")
    if (stop - start) * step <= 0:
        raise ValueError("Empty range or incorrect step direction")
    values = []
    current = start
    integers = all(isinstance(x, int) for x in value.values())
    while current < stop if step > 0 else current > stop:
        values.append(int(current) if integers else float(current))
        if len(values) > 10000:
            raise ValueError("Single range exceeds 10000 values")
        current += step
    return values


def expand_grid(grid):
    if not isinstance(grid, dict):
        raise TypeError("grid must map parameter names to values or ranges")
    names = sorted(grid)
    values = [expand_values(grid[name]) for name in names]
    if math.prod(len(v) for v in values) > 10000:
        raise ValueError("Grid exceeds 10000 combinations")
    return [
        dict(zip(names, items, strict=True)) for items in itertools.product(*values)
    ]


def validate_windows(config):
    from datetime import date

    windows = config["windows"]
    train, validation = windows["training"], windows["validation"]
    parsed = [date.fromisoformat(x) for x in (*train, *validation)]
    if len(train) != 2 or len(validation) != 2:
        raise ValueError("Each window is [start, exclusive_end]")
    if not (
        parsed[0] < parsed[1] <= parsed[2] < parsed[3] <= date.fromisoformat(HOLDOUT)
    ):
        raise ValueError("Windows overlap, are empty or access the locked holdout")
    if windows.get("holdout_start", HOLDOUT) != HOLDOUT:
        raise ValueError("The locked final boundary cannot be overridden")


def expand_jobs(config, registry=None):
    if registry is None:
        from src.strategies import get_strategy

        registry = get_strategy
    validate_windows(config)
    jobs = []
    identities = set()
    for entry in config["strategies"]:
        spec = registry(entry["id"])
        parameters = (
            expand_grid(entry["grid"]) if "grid" in entry else list(spec.default_grid)
        )
        universes = entry.get("universes", [list(spec.supported_roots)])
        frequencies = entry.get("frequencies", ["monthly"])
        for params, universe, frequency in itertools.product(
            parameters, universes, frequencies
        ):
            spec.validate_params(params)
            if (
                not universe
                or len(set(universe)) != len(universe)
                or len(universe) < spec.min_roots
                or not set(universe).issubset(spec.supported_roots)
            ):
                raise ValueError(f"Invalid universe for {entry['id']}: {universe}")
            if frequency not in ("daily", "weekly", "monthly"):
                raise ValueError("Frequency must be daily, weekly or monthly")
            job = {
                "strategy": spec.id,
                "params": json.loads(canonical(dict(params))),
                "universe": sorted(universe),
                "frequency": frequency,
            }
            if entry.get("risk"):
                job["risk"] = entry["risk"]
            identity = digest(job)[:20]
            if identity in identities:
                raise ValueError("Duplicate job in the batch")
            identities.add(identity)
            jobs.append({"id": identity, **job})
    limit = config.get("max_jobs", 512)
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("max_jobs must be a positive integer")
    if len(jobs) > limit:
        raise ValueError(f"Grid produces {len(jobs)} jobs; declared limit is {limit}")
    return jobs


def source_hashes():
    paths = [ROOT / "pyproject.toml", ROOT / "uv.lock", Path(__file__)]
    paths += sorted((ROOT / "src" / "strategies").glob("*.py"))
    paths += [
        ROOT / "src" / "futures_engine.py",
        ROOT / "src" / "futures_data.py",
        ROOT / "src" / "batch_analysis.py",
    ]
    return {str(path.relative_to(ROOT)): file_hash(path) for path in paths}


def dataset_path(config):
    context = Path(os.environ.get("GQH_CONTEXT_DIR", ROOT / ".agent-work/shared"))
    relative = Path(config["dataset"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("dataset must be relative to the context checkout")
    return (context / relative).resolve()


def make_plan(config_path):
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text())
    if config.get("version") != 1 or not re.fullmatch(
        r"[a-zA-Z0-9_-]+", config["batch_id"]
    ):
        raise ValueError("Expected version 1 and a simple batch_id")
    jobs = expand_jobs(config)
    manifest = dataset_path(config) / "prepared-manifest.json"
    metadata = json.loads(manifest.read_text())
    if metadata["period"]["end_exclusive"] > HOLDOUT:
        raise ValueError("Dataset manifest crosses the locked holdout")
    return {
        "version": 1,
        "config_path": str(config_path.relative_to(ROOT)),
        "config_sha256": file_hash(config_path),
        "config": config,
        "source_sha256": source_hashes(),
        "dataset_manifest_sha256": file_hash(manifest),
        "jobs": jobs,
        "job_count": len(jobs),
        "final_holdout_access": False,
    }


def verify_plan(plan_path, freeze_commit):
    plan_path = Path(plan_path).resolve()
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", freeze_commit):
        raise ValueError("freeze_commit must be a Git commit SHA")
    relative = str(plan_path.relative_to(ROOT))
    frozen = subprocess.run(
        ["git", "show", f"{freeze_commit}:{relative}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    if frozen != plan_path.read_bytes():
        raise ValueError(
            "Resolved plan must be committed before any market-data evaluation"
        )
    plan = json.loads(frozen)
    validate_windows(plan["config"])
    if file_hash(ROOT / plan["config_path"]) != plan["config_sha256"]:
        raise ValueError("Config differs from its frozen plan")
    if source_hashes() != plan["source_sha256"]:
        raise ValueError("Implementation/dependencies differ from the frozen plan")
    if (
        file_hash(dataset_path(plan["config"]) / "prepared-manifest.json")
        != plan["dataset_manifest_sha256"]
    ):
        raise ValueError("Dataset manifest differs from the frozen plan")
    if expand_jobs(plan["config"]) != plan["jobs"]:
        raise ValueError("Resolved jobs differ from the frozen grid")
    return plan


@lru_cache(maxsize=2)
def _inputs(path, delay):
    from src.futures_data import FuturesInputs

    return FuturesInputs.from_directory(path, extra_information_bars=delay)


def execute_job(task):
    """Process worker; all strategy inputs and execution come from the shared engine."""
    from src.futures_engine import evaluate
    from src.strategies import get_strategy

    started = time.monotonic()
    output = Path(task["output"])
    output.mkdir(parents=True, exist_ok=True)
    status_path = Path(task["status_path"]) if "status_path" in task else None
    if status_path is not None:
        running = json.loads(status_path.read_text())
        running.update(status="running", started_at=timestamp(), worker_pid=os.getpid())
        write_json(status_path, running)
    try:
        if task["job"]["strategy"] == "__long_control__":
            import pandas as pd

            def signal(view, params):
                return pd.Series(1.0, index=view.roots)
        else:
            signal = get_strategy(task["job"]["strategy"]).signal
        result = evaluate(
            _inputs(task["dataset"], task.get("delay", 0)),
            signal,
            task["job"]["params"],
            window=tuple(task["window"]),
            costs=task["costs"],
            frequency=task["job"]["frequency"],
            universe=tuple(task["job"]["universe"]),
            risk=task.get("risk", {}),
            output=output,
        )
        canonical(result.metrics)
        artefacts = {
            str(p.relative_to(output)): file_hash(p)
            for p in output.rglob("*")
            if p.is_file()
        }
        return {
            "status": "completed",
            "metrics": result.metrics,
            "artefacts": artefacts,
            "elapsed_seconds": time.monotonic() - started,
        }
    except Exception as exc:  # noqa: BLE001 -- isolate and retain arbitrary plugin failures.
        import traceback

        (output / "error.txt").write_text(traceback.format_exc())
        return {
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_seconds": time.monotonic() - started,
        }


def trial_id(job, stage, multiple=1, delay=0):
    return f"{stage}-{job['id']}-c{multiple}-d{delay}"


def _ledger(batch_id, job, record, plan, commit, output):
    import fcntl

    path = ROOT / "research/experiments.csv"
    with path.open("r+", newline="") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        names = next(csv.reader(stream))
        identity = f"{batch_id}/{record['trial_id']}/attempt-{record['attempt']}"
        if any(
            row["trial_id"] == identity
            for row in csv.DictReader(stream, fieldnames=names)
        ):
            return
        stream.seek(0, 2)
        row = {
            "trial_id": identity,
            "timestamp_utc": record["finished_at"],
            "hypothesis_commit": commit,
            "code_commit": commit,
            "data_sha256": plan["dataset_manifest_sha256"],
            "config_sha256": plan["config_sha256"],
            "sample": record["stage"],
            "parameters": canonical(job),
            "cost_model": canonical(record["costs"]),
            "result_path": str(output.relative_to(ROOT)),
            "status": record["status"],
            "conclusion": record.get("error", canonical(record.get("metrics", {}))),
            "holdout_access": "false",
        }
        csv.DictWriter(stream, fieldnames=names).writerow(row)
        stream.flush()
        os.fsync(stream.fileno())


def _stage(plan, jobs, stage, commit, workers, multiple=1, delay=0, retry_failed=False):
    config = plan["config"]
    batch = ROOT / "results" / config["batch_id"]
    costs = {
        **config.get("costs", {"commission": 2.5, "ticks": 1}),
        "multiple": multiple,
    }
    pending, records = [], []
    for job in jobs:
        identity = trial_id(job, stage, multiple, delay)
        folder = batch / "jobs" / identity
        status_file = folder / "status.json"
        previous = json.loads(status_file.read_text()) if status_file.exists() else None
        if previous and previous["plan_sha256"] != digest(plan):
            raise ValueError(
                "Existing results belong to a different frozen plan; use a new batch_id"
            )
        if previous and previous["status"] == "completed":
            attempt_folder = folder / f"attempt-{previous['attempt']}"
            artefacts = previous.get("artefacts", {})
            if not artefacts or any(
                not (attempt_folder / name).is_file()
                or file_hash(attempt_folder / name) != sha
                for name, sha in artefacts.items()
            ):
                raise ValueError(
                    f"Completed job artefacts changed or disappeared: {identity}"
                )
        if previous and (
            previous["status"] == "completed"
            or previous["status"] == "failed"
            and not retry_failed
        ):
            _ledger(
                config["batch_id"],
                job,
                previous,
                plan,
                commit,
                folder / f"attempt-{previous['attempt']}",
            )
            records.append(previous)
            continue
        if previous and previous["status"] in ("queued", "running"):
            interrupted = {
                **previous,
                "status": "failed",
                "finished_at": timestamp(),
                "error": "Previous runner stopped before recording this attempt",
            }
            write_json(
                folder / f"attempt-{previous['attempt']}" / "status.json", interrupted
            )
            _ledger(
                config["batch_id"],
                job,
                interrupted,
                plan,
                commit,
                folder / f"attempt-{previous['attempt']}",
            )
        attempt = previous.get("attempt", 0) + 1 if previous else 1
        task = {
            "job": job,
            "dataset": str(dataset_path(config)),
            "window": config["windows"][stage],
            "costs": costs,
            "delay": delay,
            "risk": {**config.get("risk", {}), **job.get("risk", {})},
            "output": str(folder / f"attempt-{attempt}"),
            "status_path": str(status_file),
        }
        record = {
            "trial_id": identity,
            "job": job,
            "stage": stage,
            "costs": costs,
            "delay": delay,
            "attempt": attempt,
            "plan_sha256": digest(plan),
            "status": "queued",
            "started_at": timestamp(),
        }
        write_json(status_file, record)
        pending.append((task, record, status_file))
    if not pending:
        return records
    started = time.monotonic()
    print(f"{stage}: {len(pending)} queued, {len(records)} retained", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(execute_job, task): (task, record, path)
            for task, record, path in pending
        }
        for number, future in enumerate(as_completed(futures), 1):
            task, record, path = futures[future]
            try:
                outcome = future.result()
            except Exception as exc:  # noqa: BLE001 -- retain process-pool failures per trial.
                outcome = {"status": "failed", "error": f"Worker failed: {exc}"}
            record.update(outcome, finished_at=timestamp())
            write_json(path, record)
            _ledger(
                config["batch_id"],
                task["job"],
                record,
                plan,
                commit,
                Path(task["output"]),
            )
            records.append(record)
            eta = (time.monotonic() - started) / number * (len(pending) - number)
            metrics = record.get("metrics", {})
            detail = (
                f"Sharpe={metrics.get('sharpe')} net={metrics.get('net_pnl')}"
                if metrics
                else record.get("error", "")
            )
            print(
                f"[{number}/{len(pending)}] {record['trial_id']} {record['status']} {detail}; ETA {eta / 60:.1f}m",
                flush=True,
            )
            write_json(
                batch / "progress.json",
                {
                    "stage": stage,
                    "finished": number,
                    "pending": len(pending) - number,
                    "retained": len(records) - number,
                    "updated_at": timestamp(),
                    "eta_seconds": eta,
                },
            )
    return records


def select_candidates(records, min_sharpe=0.25):
    groups = {}
    for record in records:
        if record["status"] != "completed":
            continue
        metrics, job = record["metrics"], record["job"]
        if (
            metrics.get("sharpe") is None
            or metrics["sharpe"] < min_sharpe
            or metrics.get("net_pnl", 0) <= 0
        ):
            continue
        key = canonical([job["strategy"], job["universe"], job["frequency"]])
        prior = groups.get(key)
        if prior is None or (-metrics["sharpe"], job["id"]) < (
            -prior["metrics"]["sharpe"],
            prior["job"]["id"],
        ):
            groups[key] = record
    return [groups[key]["job"] for key in sorted(groups)]


def run_plan(plan_path, commit, workers=4, retry_failed=False, training_only=False):
    if not 1 <= workers <= 16:
        raise ValueError("workers must be between 1 and 16")
    plan = verify_plan(plan_path, commit)
    config = plan["config"]
    batch = ROOT / "results" / config["batch_id"]
    batch.mkdir(parents=True, exist_ok=True)
    lock = batch / "run.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        pid = int(lock.read_text())
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            lock.unlink()
            return run_plan(plan_path, commit, workers, retry_failed, training_only)
        raise RuntimeError(f"Batch already running as PID {pid}") from None
    with os.fdopen(descriptor, "w") as stream:
        stream.write(str(os.getpid()))
    write_json(batch / "plan.json", plan)
    write_json(
        batch / "runtime.json",
        {
            "python": platform.python_version(),
            "freeze_commit": commit,
            "workers": workers,
            "started_at": timestamp(),
        },
    )
    try:
        training = _stage(
            plan, plan["jobs"], "training", commit, workers, retry_failed=retry_failed
        )
        selected = select_candidates(
            training, config.get("selection", {}).get("min_sharpe", 0.25)
        )
        selection_path = batch / "selection.json"
        selection = {
            "plan_sha256": digest(plan),
            "jobs": selected,
            "based_on": "training only",
        }
        if (
            selection_path.exists()
            and json.loads(selection_path.read_text()) != selection
        ):
            raise ValueError(
                "Frozen selection would change; use a new preregistered batch"
            )
        write_json(selection_path, selection)
        from src.batch_analysis import summarise_grid

        print("Writing grid tables and sensitivity plots...", flush=True)
        summarise_grid(training, batch)
        validation = []
        if (
            not training_only
            and selected
            and config.get("validation", {}).get("enabled", True)
        ):
            stress = _stage(
                plan,
                selected,
                "training",
                commit,
                workers,
                multiple=2,
                retry_failed=retry_failed,
            )
            passing = {
                r["job"]["id"]
                for r in stress
                if r["status"] == "completed" and r["metrics"].get("net_pnl", 0) > 0
            }
            finalists = [job for job in selected if job["id"] in passing]
            write_json(
                batch / "validation-selection.json",
                {"jobs": finalists, "gate": "training positive after doubled costs"},
            )
            validation = _stage(
                plan,
                finalists,
                "validation",
                commit,
                workers,
                retry_failed=retry_failed,
            )
            _stage(
                plan,
                finalists,
                "validation",
                commit,
                workers,
                multiple=2,
                retry_failed=retry_failed,
            )
            _stage(
                plan,
                finalists,
                "validation",
                commit,
                workers,
                delay=1,
                retry_failed=retry_failed,
            )
        write_json(
            batch / "summary.json",
            {
                "training_jobs": len(training),
                "training_completed": sum(r["status"] == "completed" for r in training),
                "training_failed": sum(r["status"] == "failed" for r in training),
                "selected": len(selected),
                "validation": validation,
                "final_holdout_access": False,
                "finished_at": timestamp(),
            },
        )
        print(f"Finished. Results: {batch}", flush=True)
    finally:
        lock.unlink(missing_ok=True)


def batch_status(batch_id):
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", batch_id):
        raise ValueError("Invalid batch_id")
    folder = ROOT / "results" / batch_id
    records = [
        json.loads(p.read_text()) for p in (folder / "jobs").glob("*/status.json")
    ]
    counts = {
        state: sum(r["status"] == state for r in records)
        for state in ("queued", "running", "completed", "failed")
    }
    progress = (
        json.loads((folder / "progress.json").read_text())
        if (folder / "progress.json").exists()
        else {}
    )
    return {
        "batch": batch_id,
        **counts,
        "progress": progress,
        "finished": (folder / "summary.json").exists(),
    }
