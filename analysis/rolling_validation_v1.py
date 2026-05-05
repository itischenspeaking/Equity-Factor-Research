"""
rolling_validation.py - Rolling Forward Validation

Instead of a single train/test split, evaluate the strategy on
rolling 60-day forward windows. For each window start date t:
    1. Use all data before t to estimate spread parameters
       (rolling mean, std for z-score)
    2. Run the strategy from t to t+60
    3. Record performance metrics for that window

This produces a time series of out-of-sample Sharpe ratios,
revealing how strategy performance varies across market regimes.

Currently implemented for Post-Pairs v1 Consumer Staples only.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os


BASKET = ["KO", "PEP", "PG", "CL", "KHC"]
BASKET_NAME = "Consumer_Staples"


def compute_residuals(close, basket):
    """
    Compute daily return residuals for each stock vs peer average.
    Returns cumulative spread DataFrame.
    """
    prices = close[basket]
    returns = prices.pct_change()

    spreads = pd.DataFrame(index=returns.index, columns=basket,
                           dtype=float)
    for stock in basket:
        peers = [t for t in basket if t != stock]
        spreads[stock] = returns[stock] - returns[peers].mean(axis=1)

    cum_spread = spreads.cumsum()
    return returns, cum_spread


def run_single_window(returns, cum_spread, basket,
                      window_start, window_end,
                      lookback=60, entry_z=2.0, exit_z=0.5,
                      stop_z=4.0, cost_bps=10):
    """
    Run the strategy on a single forward window.

    Parameters:
        returns: daily stock returns DataFrame
        cum_spread: cumulative spread DataFrame
        basket: list of tickers
        window_start: first day of evaluation window
        window_end: last day of evaluation window
        lookback: days before window_start to use for z-score params

    Returns:
        dict with daily returns Series and performance metrics,
        or None if insufficient data
    """
    # Get indices
    all_dates = cum_spread.index
    start_idx = all_dates.get_loc(window_start)

    if start_idx < lookback:
        return None

    # Slice data
    window_data = cum_spread.loc[window_start:window_end]
    window_returns = returns.loc[window_start:window_end]

    if len(window_data) < 10:
        return None

    # For each day in the window, compute z-score using
    # trailing lookback from BEFORE that day (expanding from
    # pre-window history + days already seen in window)
    signals = pd.DataFrame(0, index=window_data.index,
                           columns=basket, dtype=float)
    positions = {t: 0 for t in basket}

    for i, date in enumerate(window_data.index):
        date_idx = all_dates.get_loc(date)

        # Use all data up to (not including) this date for params
        history_start = max(0, date_idx - lookback)
        history = cum_spread.iloc[history_start:date_idx]

        if len(history) < 20:
            continue

        for stock in basket:
            spread_hist = history[stock]
            mean = spread_hist.mean()
            std = spread_hist.std()

            if std == 0 or np.isnan(std):
                continue

            current = cum_spread[stock].iloc[date_idx]
            z = (current - mean) / std

            pos = positions[stock]

            if pos == 0:
                if z < -entry_z:
                    pos = 1
                elif z > entry_z:
                    pos = -1
            elif pos == 1:
                if z > -exit_z or z < -stop_z:
                    pos = 0
            elif pos == -1:
                if z < exit_z or z > stop_z:
                    pos = 0

            positions[stock] = pos
            signals.loc[date, stock] = pos

    # Compute portfolio returns
    prev_signals = signals.shift(1).fillna(0)
    port_return = pd.Series(0.0, index=window_returns.index)

    for stock in basket:
        peers = [t for t in basket if t != stock]
        sig = prev_signals[stock]
        stock_contrib = sig * window_returns[stock]
        peer_contrib = -sig * window_returns[peers].mean(axis=1)
        port_return += 0.5 * stock_contrib + 0.5 * peer_contrib

    # Transaction costs
    signal_changes = signals.diff().abs().sum(axis=1).fillna(0)
    costs = signal_changes * cost_bps / 10000
    net_return = port_return - costs
    net_return = net_return.dropna()

    if len(net_return) < 10:
        return None

    # Metrics for this window
    cum = (1 + net_return).cumprod()
    total_ret = cum.iloc[-1] - 1
    ann_factor = 252 / len(net_return)
    ann_ret = (1 + total_ret) ** ann_factor - 1
    ann_vol = net_return.std() * np.sqrt(252)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
    peak = cum.cummax()
    max_dd = ((cum - peak) / peak).min()
    days_active = (signals != 0).any(axis=1).sum()

    return {
        "window_start": window_start,
        "window_end": window_data.index[-1],
        "n_days": len(net_return),
        "total_return": total_ret,
        "ann_return": ann_ret,
        "ann_vol": ann_vol,
        "sharpe": sharpe,
        "max_dd": max_dd,
        "days_active": days_active,
        "daily_returns": net_return,
    }


def run_rolling_validation(close, basket, forward_window=60,
                           step=1, min_history=252):
    """
    Run rolling forward validation across the full sample.

    Parameters:
        close: DataFrame of daily close prices
        basket: list of 5 tickers
        forward_window: evaluation window size (trading days)
        step: how many days to advance between windows
        min_history: minimum history required before first window

    Returns:
        results_df: DataFrame with one row per window
        all_daily_returns: concatenated daily returns Series
    """
    returns, cum_spread = compute_residuals(close, basket)
    all_dates = cum_spread.index

    results = []
    all_daily = []

    # Start after min_history days
    start_positions = range(min_history, len(all_dates) - forward_window,
                            step)

    print(f"  Running {len(start_positions)} windows "
          f"(step={step}, forward={forward_window}d)...")

    for i, start_pos in enumerate(start_positions):
        window_start = all_dates[start_pos]
        window_end = all_dates[min(start_pos + forward_window - 1,
                                   len(all_dates) - 1)]

        result = run_single_window(
            returns, cum_spread, basket,
            window_start, window_end
        )

        if result is not None:
            results.append({k: v for k, v in result.items()
                           if k != "daily_returns"})
            all_daily.append(result["daily_returns"])

        if (i + 1) % 200 == 0:
            print(f"    {i+1}/{len(start_positions)} windows done")

    results_df = pd.DataFrame(results)
    print(f"  Completed: {len(results_df)} valid windows")

    return results_df


def plot_rolling_results(results_df, save_dir="results/post_pairs/v1/plots"):
    """
    Plot rolling validation results: 4-panel chart.
    """
    fig, axes = plt.subplots(4, 1, figsize=(14, 16), sharex=True)
    fig.suptitle("Rolling Forward Validation: Consumer Staples v1\n"
                 "(60-day forward windows, daily step)",
                 fontsize=14, fontweight="bold")

    dates = results_df["window_start"]

    # Panel 1: Rolling Sharpe
    ax = axes[0]
    sharpe = results_df["sharpe"]
    colors = ["steelblue" if s > 0 else "salmon" for s in sharpe]
    ax.bar(dates, sharpe, width=2, color=colors, alpha=0.7)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.axhline(sharpe.mean(), color="darkblue", linestyle="--",
               alpha=0.5, label=f"Mean: {sharpe.mean():.2f}")
    ax.set_ylabel("Annualised Sharpe")
    ax.set_title("Rolling 60-Day Sharpe Ratio")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

    # Panel 2: Rolling return
    ax = axes[1]
    ax.bar(dates, results_df["total_return"] * 100, width=2,
           color="steelblue", alpha=0.7)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_ylabel("Window Return (%)")
    ax.set_title("Rolling 60-Day Total Return")
    ax.grid(True, alpha=0.3)

    # Panel 3: Rolling max drawdown
    ax = axes[2]
    ax.bar(dates, results_df["max_dd"] * 100, width=2,
           color="salmon", alpha=0.7)
    ax.set_ylabel("Max Drawdown (%)")
    ax.set_title("Rolling 60-Day Max Drawdown")
    ax.grid(True, alpha=0.3)

    # Panel 4: Days active per window
    ax = axes[3]
    pct_active = results_df["days_active"] / results_df["n_days"]
    ax.bar(dates, pct_active * 100, width=2,
           color="steelblue", alpha=0.7)
    ax.axhline(pct_active.mean() * 100, color="darkblue",
               linestyle="--", alpha=0.5,
               label=f"Mean: {pct_active.mean():.0%}")
    ax.set_ylabel("Days Active (%)")
    ax.set_title("Percentage of Days with Active Positions")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    os.makedirs(save_dir, exist_ok=True)
    path = f"{save_dir}/rolling_validation_staples.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")


def print_summary(results_df):
    """Print aggregate statistics across all windows."""
    print(f"\n{'='*60}")
    print(f"  Rolling Validation Summary: Consumer Staples v1")
    print(f"{'='*60}")
    print(f"  Windows evaluated:     {len(results_df)}")
    print(f"  Date range:            {results_df['window_start'].iloc[0].date()}"
          f" to {results_df['window_end'].iloc[-1].date()}")

    s = results_df["sharpe"]
    print(f"  ---")
    print(f"  Sharpe mean:           {s.mean():>8.2f}")
    print(f"  Sharpe median:         {s.median():>8.2f}")
    print(f"  Sharpe std:            {s.std():>8.2f}")
    print(f"  Sharpe > 0:            {(s > 0).sum()}/{len(s)} "
          f"({(s > 0).mean():.0%})")
    print(f"  Sharpe > 1:            {(s > 1).sum()}/{len(s)} "
          f"({(s > 1).mean():.0%})")

    r = results_df["total_return"]
    print(f"  ---")
    print(f"  Window return mean:    {r.mean():>8.2%}")
    print(f"  Window return median:  {r.median():>8.2%}")
    print(f"  Positive windows:      {(r > 0).sum()}/{len(r)} "
          f"({(r > 0).mean():.0%})")

    dd = results_df["max_dd"]
    print(f"  ---")
    print(f"  Avg max drawdown:      {dd.mean():>8.2%}")
    print(f"  Worst max drawdown:    {dd.min():>8.2%}")
    print(f"{'='*60}")


if __name__ == "__main__":
    close = pd.read_csv("data/close_prices.csv", index_col=0,
                        parse_dates=True)

    print(f"Running rolling validation on Consumer Staples v1...")
    print(f"Basket: {BASKET}\n")

    results_df = run_rolling_validation(close, BASKET)

    print_summary(results_df)

    print("\nGenerating charts...")
    plot_rolling_results(results_df)

    # Save results
    os.makedirs("results/data_export", exist_ok=True)
    results_df.to_csv("results/data_export/09_rolling_validation_staples.csv",
                      index=False)
    print("  Saved: results/data_export/09_rolling_validation_staples.csv")

    print("\nDone.")
