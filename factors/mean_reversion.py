"""
mean_reversion.py - Short-Term Mean Reversion Factor

Logic: stocks that dropped over the past 5 days tend to bounce back
in the near term. Factor value = negative of 5-day return, so stocks
that fell the most get the highest score.
"""
import pandas as pd


def compute_mean_reversion(close, lookback=5):
    """
    Compute short-term mean reversion factor.

    Parameters:
        close: DataFrame, daily close prices (columns = tickers)
        lookback: number of days to look back (default 5)

    Returns:
        DataFrame of mean reversion scores, same shape as input
    """
    short_term_return = close.pct_change(lookback)
    return -short_term_return


if __name__ == "__main__":
    close = pd.read_csv("data/close_prices.csv", index_col=0, parse_dates=True)
    mr = compute_mean_reversion(close)

    latest = mr.iloc[-1].dropna().sort_values(ascending=False)
    print("Mean Reversion factor - latest day, top 10:")
    for ticker, val in latest.head(10).items():
        print(f"  {ticker:6s}  {val:+.2%}")
    print("\nBottom 10:")
    for ticker, val in latest.tail(10).items():
        print(f"  {ticker:6s}  {val:+.2%}")
