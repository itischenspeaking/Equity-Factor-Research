"""
post_pairs.py - Basket Statistical Arbitrage (Post-Pairs)

Extension of classical pairs trading from 2 stocks to baskets of 5.
Instead of finding one partner, we use the equal-weighted average of
4 same-sector peers as the "fair value" for each stock.

For each stock in a sector group:
    spread = stock return - mean(other 4 stocks' returns)
    z-score = rolling standardized spread

When a stock's z-score deviates beyond a threshold, we long the
laggard and short the other 4 (or vice versa), dollar-neutral.

Advantages over classical pairs:
    - No coefficient fitting -> no overfitting risk
    - Short leg diversified across 4 stocks -> less blowup risk
    - More trading opportunities per sector group (5 stocks = 5 signals)

References:
    - Avellaneda & Lee (2010) "Statistical Arbitrage in the US
      Equities Market" — Quantitative Finance
    - Gatev et al. (2006) as the pairs trading foundation
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os


# 5-stock sector baskets
# Chosen for tight business model overlap and high liquidity
BASKETS = {
    "Banks": ["JPM", "BAC", "WFC", "GS", "MS"],
    "Tech_Software": ["MSFT", "GOOGL", "CRM", "ADBE", "ORCL"],
    "Semis": ["NVDA", "AMD", "AVGO", "QCOM", "TXN"],
    "Consumer_Staples": ["KO", "PEP", "PG", "CL", "KHC"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG"],
    "Pharma": ["JNJ", "PFE", "MRK", "ABT", "LLY"],
}


def compute_basket_zscore(close, basket, lookback=60):
    """
    For each stock in the basket, compute the z-score of its
    spread vs the equal-weighted mean of the other 4.

    Parameters:
        close: DataFrame, daily close prices
        basket: list of 5 tickers
        lookback: rolling window for z-score

    Returns:
        zscores: DataFrame (dates x 5 tickers), rolling z-scores
        spreads: DataFrame (dates x 5 tickers), raw spread values
    """
    # Daily returns for basket stocks
    prices = close[basket]
    returns = prices.pct_change()

    spreads = pd.DataFrame(index=returns.index, columns=basket, dtype=float)

    for stock in basket:
        peers = [t for t in basket if t != stock]
        peer_mean = returns[peers].mean(axis=1)
        spreads[stock] = returns[stock] - peer_mean

    # Cumulative spread (integrated daily spread differences)
    cum_spread = spreads.cumsum()

    # Rolling z-score on cumulative spread
    mean = cum_spread.rolling(lookback).mean()
    std = cum_spread.rolling(lookback).std()
    zscores = (cum_spread - mean) / std

    return zscores, cum_spread


def generate_basket_signals(zscores, entry_z=2.0, exit_z=0.5, stop_z=4.0):
    """
    Generate signals for each stock in the basket.

    For stock i:
        z < -entry_z -> long stock i, short the other 4 (stock is cheap)
        z > +entry_z -> short stock i, long the other 4 (stock is rich)
        |z| < exit_z -> close position
        |z| > stop_z -> stop loss

    Parameters:
        zscores: DataFrame (dates x tickers)
        entry_z, exit_z, stop_z: thresholds

    Returns:
        signals: DataFrame (dates x tickers), values in {-1, 0, 1}
                 1 = long this stock (short peers)
                -1 = short this stock (long peers)
                 0 = no position
    """
    signals = pd.DataFrame(0, index=zscores.index, columns=zscores.columns)
    positions = {ticker: 0 for ticker in zscores.columns}

    for i in range(len(zscores)):
        for ticker in zscores.columns:
            z = zscores[ticker].iloc[i]

            if np.isnan(z):
                signals[ticker].iloc[i] = 0
                continue

            pos = positions[ticker]

            if pos == 0:
                if z < -entry_z:
                    pos = 1    # stock is cheap -> long it
                elif z > entry_z:
                    pos = -1   # stock is rich -> short it
            elif pos == 1:
                if z > -exit_z or z < -stop_z:
                    pos = 0
            elif pos == -1:
                if z < exit_z or z > stop_z:
                    pos = 0

            positions[ticker] = pos
            signals[ticker].iloc[i] = pos

    return signals


def backtest_basket(close, basket, signals, cost_bps=10):
    """
    Backtest one basket.

    When signal for stock i = 1:
        long $1 of stock i, short $0.25 of each of the other 4
    When signal for stock i = -1:
        short $1 of stock i, long $0.25 of each of the other 4
    Multiple stocks in the same basket can be active simultaneously.

    Returns:
        daily_returns: Series of net portfolio returns
    """
    returns = close[basket].pct_change()
    prev_signals = signals.shift(1).fillna(0)
    port_return = pd.Series(0.0, index=returns.index)

    for stock in basket:
        peers = [t for t in basket if t != stock]
        sig = prev_signals[stock]

        # When sig=1: long stock, short 0.25 each peer
        # When sig=-1: short stock, long 0.25 each peer
        stock_contrib = sig * returns[stock]
        peer_contrib = -sig * returns[peers].mean(axis=1)

        # Weight: 0.5 to stock leg, 0.5 to peer leg (dollar neutral)
        port_return += 0.5 * stock_contrib + 0.5 * peer_contrib

    # Transaction costs
    signal_changes = signals.diff().abs().sum(axis=1).fillna(0)
    costs = signal_changes * cost_bps / 10000
    net_return = port_return - costs

    return net_return.dropna()


def run_post_pairs(close, baskets=None, lookback=60,
                   entry_z=2.0, exit_z=0.5, stop_z=4.0,
                   test_split=0.7, cost_bps=10):
    """
    Run the full post-pairs pipeline on all baskets.

    Parameters:
        close: DataFrame of daily close prices
        baskets: dict of {name: [5 tickers]}
        test_split: fraction of data for formation period
        cost_bps: one-way transaction cost

    Returns:
        all_results: dict of {basket_name: {returns, signals, zscores, metrics}}
    """
    if baskets is None:
        baskets = BASKETS

    n = len(close)
    split = int(n * test_split)
    test_data = close.iloc[split:]

    all_results = {}

    for name, basket in baskets.items():
        # Check all tickers available
        missing = [t for t in basket if t not in close.columns]
        if missing:
            print(f"  Skipping {name}: missing {missing}")
            continue

        zscores, spreads = compute_basket_zscore(test_data, basket, lookback)
        signals = generate_basket_signals(zscores, entry_z, exit_z, stop_z)
        returns = backtest_basket(test_data, basket, signals, cost_bps)

        # Metrics
        total_days = len(returns)
        cum = (1 + returns).cumprod()

        ann_ret = cum.iloc[-1] ** (252 / total_days) - 1
        ann_vol = returns.std() * np.sqrt(252)
        sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
        peak = cum.cummax()
        max_dd = ((cum - peak) / peak).min()

        # Count trades across all stocks in basket
        n_trades = (signals.diff().abs() > 0).sum().sum() // 2
        days_active = (signals != 0).any(axis=1).sum()

        metrics = {
            "Ann. Return": ann_ret,
            "Ann. Vol": ann_vol,
            "Sharpe": sharpe,
            "Max DD": max_dd,
            "Trades": n_trades,
            "Days Active": days_active,
            "Total Days": total_days,
        }

        all_results[name] = {
            "returns": returns,
            "signals": signals,
            "zscores": zscores,
            "spreads": spreads,
            "metrics": metrics,
            "basket": basket,
        }

        print(f"\n{'='*55}")
        print(f"  {name}: {basket}")
        print(f"{'='*55}")
        print(f"  Ann. Return:    {ann_ret:>8.2%}")
        print(f"  Ann. Vol:       {ann_vol:>8.2%}")
        print(f"  Sharpe:         {sharpe:>8.2f}")
        print(f"  Max Drawdown:   {max_dd:>8.2%}")
        print(f"  Trades:         {n_trades:>8d}")
        print(f"  Days Active:    {days_active:>8d} / {total_days} "
              f"({days_active/total_days:.0%})")
        print(f"{'='*55}")

    return all_results


def plot_basket_analysis(name, result, save_dir="results/plots"):
    """
    Plot a 3-panel chart for one basket:
      1. Z-scores of all 5 stocks
      2. Position signals
      3. Cumulative return
    """
    zscores = result["zscores"]
    signals = result["signals"]
    returns = result["returns"]
    metrics = result["metrics"]
    basket = result["basket"]

    fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=True)
    fig.suptitle(f"Post-Pairs: {name}  |  Sharpe={metrics['Sharpe']:.2f}  "
                 f"MaxDD={metrics['Max DD']:.1%}", fontsize=14, fontweight="bold")

    # Panel 1: Z-scores
    ax = axes[0]
    for ticker in basket:
        ax.plot(zscores.index, zscores[ticker], linewidth=0.8, label=ticker)
    ax.axhline(2.0, color="red", linestyle="--", alpha=0.5)
    ax.axhline(-2.0, color="red", linestyle="--", alpha=0.5)
    ax.axhline(0, color="gray", linestyle="-", alpha=0.3)
    ax.set_ylim(-5, 5)
    ax.set_ylabel("Z-Score")
    ax.set_title("Z-Scores (each stock vs peer average)")
    ax.legend(loc="upper left", fontsize=8, ncol=5)
    ax.grid(True, alpha=0.3)

    # Panel 2: Signals
    ax = axes[1]
    for j, ticker in enumerate(basket):
        sig = signals[ticker]
        active = sig != 0
        colors = sig.map({1: "blue", -1: "red", 0: "none"})
        ax.scatter(sig.index[active], [j] * active.sum(),
                   c=colors[active], s=2, alpha=0.5)
    ax.set_yticks(range(len(basket)))
    ax.set_yticklabels(basket)
    ax.set_ylabel("Stock")
    ax.set_title("Positions (blue=long, red=short)")
    ax.grid(True, alpha=0.3)

    # Panel 3: Cumulative return
    ax = axes[2]
    cum = (1 + returns).cumprod()
    ax.plot(cum.index, cum.values, color="darkblue", linewidth=1.2)
    ax.axhline(1.0, color="gray", linestyle="-", alpha=0.3)
    ax.set_ylabel("Cumulative Return")
    ax.set_title("Strategy Cumulative Return (net of costs)")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    os.makedirs(save_dir, exist_ok=True)
    filename = f"{save_dir}/post_pairs_{name}.png"
    plt.savefig(filename, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {filename}")


if __name__ == "__main__":
    close = pd.read_csv("data/close_prices.csv", index_col=0, parse_dates=True)
    print(f"Running post-pairs on {len(close.columns)} stocks...\n")

    results = run_post_pairs(close)

    print("\n\nGenerating charts...")
    for name, result in results.items():
        plot_basket_analysis(name, result)

    print("\nDone.")
