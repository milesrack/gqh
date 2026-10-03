"""Run with uv run --locked python tools/batch_research.py --help."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.batch_research import batch_status, make_plan, run_plan, write_json


def main():
    parser = argparse.ArgumentParser(
        description="Frozen futures grid search and resumable batch jobs"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser(
        "plan", help="Resolve a config without evaluating market data"
    )
    plan.add_argument("--config", required=True, type=Path)
    plan.add_argument("--output", required=True, type=Path)
    run = commands.add_parser(
        "run", help="Execute a committed plan; completed jobs resume automatically"
    )
    run.add_argument("--plan", required=True, type=Path)
    run.add_argument("--freeze-commit", required=True)
    run.add_argument("--workers", type=int, default=4)
    run.add_argument("--retry-failed", action="store_true")
    run.add_argument("--training-only", action="store_true")
    status = commands.add_parser(
        "status", help="Print saved progress without reading market data"
    )
    status.add_argument("--batch", required=True)
    args = parser.parse_args()
    if args.command == "plan":
        result = make_plan(args.config)
        write_json(args.output, result)
        print(
            f"Resolved {result['job_count']} jobs. Commit {args.output} before running."
        )
    elif args.command == "run":
        run_plan(
            args.plan,
            args.freeze_commit,
            args.workers,
            args.retry_failed,
            args.training_only,
        )
    else:
        print(json.dumps(batch_status(args.batch), indent=2))


if __name__ == "__main__":
    main()
