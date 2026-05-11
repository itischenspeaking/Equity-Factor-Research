# Equity Factor Research

Equity factor research and statistical arbitrage from scratch in
Python. This project implements classic cross-sectional factors and
a basket stat arb strategy, backtests them on S&P 1500 stocks
(2015–2024), and documents findings in a weekly research log.

## Quick Start

    pip install -r requirements.txt
    python3 data/download_data.py
    python3 -m backtest.engine
    python3 factors/pairs_trading.py
    python3 factors/post_pairs.py
    python3 -m factors.residual_momentum
    python3 -m analysis.factor_analysis

## Project Structure

    Equity-Factor-Research/
    │
    ├── data/
    │   ├── sp500_tickers.csv         # S&P 500 ticker list (legacy)
    │   ├── sp1500_tickers.csv        # S&P 1500 ticker list with index tags
    │   └── download_data.py          # Download daily prices via yfinance
    │
    ├── factors/
    │   ├── momentum.py               # 12-1 momentum (daily frequency)
    │   ├── mean_reversion.py         # 5-day short-term reversal
    │   ├── volatility.py             # Low volatility factor
    │   ├── pairs_trading.py          # Classical pairs (cointegration + z-score)
    │   ├── post_pairs.py             # Basket stat arb (5-stock sector baskets)
    │   └── residual_momentum.py      # Residual momentum (Blitz et al. 2011)
    │
    ├── backtest/
    │   ├── engine.py                 # Backtest engine (monthly rebalance)
    │   ├── portfolio.py              # Decile long-short portfolio construction
    │   └── metrics.py                # Sharpe, max drawdown, turnover, etc.
    │
    ├── analysis/
    │   └── factor_analysis.py        # Visualization and comparison charts
    │
    ├── results/
    │   ├── cross_sectional_factors/plots/  # Factor comparison charts
    │   ├── pairs_trading/plots/            # Pair analysis charts
    │   ├── post_pairs/v1/plots/            # Basket v1 charts
    │   ├── post_pairs/v2/plots/            # Basket v2 charts
    │   ├── residual_momentum/K{1,3,6}/     # Residual momentum plots
    │   └── reports/                        # Standalone analysis reports
    │
    └── research_log/                 # Weekly research notes
        ├── week_01.md                # Week 1: setup, factors, pairs, post-pairs
        └── week_02.md                # Week 2: FF attribution, residual momentum

## Research Log

- [Week 1](research_log/week_01.md) — Project setup, three
  cross-sectional factors, classical pairs trading, basket stat arb
  (post-pairs), and the sector homogeneity finding
- [Week 2](research_log/week_02.md) — FF6 factor attribution,
  rolling validation, IC analysis, residual momentum replication,
  stock forensics, universe expansion to S&P 1500

## Key Findings

1. **Universe determines whether a factor works.** Replicating
   Blitz et al. (2011) residual momentum, we confirmed the
   paper's risk-reduction mechanism (vol halved, dynamic factor
   R² from 0.39 to 0.08, max drawdown from -52% to -20%) on
   S&P 1500. Stock forensics revealed that S&P 500 "losers"
   are temporarily distressed large-caps that reliably recover,
   making the short leg unprofitable. Expanding to S&P 1500
   improved residual momentum Sharpe from 0.20 to 0.35 (K=3).
   NVDA spent 17 months in residual D1 while in total return
   D10, demonstrating its returns were factor exposure, not
   firm-specific momentum.

2. **Basket stat arb** only works in sectors where no single
   stock can structurally decouple from its peers. Consumer
   staples delivered Sharpe 0.56; semiconductors lost 75%
   because NVDA permanently diverged.

3. **IC-to-PnL gap**: a factor can have statistically significant
   predictive power (IC = 0.105, t = 3.76) while the trading
   strategy built on it loses money (-17%). The signal is right
   but the execution layer fails to convert.

## What's Implemented

**Cross-Sectional Factors**: momentum (12-1), mean reversion (5d),
low volatility (63d). Backtested as decile long-short portfolios
with monthly rebalance and 10 bps transaction cost.

**Classical Pairs Trading**: Engle-Granger cointegration screening,
z-score signal generation, out-of-sample backtest on 4 pairs.

**Post-Pairs (Basket Stat Arb)**: extension of pairs trading from
2 to 5 same-sector stocks.

**Residual Momentum**: replication of Blitz, Huij & Martens (2011).
Rolling 36-month FF3 regressions, standardised 12-1M residual
ranking. Compared to total return momentum with matched stock
pools, K=1/3/6 overlapping holding periods, conditional FF
attribution, and stock-level forensics.

**Factor Attribution**: FF5 + Momentum (6-factor) regression on
all strategy returns.

## Data

- **Universe**: 1469 S&P 1500 constituents (497 SP500 + 390
  SP400 + 582 SP600)
- **Period**: 2015–2024 daily data
- **Source**: Yahoo Finance via yfinance
- **Filters**: price < $5 excluded; |monthly return| > 300%
  excluded (yfinance corporate action errors)
- Data files are gitignored — run `download_data.py` to regenerate
- Use `--sp500` flag for legacy S&P 500 only universe
