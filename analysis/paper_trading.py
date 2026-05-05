"""
paper_trading.py - Forward Paper Money Simulation

True out-of-sample test: train on 2015-2024, simulate on 2025-01
to present. No parameter re-estimation during the test period —
all spread statistics are computed from the training set and held
fixed, exactly as if we had deployed the strategy in January 2025.
"""
import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import os
import sys

sys.path.insert(0, ".")

BASKET = ["KO", "PEP", "PG", "CL", "KHC"]


def download_forward_data(tickers, start="2025-01-01", end="2026-05-06"):
    """Download price data for the forward test period."""
    print(f"  Downloading {tickers} from {start} to {end}...")
    raw = yf.download(tickers, start=start, end=end, auto_adjust=True)
    close = raw["Close"]
    print(f"  Got {len(close)} trading days")
    return close


def train_parameters(close_train, basket, lookback=60):
    """
    Estimate spread parameters from training data (2015-2024).
    Returns the rolling mean and std of cumulative spread at the
    END of the training period — these are the parameters we
    "freeze" and carry into the forward test.
    """
    returns = close_train[basket].pct_change()

    spreads = pd.DataFrame(index=returns.index, columns=basket,
                           dtype=float)
    for stock in basket:
        peers = [t for t in basket if t != stock]
        spreads[stock] = returns[stock] - returns[peers].mean(axis=1)

    cum_spread = spreads.cumsum()

    # Use the last `lookback` days of training to set z-score params
    train_tail = cum_spread.iloc[-lookback:]
    params = {}
    for stock in basket:
        params[stock] = {
            "mean": train_tail[stock].mean(),
            "std": train_tail[stock].std(),
        }

    return cum_spread, params


def run_forward_simulation(close_train, close_forward, basket,
                           lookback=60, entry_z=2.0, exit_z=0.5,
                           stop_z=4.0, cost_bps=10):
    """
    Run the strategy on forward data using training-period parameters.

    Key difference from backtest: z-score parameters are computed
    on a rolling basis that STARTS from training data and expands
    into the forward period. This simulates real deployment where
    you have history but no future data.
    """
    # Compute cumulative spread on training data
    train_returns = close_train[basket].pct_change()
    train_spreads = pd.DataFrame(index=train_returns.index,
                                 columns=basket, dtype=float)
    for stock in basket:
        peers = [t for t in basket if t != stock]
        train_spreads[stock] = train_returns[stock] - \
            train_returns[peers].mean(axis=1)
    train_cum = train_spreads.cumsum()

    # Compute cumulative spread on forward data, continuing from
    # the end of training
    fwd_returns = close_forward[basket].pct_change()
    fwd_spreads = pd.DataFrame(index=fwd_returns.index,
                               columns=basket, dtype=float)
    for stock in basket:
        peers = [t for t in basket if t != stock]
        fwd_spreads[stock] = fwd_returns[stock] - \
            fwd_returns[peers].mean(axis=1)

    # Continue cumulative spread from training end
    last_train_cum = train_cum.iloc[-1]
    fwd_cum = fwd_spreads.cumsum() + last_train_cum

    # Combine training tail + forward for rolling z-score computation
    combined_cum = pd.concat([train_cum.iloc[-lookback:], fwd_cum])

    # Generate signals on forward period only
    signals = pd.DataFrame(0, index=fwd_cum.index, columns=basket,
                           dtype=float)
    positions = {t: 0 for t in basket}

    for i, date in enumerate(fwd_cum.index):
        combined_idx = combined_cum.index.get_loc(date)

        for stock in basket:
            # Rolling lookback from combined data
            hist_start = max(0, combined_idx - lookback)
            history = combined_cum[stock].iloc[hist_start:combined_idx]

            if len(history) < 20:
                continue

            mean = history.mean()
            std = history.std()
            if std == 0 or np.isnan(std):
                continue

            current = combined_cum[stock].iloc[combined_idx]
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

    # Portfolio returns
    prev_signals = signals.shift(1).fillna(0)
    port_return = pd.Series(0.0, index=fwd_returns.index)

    for stock in basket:
        peers = [t for t in basket if t != stock]
        sig = prev_signals[stock]
        port_return += 0.5 * sig * fwd_returns[stock] + \
            0.5 * (-sig) * fwd_returns[peers].mean(axis=1)

    signal_changes = signals.diff().abs().sum(axis=1).fillna(0)
    costs = signal_changes * cost_bps / 10000
    net_return = (port_return - costs).dropna()

    return net_return, signals


def run_ff6_attribution(daily_returns):
    """Run FF6 regression on the forward period returns."""
    from analysis.ff_attribution import download_ff_factors, \
        compute_monthly_returns, run_ff_regression, print_attribution

    ff = download_ff_factors(start="2025-01-01", end="2026-05-31")
    monthly = compute_monthly_returns(daily_returns)

    if len(monthly) < 3:
        print("  Not enough monthly observations for FF6 regression")
        return None, None

    model, summary = run_ff_regression(monthly, ff)
    print_attribution("Paper Trading: Staples (2025-2026)", summary)
    return model, summary


def plot_paper_trading(net_return, signals, basket, save_dir):
    """Plot equity curve and position activity."""
    fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=True)
    fig.suptitle("Paper Trading: Consumer Staples v1\n"
                 "Trained on 2015-2024, deployed 2025-01 to present",
                 fontsize=14, fontweight="bold")

    # Panel 1: Equity curve
    ax = axes[0]
    cum = (1 + net_return).cumprod()
    ax.plot(cum.index, cum.values, color="darkblue", linewidth=1.5)
    ax.axhline(1.0, color="gray", linestyle="-", alpha=0.3)
    ax.fill_between(cum.index, 1.0, cum.values,
                    where=cum.values >= 1.0, alpha=0.1, color="green")
    ax.fill_between(cum.index, 1.0, cum.values,
                    where=cum.values < 1.0, alpha=0.1, color="red")
    ax.set_ylabel("Cumulative Return")
    ax.set_title("Equity Curve (net of 10bps costs)")
    ax.grid(True, alpha=0.3)

    # Panel 2: Daily returns
    ax = axes[1]
    colors = ["steelblue" if r >= 0 else "salmon" for r in net_return]
    ax.bar(net_return.index, net_return.values * 100, color=colors,
           alpha=0.7, width=1)
    ax.set_ylabel("Daily Return (%)")
    ax.set_title("Daily Returns")
    ax.grid(True, alpha=0.3)

    # Panel 3: Positions
    ax = axes[2]
    for j, ticker in enumerate(basket):
        sig = signals[ticker]
        long_pos = sig == 1
        short_pos = sig == -1
        ax.fill_between(signals.index, j - 0.4, j + 0.4,
                        where=long_pos, color="blue", alpha=0.4)
        ax.fill_between(signals.index, j - 0.4, j + 0.4,
                        where=short_pos, color="red", alpha=0.4)
    ax.set_yticks(range(len(basket)))
    ax.set_yticklabels(basket)
    ax.set_ylabel("Stock")
    ax.set_title("Positions (blue=long, red=short)")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    os.makedirs(save_dir, exist_ok=True)
    path = f"{save_dir}/paper_trading_staples.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")


if __name__ == "__main__":
    # Load training data
    print("Loading training data (2015-2024)...")
    close_train = pd.read_csv("data/close_prices.csv", index_col=0,
                              parse_dates=True)

    # Download forward data
    print("\nDownloading forward data (2025-2026)...")
    close_forward = download_forward_data(BASKET)

    # Run simulation
    print("\nRunning forward simulation...")
    net_return, signals = run_forward_simulation(
        close_train, close_forward, BASKET
    )

    # Performance metrics
    total_days = len(net_return)
    cum = (1 + net_return).cumprod()
    total_ret = cum.iloc[-1] - 1
    ann_ret = (1 + total_ret) ** (252 / total_days) - 1
    ann_vol = net_return.std() * np.sqrt(252)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
    peak = cum.cummax()
    max_dd = ((cum - peak) / peak).min()
    n_trades = (signals.diff().abs() > 0).sum().sum() // 2
    days_active = (signals != 0).any(axis=1).sum()

    print(f"\n{'='*60}")
    print(f"  Paper Trading Results: Consumer Staples v1")
    print(f"  Period: {net_return.index[0].date()} to "
          f"{net_return.index[-1].date()} ({total_days} days)")
    print(f"{'='*60}")
    print(f"  Total Return:      {total_ret:>8.2%}")
    print(f"  Ann. Return:       {ann_ret:>8.2%}")
    print(f"  Ann. Volatility:   {ann_vol:>8.2%}")
    print(f"  Sharpe Ratio:      {sharpe:>8.2f}")
    print(f"  Max Drawdown:      {max_dd:>8.2%}")
    print(f"  Trades:            {n_trades:>8d}")
    print(f"  Days Active:       {days_active:>8d} / {total_days} "
          f"({days_active/total_days:.0%})")
    print(f"{'='*60}")

    # Plot
    print("\nGenerating charts...")
    plot_paper_trading(net_return, signals, BASKET,
                       save_dir="results/post_pairs/v1/plots")

    # FF6 attribution
    print("\nRunning FF6 attribution on forward period...")
    model, summary = run_ff6_attribution(net_return)

    # Save results
    os.makedirs("results/data_export", exist_ok=True)
    results_df = pd.DataFrame({
        "date": net_return.index,
        "daily_return": net_return.values,
        "cumulative_return": cum.values,
    })
    results_df.to_csv(
        "results/data_export/11_paper_trading_daily_returns.csv",
        index=False
    )
    print("  Saved: results/data_export/11_paper_trading_daily_returns.csv")

    print("\nDone.")
