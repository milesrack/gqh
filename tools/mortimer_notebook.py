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

Recent variance contains information about subsequent portfolio risk. Static allocations and slow risk-budget adjustment can leave exposure high as volatility rises. MORTIMER tests whether a lagged volatility forecast can scale a diversified equal-risk-contribution portfolio to reduce net volatility and drawdown relative to unscaled ERC, with acceptable return drag and turnover.

The registered success criteria require at least 10% lower volatility and drawdown, improved conditional tail loss, annual return drag below 150 basis points, annual turnover below two, and risk improvement under doubled costs. Validation rank IC must be positive, and annual folds and neighbouring parameter values must support the same conclusion. These criteria make the hypothesis falsifiable.

The experiment ledger records twelve primary variants and their diagnostics. This notebook presents the selected configuration, its data checks, and the recorded results."""
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
print('MORTIMER results replay; the held-out OOS test is read from its recorded evaluation.')
""")
    md(r"""## 2. Data and universe

The universe comprises QQQ, IWM, HYG, TLT, GLD, and DBC, representing growth and small-cap equities, high-yield credit, Treasury duration, gold, and broad commodities. These are surviving funds rather than point-in-time constituents, so discontinued-fund selection is not measured.

Yahoo adjusted closes include distributions and splits; raw closes and volume support liquidity estimates. Cash accrues from initial-release ALFRED DGS3MO observations, available on the first exchange session after observation and release. Accrual uses ACT/365; DGS3MO is a cash-yield proxy.

The XNYS calendar spans 2 January 2008 to 2 October 2026. Before replay, the notebook checks input hashes, dates, duplicates, positive prices, and rate availability. Missing observations stop the analysis; the history is not filled with future data.""")
    code(scientific)
    md(r"""## 3. Portfolio construction

Let $\widehat\Sigma_t$ denote the 126-session Ledoit–Wolf covariance estimate. The monthly constrained risk-balanced base solves

$$\min_b\sum_{i=1}^{6}\left[b_i(\widehat\Sigma_t b)_i-\frac{b^\top\widehat\Sigma_t b}{6}\right]^2,
\qquad \mathbf1^\top b=1,\quad 0\leq b_i\leq0.35.$$

**Risk contribution** is $b_i(\widehat\Sigma_t b)_i$ in variance units. Equal-risk-contribution (ERC) allocates similar risk contributions; binding caps can prevent exact equality. Ledoit–Wolf **covariance shrinkage** reduces finite-sample estimation noise by combining the sample covariance with a structured target.

## 4. Volatility forecast and exposure

For a fixed current base $b_t$, compute historical portfolio returns $x_s=b_t^\top r_s$ using observations through signal close $t$. The forecast is

$$\widehat\sigma_t=\sqrt{252\max\{\operatorname{EWMA}_{20}(x_s^2),\operatorname{EWMA}_{63}(x_s^2)\}},\qquad
k_t^{raw}=\min\left(1,\frac{0.10}{\widehat\sigma_t}\right).$$

An **EWMA** is an exponentially weighted moving average whose decay is set by its span. Taking the larger of the 20- and 63-span estimates combines a faster response with a slower risk measure. A five-percentage-point change triggers an exposure trade; monthly base rebalances proceed independently. Gross exposure cannot exceed one.""")
    md(r"""## 5. Execution and transaction costs

Information through close $t$ forms an order filled at close $t+1$, after that session's return. New holdings first earn the following close-to-close return. Positions drift between fills, so the 35% limit applies to base weights rather than continuously realised weights.

For pre-fee risky dollar holdings $h_i$, pre-fee NAV $V$, desired post-fee weights $w_i$, and execution charge $c=0.0005$, solve

$$V^{post}=V-c\sum_i|V^{post}w_i-h_i|.$$

Costs are five basis points of risky dollars bought plus sold, covering spread, commission, and closing slippage. Turnover is half the absolute change in risky and cash weights. A ten-basis-point stress is reported for development data; the held-out test contains one evaluation at five basis points. Cash transfers are free, and the exposure cap removes borrowing costs.

The simulator records signals, fills, positions, gross returns, cash accrual, fees, and net returns separately. Hand-computable cases verify timing and self-financing accounting.""")
    md(r"""## 6. Research design

The 550-session warm-up precedes the scored sample. Training ends on 31 December 2018; validation runs from 1 January 2019 through 1 October 2024. The competition rule reserves the shorter of the latest 20% of sessions or two years, giving an OOS test from 2 October 2024. Annual validation folds preserve chronological order and trading state.

The replay reads recorded returns for MORTIMER and matched unscaled ERC, checks the final boundary, and verifies development arithmetic. Strategy and reproduction functions appear in notebook cells for inspection.""")
    code(replay)
    code("""replay_summary = reproduce(reuse=True)
print(replay_summary)
""")
    md(r"""## 7. Data quality

Coverage, return distributions, cross-asset correlations, and lagged dollar volume describe the sample.

### Exploratory analysis These plots are exploratory diagnostics and do not alter the frozen specification.""")
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
    md(r"""## 8. Net performance and uncertainty

Annualised return compounds wealth using 252 sessions per year. Volatility is daily sample standard deviation times $\sqrt{252}$, and Sharpe uses excess returns over the cash proxy. Maximum drawdown includes initial wealth of one; CVaR is the mean return in the lower 5% tail. Turnover is annualised half-L1 change in risky and cash weights. The table and equity curves report training, validation, and held-out OOS test separately against matched unscaled ERC.""")
    code("""performance=pd.read_csv(OUT/'performance.csv')
performance_display=performance.copy()
performance_display['strategy']=performance_display['strategy'].replace({'E6':'MORTIMER'})
display(performance_display.round(5))
cost_display=pd.read_csv(OUT/'doubled-cost.csv')
if 'strategy' in cost_display: cost_display['strategy']=cost_display['strategy'].replace({'E6':'MORTIMER'})
display(cost_display.round(5))
daily={name:pd.read_csv(OUT/(name+'-daily.csv'),index_col=0,parse_dates=True) for name in ['E6','ERC']}
fig,axes=plt.subplots(2,3,figsize=(12,6))
splits=[('train',None,'2018-12-31'),('validation','2019-01-01','2024-10-01'),('oos_test','2024-10-02',None)]
for col,(label,start,end) in enumerate(splits):
    for name,color in [('E6',PURPLE),('ERC',BLUE)]:
        frame=daily[name].loc[start:end]
        wealth=(1+frame.net_return).cumprod()
        drawdown=wealth/np.maximum.accumulate(np.r_[1,wealth])[1:]-1
        axes[0,col].plot(frame.index,wealth,label='MORTIMER' if name=='E6' else 'Unscaled ERC',color=color)
        axes[1,col].plot(frame.index,drawdown,color=color)
    axes[0,col].set_title(label.replace('_',' ').capitalize())
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
    md(r"""## 9. Forecast and risk diagnostics

A volatility forecast predicts risk rather than expected return. Its **information coefficient (IC)** is correlation with subsequent realised variance; rank IC uses ranked observations. Forward windows overlap, so these correlations are dependent. The calibration plot compares the forecast with subsequent 21-session risk on the drifting unscaled portfolio, distinct from the registered constant-current-weight IC.

Monthly returns, rolling volatility, asset weights, and realised exposure show regime dependence and concentration. Asset-level holdings are available for development; the OOS record contains aggregate exposure.""")
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
    md(r"""## 10. Factors, liquidity, and capacity

The ten-basis-point comparison applies the fixed rule to development data and matched unscaled ERC. Factor attribution and paired block-bootstrap intervals quantify uncertainty around the return differences.

Dollar **ADV** is lagged average daily trading volume; **participation** is trade notional $Q$ divided by ADV. The impact estimate is $I=Y\sigma\sqrt{Q/ADV}$, using $Y=0.5$ and lagged volatility. The capital table reports participation and impact-adjusted returns across AUM scenarios.

Market, momentum, value, and duration attribution measures broad exposures alongside residual returns. Archived diagnostics retain their scoring convention; headline results use the recorded scored index. An initial cash-only observation differs between the source and comparison series, slightly changing annualisation but not the trading rule.""")
    code("""for name in ['doubled-cost','forecast-ic','annual','factor-attribution','capacity','paired-bootstrap']:
    path=OUT/(name+'.csv')
    if path.exists():
        print(name)
        table=pd.read_csv(path)
        if 'strategy' in table: table['strategy']=table['strategy'].replace({'E6':'MORTIMER'})
        display(table.round(5))
    else:
        print(name+': not supplied by the adopted replay; inspect archived reporting evidence before claiming a result.')
for name in ['forecast_diagnostics','parameter_plateau','annual_results','validation_results']:
    path=OUT/'original-diagnostics'/(name+'.csv')
    if path.exists():
        print('Retained MORTIMER diagnostic: '+name)
        display(pd.read_csv(path).round(5))
""")
    md(r"""## 11. Conclusion

## References

Validation indicates that the overlay reduces volatility and drawdown relative to unscaled ERC. In the held-out test, these reductions are smaller than the registered thresholds and accompany a lower Sharpe ratio. The results support risk moderation, while evidence of improved risk-adjusted performance is absent. The implementation combines established risk-balanced allocation, covariance shrinkage, and volatility targeting across six macro-risk instruments. Further evaluation should use point-in-time fund histories and calibrated execution costs.

See the [research specification](../research/HYPOTHESIS.md), [README](../README.md), and [quant note](../report/quant-note.pdf). Methodological and data references include [Ledoit and Wolf (2004)](https://doi.org/10.1016/S0047-259X(03)00096-4), [ALFRED initial-release observations](https://fred.stlouisfed.org/docs/api/fred/series_observations.html), [Kenneth French's factor library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html), and [Yahoo Finance](https://finance.yahoo.com/).""")
    notebook.cells = cells
    nbformat.validate(notebook)
    Path("notebooks").mkdir(exist_ok=True)
    nbformat.write(notebook, "notebooks/mortimer_research.ipynb")
    print("Wrote", len(cells), "inspectable notebook cells; outputs cleared.")


if __name__ == "__main__":
    build()
