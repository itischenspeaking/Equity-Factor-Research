# Week 1: Project Setup, Factor Backtests, Pairs Trading, Post-Pairs

**2026-04-28 ---- 2026-05-03**

---

## Day 1-2: Project Setup + 3 Basic Factors

### Data

Downloaded 10 years of daily price data (2015-2024) for S&P 500
constituents via yfinance. 23 tickers failed (delisted/acquired:
ATVI, SIVB, FRC, etc.), kept 462.

### Factor results (decile long-short, monthly rebalance, 10bps cost)

| Factor           | Ann. Return | Sharpe | Max DD  |
|------------------|-------------|--------|---------|
| Momentum (12-1)  | -5.98%      | -0.26  | -57.55% |
| Mean Reversion   | 0.11%       | 0.01   | -39.28% |
| Low Volatility   | -16.54%     | -0.66  | -88.28% |

None of the three worked in this period.

**Momentum**: COVID crash in 2020 caused a massive momentum reversal.
Past winners collapsed while past losers ripped. Never fully recovered.

**Mean Reversion**: 5-day signal decays within a week, but the
portfolio rebalances monthly. Signal is stale by trade time. Tried
weekly rebalance — worse, because turnover (0.68) ate all alpha.

**Low Volatility**: Short leg loaded with NVDA, TSLA, AMD — the best
performers of the decade. Would likely work in a risk-off regime
(2000-2010) but 2015-2024 was the worst possible period for it.

### Universe size matters: 52 vs 462 stocks

Initially tested with 52 hand-picked large caps. Momentum had
+7.26% return and 0.25 Sharpe. Expanding to 462 flipped it negative.
The larger universe includes more mid-caps that experienced sharper
momentum reversals around COVID. Mean reversion improved slightly
(Sharpe -0.28 → 0.01) — more stocks = better diversification.

---

## Day 3: Classical Pairs Trading

Screened all within-sector pairs for cointegration (Engle-Granger).

Strict filter (corr > 0.7, p < 0.05): 2 pairs.
Relaxed filter (corr > 0.6, p < 0.10): 4 pairs.

| Pair     | Corr  | Coint p | Hedge Ratio | Half-life |
|----------|-------|---------|-------------|-----------|
| CRM/ADBE | 0.693 | 0.0003  | 0.3739      | 28.5d     |
| PEP/PG   | 0.729 | 0.0415  | 0.8325      | 41.5d     |
| KO/PEP   | 0.739 | 0.0240  | 0.2913      | 43.2d     |
| KO/PG    | 0.616 | 0.0730  | 0.2412      | 52.6d     |

Out-of-sample backtest (last 30% of data, ~3 years):

| Pair     | Ann. Return | Sharpe | Max DD  | Trades |
|----------|-------------|--------|---------|--------|
| CRM/ADBE | -2.54%      | -0.15  | -29.12% | 12     |
| PEP/PG   | -2.41%      | -0.48  | -8.14%  | 7      |
| KO/PEP   | -2.53%      | -0.43  | -11.91% | 9      |
| KO/PG    | -0.76%      | -0.11  | -17.00% | 17     |

All mildly negative. The fundamental problem: only 4 tradeable
pairs, zero diversification. One structural break (CRM diverging
from ADBE in 2024H2) wipes out months of gains. Two stocks is
too few to form a robust "fair value" estimate.

---

## Day 3: Post-Pairs v1 (Basket Stat Arb)

### Motivation

Extended pairs from 2 to 5 same-sector stocks. Instead of comparing
one stock to one partner, compare each stock to the equal-weighted
average of its 4 closest peers.

Why 5: 2 is classical pairs, too fragile. 20+ requires fitting
weight coefficients, almost certain overfitting. 5 is the sweet
spot — enough peers for a stable reference, few enough for equal
weights with zero free parameters.

### v1 implementation

Equal weights, z-score entry at ±2.0, exit at ±0.5. Dollar-neutral
by construction. No parameter fitting, no filtering.

### v1 results

| Basket           | Ann. Return | Sharpe | Max DD  | Trades |
|------------------|-------------|--------|---------|--------|
| Consumer Staples | 6.04%       | 0.56   | -10.90% | 67     |
| Energy           | 1.34%       | 0.10   | -19.01% | 64     |
| Banks            | 0.31%       | 0.02   | -15.71% | 68     |
| Tech Software    | -6.74%      | -0.29  | -51.27% | 67     |
| Pharma           | -14.59%     | -0.73  | -50.91% | 58     |
| Semis            | -35.59%     | -1.10  | -75.06% | 57     |

### Key finding: sector homogeneity determines everything

Only Consumer Staples worked. The pattern is clear: **the strategy
only works when no single stock can structurally decouple from its
peers.**

KO, PEP, PG, CL, KHC sell near-identical products into
near-identical markets. There is no plausible scenario where KO
10x's while PEP doesn't. Deviations are noise, and they revert.

Every failed basket had one stock that broke away permanently:
NVDA (AI), LLY (GLP-1 drugs), ORCL (cloud pivot). The strategy
shorted the breakout stock and got destroyed.

### The Berkshire Hathaway connection

Chen & Yang (2021) used basket replication to replicate Berkshire
Hathaway's returns via stat arb (PLoS ONE 16(1): e0244541).
Buffett concentrates in consumer-facing businesses he considers
predictable — exactly where my strategy works.

Frazzini, Kabiller & Pedersen (2018) "Buffett's Alpha" (Financial
Analysts Journal) found that Berkshire's alpha is explained by
quality and low-volatility factors. These are the same
characteristics that make consumer staples the only viable sector
for basket mean reversion. This connection seems worth investigating
further.

---

## Day 4: Post-Pairs v2 (OU Filtering)

### Motivation

v1's core problem: it trades every z-score deviation, whether the
deviation is noise (will revert) or structural (will not revert).
Need a way to distinguish the two.

Read Avellaneda & Lee (2010) "Statistical Arbitrage in the US
Equities Market" (Quantitative Finance, 10(7), 761-782). Their key
insight: model the residual (stock vs sector) as an
Ornstein-Uhlenbeck process, estimate mean-reversion speed κ on a
rolling 60-day window, and only trade stocks with fast enough
reversion.

### Three filters added in v2

**Filter 1 — OU mean-reversion speed (κ)**: For each stock on each
day, estimate OU parameters on the trailing 60-day spread. Only
trade if κ > 252/30 (half-life < 30 days). Stocks that are
structurally decoupling will have low κ.

**Filter 2 — ADF stationarity test**: Before trading, verify that
the residual is stationary (ADF p-value < 0.10). Non-stationary
residuals indicate broken cointegration.

**Filter 3 — Rolling re-estimation**: All parameters are
re-estimated daily on a 60-day rolling window. If a stock starts
decoupling, κ drops within weeks and the strategy automatically
stops trading it.

### Signal change: s-score replaces z-score

Following Avellaneda & Lee, replaced the rolling z-score with an
OU-derived "s-score":

    s = (X(t) - μ) / σ_eq

where μ and σ_eq come from the OU parameter estimation. Entry at
s = ±1.25 (Avellaneda's calibrated threshold), exit at ±0.5.

### v2 results

| Basket           | Ann. Return | Sharpe | Max DD  | Days Active |
|------------------|-------------|--------|---------|-------------|
| Consumer Staples | -1.85%      | -0.68  | -8.89%  | 22%         |
| Semis            | -3.37%      | -0.51  | -13.60% | 14%         |
| Pharma           | -4.47%      | -1.02  | -15.41% | 18%         |
| Energy           | -5.49%      | -1.28  | -18.54% | 23%         |
| Banks            | -6.18%      | -1.88  | -18.14% | 24%         |
| Tech Software    | -7.86%      | -1.42  | -21.73% | 15%         |

Filter pass rates were extremely low across all stocks (5-28%).

### v1 vs v2 comparison

| Basket           | v1 Sharpe | v2 Sharpe | v1 Max DD | v2 Max DD |
|------------------|-----------|-----------|-----------|-----------|
| Consumer Staples | **0.56**  | -0.68     | -10.90%   | **-8.89%**|
| Energy           | 0.10      | -1.28     | -19.01%   | **-18.54%**|
| Banks            | 0.02      | -1.88     | -15.71%   | **-18.14%**|
| Tech Software    | -0.29     | -1.42     | -51.27%   | **-21.73%**|
| Pharma           | -0.73     | -1.02     | -50.91%   | **-15.41%**|
| Semis            | -1.10     | **-0.51** | -75.06%   | **-13.60%**|

### Analysis

**The filters work as risk management**: Semis max drawdown went from
-75% to -14%. Pharma from -51% to -15%. Tech from -51% to -22%. The
filters successfully prevented the catastrophic losses from shorting
structurally decoupled stocks.

**But the filters killed Consumer Staples**: The only profitable
basket went from Sharpe +0.56 to -0.68. The problem: ADF test with
a 60-day window is too strict for low-volatility consumer staples
spreads. These stocks have tiny spread fluctuations, making it hard
for ADF to reject the unit root null in a short window. Stocks only
pass filters 7-28% of the time, so the strategy is mostly sitting
in cash.

**Core trade-off discovered**: Filters are not free. Aggressive
filtering eliminates the worst losses but also eliminates most
trading opportunities, including the profitable ones. The filter
threshold needs to be calibrated per-sector or per-volatility-regime,
not applied uniformly. The 60-day window may also be too short for
stable consumer staples — Avellaneda & Lee's original paper used
this window on a much broader, more volatile universe.

### Lessons learned

1. Risk management and alpha generation are in tension. v1 had
   alpha in one sector but catastrophic risk in others. v2 has no
   catastrophic risk but also no alpha. The goal for v3 is to find
   the middle ground.

2. Sector-specific calibration is probably necessary. One set of
   filter thresholds cannot work across consumer staples (vol ~5%)
   and semiconductors (vol ~30%). Avellaneda & Lee note that they
   "modulated the leverage coefficient on a sector-by-sector basis."

3. The ADF test may not be the right stationarity test for short
   windows on low-vol series. Alternatives: KPSS test (tests
   stationarity as the null), Hurst exponent, or variance ratio
   tests.

---

## TODO for next week

- [ ] Tune v2 filter thresholds per sector (looser for staples,
      stricter for tech/semis). On second thought, this should wait
      until I have a stronger theoretical foundation. Without it,
      tuning thresholds is just overfitting with extra steps.
- [ ] Try longer estimation window (120d) for consumer staples.
      Same concern — without solid theory backing the choice, this
      is just parameter fishing. Suspending for now.
- [ ] **Do some background reading on ADF vs KPSS: understand the
      conceptual difference (ADF tests for unit root as null, KPSS
      tests for stationarity as null) before deciding which to use.**
- [ ] **Investigate per-stock weights (rolling OLS with
      regularization). This is something I genuinely want to try,
      even though I expect it to fail on the first attempt. The
      learning value is high regardless.**
- [ ] **Re-read Avellaneda & Lee (2010) Section 6 more carefully —
      trading-time vs calendar-time signals (volume adjustment).
      This is the core concept I need to internalise.**
- [ ] Consider using sector ETFs as factors instead of peer average
      (closer to Avellaneda's ETF approach).
- [ ] Explore the Buffett/quality connection: can a "sector
      homogeneity score" predict which baskets will work? Honestly,
      this should also wait. The idea came from my naive intuition
      rather than a solid reasoning. My goal is to get
      comfortable with the fundamentals of quant research, not to
      outsmart Buffett in my second week :).

## Reading list

- [x] Gatev, Goetzmann & Rouwenhorst (2006) "Pairs Trading" — RFS
- [x] Engle & Granger (1987) "Co-integration and Error Correction"
      — Econometrica (skimmed)
- [ ] Krauss (2017) "Statistical Arbitrage Pairs Trading Strategies:
      Review and Outlook" — J. of Economic Surveys
- [ ] Vidyamurthy (2004) "Pairs Trading" — Wiley Finance
- [x] Avellaneda & Lee (2010) "Statistical Arbitrage in the US
      Equities Market" — Quantitative Finance (skimmed, focused on
      Sections 3-5 on OU estimation and signal generation)
- [x] Frazzini, Kabiller & Pedersen (2018) "Buffett's Alpha" — FAJ
- [ ] Asness, Frazzini & Pedersen (2019) "Quality Minus Junk" — RFS
- [ ] Chen & Yang (2021) "Optimal statistical arbitrage trading of
      Berkshire Hathaway" — PLoS ONE
