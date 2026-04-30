"""
momentum.py - 12-1 Momentum Factor

Logic: stocks that went up over the past 12 months (skipping the most
recent month) tend to continue going up. The skip avoids the short-term
reversal effect.
"""
import pandas as pd


def compute_momentum(close, lookback=252, skip=21):
    """
    Compute 12-1 momentum factor.

    For each stock, calculate cumulative return from (lookback) days ago
    to (skip) days ago.

    Parameters:
        close: DataFrame, daily close prices (columns = tickers)
        lookback: total lookback window in trading days (252 ~ 12 months)
        skip: skip the most recent N days (21 ~ 1 month)

    Returns:
        DataFrame of momentum scores, same shape as input
    """
    momentum = close.shift(skip).pct_change(lookback - skip)
    return momentum


if __name__ == "__main__":
    close = pd.read_csv("data/close_prices.csv", index_col=0, parse_dates=True)
    mom = compute_momentum(close)

    latest = mom.iloc[-1].dropna().sort_values(ascending=False)
    print("Momentum factor - latest day, top 10:")
    for ticker, val in latest.head(10).items():
        print(f"  {ticker:6s}  {val:+.2%}")
    print("\nBottom 10:")
    for ticker, val in latest.tail(10).items():
        print(f"  {ticker:6s}  {val:+.2%}")
    print(f"\nTotal stocks with valid momentum: {latest.count()}")
