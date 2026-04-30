# Equity Factor Research

A from-scratch factor research pipeline in Python. Constructs classic
equity factors from raw price data, backtests long-short portfolios,
and evaluates performance with standard risk metrics.

## Factors Implemented

- **Momentum (12-1)**: long past winners, short past losers, skipping the most recent month to avoid short-term reversal
- **Mean Reversion (5d)**: short-term contrarian signal based on 5-day returns
- **Low Volatility (63d)**: long low-vol stocks, short high-vol stocks

## Backtest Results

| Factor           | Ann. Return | Ann. Vol | Sharpe | Max Drawdown |
|------------------|-------------|----------|--------|--------------|
| Momentum (12-1)  | -5.98%      | 23.14%   | -0.26  | -57.55%      |
| Mean Reversion   | 0.11%       | 16.01%   | 0.01   | -39.28%      |
| Low Volatility   | -16.54%     | 25.24%   | -0.66  | -88.28%      |

None of the three factors delivered strong positive returns in this
period. Momentum suffered from sharp reversals during the 2020 COVID
crash and subsequent recovery. Mean reversion broke even — the 5-day
signal is too short-lived for monthly rebalancing. Low volatility's
short leg (high-vol tech) dramatically outperformed, driving large
losses. These results highlight the importance of regime awareness
and factor timing.

## Methodology

- **Universe**: 462 S&P 500 constituents
- **Period**: 2015-01-02 to 2024-12-30 (daily data)
- **Data source**: Yahoo Finance via yfinance
- **Rebalance**: Monthly (month-end)
- **Portfolio**: Decile long-short, equal-weighted
- **Transaction costs**: 10 bps one-way

## Project Structure
Equity-Factor-Research/
├── data/
│   ├── sp500_tickers.csv      # S&P 500 ticker list
│   ├── download_data.py       # Download price data from Yahoo Finance
│   ├── close_prices.csv       # (generated, not tracked)
│   └── volumes.csv            # (generated, not tracked)
├── factors/
│   ├── momentum.py            # 12-1 momentum factor
│   ├── mean_reversion.py      # 5-day mean reversion factor
│   └── volatility.py          # Low volatility factor
├── backtest/
│   ├── engine.py              # Backtest engine
│   ├── portfolio.py           # Long-short portfolio construction
│   └── metrics.py             # Sharpe, max drawdown, turnover, etc.
└── analysis/
└── factor_analysis.py     # IC, quantile returns (WIP)

## How to Run

```bash
pip install -r requirements.txt
python3 data/download_data.py
python3 -m backtest.engine
```
