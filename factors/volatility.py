"""
volatility.py - Low Volatility Factor

Logic: stocks with lower recent volatility tend to deliver better
risk-adjusted returns (the Low Volatility Anomaly). Factor value =
negative of rolling standard deviation, so low-vol stocks score highest.
"""
import pandas as pd


def compute_volatility_factor(close, lookback=63):
    """
    Compute low volatility factor.

    Parameters:
        close: DataFrame, daily close prices (columns = tickers)
        lookback: rolling window in trading days (63 ~ 3 months)

    Returns:
        DataFrame of volatility factor scores, same shape as input
    """
    daily_returns = close.pct_change()
    vol = daily_returns.rolling(window=lookback).std()
    return -vol


if __name__ == "__main__":
    close = pd.read_csv("data/close_prices.csv", index_col=0, parse_dates=True)
    vf = compute_volatility_factor(close)

    latest = vf.iloc[-1].dropna().sort_values(ascending=False)
    print("Low Volatility factor - latest day, top 10:")
    for ticker, val in latest.head(10).items():
        print(f"  {ticker:6s}  {val:.4f}")
    print("\nBottom 10 (highest vol):")
    for ticker, val in latest.tail(10).items():
        print(f"  {ticker:6s}  {val:.4f}")
