"""
factor_analysis.py - Visualization and analysis for all strategies

Generates:
1. Pairs trading: spread, z-score, signals, cumulative returns
2. Factor strategies: cumulative return curves comparison
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os

from factors.pairs_trading import screen_pairs, backtest_all_pairs
from factors.momentum import compute_momentum
from factors.mean_reversion import compute_mean_reversion
from factors.volatility import compute_volatility_factor
from backtest.engine import run_backtest


def plot_pair_analysis(pair_name, pair_result, save_dir="results/plots"):
    """
    Plot a 4-panel analysis for a single pair:
      1. Normalized prices of both stocks
      2. Spread over time
      3. Z-score with entry/exit thresholds and position shading
      4. Cumulative return of the strategy
    """
    signals = pair_result["signals"]
    zscore = pair_result["zscore"]
    spread = pair_result["spread"]
    returns = pair_result["returns"]
    metrics = pair_result["metrics"]

    stock_a, stock_b = pair_name.split("/")

    fig, axes = plt.subplots(4, 1, figsize=(14, 16), sharex=True)
    fig.suptitle(f"Pairs Trading: {pair_name}  |  Sharpe={metrics['Sharpe']:.2f}  "
                 f"MaxDD={metrics['Max DD']:.1%}", fontsize=14, fontweight="bold")

    # Panel 1: Normalized prices
    ax = axes[0]
    # Get prices from spread calculation period
    idx = spread.index
    close = pd.read_csv("data/close_prices.csv", index_col=0, parse_dates=True)
    pa = close.loc[idx, stock_a]
    pb = close.loc[idx, stock_b]
    ax.plot(idx, pa / pa.iloc[0], label=stock_a, linewidth=1.2)
    ax.plot(idx, pb / pb.iloc[0], label=stock_b, linewidth=1.2)
    ax.set_ylabel("Normalized Price")
    ax.legend(loc="upper left")
    ax.set_title("Normalized Prices (start = 1.0)")
    ax.grid(True, alpha=0.3)

    # Panel 2: Spread
    ax = axes[1]
    ax.plot(idx, spread, color="purple", linewidth=0.8)
    ax.axhline(spread.mean(), color="gray", linestyle="--", alpha=0.5, label="Mean")
    ax.set_ylabel("Spread")
    ax.set_title(f"Spread = {stock_a} - β × {stock_b}")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)

    # Panel 3: Z-score with signals
    ax = axes[2]
    ax.plot(idx, zscore, color="black", linewidth=0.8)
    ax.axhline(2.0, color="red", linestyle="--", alpha=0.7, label="Entry (±2)")
    ax.axhline(-2.0, color="red", linestyle="--", alpha=0.7)
    ax.axhline(0.5, color="green", linestyle=":", alpha=0.5, label="Exit (±0.5)")
    ax.axhline(-0.5, color="green", linestyle=":", alpha=0.5)
    ax.axhline(0, color="gray", linestyle="-", alpha=0.3)

    # Shade long and short positions
    long_mask = signals == 1
    short_mask = signals == -1
    ax.fill_between(idx, -5, 5, where=long_mask, alpha=0.1, color="blue", label="Long spread")
    ax.fill_between(idx, -5, 5, where=short_mask, alpha=0.1, color="red", label="Short spread")
    ax.set_ylim(-5, 5)
    ax.set_ylabel("Z-Score")
    ax.set_title("Z-Score and Trading Signals")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.3)

    # Panel 4: Cumulative returns
    ax = axes[3]
    cum = (1 + returns).cumprod()
    ax.plot(cum.index, cum.values, color="darkblue", linewidth=1.2)
    ax.axhline(1.0, color="gray", linestyle="-", alpha=0.3)
    ax.set_ylabel("Cumulative Return")
    ax.set_title("Strategy Cumulative Return (net of costs)")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    os.makedirs(save_dir, exist_ok=True)
    filename = f"{save_dir}/pairs_{stock_a}_{stock_b}.png"
    plt.savefig(filename, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {filename}")


def plot_factor_comparison(close, save_dir="results/plots"):
    """
    Plot cumulative returns of all three factor strategies on one chart.
    """
    mom = compute_momentum(close)
    mr = compute_mean_reversion(close)
    vol = compute_volatility_factor(close)

    ret_mom, _, _ = run_backtest(mom, close, name="Momentum (12-1)")
    ret_mr, _, _ = run_backtest(mr, close, name="Mean Reversion (5d)")
    ret_vol, _, _ = run_backtest(vol, close, name="Low Volatility (63d)")

    fig, ax = plt.subplots(figsize=(14, 7))

    cum_mom = (1 + ret_mom).cumprod()
    cum_mr = (1 + ret_mr).cumprod()
    cum_vol = (1 + ret_vol).cumprod()

    ax.plot(cum_mom.index, cum_mom.values, label="Momentum (12-1)", linewidth=1.2)
    ax.plot(cum_mr.index, cum_mr.values, label="Mean Reversion (5d)", linewidth=1.2)
    ax.plot(cum_vol.index, cum_vol.values, label="Low Volatility (63d)", linewidth=1.2)

    ax.axhline(1.0, color="gray", linestyle="-", alpha=0.3)
    ax.set_ylabel("Cumulative Return (starting at 1.0)")
    ax.set_xlabel("Date")
    ax.set_title("Factor Strategy Comparison: Cumulative Returns (2015-2024)")
    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)

    os.makedirs(save_dir, exist_ok=True)
    filename = f"{save_dir}/factor_comparison.png"
    plt.savefig(filename, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {filename}")


if __name__ == "__main__":
    close = pd.read_csv("data/close_prices.csv", index_col=0, parse_dates=True)

    # 1. Factor comparison chart
    print("Generating factor comparison chart...")
    plot_factor_comparison(close)

    # 2. Pairs trading analysis
    print("\nScreening pairs...")
    pairs = screen_pairs(close, corr_threshold=0.6, coint_pvalue=0.10)

    if len(pairs) > 0:
        print(f"Found {len(pairs)} pairs. Running backtest...\n")
        results = backtest_all_pairs(close, pairs)

        print("\nGenerating pair analysis charts...")
        for pair_name, pair_result in results.items():
            plot_pair_analysis(pair_name, pair_result)

    print("\nDone. All charts saved to results/plots/")
