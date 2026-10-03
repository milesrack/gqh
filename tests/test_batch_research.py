"""Independent frozen-grid, early-guard and resumable-ledger regressions."""

import copy
import json
from concurrent.futures import Future
from types import SimpleNamespace

import pytest

from src import batch_research as batch


def config():
    return {
        "version": 1,
        "batch_id": "synthetic",
        "dataset": "data/synthetic",
        "windows": {
            "training": ["2015-01-01", "2022-01-19"],
            "validation": ["2022-01-19", "2024-05-27"],
        },
        "strategies": [
            {
                "id": "synthetic",
                "grid": {"length": [20, 40]},
                "universes": [["ES", "NQ"]],
            }
        ],
    }


def registry(name):
    assert name == "synthetic"

    def validate(params):
        if (
            set(params) != {"length"}
            or not isinstance(params["length"], int)
            or params["length"] < 1
        ):
            raise ValueError("Invalid length")

    return SimpleNamespace(
        id=name,
        default_grid=[{"length": 20}],
        supported_roots=("ES", "NQ"),
        min_roots=1,
        validate_params=validate,
    )


def test_decimal_ranges_are_exact_stop_exclusive_and_directional():
    assert batch.expand_values({"start": 0.1, "stop": 0.4, "step": 0.1}) == [
        0.1,
        0.2,
        0.3,
    ]
    assert batch.expand_values({"start": 3, "stop": 0, "step": -1}) == [3, 2, 1]
    assert batch.expand_grid({"z": [1, 2], "a": [3, 4]}) == [
        {"a": 3, "z": 1},
        {"a": 3, "z": 2},
        {"a": 4, "z": 1},
        {"a": 4, "z": 2},
    ]


@pytest.mark.parametrize(
    "value",
    [
        [],
        [1, 1],
        {"start": 1, "stop": 2, "step": 0},
        {"start": 2, "stop": 1, "step": 1},
        {"start": True, "stop": 3, "step": 1},
        {"start": 0, "stop": float("inf"), "step": 1},
    ],
)
def test_invalid_grid_values_fail(value):
    with pytest.raises(ValueError):
        batch.expand_values(value)


def test_grid_size_bound_prevents_runaway_expansion():
    with pytest.raises(ValueError, match="10000"):
        batch.expand_grid({"a": list(range(101)), "b": list(range(101))})


def test_job_identity_independent_of_universe_order_and_config_key_order():
    original = config()
    reversed_universe = copy.deepcopy(original)
    reversed_universe["strategies"][0]["universes"] = [["NQ", "ES"]]
    assert batch.expand_jobs(original, registry) == batch.expand_jobs(
        reversed_universe, registry
    )
    jobs = batch.expand_jobs(original, registry)
    assert jobs[0]["id"] != jobs[1]["id"]
    assert len({j["id"] for j in jobs}) == 2


def test_duplicate_jobs_and_declared_budget_are_fatal():
    duplicate = config()
    duplicate["strategies"] *= 2
    with pytest.raises(ValueError, match="Duplicate job"):
        batch.expand_jobs(duplicate, registry)
    limited = config()
    limited["max_jobs"] = 1
    with pytest.raises(ValueError, match="declared limit"):
        batch.expand_jobs(limited, registry)


@pytest.mark.parametrize(
    "window",
    [
        {
            "training": ["2015-01-01", "2022-01-20"],
            "validation": ["2022-01-19", "2024-05-27"],
        },
        {
            "training": ["2015-01-01", "2022-01-19"],
            "validation": ["2022-01-19", "2024-05-28"],
        },
        {
            "training": ["2015-01-01", "2022-01-19"],
            "validation": ["2022-01-19", "2024-05-27"],
            "holdout_start": "2025-01-01",
        },
    ],
)
def test_windows_reject_overlap_holdout_and_boundary_override(window):
    value = config()
    value["windows"] = window
    with pytest.raises(ValueError):
        batch.validate_windows(value)


def test_failed_and_unprofitable_trials_cannot_enter_selection():
    jobs = batch.expand_jobs(config(), registry)

    def record(job, status, sharpe, pnl):
        return {
            "job": job,
            "status": status,
            "metrics": {"sharpe": sharpe, "net_pnl": pnl},
        }

    records = [record(jobs[0], "failed", 20, 100), record(jobs[1], "completed", 2, -1)]
    assert batch.select_candidates(records) == []
    records = [record(j, "completed", 1, 100) for j in jobs]
    assert batch.select_candidates(records) == [min(jobs, key=lambda j: j["id"])]
    assert batch.select_candidates(list(reversed(records))) == batch.select_candidates(
        records
    )


def install_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "ROOT", tmp_path)
    cfg = config()
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(cfg))
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "prepared-manifest.json").write_text("{}")
    jobs = batch.expand_jobs(cfg, registry)
    plan = {
        "config_path": "config.json",
        "config_sha256": batch.file_hash(config_path),
        "config": cfg,
        "source_sha256": {"src/synthetic.py": "source"},
        "dataset_manifest_sha256": batch.file_hash(dataset / "prepared-manifest.json"),
        "jobs": jobs,
        "job_count": len(jobs),
        "final_holdout_access": False,
    }
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    frozen = path.read_bytes()
    monkeypatch.setattr(
        batch.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=frozen)
    )
    monkeypatch.setattr(batch, "source_hashes", lambda: {"src/synthetic.py": "source"})
    monkeypatch.setattr(batch, "dataset_path", lambda c: dataset)
    original = batch.expand_jobs
    monkeypatch.setattr(batch, "expand_jobs", lambda c: original(c, registry))
    monkeypatch.setattr(
        batch, "_inputs", lambda *a: pytest.fail("price access before guard")
    )
    return path, plan, dataset


@pytest.mark.parametrize("changed", ["plan", "config", "source", "dataset"])
def test_frozen_artifact_mutation_rejected_before_price_access(
    tmp_path, monkeypatch, changed
):
    path, _plan, dataset = install_plan(tmp_path, monkeypatch)
    if changed == "plan":
        path.write_text(path.read_text() + "\n")
    elif changed == "config":
        (tmp_path / "config.json").write_text("{}")
    elif changed == "source":
        monkeypatch.setattr(
            batch, "source_hashes", lambda: {"src/synthetic.py": "changed"}
        )
    else:
        (dataset / "prepared-manifest.json").write_text('{"changed":true}')
    with pytest.raises(ValueError):
        batch.verify_plan(path, "abcdef0")


def ledger_sink(records):
    def append(*args):
        record = args[2]
        key = (record["trial_id"], record["attempt"])
        if not any((r["trial_id"], r["attempt"]) == key for r in records):
            records.append(record.copy())

    return append


class ImmediatePool:
    def __init__(self, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def submit(self, fn, task):
        future = Future()
        future.set_result(fn(task))
        return future


def test_stage_failure_ledger_resume_and_explicit_retry(tmp_path, monkeypatch):
    _, plan, _ = install_plan(tmp_path, monkeypatch)
    calls, ledger = [], []
    monkeypatch.setattr(batch, "ProcessPoolExecutor", ImmediatePool)

    def worker(task):
        calls.append(task)
        return {"status": "failed", "error": "synthetic missing contract"}

    monkeypatch.setattr(batch, "execute_job", worker)
    monkeypatch.setattr(batch, "_ledger", ledger_sink(ledger))
    first = batch._stage(plan, plan["jobs"], "training", "abcdef0", 1)
    assert len(calls) == len(ledger) == 2
    assert all(r["status"] == "failed" and r["attempt"] == 1 for r in first)
    second = batch._stage(plan, plan["jobs"], "training", "abcdef0", 1)
    assert len(calls) == len(ledger) == 2
    assert sorted(second, key=lambda r: r["trial_id"]) == sorted(
        first, key=lambda r: r["trial_id"]
    )
    third = batch._stage(
        plan, plan["jobs"], "training", "abcdef0", 1, retry_failed=True
    )
    assert len(calls) == len(ledger) == 4
    assert all(r["attempt"] == 2 for r in third)


def test_run_guard_fails_before_workers_or_price_access(tmp_path, monkeypatch):
    path, _, _ = install_plan(tmp_path, monkeypatch)
    path.write_text(path.read_text() + "\n")
    monkeypatch.setattr(
        batch, "ProcessPoolExecutor", lambda **k: pytest.fail("workers started")
    )
    with pytest.raises(ValueError, match="committed"):
        batch.run_plan(path, "abcdef0")
    assert not (tmp_path / "results").exists()


def test_completed_jobs_retain_artifacts_and_do_not_duplicate_ledger(
    tmp_path, monkeypatch
):
    _, plan, _ = install_plan(tmp_path, monkeypatch)
    calls, ledger = [], []
    monkeypatch.setattr(batch, "ProcessPoolExecutor", ImmediatePool)

    def worker(task):
        calls.append(task)
        folder = batch.Path(task["output"])
        folder.mkdir(parents=True)
        artifact = folder / "metrics.json"
        artifact.write_text('{"net_pnl":100,"sharpe":1}')
        return {
            "status": "completed",
            "metrics": {"net_pnl": 100, "sharpe": 1},
            "artefacts": {"metrics.json": batch.file_hash(artifact)},
        }

    monkeypatch.setattr(batch, "execute_job", worker)
    monkeypatch.setattr(batch, "_ledger", ledger_sink(ledger))
    batch._stage(plan, plan["jobs"], "training", "abcdef0", 1)
    batch._stage(plan, plan["jobs"], "training", "abcdef0", 1, retry_failed=True)
    assert len(calls) == len(ledger) == 2
    artifact = batch.Path(calls[0]["output"]) / "metrics.json"
    artifact.write_text("tampered result")
    with pytest.raises(ValueError, match="artefacts"):
        batch._stage(plan, plan["jobs"], "training", "abcdef0", 1)
    assert len(calls) == 2


def test_ledger_append_is_idempotent_per_attempt(tmp_path, monkeypatch):
    import csv

    _, plan, _ = install_plan(tmp_path, monkeypatch)
    path = tmp_path / "research" / "experiments.csv"
    path.parent.mkdir()
    names = [
        "trial_id",
        "timestamp_utc",
        "hypothesis_commit",
        "code_commit",
        "data_sha256",
        "config_sha256",
        "sample",
        "parameters",
        "cost_model",
        "result_path",
        "status",
        "conclusion",
        "holdout_access",
    ]
    path.write_text(",".join(names) + "\n")
    job = plan["jobs"][0]
    record = {
        "trial_id": batch.trial_id(job, "training"),
        "attempt": 1,
        "finished_at": "2026-10-03T00:00:00Z",
        "stage": "training",
        "costs": {"multiple": 1},
        "status": "failed",
        "error": "missing bar",
    }
    output = tmp_path / "results" / "synthetic" / "attempt-1"
    for _ in range(2):
        batch._ledger("synthetic", job, record, plan, "abcdef0", output)
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 1
    assert rows[0]["holdout_access"] == "false"


def test_resume_repairs_terminal_status_written_before_ledger_failure(
    tmp_path, monkeypatch
):
    _, plan, _ = install_plan(tmp_path, monkeypatch)
    monkeypatch.setattr(batch, "ProcessPoolExecutor", ImmediatePool)
    calls, appended = [], []

    def worker(task):
        calls.append(task)
        return {"status": "failed", "error": "synthetic missing bar"}

    def broken_ledger(*args):
        raise OSError("synthetic interruption after terminal status")

    monkeypatch.setattr(batch, "execute_job", worker)
    monkeypatch.setattr(batch, "_ledger", broken_ledger)
    with pytest.raises(OSError):
        batch._stage(plan, plan["jobs"][:1], "training", "abcdef0", 1)
    monkeypatch.setattr(batch, "_ledger", lambda *args: appended.append(args[2]))
    batch._stage(plan, plan["jobs"][:1], "training", "abcdef0", 1)
    assert len(calls) == 1
    assert len(appended) == 1
    assert appended[0]["attempt"] == 1


def test_plan_resolution_is_metadata_only_and_offline(tmp_path, monkeypatch):
    import socket

    _, _, dataset = install_plan(tmp_path, monkeypatch)
    (dataset / "prepared-manifest.json").write_text(
        json.dumps(
            {
                "period": {"end_exclusive": "2024-05-27"},
                "fixed_holdout_start": "2024-05-27",
            }
        )
    )
    monkeypatch.setattr(
        socket.socket, "connect", lambda *a, **k: pytest.fail("network access")
    )
    monkeypatch.setattr(
        batch, "execute_job", lambda *a: pytest.fail("outcome evaluation")
    )
    resolved = batch.make_plan(tmp_path / "config.json")
    assert resolved["job_count"] == 2
    assert not resolved["final_holdout_access"]
    assert not (tmp_path / "results").exists()


def test_resume_preserves_abandoned_running_attempt_in_failure_ledger(
    tmp_path, monkeypatch
):
    _, plan, _ = install_plan(tmp_path, monkeypatch)
    job = plan["jobs"][0]
    identity = batch.trial_id(job, "training")
    path = tmp_path / "results" / "synthetic" / "jobs" / identity / "status.json"
    batch.write_json(
        path,
        {
            "trial_id": identity,
            "job": job,
            "stage": "training",
            "costs": {"commission": 2.5, "ticks": 1, "multiple": 1},
            "delay": 0,
            "attempt": 1,
            "plan_sha256": batch.digest(plan),
            "status": "running",
            "started_at": "2026-10-03T00:00:00Z",
        },
    )
    entries = []
    monkeypatch.setattr(batch, "ProcessPoolExecutor", ImmediatePool)
    monkeypatch.setattr(
        batch, "execute_job", lambda task: {"status": "failed", "error": "missing bar"}
    )
    monkeypatch.setattr(batch, "_ledger", ledger_sink(entries))
    result = batch._stage(plan, [job], "training", "abcdef0", 1)
    assert result[0]["attempt"] == 2
    assert sorted(r["attempt"] for r in entries) == [1, 2]
    assert all(r["status"] == "failed" for r in entries)
    assert entries[0]["error"] and entries[0]["error"] != "missing bar"
