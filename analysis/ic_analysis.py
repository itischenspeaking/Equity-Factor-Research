"""
ic_analysis.py - Information Coefficient Analysis

For the Consumer Staples basket strategy, compute rolling IC:
at each date, correlate the z-score (signal) with forward N-day
returns across the 5 stocks. This measures whether the signal
has predictive power at each point in time.

A declining or persistently negative IC curve is an early warning
that the factor has lost its edge — visible BEFORE the PnL turns
negative, unlike Sharpe which is a lagging indicator.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import spearmanr
import os


BASKET = ["KO", "PEP", "PG", "CL", "KHC"]


def compute_signals_and_returns(close, basket, lookback=60,
                                forward=21):
    """
    Compute z-scores (signal) and forward returns for IC calculation.

    Parameters:
        close: DataFrame of daily prices
        basket: list of tickers
        lookback: rolling window for z-score estimation
        forward: how many days ahead to measure return

    Returns:
        signals_df: DataFrame (dates x tickers), z-scores
        fwd_returns_df: DataFrame (dates x tickers), forward returns
    """
    returns = close[basket].pct_change()

    # Compute cumulative spread
    spreads = pd.DataFrame(index=returns.index, columns=basket,
                           dtype=float)
    for stock in basket:
        peers = [t for t in basket if t != stock]
        spreads[stock] = returns[stock] - returns[peers].mean(axis=1)

    cum_spread = spreads.cumsum()

    # Rolling z-score
    mean = cum_spread.rolling(lookback).mean()
    std = cum_spread.rolling(lookback).std()
    zscores = (cum_spread - mean) / std

    # Forward returns (what actually happens next N days)
    fwd_returns = close[basket].pct_change(forward).shift(-forward)

    return zscores, fwd_returns


def compute_rolling_ic(zscores, fwd_returns, basket):
    """
    At each date, compute Spearman rank correlation between
    z-scores and forward returns across the basket stocks.

    Returns Series of IC values indexed by date.
    """
    common = zscores.index.intersection(fwd_returns.index)
    zscores = zscores.loc[common]
    fwd_returns = fwd_returns.loc[common]

    ic_series = pd.Series(np.nan, index=common)

    for date in common:
        z = zscores.loc[date, basket].values
        r = fwd_returns.loc[date, basket].values

        # Need at least 4 non-NaN pairs for meaningful correlation
        mask = ~(np.isnan(z) | np.isnan(r))
        if mask.sum() < 4:
            continue

        corr, _ = spearmanr(z[mask], r[mask])
        ic_series[date] = corr

    return ic_series.dropna()


def compute_spread_dispersion(close, basket, window=60):
    """
    Measure how much the stocks in the basket are diverging.
    High dispersion = more trading opportunities.
    Low dispersion = stocks move in lockstep, no signal.
    """
    returns = close[basket].pct_change()
    dispersion = returns.rolling(window).std().mean(axis=1)
    return dispersion


def compute_ic_metrics(ic_series, window=60):
    """Compute rolling IC statistics."""
    rolling_mean = ic_series.rolling(window).mean()
    rolling_std = ic_series.rolling(window).std()
    rolling_ir = rolling_mean / rolling_std
    rolling_hit = ic_series.rolling(window).apply(
        lambda x: (x > 0).mean()
    )
    return rolling_mean, rolling_std, rolling_ir, rolling_hit


def plot_ic_analysis(ic_series, rolling_mean, rolling_ir,
                     rolling_hit, dispersion,
                     save_dir="results/post_pairs/v1/plots"):
    """
    5-panel IC analysis chart.
    """
    fig, axes = plt.subplots(5, 1, figsize=(14, 20), sharex=True)
    fig.suptitle("IC Analysis: Consumer Staples Basket\n"
                 "(z-score vs 21-day forward return, Spearman rank)",
                 fontsize=14, fontweight="bold")

    # Panel 1: Raw IC
    ax = axes[0]
    colors = ["steelblue" if v > 0 else "salmon" for v in ic_series]
    ax.bar(ic_series.index, ic_series.values, width=2,
           color=colors, alpha=0.6)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_ylabel("IC")
    ax.set_title(f"Daily IC (mean={ic_series.mean():.3f})")
    ax.grid(True, alpha=0.3)

    # Panel 2: Rolling IC mean (60-day)
    ax = axes[1]
    ax.plot(rolling_mean.index, rolling_mean.values,
            color="darkblue", linewidth=1)
    ax.fill_between(rolling_mean.index, 0, rolling_mean.values,
                    where=rolling_mean > 0, alpha=0.2, color="green")
    ax.fill_between(rolling_mean.index, 0, rolling_mean.values,
                    where=rolling_mean <= 0, alpha=0.2, color="red")
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_ylabel("Rolling IC Mean")
    ax.set_title("60-Day Rolling IC Mean")
    ax.grid(True, alpha=0.3)

    # Panel 3: IC_IR (IC mean / IC std)
    ax = axes[2]
    ax.plot(rolling_ir.index, rolling_ir.values,
            color="purple", linewidth=1)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.axhline(0.5, color="green", linestyle="--", alpha=0.3,
               label="Good (0.5)")
    ax.axhline(-0.5, color="red", linestyle="--", alpha=0.3,
               label="Bad (-0.5)")
    ax.set_ylabel("IC_IR")
    ax.set_title("60-Day Rolling IC_IR (IC Mean / IC Std)")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

    # Panel 4: Hit rate (fraction of positive IC days)
    ax = axes[3]
    ax.plot(rolling_hit.index, rolling_hit.values * 100,
            color="teal", linewidth=1)
    ax.axhline(50, color="black", linestyle="--", linewidth=0.5)
    ax.set_ylabel("Hit Rate (%)")
    ax.set_title("60-Day Rolling Hit Rate (% of days with IC > 0)")
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3)

    # Panel 5: Spread dispersion
    ax = axes[4]
    ax.plot(dispersion.index, dispersion.values * 100,
            color="darkorange", linewidth=1)
    ax.set_ylabel("Dispersion (%)")
    ax.set_title("60-Day Rolling Intra-Basket Return Dispersion")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    os.makedirs(save_dir, exist_ok=True)
    path = f"{save_dir}/ic_analysis_staples.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")


def print_ic_summary(ic_series, label="Full Sample"):
    """Print IC statistics."""
    print(f"\n{'='*55}")
    print(f"  IC Summary: {label}")
    print(f"{'='*55}")
    print(f"  Observations:    {len(ic_series)}")
    print(f"  IC Mean:         {ic_series.mean():>8.4f}")
    print(f"  IC Median:       {ic_series.median():>8.4f}")
    print(f"  IC Std:          {ic_series.std():>8.4f}")
    print(f"  IC_IR:           {ic_series.mean()/ic_series.std():>8.4f}")
    print(f"  Hit Rate:        {(ic_series > 0).mean():>8.1%}")
    print(f"  t-stat:          {ic_series.mean()/ic_series.std()*np.sqrt(len(ic_series)):>8.2f}")
    print(f"{'='*55}")


if __name__ == "__main__":
    import yfinance as yf

    # Load training data
    close_train = pd.read_csv("data/close_prices.csv", index_col=0,
                              parse_dates=True)

    # Download 2025-2026 data
    print("Downloading 2025-2026 data...")
    close_fwd = yf.download(BASKET, start="2025-01-01",
                            end="2026-05-06", auto_adjust=True)["Close"]

    # Combine
    close_all = pd.concat([close_train[BASKET], close_fwd])
    close_all = close_all[~close_all.index.duplicated(keep="last")]
    close_all = close_all.sort_index()

    print(f"Total data: {close_all.index[0].date()} to "
          f"{close_all.index[-1].date()}\n")

    # Compute IC on full sample
    print("Computing IC (21-day forward returns)...")
    zscores, fwd_returns = compute_signals_and_returns(
        close_all, BASKET, lookback=60, forward=21
    )
    ic = compute_rolling_ic(zscores, fwd_returns, BASKET)

    # Overall summary
    print_ic_summary(ic, "Full Sample (2015-2026)")

    # Split by period
    ic_train = ic[ic.index < "2025-01-01"]
    ic_forward = ic[ic.index >= "2025-01-01"]

    print_ic_summary(ic_train, "Training Period (2015-2024)")
    print_ic_summary(ic_forward, "Forward Period (2025-2026)")

    # Compute rolling metrics
    rolling_mean, rolling_std, rolling_ir, rolling_hit = \
        compute_ic_metrics(ic, window=60)

    # Dispersion
    dispersion = compute_spread_dispersion(close_all, BASKET)

    # Plot
    print("\nGenerating charts...")
    plot_ic_analysis(ic, rolling_mean, rolling_ir, rolling_hit,
                     dispersion)

    # Save
    os.makedirs("results/data_export", exist_ok=True)
    ic_df = pd.DataFrame({
        "date": ic.index,
        "ic": ic.values,
    })
    ic_df.to_csv("results/data_export/12_ic_analysis_staples.csv",
                 index=False)
    print("  Saved: results/data_export/12_ic_analysis_staples.csv")

    print("\nDone.")
