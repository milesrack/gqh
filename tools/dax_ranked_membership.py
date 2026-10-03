"""Historical membership wrapper for the frozen DAX pilot window."""

import json
import shutil
import subprocess
from pathlib import Path

import dax_ranked_pilot as pilot
import pandas as pd

ROOT = pilot.ROOT
CONFIG = ROOT / "research/configs/dax-ranked-membership.json"


def main():
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    cfg = json.loads(CONFIG.read_text())
    table_path = ROOT / cfg["membership_file"]
    for path in [
        CONFIG,
        table_path,
        Path(__file__).resolve(),
        ROOT / "research/hypotheses/dax-ranked-membership.md",
    ]:
        if (
            subprocess.check_output(
                ["git", "show", f"{commit}:{path.relative_to(ROOT)}"], cwd=ROOT
            )
            != path.read_bytes()
        ):
            raise ValueError("Commit the historical membership experiment first")
    if pilot.sha(table_path) != cfg["membership_sha256"]:
        raise ValueError("Membership hash changed")
    table = pd.read_csv(table_path)
    if table.ticker.duplicated().any():
        raise ValueError("Duplicate membership ticker")
    # Official changes are empty within this bounded pilot; assert every date.
    for day in pd.date_range(
        cfg["start"], pd.Timestamp(cfg["end"]) - pd.Timedelta(days=1)
    ):
        active = table[
            (pd.to_datetime(table.covered_from) <= day)
            & (pd.to_datetime(table.covered_until) > day)
        ]
        if sorted(active.ticker) != sorted(cfg["universe"]) or len(active) != 40:
            raise ValueError(f"Membership coverage incomplete on {day.date()}")
    original = pilot.DATA
    pilot.CONFIG = CONFIG
    pilot.DATA = ROOT / ".agent-work/shared/data/dax-ranked-membership"
    pilot.DATA.mkdir(parents=True, exist_ok=True)
    # Reuse exact original downloads; never modify the concurrently running pilot.
    for ticker in cfg["universe"]:
        source = original / f"{ticker}.parquet"
        target = pilot.DATA / source.name
        if source.exists() and not target.exists():
            shutil.copy2(source, target)
    pilot.main()


if __name__ == "__main__":
    main()
