# Equity Factor Research

A Python research repository for learning and implementing equity alpha research workflows.

The main case study replicates and stress-tests the residual momentum framework introduced in *Residual Momentum* (Blitz, Huij, and Martens, 2011). The project compares conventional total-return momentum with residual momentum using rolling Fama-French regressions, cross-sectional portfolio construction, factor attribution, crisis-period diagnostics, calendar-month effects, and IC analysis.

This repository is intended as a research and learning project, not as a production trading system.

## Current Project: Residual Momentum

Traditional momentum ranks stocks by their past total returns. Residual momentum instead ranks stocks by the part of past returns that cannot be explained by common Fama-French factors such as market, size, and value.

The project implements the following workflow:

1. Convert daily equity prices into monthly returns.
2. Estimate rolling 36-month Fama-French regressions for each stock.
3. Extract residual returns.
4. Construct 12-1M total-return and residual momentum signals.
5. Sort stocks into decile portfolios.
6. Compare top-minus-bottom long-short portfolios.
7. Analyse performance, drawdowns, factor exposure, crisis-month behaviour, calendar-month effects, and cross-sectional IC.

## Key Findings

- Residual momentum materially reduced risk relative to total-return momentum in this sample. Across K=1, K=3, and K=6 holding periods, residual momentum had roughly half the volatility of total-return momentum and smaller drawdowns.

- Conditional Fama-French attribution supports the paper’s core mechanism: total-return momentum had substantial dynamic factor exposure, while residual momentum largely removed it.

- The return prediction evidence is more mixed. Residual momentum improved risk-adjusted performance, but its standalone cross-sectional IC and alpha were weak and statistically insignificant in this short modern sample.

The full analysis is discussed in the residual momentum report.

## Research Outputs
 
### Residual Momentum Report

Coming soon. This will be the structured research note covering the paper motivation, methodology, portfolio results, conditional Fama-French attribution, crisis-month case study, calendar-month effects, IC analysis, limitations, and interpretation.

### Residual Momentum Code

Main implementation of the residual momentum [research pipeline](factors/residual_momentum.py).

### Research Log

Chronological notes from the development process. These include exploratory work, debugging notes, abandoned ideas, and intermediate results. The logs are kept as a research diary rather than polished strategy claims.

- [Week 1](research_log/week_01.md) — exploratory factor construction, basic metrics, and early statistical arbitrage experiments.
- [Week 2](research_log/week_02.md) — factor attribution, residual momentum development, debugging, and interpretation.
- [Week 3](research_log/week_03.md) — residual momentum forensics, S&P 1500 universe expansion, crisis/calendar/decile diagnostics, IC analysis, and documentation cleanup.

### Results

Generated [charts and outputs](results/residual_momentum/), including cumulative returns, drawdowns, decile returns, and crisis-month visualisations.

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

