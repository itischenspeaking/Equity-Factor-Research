"""
download_data.py - Download price data for S&P 500 or S&P 1500

Usage:
    python3 data/download_data.py              # S&P 1500 (default)
    python3 data/download_data.py --sp500      # S&P 500 only (legacy)
"""
import pandas as pd
import yfinance as yf
import os
import sys
import time
import requests

def _read_wiki_table(url):
    """Fetch Wikipedia page with proper headers, return parsed tables."""
    headers = {
        "User-Agent": "EquityFactorResearch/1.0 (student project)"
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return pd.read_html(resp.text)

def get_sp500_tickers():
    """Scrape current S&P 500 constituents from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    table = _read_wiki_table(url)
    tickers = table[0]["Symbol"].tolist()
    tickers = [t.replace(".", "-") for t in tickers]
    print(f"  S&P 500:  {len(tickers)} tickers")
    return tickers


def get_sp400_tickers():
    """Scrape current S&P 400 MidCap constituents from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies"
    table = _read_wiki_table(url)
    # The table structure: first table has the constituents
    # Symbol column may be named "Symbol" or "Ticker Symbol"
    df = table[0]
    col = [c for c in df.columns if "ymbol" in str(c) or "icker" in str(c)]
    if col:
        tickers = df[col[0]].tolist()
    else:
        # Fallback: first column is often the ticker
        tickers = df.iloc[:, 0].tolist()
    tickers = [str(t).strip().replace(".", "-") for t in tickers]
    # Filter out any non-ticker entries
    tickers = [t for t in tickers if t.isalpha() or "-" in t]
    print(f"  S&P 400:  {len(tickers)} tickers")
    return tickers


def get_sp600_tickers():
    """Scrape current S&P 600 SmallCap constituents from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies"
    table = _read_wiki_table(url)
    df = table[0]
    col = [c for c in df.columns if "ymbol" in str(c) or "icker" in str(c)]
    if col:
        tickers = df[col[0]].tolist()
    else:
        tickers = df.iloc[:, 0].tolist()
    tickers = [str(t).strip().replace(".", "-") for t in tickers]
    tickers = [t for t in tickers if t.isalpha() or "-" in t]
    print(f"  S&P 600:  {len(tickers)} tickers")
    return tickers


def get_sp1500_tickers():
    """Get S&P 1500 = S&P 500 + S&P 400 + S&P 600."""
    print("Fetching S&P 1500 constituents from Wikipedia...")
    t500 = get_sp500_tickers()
    t400 = get_sp400_tickers()
    t600 = get_sp600_tickers()

    # Deduplicate (shouldn't overlap, but just in case)
    all_tickers = sorted(set(t500 + t400 + t600))
    print(f"  Combined: {len(all_tickers)} unique tickers")

    # Tag each ticker with its index membership
    tags = {}
    for t in t500:
        tags[t] = "SP500"
    for t in t400:
        tags[t] = "SP400"
    for t in t600:
        tags[t] = "SP600"

    return all_tickers, tags


def download_price_data(tickers, start="2015-01-01", end="2024-12-31",
                        batch_size=100):
    """
    Download daily close prices and volumes via yfinance.
    Downloads in batches to avoid timeouts with large ticker lists.
    """
    print(f"\nDownloading {len(tickers)} tickers from {start} to {end}...")

    all_close = []
    all_volume = []
    failed = []

    n_batches = (len(tickers) + batch_size - 1) // batch_size

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        batch_num = i // batch_size + 1
        print(f"  Batch {batch_num}/{n_batches}: "
              f"{batch[0]}..{batch[-1]} ({len(batch)} tickers)")

        try:
            raw = yf.download(batch, start=start, end=end,
                              group_by="ticker", auto_adjust=True,
                              threads=True, progress=False)

            if len(batch) == 1:
                # yfinance returns flat columns for single ticker
                t = batch[0]
                if "Close" in raw.columns:
                    close = raw[["Close"]].rename(columns={"Close": t})
                    volume = raw[["Volume"]].rename(columns={"Volume": t})
                    all_close.append(close)
                    all_volume.append(volume)
                else:
                    failed.append(t)
            else:
                for t in batch:
                    try:
                        if (t, "Close") in raw.columns:
                            c = raw[(t, "Close")].rename(t)
                            v = raw[(t, "Volume")].rename(t)
                            all_close.append(c)
                            all_volume.append(v)
                        else:
                            failed.append(t)
                    except Exception:
                        failed.append(t)

        except Exception as e:
            print(f"    Batch failed: {e}")
            failed.extend(batch)

        # Brief pause between batches to be polite to Yahoo
        if i + batch_size < len(tickers):
            time.sleep(1)

    # Combine
    close = pd.concat(all_close, axis=1) if all_close else pd.DataFrame()
    volume = pd.concat(all_volume, axis=1) if all_volume else pd.DataFrame()

    if failed:
        print(f"\n  Failed to download: {len(failed)} tickers")
        if len(failed) <= 20:
            print(f"    {failed}")

    # Filter: require at least 500 trading days
    min_days = 500
    if not close.empty:
        good = close.columns[close.count() >= min_days]
        close = close[good]
        volume = volume[[c for c in good if c in volume.columns]]

    print(f"\n  Kept {close.shape[1]} tickers with >= {min_days} days of data")
    return close, volume, failed


if __name__ == "__main__":
    sp500_only = "--sp500" in sys.argv

    os.makedirs("data", exist_ok=True)

    if sp500_only:
        print("=== S&P 500 Universe ===")
        tickers = get_sp500_tickers()
        tags = {t: "SP500" for t in tickers}
        ticker_file = "data/sp500_tickers.csv"
    else:
        print("=== S&P 1500 Universe ===")
        tickers, tags = get_sp1500_tickers()
        ticker_file = "data/sp1500_tickers.csv"

    # Save ticker list with index membership
    ticker_df = pd.DataFrame([
        {"Ticker": t, "Index": tags.get(t, "Unknown")}
        for t in sorted(tags.keys())
    ])
    ticker_df.to_csv(ticker_file, index=False)
    print(f"Saved ticker list to {ticker_file}")

    # Download
    close, volume, failed = download_price_data(sorted(tags.keys()))

    # Save
    close.to_csv("data/close_prices.csv")
    volume.to_csv("data/volumes.csv")

    # Summary
    print(f"\n{'=' * 50}")
    print(f"  Close prices: {close.shape[0]} days x {close.shape[1]} stocks")
    print(f"  Volumes:      {volume.shape[0]} days x {volume.shape[1]} stocks")
    print(f"  Date range:   {close.index[0].date()} to "
          f"{close.index[-1].date()}")

    # Breakdown by index
    if not sp500_only:
        for idx_name in ["SP500", "SP400", "SP600"]:
            count = sum(1 for c in close.columns
                        if tags.get(c) == idx_name)
            print(f"  {idx_name}: {count} stocks with data")

    if failed:
        pd.Series(failed).to_csv("data/failed_tickers.csv",
                                 index=False, header=["Ticker"])
        print(f"  Failed tickers saved to data/failed_tickers.csv")

    print(f"\nSaved to data/close_prices.csv and data/volumes.csv")
