"""Calculate risk, factor, and capacity diagnostics from recorded returns."""

import hashlib
import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests

OUT = Path("results/mortimer-submission")
CACHE = Path("data/cache/e6-factors")
ASSETS = ["QQQ", "IWM", "HYG", "TLT", "GLD", "DBC"]


def french():
    CACHE.mkdir(parents=True, exist_ok=True)
    panels, sources = [], []
    for stem, columns in [
        ("F-F_Research_Data_Factors_daily", ["Mkt-RF", "SMB", "HML", "RF"]),
        ("F-F_Momentum_Factor_daily", ["Mom"]),
    ]:
        url = f"https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{stem}_CSV.zip"
        path = CACHE / f"{stem}.zip"
        if not path.exists():
            response = requests.get(url, timeout=45)
            response.raise_for_status()
            path.write_bytes(response.content)
        payload = path.read_bytes()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            text = archive.read(archive.namelist()[0]).decode("utf-8-sig")
        records = []
        for line in text.splitlines():
            fields = [x.strip() for x in line.split(",")]
            if (
                len(fields) == len(columns) + 1
                and len(fields[0]) == 8
                and fields[0].isdigit()
            ):
                records.append(fields)
        panel = pd.DataFrame(records, columns=["date", *columns])
        panel["date"] = pd.to_datetime(panel.date, format="%Y%m%d")
        panel = panel.set_index("date").astype(float) / 100
        panels.append(panel)
        sources.append(
            {
                "url": url,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "first": str(panel.index.min().date()),
                "last": str(panel.index.max().date()),
                "units": "daily decimal return; source percentage divided by 100",
            }
        )
    (OUT / "factor-sources.json").write_text(json.dumps(sources, indent=2) + "\n")
    return pd.concat(panels, axis=1).dropna()


def main():
    e6 = pd.read_csv(OUT / "E6-daily.csv", index_col=0, parse_dates=True)
    erc = pd.read_csv(OUT / "ERC-daily.csv", index_col=0, parse_dates=True)
    prices = pd.read_csv(
        OUT / "market-adjusted-prices.csv", index_col=0, parse_dates=True
    )
    factors = french()
    factors["Duration"] = prices.TLT.pct_change(fill_method=None)
    coefficients = []
    for sample, start, end in [
        ("validation", "2019", "2024-10-01"),
        ("oos_test", "2024-10-02", "2026-10-02"),
    ]:
        frame = pd.concat(
            [e6.net_return.loc[start:end].rename("strategy"), factors],
            axis=1,
            join="inner",
        ).dropna()
        names = ["Mkt-RF", "SMB", "HML", "Mom", "Duration"]
        x = np.column_stack([np.ones(len(frame)), frame[names].to_numpy()])
        y = (frame.strategy - frame.RF).to_numpy()
        inverse = np.linalg.inv(x.T @ x)
        beta = inverse @ x.T @ y
        residual = y - x @ beta
        z = x * residual[:, None]
        meat = z.T @ z
        for lag in range(1, 6):
            cross = z[lag:].T @ z[:-lag]
            meat += (1 - lag / 6) * (cross + cross.T)
        se = np.sqrt(np.diag(inverse @ meat @ inverse))
        for name, b, error in zip(["intercept_daily", *names], beta, se):
            coefficients.append(
                {
                    "sample": sample,
                    "factor": name,
                    "coefficient": b,
                    "hac_standard_error": error,
                    "t_statistic": b / error,
                    "n": len(y),
                    "first": str(frame.index.min().date()),
                    "last": str(frame.index.max().date()),
                }
            )
    pd.DataFrame(coefficients).to_csv(OUT / "factor-attribution.csv", index=False)

    ci = []
    for sample, start, end in [
        ("validation", "2019", "2024-10-01"),
        ("oos_test", "2024-10-02", "2026-10-02"),
    ]:
        a, b = (
            e6.net_return.loc[start:end].to_numpy(),
            erc.net_return.loc[start:end].to_numpy(),
        )
        for block in [5, 10, 20]:
            rng = np.random.default_rng(42)
            values = []
            for _ in range(1000):
                index = np.concatenate(
                    [
                        np.arange(j, j + block) % len(a)
                        for j in rng.integers(len(a), size=int(np.ceil(len(a) / block)))
                    ]
                )[: len(a)]
                ca = np.expm1(np.log1p(a[index]).mean() * 252)
                cb = np.expm1(np.log1p(b[index]).mean() * 252)
                values.append(ca - cb)
            lo, hi = np.quantile(values, [0.025, 0.975])
            ci.append(
                {
                    "sample": sample,
                    "metric": "incremental_cagr",
                    "lower_95": lo,
                    "upper_95": hi,
                    "block_sessions": block,
                    "repetitions": 1000,
                    "seed": 42,
                    "interpretation": "paired descriptive interval; no historical-search correction",
                }
            )
    pd.DataFrame(ci).to_csv(OUT / "paired-bootstrap.csv", index=False)

    raw = pd.read_parquet("data/cache/erc/market-20080102-20241002.parquet")
    dollar_volume = pd.DataFrame(
        {a: raw[a]["Close"] * raw[a]["Volume"] for a in ASSETS}
    )
    adv = dollar_volume.rolling(20, min_periods=20).mean().shift()
    sigma = (
        prices[ASSETS]
        .pct_change(fill_method=None)
        .rolling(20, min_periods=20)
        .std()
        .shift()
    )
    trades = pd.read_csv(
        OUT / "E6-development-trades.csv", index_col=0, parse_dates=True
    )
    dates = e6.loc["2019":"2024-10-01"].index
    trades = trades.reindex(dates).abs()
    previous_nav = e6.equity.shift().reindex(dates)
    nav = (e6.equity + e6.equity.shift() * e6.transaction_cost).reindex(dates)
    adv, sigma = adv.reindex(dates), sigma.reindex(dates)
    if trades.isna().any().any() or adv.isna().any().any() or sigma.isna().any().any():
        raise ValueError("Unsupported development capacity observations")
    rows = []
    for aum in [1e6, 1e7, 1e8, 5e8, 1e9]:
        q = trades.mul(nav * aum, axis=0)
        participation = q / adv
        impact = 0.5 * sigma * np.sqrt(participation)
        drag = (impact * trades).sum(axis=1) * nav / previous_nav
        net = e6.net_return.reindex(dates) - drag
        rows.append(
            {
                "aum": aum,
                "sample": "validation",
                "impact_y": 0.5,
                "max_participation": participation.to_numpy().max(),
                "p99_participation": np.quantile(participation.to_numpy(), 0.99),
                "impact_adjusted_cagr": np.expm1(np.log1p(net).mean() * 252),
            }
        )
    pd.DataFrame(rows).to_csv(OUT / "capacity.csv", index=False)
    (OUT / "diagnostics-protocol.json").write_text(
        json.dumps(
            {
                "mode": "reporting-only saved outcomes; no strategy evaluation",
                "bootstrap": "paired circular moving blocks, 5/10/20 sessions, 1000 draws, seed42",
                "factor_model": "OLS strategy net return minus French RF, MktRF/SMB/HML/Mom/TLT, HAC5",
                "factor_timing": "French US equity close-to-close and recorded adjusted ETF close-to-close, intersecting dates",
                "factor_limit": "equity style proxies do not identify full cross-asset value or momentum",
                "cash_limit": "strategy cash uses causal ALFRED proxy; regression subtracts French RF, a different convention",
                "capacity": "development holdings only; Q uses saved trade fraction times pre-fee portfolio NAV reconstructed as current NAV plus saved fees times initial AUM; ADV raw Close times Volume,20sessions lag1; sigma20sessions lag1; Y=.5scenario",
                "final_capacity": "unavailable: individual-asset final trades not recorded",
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
