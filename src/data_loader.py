"""
data_loader.py - 从 Kenneth French Data Library 下载因子数据
"""
import os
import pandas as pd
import pandas_datareader.data as web


def download_ff_factors(start="1960-01-01", end="2024-12-31", save=True):
    """下载 Fama-French 三因子月度数据"""
    ff = web.DataReader("F-F_Research_Data_Factors", "famafrench", start, end)
    df = ff[0]  # key 0 = 月度, key 1 = 年度
    if save:
        os.makedirs("data/raw", exist_ok=True)
        df.to_csv("data/raw/ff3_monthly.csv")
        print(f"Saved to data/raw/ff3_monthly.csv, {len(df)} rows")
    return df


def download_momentum(start="1960-01-01", end="2024-12-31", save=True):
    """下载动量因子月度数据"""
    mom = web.DataReader("F-F_Momentum_Factor", "famafrench", start, end)
    df = mom[0]
    if save:
        os.makedirs("data/raw", exist_ok=True)
        df.to_csv("data/raw/momentum_monthly.csv")
        print(f"Saved to data/raw/momentum_monthly.csv, {len(df)} rows")
    return df


def load_all_factors(start="1960-01-01", end="2024-12-31"):
    """下载并合并所有因子，列: [Mkt-RF, SMB, HML, Mom, RF]"""
    ff3 = download_ff_factors(start, end, save=True)
    mom = download_momentum(start, end, save=True)
    combined = ff3.join(mom, how="inner")
    os.makedirs("data/processed", exist_ok=True)
    combined.to_csv("data/processed/all_factors_monthly.csv")
    print(f"Merged: {len(combined)} rows -> data/processed/all_factors_monthly.csv")
    return combined


if __name__ == "__main__":
    df = load_all_factors()
    print("\nPreview:")
    print(df.head(10))
    print(f"\nRange: {df.index[0]} to {df.index[-1]}")
