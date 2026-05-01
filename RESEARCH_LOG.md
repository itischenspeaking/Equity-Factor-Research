# Research Log

## 2026-04-28 ---- 2026-05-03 | Week 1: Project Setup + Factor Backtests + Pairs Trading

### What I did

Set up the project from scratch. Downloaded 10 years of daily price
data (2015-2024) for 462 S&P 500 constituents via yfinance.
23 tickers failed (delisted/acquired: ATVI, SIVB, FRC, etc.), kept 462.

Implemented three cross-sectional factors and a pairs trading strategy.

### Factor results (decile long-short, monthly rebalance, 10bps cost)

| Factor           | Ann. Return | Sharpe | Max DD  |
|------------------|-------------|--------|---------|
| Momentum (12-1)  | -5.98%      | -0.26  | -57.55% |
| Mean Reversion   | 0.11%       | 0.01   | -39.28% |
| Low Volatility   | -16.54%     | -0.66  | -88.28% |

None of the three worked in this period. Notes on why:

**Momentum**: COVID crash in 2020 caused a massive momentum reversal.
Past winners (airlines, banks, energy) collapsed while past losers
(stay-at-home tech) ripped. The strategy was on the wrong side of
this and never fully recovered.

**Mean Reversion**: The 5-day signal decays within a week, but the
portfolio only rebalances monthly. By the time we trade, the signal
is stale. Tried weekly rebalance — made it worse because turnover
(0.68) ate all the alpha through transaction costs.

**Low Volatility**: The short leg was loaded with NVDA, TSLA, AMD —
the best performers of the decade. Shorting them was catastrophic.
This factor would likely work in a risk-off regime (2000-2010) but
2015-2024 was the worst possible period for it.

### 52 vs 462 stock universe

Initially tested with 52 hand-picked large caps. Momentum had a
+7.26% return and 0.25 Sharpe with that universe. Expanding to 462
flipped it negative. The larger universe includes more mid-caps that
experienced sharper momentum reversals around COVID.

Mean reversion improved slightly (Sharpe -0.28 → 0.01) — more stocks
= better diversification, individual stock noise cancels out.

### Pairs trading

Screened all within-sector pairs for cointegration (Engle-Granger test).

Strict filter (corr > 0.7, p < 0.05): 2 pairs
Relaxed filter (corr > 0.6, p < 0.10): 4 pairs

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

All mildly negative. PEP/PG had the tightest vol (5%) and smallest
drawdown (-8%) — market neutral property is clearly working, the
pairs just didn't revert cleanly enough to profit.

CRM/ADBE was the most interesting: it was up 25% at one point
(late 2022 - early 2023) before CRM structurally diverged from ADBE
in 2024H2 and the last short-spread trade blew up. Classic example
of cointegration breakdown — the formation period relationship
stopped holding out-of-sample.

### Observations

1. Negative results are not failures. Every factor has regimes where
   it doesn't work. The question is whether you can explain why.

2. Transaction costs matter enormously for high-frequency signals.
   Mean reversion with weekly rebalance had 0.68 turnover — that's
   ~68bps/day in costs eating a signal that generates maybe 1-2% 
   per trade.

3. Formation vs test period split (70/30) is crude. Should consider
   rolling window or expanding window for more robust estimates.

4. Pairs trading with only 4 pairs is not a real portfolio. Need
   20-30 pairs to diversify pair-specific risk. Current stock pool
   is too small and sector groups too narrow.

### TODO

- [ ] IC (Information Coefficient) analysis: rank correlation between
      factor scores and forward returns
- [ ] Rolling IC to see when factors were hot vs cold
- [ ] Quantile return bar charts (Q1 through Q10)
- [ ] Expand pairs universe: add more sector groups, consider ETFs
- [ ] Try Kalman filter for dynamic hedge ratio instead of static OLS
- [ ] Drawdown duration analysis
- [ ] Read key papers:
      - Gatev, Goetzmann & Rouwenhorst (2006) "Pairs Trading: Performance of a Relative-Value Arbitrage Rule" — RFS
      - Engle & Granger (1987) "Co-integration and Error Correction" — Econometrica
      - Krauss (2017) "Statistical Arbitrage Pairs Trading Strategies: Review and Outlook" — J. of Economic Surveys
      - Vidyamurthy (2004) "Pairs Trading: Quantitative Methods and Analysis" — Wiley Finance


### Why Pairs Trading Underperformed
 
Classical pairs trading found only 2 cointegrated pairs under strict
filters (corr > 0.7, p < 0.05), and 4 under relaxed filters. All
four produced mildly negative returns out-of-sample. Two problems:
 
1. **Too few pairs**: with only 4 tradeable pairs, there is no
   diversification of pair-specific risk. One structural break
   (e.g. CRM diverging from ADBE in 2024H2) wipes out months
   of gains across the entire strategy.
2. **Cointegration is fragile**: the Engle-Granger test found a
   relationship in the formation period, but that relationship
   didn't hold out-of-sample. This is a known issue — Krauss (2017)
   documents declining pairs trading profitability since the 2000s
   as more participants exploit the same signals and structural
   shifts happen faster.
The fundamental limitation is that 2 stocks is too few to form a
robust "fair value" estimate. If stock A deviates from stock B,
you don't know if A moved too much or B moved too little.
 
### Extension: Post-Pairs (Basket Statistical Arbitrage)
 
To address this, I extended the pairs framework from 2 stocks to
baskets of 5 same-sector stocks. The idea: instead of comparing
one stock to one partner, compare each stock to the equal-weighted
average of its 4 closest peers. The peer average acts as a more
robust estimate of "fair sector value" — if one stock deviates,
4 stocks agreeing against it is a stronger signal than 1.
 
Why 5 stocks specifically:
 
- 2 is classical pairs — too fragile, as shown above
- 20+ stocks requires fitting weight coefficients, which at this
  sample size would almost certainly overfit
- 5 is the sweet spot: enough peers (4) to form a stable reference
  price, few enough that I can use equal weights with no fitting,
  zero free parameters, zero overfitting risk
Current implementation uses **equal weights** — when a stock's
z-score crosses ±2 vs its peer average, go long $1 of the anomalous
stock and short $0.25 of each of the 4 peers (or vice versa).
Dollar-neutral by construction. **Next step: investigate whether
optimized per-stock weights improve results**, though the overfitting
risk needs careful handling (possibly regularized regression or
rolling OLS).
 
### Post-Pairs Results
 
Tested 6 sector baskets on the out-of-sample period (last 30% of
data, roughly 2022-2024):
 
| Basket           | Ann. Return | Sharpe | Max DD  | Trades |
|------------------|-------------|--------|---------|--------|
| Consumer Staples | 6.04%       | 0.56   | -10.90% | 67     |
| Energy           | 1.34%       | 0.10   | -19.01% | 64     |
| Banks            | 0.31%       | 0.02   | -15.71% | 68     |
| Tech Software    | -6.74%      | -0.29  | -51.27% | 67     |
| Pharma           | -14.59%     | -0.73  | -50.91% | 58     |
| Semis            | -35.59%     | -1.10  | -75.06% | 57     |
 
### Key Finding: Strategy Only Works in Homogeneous Sectors
 
Only Consumer Staples (KO, PEP, PG, CL, KHC) produced meaningful
positive returns. The pattern across baskets reveals a clear rule:
 
**The strategy works when no single stock can structurally decouple
from its peers.**
 
Consumer staples companies sell near-identical products (beverages,
household goods, packaged food) into near-identical markets. There
is no plausible scenario where KO 10x's while PEP doesn't. When
one stock deviates, it really is noise, and it really does revert.
 
The baskets that failed all had one stock that broke away from the
group permanently:
 
- **Semis**: NVDA decoupled due to AI demand (2023 onwards). The
  strategy kept shorting NVDA and longing TXN/QCOM. Catastrophic.
- **Pharma**: LLY decoupled due to GLP-1 drugs (Ozempic/Mounjaro).
  Same dynamic — strategy shorted the breakout stock.
- **Tech Software**: ORCL surged on cloud/AI pivot while ADBE
  stagnated. The strategy was up 55% at one point (mid-2023) before
  this structural shift erased everything.
- **Banks / Energy**: roughly flat, no catastrophic breakout but
  also not enough clean mean reversion to generate profit.
This is the central tension of stat arb: the strategy assumes the
group relationship is stable. When it is (consumer staples), you
get Sharpe 0.56 with 10% max drawdown. When it isn't (semis), you
lose 75%.
 
### Next Steps: The Berkshire Hathaway Connection
 
Interesting finding while reading the literature: Chen & Yang (2021)
used a similar basket replication approach to replicate Berkshire
Hathaway's portfolio returns using statistical arbitrage:
 
> Chen A-S, Yang C-M (2021) "Optimal statistical arbitrage trading
> of Berkshire Hathaway stock and its replicating portfolio."
> PLoS ONE 16(1): e0244541.
 
Buffett has famously concentrated his portfolio in consumer-facing
businesses he considers predictable — Coca-Cola, American Express,
Kraft Heinz — precisely the kind of stable, homogeneous companies
where my post-pairs strategy works best. His "I only invest in
businesses I can understand" philosophy may be, in quant terms,
a preference for stocks whose returns are well-explained by their
sector peers (low idiosyncratic volatility, strong mean reversion
to sector average).
 
**I want to investigate whether there is a systematic relationship
between "Buffett-style" stock characteristics (stable cash flows,
low business model variance, high peer-group cointegration) and
the effectiveness of basket mean reversion strategies.** If the
connection holds, it could provide a quantitative framework for
identifying which sectors and stocks are suitable for this type
of stat arb — rather than discovering after the fact that NVDA
was the wrong stock to short.

-------------------------------------

In fact,after a little bit of research, I found this: Frazzini, Kabiller & Pedersen (2018) "Buffett's Alpha"
(Financial Analysts Journal, 74(4), 35-55) decomposed
Berkshire Hathaway's returns and found that Buffett's edge is largely
explained by quality and low-volatility factors — precisely the
characteristics that make consumer staples the only sector where
my basket strategy works. 

Hmmmmmm, interesting.
