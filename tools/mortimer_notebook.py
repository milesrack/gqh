"""Build the self-contained MORTIMER research notebook from inspected source."""

import ast
from pathlib import Path

import nbformat

TITLE = (
    "MORTIMER: Multi-asset Optimisation and Risk Targeting "
    "with Integrated Monthly E6 Rebalancing"
)


def inspectable_source(path, exclude=()):
    """Copy declarations for inspection, omitting entry points and project imports."""
    source = Path(path).read_text()
    selected = []
    for node in ast.parse(source).body:
        if isinstance(node, ast.If) or (
            isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in exclude
        ):
            continue
        if isinstance(node, ast.ImportFrom) and (
            node.module == "e6" or (node.module or "").startswith("src")
        ):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        start = min(
            [node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])]
        )
        selected.append("\n".join(source.splitlines()[start - 1 : node.end_lineno]))
    return "\n\n".join(selected)


def build():
    scientific = inspectable_source("src/mortimer.py")
    replay = inspectable_source("tools/reproduce_mortimer.py", exclude=("main",))
    notebook = nbformat.v4.new_notebook()
    notebook.metadata.kernelspec = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    cells = []

    def md(source):
        cells.append(nbformat.v4.new_markdown_cell(source.replace("\\\\", "\\")))

    def code(source):
        cells.append(nbformat.v4.new_code_cell(source))

    md(
        "# "
        + TITLE
        + "\n\n"
        + r"""## 1. Research question

Recent variance contains information about subsequent portfolio risk. Static allocations and slow risk-budget adjustment can leave exposure high as volatility rises. MORTIMER tests whether a lagged volatility forecast can scale a diversified equal-risk-contribution portfolio to reduce net volatility and drawdown relative to an unscaled portfolio, with acceptable return drag and turnover.

The success criteria require at least 10% lower volatility and drawdown, improved conditional tail loss, annual return drag below 150 basis points, annual turnover below two, and risk improvement under doubled costs. Validation rank information coefficient must be positive, and annual folds must support the same conclusion. These criteria make the hypothesis falsifiable."""
    )
    code("""import os
from pathlib import Path
ROOT = Path.cwd()
while not (ROOT / "research/mortimer-provenance.json").exists() and ROOT != ROOT.parent:
    ROOT = ROOT.parent
if not (ROOT / "research/mortimer-provenance.json").exists():
    raise FileNotFoundError("Open the notebook inside the GQH repository")
os.chdir(ROOT)
""")
    code("""from pathlib import Path
import hashlib
import json
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import PercentFormatter
from scipy.stats import spearmanr
from IPython.display import Image, display
OUT = Path('results/mortimer-submission')
OUT.mkdir(parents=True, exist_ok=True)
NB_OUT = OUT / 'notebook-evidence'
NB_OUT.mkdir(parents=True, exist_ok=True)
PURPLE = '#6D3B91'
BLUE = '#366A9B'
plt.rcParams.update({'font.size':12,'axes.labelsize':12,'axes.titlesize':12,'xtick.labelsize':11,'ytick.labelsize':11,'legend.fontsize':11})
print('MORTIMER results replay; the held-out out-of-sample (OOS) test is read from its recorded evaluation.')
""")
    md(r"""## 2. Data and universe

The universe comprises six exchange-traded funds (ETFs): QQQ, IWM, HYG, TLT, GLD, and DBC, representing growth and small-cap equities, high-yield credit, Treasury duration, gold, and broad commodities. These are surviving funds rather than point-in-time constituents, so discontinued-fund selection is not measured.

Yahoo adjusted closes include distributions and splits; raw closes and volume support liquidity estimates. Cash accrues from initial-release observations in the Archival Federal Reserve Economic Data (ALFRED) three-month Treasury bill yield series, available on the first exchange session after observation and release. Accrual uses actual days over 365.

The New York Stock Exchange (NYSE) calendar spans 2 January 2008 to 2 October 2026. Before replay, the notebook checks dates, duplicates, positive prices, and rate availability. Missing observations stop the analysis; the history is not filled with future data.""")
    code(scientific)
    md(r"""## 3. Portfolio construction

Let $\widehat\Sigma_t$ denote the 126-session Ledoit–Wolf covariance estimate. The monthly constrained risk-balanced base solves

$$\min_b\sum_{i=1}^{6}\left[b_i(\widehat\Sigma_t b)_i-\frac{b^\top\widehat\Sigma_t b}{6}\right]^2,
\qquad \mathbf1^\top b=1,\quad 0\leq b_i\leq0.35.$$

**Risk contribution** is $b_i(\widehat\Sigma_t b)_i$ in variance units. Equal-risk contribution (ERC) allocates similar risk contributions; binding caps can prevent exact equality. Ledoit–Wolf **covariance shrinkage** reduces finite-sample estimation noise by combining the sample covariance with a structured target.

## 4. Volatility forecast and exposure

An exponentially weighted moving average (EWMA) assigns geometrically declining weights to past squared returns. For a fixed current base $b_t$, compute historical portfolio returns $x_s=b_t^\top r_s$ using observations through signal close $t$. The forecast is

$$\widehat\sigma_t=\sqrt{252\max\{\operatorname{EWMA}_{20}(x_s^2),\operatorname{EWMA}_{63}(x_s^2)\}},\qquad
k_t^{raw}=\min\left(1,\frac{0.10}{\widehat\sigma_t}\right).$$

Taking the larger of the 20- and 63-span estimates combines a faster response with a slower risk measure. A five-percentage-point change triggers an exposure trade; monthly base rebalances proceed independently. Gross exposure cannot exceed one.""")
    md(r"""## 5. Execution and transaction costs

Information through close $t$ forms an order filled at close $t+1$, after that session's return. New holdings first earn the following close-to-close return. Positions drift between fills, so the 35% limit applies to base weights rather than continuously realised weights.

For pre-fee risky dollar holdings $h_i$, pre-fee net asset value (NAV) $V$, desired post-fee weights $w_i$, and execution charge $c=0.0005$, solve

$$V^{post}=V-c\sum_i|V^{post}w_i-h_i|.$$

Costs are five basis points of risky dollars bought plus sold, covering spread, commission, and closing slippage. Turnover is half the absolute change in risky and cash weights. A ten-basis-point stress is reported for development data; the held-out test contains one evaluation at five basis points. Cash transfers are free, and the exposure cap removes borrowing costs.

The simulator records signals, fills, positions, gross returns, cash accrual, fees, and net returns separately. Hand-computable cases verify timing and self-financing accounting.""")
    md(r"""## 6. Research design

The 550-session warm-up precedes the scored sample. Training ends on 31 December 2018; validation runs from 1 January 2019 through 1 October 2024. The held-out out-of-sample (OOS) period runs from 2 October 2024 through 2 October 2026, the shorter of the most recent 20% of sessions and two years. Annual validation folds preserve chronological order and trading state.

The replay reads recorded returns for MORTIMER and matched unscaled ERC, checks the final boundary, and verifies development arithmetic. Strategy and reproduction functions appear in notebook cells for inspection.""")
    code(replay)
    code("""replay_summary = reproduce(reuse=True)
print(replay_summary)
""")
    md(r"""## 7. Data quality

Coverage, return distributions, cross-asset correlations, and lagged dollar volume describe the sample.

### Price history and return distribution

Price indices, daily return distributions, cross-asset correlations, and coverage summarise the observed sample.""")
    code("""def save_figure(fig, name):
    fig.savefig(NB_OUT / (name+'.pdf'))
    fig.savefig(NB_OUT / (name+'.png'), dpi=150)
    display(Image(filename=str(NB_OUT / (name+'.png'))))
    plt.close(fig)

def centred_legend(fig, axes, ncol=2):
    handles, labels = axes.get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5,0.995), ncol=ncol, frameon=False, fontsize=11)

# Cached market inputs are inspected without acquisition.
dev_panel = pd.read_parquet('data/cache/erc/market-20080102-20241002.parquet')
final_panel = pd.read_parquet('data/cache/erc-final/market.parquet')
observed = pd.concat([dev_panel,final_panel]).sort_index()
observed = observed.loc[~observed.index.duplicated(keep='last')]
prices = pd.read_csv(OUT/'market-adjusted-prices.csv',index_col=0,parse_dates=True).reindex(columns=MACRO)
asset_returns = prices.pct_change(fill_method=None).dropna()
coverage = pd.DataFrame({'observed_sessions':prices.notna().sum(),'missing_sessions':prices.isna().sum(),'positive_prices':(prices>0).all()})
display(coverage)
display(asset_returns.describe().T)
coverage.to_csv(NB_OUT/'coverage.csv')
fig,axes = plt.subplots(1,2,figsize=(11,4))
for ticker in MACRO: axes[0].plot(prices.index,prices[ticker]/prices[ticker].iloc[0],label=ticker)
axes[0].set(xlabel='Session date',ylabel='Adjusted price index (start = 1)')
centred_legend(fig,axes[0],ncol=6)
axes[0].set_xticks(pd.to_datetime(['2008-01-01','2014-01-01','2020-01-01','2026-01-01']))
axes[0].xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
correlation=asset_returns.corr()
im=axes[1].imshow(correlation,vmin=-1,vmax=1,cmap='RdBu_r')
axes[1].set_xticks(range(6),MACRO,rotation=40)
axes[1].set_yticks(range(6),MACRO)
fig.colorbar(im,ax=axes[1],label='Return correlation')
fig.subplots_adjust(left=.08,right=.92,bottom=.20,top=.82,wspace=.35)
save_figure(fig,'observed-data')
fig,ax=plt.subplots(figsize=(8,4))
for ticker in MACRO:ax.hist(asset_returns[ticker],bins=80,density=True,histtype='step',label=ticker)
ax.set(xlabel='Daily adjusted return',ylabel='Density')
ax.xaxis.set_major_formatter(PercentFormatter(1))
centred_legend(fig,ax,ncol=6)
fig.subplots_adjust(left=.11,right=.89,bottom=.16,top=.82)
save_figure(fig,'return-distributions')
""")
    md(r"""## 8. Performance and uncertainty

We calculate compound annual growth rate (CAGR) from split-local net wealth using 252 trading sessions per year. Annualised volatility is the sample standard deviation of daily returns multiplied by $\sqrt{252}$, and the Sharpe ratio uses daily excess returns relative to the cash return proxy. Maximum drawdown is measured from initial wealth of one. Conditional value at risk (CVaR) is the mean return in the lower 5% tail. Annual turnover is half the L1 change in risky and cash weights. Results are reported separately for training, validation, and the held-out out-of-sample (OOS) test against matched unscaled ERC.""")
    code("""performance=pd.read_csv(OUT/'performance.csv')
performance_display=performance.copy()
performance_display['strategy']=performance_display['strategy'].replace({'E6':'MORTIMER'})
display(performance_display.round(5))
cost_display=pd.read_csv(OUT/'doubled-cost.csv')
if 'strategy' in cost_display: cost_display['strategy']=cost_display['strategy'].replace({'E6':'MORTIMER'})
display(cost_display.round(5))
daily={name:pd.read_csv(OUT/(name+'-daily.csv'),index_col=0,parse_dates=True) for name in ['E6','ERC']}
fig,axes=plt.subplots(2,3,figsize=(12,6))
splits=[('Training',None,'2018-12-31'),('Validation','2019-01-01','2024-10-01'),('Out-of-sample test','2024-10-02',None)]
for col,(label,start,end) in enumerate(splits):
    for name,color in [('E6',PURPLE),('ERC',BLUE)]:
        frame=daily[name].loc[start:end]
        wealth=(1+frame.net_return).cumprod()
        drawdown=wealth/np.maximum.accumulate(np.r_[1,wealth])[1:]-1
        axes[0,col].plot(frame.index,wealth,label='MORTIMER' if name=='E6' else 'Unscaled ERC',color=color)
        axes[1,col].plot(frame.index,drawdown,color=color)
    axes[0,col].set_title(label)
    axes[0,col].set_ylabel('Net wealth (start = 1)')
    axes[1,col].set(xlabel='Session date',ylabel='Drawdown')
    axes[1,col].yaxis.set_major_formatter(PercentFormatter(1))
    ticks=pd.to_datetime(['2010-01-01','2014-01-01','2018-01-01'] if col==0 else ['2019-01-01','2021-01-01','2023-01-01'] if col==1 else ['2024-10-02','2025-10-01','2026-10-02'])
    for row in range(2):
        axes[row,col].set_xticks(ticks)
        axes[row,col].xaxis.set_major_formatter(mdates.DateFormatter('%Y' if col<2 else '%Y-%m'))
        axes[row,col].grid(alpha=.2)
centred_legend(fig,axes[0,0])
fig.subplots_adjust(left=.08,right=.92,bottom=.13,top=.87,wspace=.42,hspace=.38)
save_figure(fig,'split-net-evidence')
""")
    md(r"""## 9. Forecast evaluation

The **information coefficient (IC)** is the correlation between the volatility forecast and subsequent realised variance; the rank IC uses ranked observations. The calibration plot compares the forecast with subsequent 21-session risk on the drifting unscaled portfolio.

Monthly returns, rolling volatility, asset weights, and realised exposure characterise the portfolio through time. Asset-level holdings are available for development; aggregate exposure is reported for the OOS period.""")
    code("""e6=daily['E6']
monthly=(1+e6.net_return).resample('ME').prod()-1
heat=pd.DataFrame({'year':monthly.index.year,'month':monthly.index.month,'net_return':monthly.to_numpy()}).pivot(index='year',columns='month',values='net_return')
fig,axes=plt.subplots(2,1,figsize=(9,7))
im=axes[0].imshow(heat,aspect='auto',cmap='RdBu',vmin=-.06,vmax=.06)
axes[0].set_xticks(range(12),['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'])
axes[0].set_yticks(range(len(heat)),heat.index)
axes[0].set(xlabel='Month',ylabel='Year')
fig.colorbar(im,ax=axes[0],format=PercentFormatter(1),label='Monthly net return')
for name,color in [('E6',PURPLE),('ERC',BLUE)]:
    rolling=daily[name].net_return.rolling(126).std()*np.sqrt(252)
    axes[1].plot(rolling.index,rolling,label='MORTIMER' if name=='E6' else 'Unscaled ERC',color=color)
axes[1].set(xlabel='Session date',ylabel='126-session net volatility')
axes[1].yaxis.set_major_formatter(PercentFormatter(1))
axes[1].legend(loc='upper center',bbox_to_anchor=(.5,1.13),ncol=2,frameon=False)
fig.subplots_adjust(left=.10,right=.90,bottom=.09,top=.96,hspace=.35)
save_figure(fig,'monthly-and-rolling-risk')
fig,axes=plt.subplots(2,1,figsize=(9,5))
axes[0].plot(e6.index,e6.exposure,color=PURPLE,label='MORTIMER')
axes[0].set(ylabel='Realised risky exposure',ylim=(0,1.05))
axes[1].plot(e6.index,e6.turnover.rolling(63).sum(),color=PURPLE)
axes[1].set(xlabel='Session date',ylabel='63-session turnover')
centred_legend(fig,axes[0],ncol=1)
fig.subplots_adjust(left=.14,right=.86,bottom=.13,top=.86,hspace=.28)
save_figure(fig,'exposure-and-turnover')
heat.to_csv(NB_OUT/'monthly-net-returns.csv')
# Following-window risk is a retrospective diagnostic, never a trading feature.
future=(daily['ERC'].net_return.pow(2).rolling(21).mean().shift(-21)*252).pow(.5)
calibration=pd.DataFrame({'forecast':e6.forecast,'following_unscaled_risk':future}).dropna()
calibration.to_csv(NB_OUT/'risk-calibration.csv')
fig,ax=plt.subplots(figsize=(8,4))
ax.scatter(calibration.forecast,calibration.following_unscaled_risk,s=8,alpha=.25,color=PURPLE)
ax.set(xlabel='Signal-close fast/slow volatility forecast',ylabel='Following 21-session\\nunscaled realised risk')
ax.xaxis.set_major_formatter(PercentFormatter(1))
ax.yaxis.set_major_formatter(PercentFormatter(1))
fig.subplots_adjust(left=.15,right=.85,bottom=.19,top=.94)
save_figure(fig,'risk-calibration')
weights_path=OUT/'E6-development-weights.csv'
if weights_path.exists():
    weights=pd.read_csv(weights_path,index_col=0,parse_dates=True).loc[e6.index[0]:]
    fig,ax=plt.subplots(figsize=(9,4))
    ax.stackplot(weights.index,weights.T,labels=weights.columns)
    ax.set(xlabel='Session date',ylabel='Post-cost risky weight',ylim=(0,1.05))
    centred_legend(fig,ax,ncol=6)
    fig.subplots_adjust(left=.13,right=.87,bottom=.16,top=.80)
    save_figure(fig,'development-asset-weights')
    display(pd.Series({'maximum_realised_instrument_weight':weights.max().max(),'maximum_realised_gross_exposure':weights.sum(axis=1).max(),'mean_cash_weight':(1-weights.sum(axis=1)).mean()}))
""")
    md(r"""## 10. Cost sensitivity

## 11. Factor exposure

## 12. Liquidity and capacity

A ten-basis-point cost case applies to development data. Paired block-bootstrap intervals quantify uncertainty in validation return differences.

Average daily dollar volume (ADDV) is calculated from lagged volume and closing prices. Participation is risky trade notional $Q$ divided by ADDV. The impact scenario is $I=Y\sigma\sqrt{Q/ADDV}$, with $Y=0.5$ and lagged volatility. The capital table reports maximum participation and impact-adjusted returns by initial net asset value (NAV).""")
    code("""costs=pd.read_csv(OUT/'doubled-cost.csv')
costs['strategy']=costs['strategy'].replace({'E6':'MORTIMER'})
display(costs.round(5))
display(pd.read_csv(OUT/'paired-bootstrap.csv').round(5))
""")
    code("""factors=pd.read_csv(OUT/'factor-attribution.csv')
display(factors.round(5))
""")
    code("""capacity=pd.read_csv(OUT/'capacity.csv')
display(capacity.round(5))
""")
    md(r"""## 13. Conclusion

The validation results show lower volatility and drawdown alongside a 15-basis-point annual return difference. In the held-out out-of-sample (OOS) test, risk reductions are smaller and the Sharpe ratio is lower than for unscaled ERC, indicating that the overlay moderates portfolio risk without improving risk-adjusted return. Further work can extend the cost sensitivity with point-in-time fund histories, transaction-level execution data, and observed market-impact estimates.

## References

See the [research specification](../research/HYPOTHESIS.md), [README](../README.md), and [quant note](../report/quant-note.pdf). Methodological and data references include [Ledoit and Wolf (2004)](https://doi.org/10.1016/S0047-259X(03)00096-4), [ALFRED initial-release observations](https://fred.stlouisfed.org/docs/api/fred/series_observations.html), [Kenneth French's factor library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html), and [Yahoo Finance](https://finance.yahoo.com/).""")
    notebook.cells = cells
    nbformat.validate(notebook)
    Path("notebooks").mkdir(exist_ok=True)
    nbformat.write(notebook, "notebooks/mortimer_research.ipynb")
    print("Wrote", len(cells), "inspectable notebook cells; outputs cleared.")


if __name__ == "__main__":
    build()
