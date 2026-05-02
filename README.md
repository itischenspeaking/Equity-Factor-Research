# Equity Factor Research

Equity factor research and statistical arbitrage from scratch in
Python. This project implements classic cross-sectional factors and
a basket stat arb strategy, backtests them on 462 S&P 500 stocks
(2015–2024), and documents findings in a weekly research log.

## Quick Start

    pip install -r requirements.txt
    python3 data/download_data.py
    python3 -m backtest.engine
    python3 factors/pairs_trading.py
    python3 factors/post_pairs.py
    python3 -m analysis.factor_analysis

## Project Structure

    Equity-Factor-Research/
    │
    ├── data/
    │   ├── sp500_tickers.csv         # S&P 500 ticker list (static)
    │   └── download_data.py          # Download daily prices via yfinance
    │
    ├── factors/
    │   ├── momentum.py               # 12-1 momentum
    │   ├── mean_reversion.py         # 5-day short-term reversal
    │   ├── volatility.py             # Low volatility factor
    │   ├── pairs_trading.py          # Classical pairs (cointegration + z-score)
    │   └── post_pairs.py             # Basket stat arb (5-stock sector baskets)
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
    │   └── reports/                        # Standalone analysis reports
    └── research_log/                 # Weekly research notes
        └── week_01.md                # Week 1: setup, factors, pairs, post-pairs

## Research Log

Detailed findings, methodology notes, and analysis are documented in
the `research_log/` folder, updated weekly:

- [Week 1](research_log/week_01.md) — Project setup, three
  cross-sectional factors, classical pairs trading, basket stat arb
  (post-pairs), and the sector homogeneity finding

## What's Implemented

**Cross-Sectional Factors**: momentum (12-1), mean reversion (5d),
low volatility (63d). Backtested as decile long-short portfolios
with monthly rebalance and 10 bps transaction cost.

**Classical Pairs Trading**: Engle-Granger cointegration screening,
z-score signal generation, out-of-sample backtest on 4 pairs.

**Post-Pairs (Basket Stat Arb)**: extension of pairs trading from
2 to 5 same-sector stocks. Each stock is compared against the
equal-weighted average of its 4 peers. Tested on 6 sector baskets.

## Key Finding

Basket stat arb only works in sectors where no single stock can
structurally decouple from its peers. Consumer staples (KO, PEP, PG,
CL, KHC) delivered Sharpe 0.56 with -10.9% max drawdown.
Semiconductors lost 75% because NVDA permanently diverged due to AI
demand. See [Week 1 log](research_log/week_01.md) for full analysis.

## Data

- **Universe**: 462 S&P 500 constituents
- **Period**: 2015–2024 daily data
- **Source**: Yahoo Finance via yfinance
- Data files (CSVs) are gitignored — run `download_data.py` to
  regenerate
