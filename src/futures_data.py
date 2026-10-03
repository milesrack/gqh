"""Local, dated-contract futures inputs with a fixed locked-price boundary."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOTS = ("ES", "NQ", "ZN", "CL", "GC", "6E")
FIXED_HOLDOUT_START = pd.Timestamp("2024-05-27", tz="UTC")
CALENDAR_CLOSURES = ("2015-04-03", "2021-04-02", "2023-04-07")


@dataclass(frozen=True)
class ContractSpec:
    multiplier: float
    tick: float


SPECS = {
    "ES": ContractSpec(50.0, 0.25),
    "NQ": ContractSpec(20.0, 0.25),
    "ZN": ContractSpec(1000.0, 1 / 64),
    "CL": ContractSpec(1000.0, 0.01),
    "GC": ContractSpec(100.0, 0.1),
    "6E": ContractSpec(125000.0, 0.00005),
}


def utc(value) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def native_tick(root: str, execution_at) -> float:
    if root == "6E" and utc(execution_at) < utc("2016-01-11"):
        return 0.00010
    return SPECS[root].tick


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def contract_is_safe(candidate, execution_at, root=None):
    """Frozen reusable operational bounds, using causally known dated metadata."""
    day = utc(execution_at)
    if candidate["expiry"] <= day:
        return False
    if root == "ZN":
        maturity = pd.Timestamp(
            year=candidate["maturity_year"],
            month=candidate["maturity_month"],
            day=1,
            tz="UTC",
        )
        return day < maturity - pd.Timedelta(days=7)
    return (candidate["expiry"] - day).days >= (14 if root == "NQ" else 40)


def select_liquid_contract(
    candidates,
    execution_at,
    incumbent=None,
    *,
    root=None,
    retain_eligible_incumbent=False,
):
    """Nearest-two new entries; optional frozen safe incumbent continuation."""
    all_eligible = sorted(
        [
            c
            for c in candidates
            if contract_is_safe(c, execution_at, root)
            and c["observed_bars"] == 20
            and c["adv"] >= 100
        ],
        key=lambda c: (c["expiry"], c["symbol"]),
    )
    eligible = all_eligible[:2]
    held = next((c for c in candidates if c["symbol"] == incumbent), None)
    if incumbent is not None and held is None:
        raise ValueError("Incumbent dated metadata disappeared")
    if held is not None:
        eligible = [c for c in eligible if c["expiry"] >= held["expiry"]]
        if retain_eligible_incumbent and held in all_eligible and held not in eligible:
            eligible.append(held)
    if not eligible:
        raise ValueError("No forward, sufficiently liquid eligible maturity")
    chosen = max(eligible, key=lambda c: (c["adv"], c["expiry"], c["symbol"]))
    if held in eligible and held["adv"] >= chosen["adv"]:
        return held
    return chosen


class FuturesInputs:
    """Read-only-by-convention development data; no provider or download client."""

    def __init__(
        self,
        bars,
        definitions,
        *,
        roots=ROOTS,
        extra_information_bars=0,
        source_manifest=None,
    ):
        self.roots = tuple(roots)
        if not self.roots or not set(self.roots) <= set(ROOTS):
            raise ValueError("Unknown or empty futures universe")
        if extra_information_bars not in (0, 1):
            raise ValueError(
                "Information delay must be the frozen zero or one extra bar"
            )
        self.extra_information_bars = extra_information_bars
        self.source_manifest = source_manifest or {}
        self.selection_policy = "book151-reusable-operational-v1"
        self.bars = bars.copy()
        self.definitions = definitions.copy()
        self.bars["date"] = pd.to_datetime(self.bars["date"], utc=True)
        if (self.bars.date >= FIXED_HOLDOUT_START).any():
            raise ValueError("Locked final price in input frames")
        source_days = pd.DatetimeIndex(sorted(self.bars.date.unique()))
        source_days = source_days[source_days.dayofweek < 5]
        self.bars = self.bars[self.bars.root.isin(self.roots)]
        if self.bars.duplicated(["date", "symbol"]).any():
            raise ValueError("Ambiguous raw-symbol/date identity")
        if not np.isfinite(self.bars[["open", "close", "volume"]]).all().all():
            raise ValueError("Nonfinite observed price or volume")
        d = self.definitions
        d["known_at"] = pd.to_datetime(d.ts_recv, utc=True)
        d["expiry"] = pd.to_datetime(d.expiration, utc=True)
        if not d.instrument_class.eq("F").all():
            raise ValueError("Definition archive contains non-outright instruments")
        keys = [
            "raw_symbol",
            "instrument_id",
            "expiry",
            "min_price_increment",
            "maturity_year",
            "maturity_month",
            "unit_of_measure_qty",
        ]
        self.meta = d.groupby(keys, dropna=False).known_at.min().reset_index()
        # Every price contributing to root volume needs received identity coverage.
        first = d.groupby(["raw_symbol", "instrument_id"]).known_at.min()
        pairs = pd.MultiIndex.from_frame(self.bars[["symbol", "instrument_id"]])
        received = first.reindex(pairs).to_numpy()
        if (
            pd.isna(received).any()
            or (pd.DatetimeIndex(received) > self.bars.date.to_numpy()).any()
        ):
            raise ValueError(
                "A traded outright lacks causally received identity metadata"
            )
        weekday = self.bars.date.dt.dayofweek < 5
        self.bars = self.bars[weekday].copy()
        self.prices = self.bars.set_index(["date", "symbol"]).sort_index()
        closures = pd.to_datetime(CALENDAR_CLOSURES, utc=True)
        self.days = source_days.difference(closures)
        root_presence = self.bars.groupby("date").root.nunique().reindex(self.days)
        if not root_presence.eq(len(self.roots)).all():
            raise ValueError(
                "Unexpected whole-market absence outside frozen holiday calendar"
            )
        self.contract_histories = {
            (symbol, int(instrument_id)): frame.set_index("date").sort_index()
            for (symbol, instrument_id), frame in self.bars[
                self.bars.date.isin(self.days)
            ].groupby(["symbol", "instrument_id"])
        }
        self.volumes = self.bars.pivot(
            index="date", columns="symbol", values="volume"
        ).reindex(self.days)
        self.whole_root_volume = (
            self.bars.groupby(["date", "root"])
            .volume.sum()
            .unstack()
            .reindex(self.days)[list(self.roots)]
        )
        self.selections = {}
        self.curves = {}
        self.notice_audit = []
        incumbent = {}
        changes = []
        bases = []
        change_days = []
        previous_day = None
        for day in self.days:
            available = self.days[self.days <= day - pd.Timedelta(days=2)]
            if len(available) <= extra_information_bars:
                continue
            lag = available[-1 - extra_information_bars]
            history_days = self.days[self.days <= lag][-20:]
            if len(history_days) != 20:
                continue
            vol = self.volumes.loc[history_days]
            counts = vol.count()
            adv = vol.mean()
            meta = (
                self.meta[self.meta.known_at <= lag]
                .sort_values("known_at")
                .drop_duplicates(["raw_symbol", "instrument_id"], keep="last")
                .set_index(["raw_symbol", "instrument_id"])
            )
            lag_bars = self.bars[self.bars.date == lag]
            selected = {}
            curves = {}
            for root in self.roots:
                candidates = []
                for row in lag_bars[lag_bars.root == root].itertuples():
                    key = (row.symbol, row.instrument_id)
                    if key not in meta.index:
                        raise ValueError(f"Unknown dated identity {lag} {key}")
                    m = meta.loc[key]
                    candidates.append(
                        {
                            "symbol": row.symbol,
                            "instrument_id": int(row.instrument_id),
                            "expiry": m.expiry,
                            "known_at": m.known_at,
                            "unit_of_measure_qty": float(m.unit_of_measure_qty),
                            "maturity_year": int(m.maturity_year),
                            "maturity_month": int(m.maturity_month),
                            "observed_bars": int(counts[row.symbol]),
                            "adv": float(adv[row.symbol]),
                        }
                    )
                old = incumbent.get(root)
                if old and old["symbol"] not in [c["symbol"] for c in candidates]:
                    candidate = dict(old)
                    candidate.update(
                        observed_bars=int(counts.get(old["symbol"], 0)),
                        adv=float(adv.get(old["symbol"], 0)),
                    )
                    candidates.append(candidate)
                try:
                    choice = select_liquid_contract(
                        candidates,
                        day,
                        old["symbol"] if old else None,
                        root=root,
                        retain_eligible_incumbent=True,
                    )
                except ValueError as exc:
                    if not incumbent:
                        break
                    raise ValueError(
                        f"{day} {root}: {exc}; incumbent={old}; candidates={candidates}"
                    ) from exc
                expected_unit = 100000 if root == "ZN" else SPECS[root].multiplier
                if not np.isclose(choice["unit_of_measure_qty"], expected_unit):
                    raise ValueError(f"Dated contract multiplier mismatch {day} {root}")
                current = self.row(day, choice["symbol"])
                if int(current.instrument_id) != choice["instrument_id"]:
                    raise ValueError(
                        "Selected dated contract identity changed at execution"
                    )
                tick_meta = self.meta[
                    (self.meta.raw_symbol == choice["symbol"])
                    & (self.meta.instrument_id == choice["instrument_id"])
                    & (self.meta.known_at <= day)
                ].sort_values("known_at")
                if not np.isclose(
                    float(tick_meta.iloc[-1].min_price_increment),
                    native_tick(root, day),
                    atol=1e-10,
                ):
                    raise ValueError(f"Native tick mismatch {day} {choice['symbol']}")
                maturity = pd.Timestamp(
                    year=choice["maturity_year"],
                    month=choice["maturity_month"],
                    day=1,
                    tz="UTC",
                )
                bound = (
                    choice["expiry"]
                    if root == "CL"
                    else maturity - pd.Timedelta(days=7)
                )
                if root in ("CL", "GC", "ZN", "6E") and day >= bound:
                    raise ValueError("Conservative first-delivery-risk bound reached")
                self.notice_audit.append(
                    {
                        "date": str(day),
                        "root": root,
                        **choice,
                        "conservative_delivery_risk_bound": str(bound),
                    }
                )
                selected[root] = choice
                curves[root] = sorted(
                    [
                        c
                        for c in candidates
                        if c["observed_bars"] == 20
                        and c["adv"] >= 100
                        and contract_is_safe(c, day, root)
                    ],
                    key=lambda c: c["expiry"],
                )[:2]
            if len(selected) != len(self.roots):
                continue
            self.selections[day] = selected
            self.curves[day] = curves
            if previous_day is not None:
                row_changes = []
                row_bases = []
                for root in self.roots:
                    old = self.selections[previous_day][root]
                    a = self.row(day, old["symbol"])
                    b = self.row(previous_day, old["symbol"])
                    if (
                        int(a.instrument_id) != old["instrument_id"]
                        or int(b.instrument_id) != old["instrument_id"]
                    ):
                        raise ValueError(
                            "Within-contract feature crossed a dated identity"
                        )
                    row_changes.append(a.close - b.close)
                    row_bases.append(abs(b.close))
                changes.append(row_changes)
                bases.append(row_bases)
                change_days.append(day)
            incumbent = selected
            previous_day = day
        # Reserve the extra-clock first return and warm-up for both clocks.
        shared_first_selection = next(
            d
            for d in self.days
            if len(self.days[self.days <= d - pd.Timedelta(days=2)]) >= 21
        )
        shared_first_change = self.days[self.days > shared_first_selection][0]
        self.point_changes = pd.DataFrame(
            changes, index=change_days, columns=self.roots
        )
        denominators = pd.DataFrame(
            bases, index=change_days, columns=self.roots
        ).replace(0, np.nan)
        self.point_changes = self.point_changes.loc[shared_first_change:]
        self.notional_returns = (self.point_changes / denominators).loc[
            shared_first_change:
        ]
        if len(self.point_changes) < 240:
            raise ValueError(
                "Insufficient development history for common 240-bar warm-up"
            )
        self.common_start = next(
            d
            for d in self.selections
            if len(self.days[self.days <= d - pd.Timedelta(days=2)]) >= 2
            and self.days[self.days <= d - pd.Timedelta(days=2)][-2]
            >= self.point_changes.index[239]
        )

    def information_day(self, day):
        available = self.days[self.days <= utc(day) - pd.Timedelta(days=2)]
        if len(available) <= self.extra_information_bars:
            raise ValueError("No completed information bar")
        return available[-1 - self.extra_information_bars]

    def row(self, day, symbol):
        try:
            return self.prices.loc[(utc(day), symbol)]
        except KeyError as exc:
            raise ValueError(
                f"Missing required actual-contract bar {day} {symbol}"
            ) from exc

    @classmethod
    def from_directory(
        cls, directory, *, roots=ROOTS, holdout_start=None, extra_information_bars=0
    ):
        directory = Path(directory)
        manifest = json.loads((directory / "prepared-manifest.json").read_text())
        if holdout_start is not None and utc(holdout_start) != FIXED_HOLDOUT_START:
            raise ValueError("Fixed final holdout boundary cannot be overridden")
        if utc(manifest["period"]["end_exclusive"]) > FIXED_HOLDOUT_START:
            raise ValueError(
                "Manifest price range crosses locked holdout; no parquet parsed"
            )
        if utc(manifest["fixed_holdout_start"]) != FIXED_HOLDOUT_START:
            raise ValueError("Prepared source has a different locked boundary")
        for source in manifest.get("sources", []):
            source_path = (directory / source["path"]).resolve()
            if file_hash(source_path) != source["sha256"]:
                raise ValueError("Raw source checksum mismatch")
        paths = {}
        for role in ("bars", "definitions"):
            item = manifest["files"][role]
            path = (directory / item["path"]).resolve()
            if not path.is_relative_to(directory.resolve()):
                raise ValueError("Prepared file escaped its dataset directory")
            if file_hash(path) != item["sha256"]:
                raise ValueError(f"Prepared {role} checksum mismatch")
            paths[role] = path
        bars = pd.read_parquet(paths["bars"])
        definitions = pd.read_parquet(
            paths["definitions"],
            columns=[
                "ts_recv",
                "ts_event",
                "raw_symbol",
                "instrument_id",
                "instrument_class",
                "min_price_increment",
                "expiration",
                "maturity_year",
                "maturity_month",
                "unit_of_measure_qty",
            ],
        )
        return cls(
            bars,
            definitions,
            roots=roots,
            extra_information_bars=extra_information_bars,
            source_manifest=manifest,
        )
