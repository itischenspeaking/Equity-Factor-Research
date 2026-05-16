# Week 1: Project Setup, Basic Factors, Pairs Trading, and Post-Pairs

**2026-04-28 ---- 2026-05-03**

This was the first week of the project. Most of the work was exploratory: I was trying to get comfortable with the basic mechanics of quant research rather than trying to produce a polished strategy.

The main goals were:

- set up the data and backtest workflow;
- understand basic performance metrics such as return, Sharpe, drawdown, and turnover;
- test a few simple cross-sectional factors;
- move from classical pairs trading to a small basket stat-arb setup;
- start learning what can go wrong when a signal looks reasonable but is not robust.

---

## Day 1-2: Project Setup and Three Basic Factors

### Data

Downloaded 10 years of daily price data from 2015 to 2024 for S&P 500 constituents using `yfinance`.

A few tickers failed because of delistings, acquisitions, or data availability issues, including names such as ATVI, SIVB, and FRC. The final usable universe contained 462 stocks.

This already exposed an important practical issue: even a simple equity backtest depends heavily on the quality and definition of the universe.

### Factor results

Tested three simple factors using decile long-short portfolios, monthly rebalancing, and 10 bps transaction cost.

| Factor | Ann. Return | Sharpe | Max DD |
|---|---:|---:|---:|
| Momentum (12-1) | -5.98% | -0.26 | -57.55% |
| Mean Reversion | 0.11% | 0.01 | -39.28% |
| Low Volatility | -16.54% | -0.66 | -88.28% |

None of the three simple factors worked well in this sample.

### Interpretation

**Momentum:**  
The COVID crash and rebound created a large momentum reversal. Past winners suffered while past losers rebounded, and the strategy never fully recovered.

**Mean Reversion:**  
The 5-day signal likely decays too quickly for a monthly rebalance. I also tried weekly rebalancing, but turnover became too high and appeared to eat away any potential edge.

**Low Volatility:**  
The short leg ended up containing names like NVDA, TSLA, and AMD, which were among the strongest performers of the decade. This factor might behave differently in a risk-off regime, but 2015-2024 was a difficult period for this version of the strategy.

### Universe size: 52 vs 462 stocks

Before using the full S&P 500 universe, I had tested a smaller hand-picked universe of 52 large caps. Momentum looked mildly positive there, with +7.26% annual return and a 0.25 Sharpe.

After expanding to 462 stocks, momentum flipped negative.

This was a useful early lesson: a small hand-picked universe can give a misleading impression. Expanding the universe changes both the opportunity set and the failure modes.

Mean reversion improved slightly with the larger universe, which makes sense because more stocks can provide better diversification. But the improvement was still not enough to make the signal attractive.

---

## Day 3: Classical Pairs Trading

Screened within-sector stock pairs for cointegration using the Engle-Granger test.

A strict filter produced only 2 pairs. A relaxed filter produced 4 pairs.

| Pair | Corr | Coint p | Hedge Ratio | Half-life |
|---|---:|---:|---:|---:|
| CRM/ADBE | 0.693 | 0.0003 | 0.3739 | 28.5d |
| PEP/PG | 0.729 | 0.0415 | 0.8325 | 41.5d |
| KO/PEP | 0.739 | 0.0240 | 0.2913 | 43.2d |
| KO/PG | 0.616 | 0.0730 | 0.2412 | 52.6d |

Out-of-sample backtest on the last 30% of the data:

| Pair | Ann. Return | Sharpe | Max DD | Trades |
|---|---:|---:|---:|---:|
| CRM/ADBE | -2.54% | -0.15 | -29.12% | 12 |
| PEP/PG | -2.41% | -0.48 | -8.14% | 7 |
| KO/PEP | -2.53% | -0.43 | -11.91% | 9 |
| KO/PG | -0.76% | -0.11 | -17.00% | 17 |

All results were mildly negative.

The biggest issue was not just that the returns were negative, but that there were too few tradable pairs. With only a handful of pairs, there is almost no diversification. A single structural break can dominate the whole result.

This made the classical two-stock pairs setup feel too fragile for the type of research project I wanted to build.

---

## Day 3: Post-Pairs v1 — Basket Stat Arb

### Motivation

After seeing that two-stock pairs were too fragile, I extended the idea from pairs to small baskets.

Instead of comparing one stock to one other stock, each stock is compared to the equal-weighted average of four close peers in the same sector.

Why 5 stocks?

- 2 stocks is classical pairs trading, but too fragile.
- 20+ stocks would require fitting weights, which introduces more room for overfitting.
- 5 stocks felt like a reasonable middle ground: enough peers to make the reference value more stable, but simple enough to avoid too many fitted parameters.

### v1 implementation

- Equal-weighted peer basket
- Z-score entry at ±2.0
- Exit at ±0.5
- Dollar-neutral construction
- No parameter fitting
- No additional filtering

### v1 results

| Basket | Ann. Return | Sharpe | Max DD | Trades |
|---|---:|---:|---:|---:|
| Consumer Staples | 6.04% | 0.56 | -10.90% | 67 |
| Energy | 1.34% | 0.10 | -19.01% | 64 |
| Banks | 0.31% | 0.02 | -15.71% | 68 |
| Tech Software | -6.74% | -0.29 | -51.27% | 67 |
| Pharma | -14.59% | -0.73 | -50.91% | 58 |
| Semis | -35.59% | -1.10 | -75.06% | 57 |

### Interpretation

Consumer Staples was the only basket that worked in this exploratory test.

A plausible explanation is that the strategy works better when the stocks are economically similar and less likely to structurally decouple from one another.

KO, PEP, PG, CL, and KHC sell relatively similar products into relatively similar markets. Large deviations between them are more likely to be temporary noise.

The failed baskets tended to contain stocks that could break away from their peers for real business reasons:

- NVDA during the AI boom;
- LLY during the GLP-1 drug repricing;
- ORCL during its cloud pivot.

In those cases, the strategy shorted structural winners and got hurt.

I do not want to overstate this as a general finding. It is only one small exploratory test. But it gave me a useful intuition: mean-reversion strategies need not only statistical similarity, but also economic similarity.

### The Berkshire Hathaway connection

I also noticed a connection with the Berkshire/stat-arb and quality literature.

Chen and Yang (2021) use basket replication to study Berkshire Hathaway through a statistical arbitrage lens. Frazzini, Kabiller, and Pedersen (2018) argue that Berkshire's returns can largely be explained by quality, low-risk, and leverage.

Consumer staples are also the sector where my simple basket strategy behaved best.

This may or may not be meaningful, but it gave me a useful research question: can a measure of sector homogeneity or quality help identify where basket mean reversion is more likely to work?

This is interesting, but I should not get carried away. The point is to build fundamentals first, not to outsmart Buffett in my second week :).

---

## Day 4: Post-Pairs v2 — OU Filtering

### Motivation

The main weakness of v1 was that it traded every large z-score deviation, whether the deviation was temporary or structural.

I read Avellaneda and Lee (2010), which models residuals as Ornstein-Uhlenbeck processes and uses mean-reversion speed to decide which signals are more tradable.

The idea was to add filters that might avoid trading structural decouplings.

### Filters added in v2

**Filter 1 — OU mean-reversion speed**

For each stock on each day, estimate OU parameters on a trailing 60-day spread. Only trade if the estimated mean-reversion speed implies a half-life below 30 days.

**Filter 2 — ADF stationarity test**

Only trade if the residual passes an ADF stationarity check.

**Filter 3 — Rolling re-estimation**

Re-estimate parameters daily using a 60-day rolling window, so that if a stock starts decoupling, it should eventually stop passing the filters.

### Signal change

Following Avellaneda and Lee, replaced the rolling z-score with an OU-derived s-score:

```text
s = (X(t) - μ) / σ_eq
```

where `μ` and `σ_eq` come from the OU parameter estimation.

Entry threshold: ±1.25  
Exit threshold: ±0.5

### v2 results

| Basket | Ann. Return | Sharpe | Max DD | Days Active |
|---|---:|---:|---:|---:|
| Consumer Staples | -1.85% | -0.68 | -8.89% | 22% |
| Semis | -3.37% | -0.51 | -13.60% | 14% |
| Pharma | -4.47% | -1.02 | -15.41% | 18% |
| Energy | -5.49% | -1.28 | -18.54% | 23% |
| Banks | -6.18% | -1.88 | -18.14% | 24% |
| Tech Software | -7.86% | -1.42 | -21.73% | 15% |

Filter pass rates were low across most stocks.

### v1 vs v2 comparison

| Basket | v1 Sharpe | v2 Sharpe | v1 Max DD | v2 Max DD |
|---|---:|---:|---:|---:|
| Consumer Staples | 0.56 | -0.68 | -10.90% | -8.89% |
| Energy | 0.10 | -1.28 | -19.01% | -18.54% |
| Banks | 0.02 | -1.88 | -15.71% | -18.14% |
| Tech Software | -0.29 | -1.42 | -51.27% | -21.73% |
| Pharma | -0.73 | -1.02 | -50.91% | -15.41% |
| Semis | -1.10 | -0.51 | -75.06% | -13.60% |

### Interpretation

The filters helped reduce some of the largest drawdowns. For example:

- Semis max drawdown improved from -75% to -14%;
- Pharma improved from -51% to -15%;
- Tech improved from -51% to -22%.

So the filters did have risk-management value.

But they also removed too many trading opportunities. The only basket that had positive performance in v1, Consumer Staples, became negative in v2.

A likely issue is that the 60-day ADF test is too strict for low-volatility consumer staples spreads. These spreads may mean-revert slowly and quietly, making it hard to reject a unit-root null in a short window.

The main lesson was that filters are not free. Aggressive filtering can remove the worst trades, but it can also remove the profitable ones.

### Lessons learned

1. Risk management and alpha generation are in tension.  
   v1 had positive results in one sector but large risk elsewhere. v2 reduced catastrophic drawdowns but also removed most of the signal.

2. Sector-specific calibration may be necessary.  
   One threshold is unlikely to work equally well for consumer staples and semiconductors.

3. The ADF test may not be ideal for short windows on low-volatility spreads.  
   I need to understand ADF vs KPSS better before deciding which stationarity test belongs in this framework.

---

## TODO for next week

- [ ] Tune v2 filter thresholds per sector. On second thought, this should wait until I have a stronger theoretical foundation. Without it, tuning thresholds is just overfitting with extra steps.
- [ ] Try a longer estimation window, such as 120 days, for consumer staples. Same concern: without solid theory backing the choice, this is just parameter fishing. Suspending for now.
- [ ] Do background reading on ADF vs KPSS. Goal: understand the conceptual difference before choosing a stationarity test.
- [ ] Investigate per-stock weights using rolling OLS with regularization. I genuinely want to try this, even if I expect the first attempt to fail. The learning value is high regardless.
- [ ] Re-read Avellaneda and Lee (2010), especially Section 6 on trading-time vs calendar-time signals and volume adjustment. This feels like the core concept I need to internalise.
- [ ] Consider using sector ETFs as factors instead of peer averages, which would be closer to Avellaneda and Lee's ETF approach.
- [ ] Explore whether a sector homogeneity score can predict which baskets work. Honestly, this should wait. The idea came from my naive intuition rather than a solid research design.
- [ ] Fama-French factor attribution:
  - [ ] Part 1: work through a basic Fama-French tutorial to understand the factors, regression, alpha, and factor loadings.
  - [ ] Part 2: learn how to manually download, parse, and align Fama-French data from Kenneth French's website.
  - [ ] Part 3: bookmark full CRSP/Compustat factor construction references for later. Not doing this now because it is far outside the current scope.

---

## Reading List

- [x] Gatev, Goetzmann & Rouwenhorst (2006), "Pairs Trading"
- [x] Engle & Granger (1987), "Co-integration and Error Correction" — skimmed
- [ ] Krauss (2017), "Statistical Arbitrage Pairs Trading Strategies: Review and Outlook"
- [ ] Vidyamurthy (2004), "Pairs Trading"
- [x] Avellaneda & Lee (2010), "Statistical Arbitrage in the US Equities Market" — skimmed, focused on OU estimation and signal generation
- [x] Frazzini, Kabiller & Pedersen (2018), "Buffett's Alpha"
- [ ] Asness, Frazzini & Pedersen (2019), "Quality Minus Junk"
- [ ] Chen & Yang (2021), "Optimal statistical arbitrage trading of Berkshire Hathaway"
