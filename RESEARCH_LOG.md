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
