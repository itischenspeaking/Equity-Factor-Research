"""
post_pairs_v2.py - Basket Stat Arb with OU-based filtering

Improvements over v1:
    1. OU mean-reversion speed filter (kappa): only trade stocks whose
       residual reverts fast enough. Structurally decoupling stocks
       (NVDA, LLY) will have low kappa and get excluded automatically.
    2. ADF stationarity test: reject stocks whose residual is not
       stationary (cointegration has broken down).
    3. Rolling re-estimation: all parameters (kappa, mean, sigma) are
       re-estimated on a rolling 60-day window, so the model adapts
       as relationships shift.

Reference:
    Avellaneda & Lee (2010) "Statistical Arbitrage in the US Equities
    Market", Quantitative Finance 10(7), 761-782.
    - Uses 60-day rolling OU estimation
    - Filters on kappa > 252/30 (mean-reversion time < 30 trading days)
    - Entry at 1.25 sigma, exit at 0.5-0.75 sigma
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
from statsmodels.tsa.stattools import adfuller
from statsmodels.regression.linear_model import OLS
from statsmodels.tools import add_constant


BASKETS = {
    "Banks": ["JPM", "BAC", "WFC", "GS", "MS"],
    "Tech_Software": ["MSFT", "GOOGL", "CRM", "ADBE", "ORCL"],
    "Semis": ["NVDA", "AMD", "AVGO", "QCOM", "TXN"],
    "Consumer_Staples": ["KO", "PEP", "PG", "CL", "KHC"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG"],
    "Pharma": ["JNJ", "PFE", "MRK", "ABT", "LLY"],
}


# ============================================================
# PART 1: OU Parameter Estimation (following Avellaneda & Lee)
# ============================================================

def estimate_ou_params(spread_series):
    """
    Estimate Ornstein-Uhlenbeck parameters from a spread series
    using the discrete AR(1) regression method from Avellaneda & Lee.

    Model: X(n+1) = a + b * X(n) + noise

    From which we extract:
        kappa = -log(b) * 252      (annualised mean-reversion speed)
        mu    = a / (1 - b)        (equilibrium level)
        sigma = std(noise) * sqrt(2*kappa / (1 - b^2))
        sigma_eq = std(noise) / sqrt(1 - b^2)
        half_life = log(2) / kappa * 252   (in trading days)

    Returns dict of params, or None if estimation fails.
    """
    spread = spread_series.dropna().values
    if len(spread) < 20:
        return None

    x_lag = spread[:-1]
    x_next = spread[1:]

    # AR(1) regression: X(n+1) = a + b * X(n)
    X = add_constant(x_lag)
    try:
        result = OLS(x_next, X).fit()
    except Exception:
        return None

    a = result.params[0]
    b = result.params[1]

    # b must be in (0, 1) for mean reversion
    if b <= 0 or b >= 1:
        return None

    residual_std = np.std(result.resid, ddof=1)
    if residual_std == 0:
        return None

    kappa = -np.log(b) * 252
    mu = a / (1 - b)
    sigma_eq = residual_std / np.sqrt(1 - b**2)
    half_life = np.log(2) / (-np.log(b))  # in trading days

    return {
        "kappa": kappa,
        "mu": mu,
        "sigma_eq": sigma_eq,
        "half_life": half_life,
        "b": b,
    }


def compute_s_score(current_spread, ou_params):
    """
    s-score = (X(t) - mu) / sigma_eq

    Measures how many equilibrium standard deviations the spread
    is away from its mean. Equivalent to a z-score but derived
    from the OU model parameters.
    """
    if ou_params is None or ou_params["sigma_eq"] == 0:
        return np.nan
    return (current_spread - ou_params["mu"]) / ou_params["sigma_eq"]


# ============================================================
# PART 2: Filtering
# ============================================================

def passes_filters(spread_series, ou_params,
                   min_kappa=252/30, adf_pvalue=0.05):
    """
    Check whether a stock's residual passes quality filters.

    Filter 1 - Mean-reversion speed:
        kappa > min_kappa (default 252/30 = 8.4, i.e. half-life < 30 days)
        Stocks that are structurally decoupling will have low kappa.

    Filter 2 - ADF stationarity test:
        p-value < adf_pvalue means residual is stationary.
        Non-stationary residuals indicate broken cointegration.

    Returns (passes: bool, reason: str)
    """
    if ou_params is None:
        return False, "OU estimation failed"

    # Filter 1: mean-reversion speed
    if ou_params["kappa"] < min_kappa:
        return False, f"kappa too low ({ou_params['kappa']:.1f} < {min_kappa:.1f})"

    # Filter 2: ADF test
    spread = spread_series.dropna().values
    if len(spread) < 20:
        return False, "insufficient data for ADF"

    try:
        adf_stat, pval, *_ = adfuller(spread, maxlag=10, autolag="AIC")
    except Exception:
        return False, "ADF test failed"

    if pval > adf_pvalue:
        return False, f"ADF p-value too high ({pval:.3f} > {adf_pvalue})"

    return True, "passed"


# ============================================================
# PART 3: Rolling Estimation + Signal Generation
# ============================================================

def run_basket_v2(close, basket, estimation_window=60,
                  entry_s=1.25, exit_s=0.5, stop_s=4.0,
                  min_kappa=252/30, adf_pvalue=0.10):
    """
    Run the full v2 pipeline for one basket with rolling estimation.

    At each trading day:
    1. For each stock, compute its spread vs peer average over the
       trailing estimation_window
    2. Estimate OU parameters on that window
    3. Apply filters (kappa, ADF)
    4. If filters pass, compute s-score and generate signal
    5. If filters fail, close any existing position

    Parameters:
        close: DataFrame of prices
        basket: list of 5 tickers
        estimation_window: rolling window for OU estimation (days)
        entry_s: s-score threshold to open (Avellaneda uses 1.25)
        exit_s: s-score threshold to close
        stop_s: s-score threshold for stop-loss
        min_kappa: minimum mean-reversion speed
        adf_pvalue: max p-value for ADF test

    Returns:
        signals: DataFrame (dates x tickers)
        s_scores: DataFrame (dates x tickers)
        filter_log: DataFrame tracking which stocks pass/fail each day
        diagnostics: dict of per-stock filter statistics
    """
    prices = close[basket]
    returns = prices.pct_change()

    dates = prices.index
    n_dates = len(dates)

    signals = pd.DataFrame(0, index=dates, columns=basket, dtype=float)
    s_scores = pd.DataFrame(np.nan, index=dates, columns=basket, dtype=float)
    filter_status = pd.DataFrame("", index=dates, columns=basket)

    positions = {t: 0 for t in basket}

    # Track cumulative spread for each stock vs peers
    spreads_daily = pd.DataFrame(index=dates, columns=basket, dtype=float)
    for stock in basket:
        peers = [t for t in basket if t != stock]
        peer_mean_ret = returns[peers].mean(axis=1)
        spreads_daily[stock] = (returns[stock] - peer_mean_ret)

    cum_spread = spreads_daily.cumsum()

    for i in range(estimation_window, n_dates):
        window_start = i - estimation_window
        date = dates[i]

        for stock in basket:
            # Extract trailing window of cumulative spread
            spread_window = cum_spread[stock].iloc[window_start:i]

            # Step 1: Estimate OU parameters
            ou = estimate_ou_params(spread_window)

            # Step 2: Apply filters
            passed, reason = passes_filters(spread_window, ou,
                                            min_kappa, adf_pvalue)
            filter_status.loc[date, stock] = reason

            if not passed:
                # Filters failed: close any existing position
                positions[stock] = 0
                signals.loc[date, stock] = 0
                s_scores.loc[date, stock] = np.nan
                continue

            # Step 3: Compute s-score using current spread value
            current_spread = cum_spread[stock].iloc[i]
            s = compute_s_score(current_spread, ou)
            s_scores.loc[date, stock] = s

            if np.isnan(s):
                positions[stock] = 0
                signals.loc[date, stock] = 0
                continue

            # Step 4: Generate signal
            pos = positions[stock]

            if pos == 0:
                if s < -entry_s:
                    pos = 1    # spread too low -> stock is cheap -> long
                elif s > entry_s:
                    pos = -1   # spread too high -> stock is rich -> short
            elif pos == 1:
                if s > -exit_s or s < -stop_s:
                    pos = 0
            elif pos == -1:
                if s < exit_s or s > stop_s:
                    pos = 0

            positions[stock] = pos
            signals.loc[date, stock] = pos

    # Compute filter diagnostics
    diagnostics = {}
    for stock in basket:
        total = (filter_status[stock] != "").sum()
        passed = (filter_status[stock] == "passed").sum()
        diagnostics[stock] = {
            "pass_rate": passed / total if total > 0 else 0,
            "total_days": total,
            "passed_days": passed,
        }

    return signals, s_scores, filter_status, diagnostics


def backtest_basket_v2(close, basket, signals, cost_bps=10):
    """
    Backtest one basket (same logic as v1).
    """
    returns = close[basket].pct_change()
    prev_signals = signals.shift(1).fillna(0)
    port_return = pd.Series(0.0, index=returns.index)

    for stock in basket:
        peers = [t for t in basket if t != stock]
        sig = prev_signals[stock]

        stock_contrib = sig * returns[stock]
        peer_contrib = -sig * returns[peers].mean(axis=1)

        port_return += 0.5 * stock_contrib + 0.5 * peer_contrib

    signal_changes = signals.diff().abs().sum(axis=1).fillna(0)
    costs = signal_changes * cost_bps / 10000
    net_return = port_return - costs

    return net_return.dropna()


# ============================================================
# PART 4: Run All Baskets
# ============================================================

def run_all_baskets_v2(close, baskets=None, test_split=0.7, **kwargs):
    """
    Run v2 on all baskets, out-of-sample.
    """
    if baskets is None:
        baskets = BASKETS

    n = len(close)
    split = int(n * test_split)
    test_data = close.iloc[split:]

    all_results = {}

    for name, basket in baskets.items():
        missing = [t for t in basket if t not in close.columns]
        if missing:
            print(f"  Skipping {name}: missing {missing}")
            continue

        signals, s_scores, filter_status, diagnostics = \
            run_basket_v2(test_data, basket, **kwargs)
        returns = backtest_basket_v2(test_data, basket, signals)

        # Metrics
        total_days = len(returns)
        cum = (1 + returns).cumprod()

        ann_ret = cum.iloc[-1] ** (252 / total_days) - 1
        ann_vol = returns.std() * np.sqrt(252)
        sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
        peak = cum.cummax()
        max_dd = ((cum - peak) / peak).min()

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
            "s_scores": s_scores,
            "filter_status": filter_status,
            "diagnostics": diagnostics,
            "metrics": metrics,
            "basket": basket,
        }

        # Print results
        print(f"\n{'='*60}")
        print(f"  {name}: {basket}")
        print(f"{'='*60}")
        print(f"  Ann. Return:    {ann_ret:>8.2%}")
        print(f"  Ann. Vol:       {ann_vol:>8.2%}")
        print(f"  Sharpe:         {sharpe:>8.2f}")
        print(f"  Max Drawdown:   {max_dd:>8.2%}")
        print(f"  Trades:         {n_trades:>8d}")
        print(f"  Days Active:    {days_active:>8d} / {total_days} "
              f"({days_active/total_days:.0%})")
        print(f"  --- Filter pass rates ---")
        for stock, diag in diagnostics.items():
            print(f"    {stock:6s}: {diag['pass_rate']:.0%} "
                  f"({diag['passed_days']}/{diag['total_days']} days)")
        print(f"{'='*60}")

    return all_results


# ============================================================
# PART 5: Visualization
# ============================================================

def plot_basket_v2(name, result, save_dir="results/post_pairs/v2/plots"):
    """
    Plot a 4-panel chart for one basket:
      1. S-scores of all 5 stocks (only when filter passes)
      2. Filter pass/fail status
      3. Position signals
      4. Cumulative return, compared with v1 if available
    """
    s_scores = result["s_scores"]
    signals = result["signals"]
    returns = result["returns"]
    metrics = result["metrics"]
    basket = result["basket"]
    filter_status = result["filter_status"]

    fig, axes = plt.subplots(4, 1, figsize=(14, 16), sharex=True)
    fig.suptitle(
        f"Post-Pairs v2: {name}  |  Sharpe={metrics['Sharpe']:.2f}  "
        f"MaxDD={metrics['Max DD']:.1%}",
        fontsize=14, fontweight="bold"
    )

    # Panel 1: S-scores
    ax = axes[0]
    for ticker in basket:
        ax.plot(s_scores.index, s_scores[ticker], linewidth=0.8, label=ticker)
    ax.axhline(1.25, color="red", linestyle="--", alpha=0.5, label="Entry (±1.25)")
    ax.axhline(-1.25, color="red", linestyle="--", alpha=0.5)
    ax.axhline(0, color="gray", linestyle="-", alpha=0.3)
    ax.set_ylim(-5, 5)
    ax.set_ylabel("S-Score")
    ax.set_title("S-Scores (OU-based, shown only when filters pass)")
    ax.legend(loc="upper left", fontsize=8, ncol=5)
    ax.grid(True, alpha=0.3)

    # Panel 2: Filter status (green = pass, red = fail)
    ax = axes[1]
    for j, ticker in enumerate(basket):
        passed = filter_status[ticker] == "passed"
        failed = (filter_status[ticker] != "passed") & (filter_status[ticker] != "")
        ax.fill_between(filter_status.index, j - 0.4, j + 0.4,
                         where=passed, color="green", alpha=0.3)
        ax.fill_between(filter_status.index, j - 0.4, j + 0.4,
                         where=failed, color="red", alpha=0.15)
    ax.set_yticks(range(len(basket)))
    ax.set_yticklabels(basket)
    ax.set_ylabel("Stock")
    ax.set_title("Filter Status (green=pass, red=filtered out)")
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

    # Panel 4: Cumulative return
    ax = axes[3]
    cum = (1 + returns).cumprod()
    ax.plot(cum.index, cum.values, color="darkblue", linewidth=1.2, label="v2")
    ax.axhline(1.0, color="gray", linestyle="-", alpha=0.3)
    ax.set_ylabel("Cumulative Return")
    ax.set_title("Strategy Cumulative Return (net of costs)")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    os.makedirs(save_dir, exist_ok=True)
    filename = f"{save_dir}/post_pairs_v2_{name}.png"
    plt.savefig(filename, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {filename}")


if __name__ == "__main__":
    close = pd.read_csv("data/close_prices.csv", index_col=0, parse_dates=True)
    print(f"Running post-pairs v2 on {len(close.columns)} stocks...\n")

    results = run_all_baskets_v2(close)

    print("\n\nGenerating charts...")
    for name, result in results.items():
        plot_basket_v2(name, result)

    print("\nDone.")
