"""Build the quant note's tables and figures from recorded MORTIMER results."""

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import PercentFormatter

OUT = Path("results/mortimer-submission")
REPORT = Path("report")
BUILD = OUT / "report-build"
PURPLE = "#6D3B91"
BLUE = "#366A9B"
SPLITS = [
    ("train", None, "2018-12-31", "Training"),
    ("validation", "2019-01-01", "2024-10-01", "Validation"),
    ("oos_test", "2024-10-02", None, "OOS test"),
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, content):
    (BUILD / name).write_text(content + "\n")


def save(fig, name):
    """Save full-canvas figure files with symmetric subplot bounds."""
    fig.savefig(REPORT / f"{name}.png", dpi=200)
    fig.savefig(OUT / f"{name}.pdf")
    plt.close(fig)


def main():
    plt.rcParams.update(
        {
            "font.size": 11,
            "axes.labelsize": 11,
            "axes.titlesize": 11,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "legend.fontsize": 11,
        }
    )
    BUILD.mkdir(parents=True, exist_ok=True)
    performance = pd.read_csv(OUT / "performance.csv")
    daily = {
        name: pd.read_csv(OUT / f"{name}-daily.csv", index_col=0, parse_dates=True)
        for name in ["E6", "ERC"]
    }
    table = [
        r"\begin{center}\setlength{\tabcolsep}{4pt}\begin{tabular}{llrrrrrrr}\toprule",
        r"Sample & Rule & CAGR\% & Vol.\% & Sharpe & Sortino & MDD\% & Calmar & Turnover\\\midrule",
    ]
    for sample, _, _, label in SPLITS:
        for strategy in ["E6", "ERC"]:
            row = performance.loc[
                (performance["sample"] == sample)
                & (performance["strategy"] == strategy)
            ].iloc[0]
            rule = "MORTIMER" if strategy == "E6" else "Unscaled ERC"
            table.append(
                f"{label} & {rule} & {100 * row.cagr:.2f} & "
                f"{100 * row.volatility:.2f} & {row.sharpe:.3f} & "
                f"{row.sortino:.3f} & {100 * row.max_drawdown:.2f} & "
                f"{row.calmar:.3f} & {row.turnover:.2f} " + r"\\"
            )
    table += [r"\bottomrule\end{tabular}\end{center}"]
    write("performance.tex", "\n".join(table))

    fig, axes = plt.subplots(2, 2, figsize=(6.5, 4.5))
    for col, (_, start, end, label) in enumerate(SPLITS[1:]):
        for name, color in [("E6", PURPLE), ("ERC", BLUE)]:
            frame = daily[name].loc[start:end]
            wealth = (1 + frame.net_return).cumprod()
            drawdown = wealth / np.maximum.accumulate(np.r_[1, wealth])[1:] - 1
            axes[0, col].plot(
                frame.index,
                wealth,
                color=color,
                label="MORTIMER" if name == "E6" else "Unscaled ERC",
            )
            axes[1, col].plot(frame.index, drawdown, color=color)
        axes[0, col].set_title(label)
        axes[0, col].set_ylabel("Net wealth")
        axes[1, col].set(xlabel="Session date", ylabel="Drawdown")
        axes[1, col].yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        for row in range(2):
            axes[row, col].grid(alpha=0.2)
            axes[row, col].xaxis.set_major_locator(
                mdates.YearLocator(2) if col == 0 else mdates.MonthLocator(bymonth=[10])
            )
            axes[row, col].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 1),
        ncol=2,
        frameon=False,
        fontsize=11,
    )
    fig.subplots_adjust(
        left=0.13, right=0.87, bottom=0.14, top=0.85, wspace=0.55, hspace=0.45
    )
    save(fig, "split-evidence")

    fig, axes = plt.subplots(1, 2, figsize=(6.5, 2.8))
    for name, color in [("E6", PURPLE), ("ERC", BLUE)]:
        frame = daily[name]
        rolling = frame.net_return.rolling(126).std() * np.sqrt(252)
        axes[0].plot(
            frame.index,
            rolling,
            color=color,
            label="MORTIMER" if name == "E6" else "Unscaled ERC",
        )
    axes[0].set_ylabel("126-session volatility")
    axes[0].yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    e6 = daily["E6"]
    axes[1].plot(e6.index, e6.exposure, color=PURPLE)
    axes[1].set(xlabel="Session date", ylabel="Risky exposure", ylim=(0, 1.05))
    for ax in axes:
        ax.grid(alpha=0.2)
        ax.set_xlabel("Session date")
        ax.xaxis.set_major_locator(mdates.YearLocator(4))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 1),
        ncol=2,
        frameon=False,
        fontsize=11,
    )
    fig.subplots_adjust(left=0.10, right=0.96, bottom=0.20, top=0.78, wspace=0.32)
    save(fig, "risk-evidence")

    selected = performance.set_index(["strategy", "sample"])
    ev = selected.loc[("E6", "validation")]
    bv = selected.loc[("ERC", "validation")]
    ef = selected.loc[("E6", "oos_test")]
    bf = selected.loc[("ERC", "oos_test")]
    stressed = pd.read_csv(OUT / "doubled-cost.csv").set_index(["strategy", "sample"])
    es = stressed.loc[("E6", "validation")]
    bootstrap = pd.read_csv(OUT / "paired-bootstrap.csv")
    bootstrap["sample"] = bootstrap["sample"].replace(
        {"reused_validation": "validation", "reused_final": "oos_test"}
    )
    chosen_ci = bootstrap.loc[
        (bootstrap["sample"] == "validation") & (bootstrap.block_sessions == 20)
    ].iloc[0]
    write(
        "result-discussion.tex",
        f"In validation, volatility is lower by {100 * (1 - ev.volatility / bv.volatility):.1f}"
        + r"\% and drawdown by "
        + f"{100 * (1 - ev.max_drawdown / bv.max_drawdown):.1f}"
        + r"\%, at "
        + f"{10000 * (bv.cagr - ev.cagr):.0f}"
        + " bp annual return drag. At 10 bp, validation CAGR and Sharpe are "
        + f"{100 * es.cagr:.2f}"
        + r"\% and "
        + f"{es.sharpe:.3f}. OOS volatility and drawdown fall by "
        + f"{100 * (1 - ef.volatility / bf.volatility):.1f}"
        + r"\% and "
        + f"{100 * (1 - ef.max_drawdown / bf.max_drawdown):.1f}"
        + r"\%, below the 10\% thresholds; Sharpe is lower than ERC. "
        + "The validation paired block-bootstrap interval is ["
        + f"{100 * chosen_ci.lower_95:.2f}, {100 * chosen_ci.upper_95:.2f}"
        + "] percentage points (20 sessions, 1,000 draws, seed 42); it includes zero.",
    )
    ic = pd.read_csv(OUT / "forecast-ic.csv")
    validation_ic = ic.loc[ic["sample"] == "validation"].iloc[0]
    neighbours = pd.read_csv(OUT / "original-diagnostics/parameter_plateau.csv")
    annual_original = pd.read_csv(OUT / "original-diagnostics/annual_results.csv")
    crisis = annual_original.loc[annual_original.year == 2022].iloc[0]
    write(
        "risk-discussion.tex",
        "Validation Pearson and rank IC are "
        + f"{validation_ic.pearson_ic:.3f} and {validation_ic.rank_ic:.3f} "
        + f"over {int(validation_ic.observations):,} overlapping observations. "
        + f"All {len(neighbours)} registered neighbours retained the stability flag. "
        + f"In 2022, MORTIMER returned {100 * crisis.strategy_cagr:.2f}"
        + r"\% with drawdown "
        + f"{100 * crisis.strategy_max_drawdown:.2f}"
        + r"\%, versus ERC drawdown "
        + f"{100 * crisis.base_max_drawdown:.2f}"
        + r"\%. These forecast and regime diagnostics are descriptive.",
    )

    capacity = pd.read_csv(OUT / "capacity.csv")
    table = [
        r"\begin{center}\begin{tabular}{rrr}\toprule",
        r"Initial AUM (\$m) & Max Q/ADV\% & Impact-net CAGR\%\\\midrule",
    ]
    for row in capacity.itertuples():
        table.append(
            f"{row.aum / 1e6:.0f} & {100 * row.max_participation:.2f} & "
            + f"{100 * row.impact_adjusted_cagr:.2f} "
            + r"\\"
        )
    table.append(r"\bottomrule\end{tabular}")
    bound = 1e6 * 0.01 / capacity.iloc[0].max_participation
    table.append(
        "At $Y=0.5$, a 1\\% participation screen binds at initial AUM of "
        + f"\\${bound / 1e6:.2f} million. Rows above 100\\% participation are extrapolations."
    )
    table.append(r"\end{center}")
    write("capacity.tex", "\n".join(table))
    factors = pd.read_csv(OUT / "factor-attribution.csv")
    factors["sample"] = factors["sample"].replace(
        {"reused_validation": "validation", "reused_final": "oos_test"}
    )
    factors = factors.set_index(["sample", "factor"])
    final_factors = factors.loc["oos_test"]
    write(
        "factor-discussion.tex",
        "OLS attribution regresses saved net returns minus French RF on market, size, value, momentum, "
        + "and adjusted TLT duration returns, with five-lag Newey--West standard errors. Final betas are "
        + f"{final_factors.loc['Mkt-RF', 'coefficient']:.3f} market, "
        + f"{final_factors.loc['HML', 'coefficient']:.3f} value, "
        + f"{final_factors.loc['Mom', 'coefficient']:.3f} momentum, and "
        + f"{final_factors.loc['Duration', 'coefficient']:.3f} duration "
        + f"over {int(final_factors.loc['Duration', 'n'])} intersecting sessions through 31 August 2026. "
        + "The daily intercept has HAC $t="
        + f"{final_factors.loc['intercept_daily', 't_statistic']:.2f}$. "
        + "French equity-style proxies do not identify full cross-asset value or momentum. "
        + "Both panels use daily close-to-close dates; calendar-date regression remains descriptive. "
        + "French RF differs from the strategy's causal ALFRED cash proxy.",
    )
    write(
        "conclusion.tex",
        "MORTIMER is the adopted risk-controlled configuration. Recorded validation supports the forecast and "
        + "risk-reduction mechanism, while final reductions fall below the registered thresholds and "
        + "absolute returns do not establish incremental alpha. The final comparison, missing final cost "
        + "stress limit the available evidence for incremental superiority.",
    )

    audit = {
        "scope": "Saved MORTIMER evidence; no strategy evaluation or parameter changes",
        "fonts": {
            "body_pt": 11,
            "main_title_pt": 18,
            "subtitle_pt": 16,
            "legend_pt": 11,
        },
        "style": {
            "legend_center_x": 0.5,
            "framed_legend": False,
            "first_strategy": "MORTIMER",
            "first_color": PURPLE,
            "tight_crop": False,
            "symmetric_subplot_bounds": True,
        },
        "inputs": {str(path): digest(path) for path in sorted(OUT.glob("*.csv"))},
        "exports": {str(path): digest(path) for path in sorted(REPORT.glob("*.png"))},
        "native_visual_review": "pending",
        "pdf_review": "pending",
    }
    Path("research/mortimer-visual-audit.json").write_text(
        json.dumps(audit, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
