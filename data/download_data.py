"""
download_data.py - 下载美股价格数据
"""
import pandas as pd
import yfinance as yf
import os


# 手动列出 ~50 只流动性好的大盘股，覆盖主要行业
# 不从 Wikipedia 抓了，省去 SSL/403 的麻烦
TICKERS = [
    # Tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO", "CRM", "AMD",
    # Finance
    "JPM", "BAC", "WFC", "GS", "MS", "BLK", "C", "AXP",
    # Healthcare
    "JNJ", "UNH", "PFE", "ABT", "MRK", "LLY", "TMO",
    # Consumer
    "WMT", "PG", "KO", "PEP", "COST", "MCD", "NKE", "SBUX",
    # Industrial
    "CAT", "BA", "HON", "UPS", "GE", "MMM",
    # Energy
    "XOM", "CVX", "COP", "SLB",
    # Telecom / Utilities
    "VZ", "T", "NEE", "DUK",
    # Other
    "DIS", "NFLX", "PYPL", "INTC", "QCOM",
]


def download_price_data(tickers, start="2015-01-01", end="2024-12-31"):
    """
    下载日线数据：Close 和 Volume
    """
    print(f"Downloading {len(tickers)} tickers from {start} to {end}...")
    raw = yf.download(tickers, start=start, end=end,
                      auto_adjust=True, threads=True)

    close = raw["Close"]
    volume = raw["Volume"]

    # 删掉数据太少的股票
    min_days = 500
    close = close.loc[:, close.count() >= min_days]
    volume = volume.loc[:, volume.count() >= min_days]

    # 只保留两者都有的股票
    common = close.columns.intersection(volume.columns)
    close = close[common]
    volume = volume[common]

    print(f"Kept {len(common)} tickers with >= {min_days} days of data")
    return close, volume


if __name__ == "__main__":
    close, volume = download_price_data(TICKERS)

    os.makedirs("data", exist_ok=True)
    close.to_csv("data/close_prices.csv")
    volume.to_csv("data/volumes.csv")

    print(f"\nClose prices: {close.shape[0]} days x {close.shape[1]} stocks")
    print(f"Volumes:      {volume.shape[0]} days x {volume.shape[1]} stocks")
    print(f"Date range:   {close.index[0].date()} to {close.index[-1].date()}")
    print("Saved to data/close_prices.csv and data/volumes.csv")
