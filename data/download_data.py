"""
download_data.py - Download US equity price data

Reads S&P 500 tickers from a local CSV file and downloads
daily close prices and volumes from Yahoo Finance.
"""
import pandas as pd
import yfinance as yf
import os


def get_tickers():
    """
    Read ticker list from local CSV.

    We use a static local file instead of scraping Wikipedia's S&P 500
    page at runtime because pandas.read_html() is blocked by Wikipedia's
    HTTP 403 policy. A local file also makes the pipeline reproducible
    without depending on external HTML structure.
    """
    df = pd.read_csv("data/sp500_tickers.csv")
    return df["ticker"].tolist()

def download_price_data(tickers, start="2015-01-01", end="2024-12-31"):
    """
    Download daily close prices and volumes.

    Drops tickers with fewer than 500 days of data.
    Returns: (close, volume) DataFrames
    """
    print(f"Downloading {len(tickers)} tickers from {start} to {end}...")
    raw = yf.download(tickers, start=start, end=end,
                      auto_adjust=True, threads=True)

    close = raw["Close"]
    volume = raw["Volume"]

    min_days = 500
    close = close.loc[:, close.count() >= min_days]
    volume = volume.loc[:, volume.count() >= min_days]

    common = close.columns.intersection(volume.columns)
    close = close[common]
    volume = volume[common]

    print(f"Kept {len(common)} tickers with >= {min_days} days of data")
    return close, volume


if __name__ == "__main__":
    tickers = get_tickers()
    close, volume = download_price_data(tickers)

    os.makedirs("data", exist_ok=True)
    close.to_csv("data/close_prices.csv")
    volume.to_csv("data/volumes.csv")

    print(f"\nClose prices: {close.shape[0]} days x {close.shape[1]} stocks")
    print(f"Volumes:      {volume.shape[0]} days x {volume.shape[1]} stocks")
    print(f"Date range:   {close.index[0].date()} to {close.index[-1].date()}")
    print("Saved to data/close_prices.csv and data/volumes.csv")
