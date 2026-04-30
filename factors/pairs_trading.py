"""
pairs_trading.py - Statistical Arbitrage via Pairs Trading

Finds cointegrated stock pairs, generates z-score based trading
signals, and backtests the strategy.

Theory:
    Two stocks sharing the same business drivers (e.g. KO and PEP)
    tend to move together. When their price spread deviates from
    the historical norm, we bet on mean reversion: long the laggard,
    short the leader, and close when the spread normalizes.

References:
    - Gatev, Goetzmann & Rouwenhorst (2006), Review of Financial Studies
    - Engle & Granger (1987), Econometrica
    - Vidyamurthy (2004), Pairs Trading, Wiley Finance
"""
import itertools
import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint
from statsmodels.regression.linear_model import OLS
from statsmodels.tools import add_constant


# ============================================================
# PART 1: Pair Selection
# ============================================================

# Candidate pairs grouped by sector.
# Only stocks with similar business models should be paired.
SECTOR_GROUPS = {
    "Tech": ["MSFT", "GOOGL", "CRM", "ADBE", "ORCL"],
    "Semis": ["NVDA", "AMD", "INTC", "TXN", "AVGO", "QCOM"],
    "Banks": ["JPM", "BAC", "WFC", "C", "GS", "MS"],
    "Energy": ["XOM", "CVX", "COP", "SLB"],
    "Consumer_Staples": ["KO", "PEP", "PG", "CL", "WMT", "COST"],
    "Fast_Food": ["MCD", "SBUX"],
    "Pharma": ["JNJ", "PFE", "MRK", "ABT", "LLY"],
    "Insurance": ["UNH", "CI"],
    "Industrial": ["CAT", "DE", "HON", "MMM"],
    "Telecom": ["VZ", "T"],
}


def get_candidate_pairs(sector_groups=None):
    """Generate all within-sector pairs from the sector groups."""
    if sector_groups is None:
        sector_groups = SECTOR_GROUPS

    pairs = []
    for sector, tickers in sector_groups.items():
        for a, b in itertools.combinations(tickers, 2):
            pairs.append((a, b))
    return pairs


def compute_hedge_ratio(price_a, price_b):
    """
    OLS regression: price_a = alpha + beta * price_b + epsilon

    Returns beta (the hedge ratio). This tells you how many dollars
    of stock B to hold for every dollar of stock A so that the
    resulting spread is stationary.
    """
    y = price_a.values
    x = add_constant(price_b.values)
    result = OLS(y, x).fit()
    beta = result.params[1]
    return beta


def compute_spread(price_a, price_b, beta):
    """
    Spread = price_a - beta * price_b

    If the pair is cointegrated, this spread is mean-reverting.
    """
    return price_a - beta * price_b


def compute_half_life(spread):
    """
    Estimate the half-life of mean reversion via AR(1) model.

    Regress delta_spread on spread_lag:
        spread(t) - spread(t-1) = phi * spread(t-1) + noise

    Half-life = -log(2) / log(1 + phi)

    Shorter half-life = faster mean reversion = better for trading.
    """
    spread_lag = spread.shift(1).dropna()
    delta = spread.diff().dropna()

    common = spread_lag.index.intersection(delta.index)
    spread_lag = spread_lag.loc[common]
    delta = delta.loc[common]

    x = add_constant(spread_lag.values)
    result = OLS(delta.values, x).fit()
    phi = result.params[1]

    if phi >= 0:
        return np.inf

    half_life = -np.log(2) / np.log(1 + phi)
    return half_life


def screen_pairs(close, formation_start=None, formation_end=None,
                 corr_threshold=0.7, coint_pvalue=0.05):
    """
    Full screening pipeline:
    1. Generate within-sector candidate pairs
    2. Filter by return correlation (> corr_threshold)
    3. Run Engle-Granger cointegration test
    4. Compute hedge ratio and spread half-life
    5. Return ranked table (fastest mean reversion first)

    Parameters:
        close: DataFrame, daily close prices (dates x tickers)
        formation_start/end: date range for estimation
                             (default: first 70% of data)
        corr_threshold: minimum return correlation
        coint_pvalue: max p-value for cointegration test

    Returns:
        DataFrame: [stock_a, stock_b, correlation, coint_pvalue,
                    hedge_ratio, half_life_days]
    """
    if formation_start is None:
        n = len(close)
        split = int(n * 0.7)
        formation = close.iloc[:split]
    else:
        formation = close.loc[formation_start:formation_end]

    candidates = get_candidate_pairs()
    available = close.columns.tolist()

    results = []
    for stock_a, stock_b in candidates:
        if stock_a not in available or stock_b not in available:
            continue

        pa = formation[stock_a].dropna()
        pb = formation[stock_b].dropna()

        common = pa.index.intersection(pb.index)
        if len(common) < 200:
            continue
        pa = pa.loc[common]
        pb = pb.loc[common]

        # Correlation filter
        corr = pa.pct_change().corr(pb.pct_change())
        if corr < corr_threshold:
            continue

        # Engle-Granger cointegration test
        score, pvalue, _ = coint(pa, pb)
        if pvalue > coint_pvalue:
            continue

        # Hedge ratio and spread
        beta = compute_hedge_ratio(pa, pb)
        spread = compute_spread(pa, pb, beta)
        hl = compute_half_life(spread)

        # Keep pairs with reasonable half-life (2-120 trading days)
        if hl < 2 or hl > 120 or np.isinf(hl):
            continue

        results.append({
            "stock_a": stock_a,
            "stock_b": stock_b,
            "correlation": round(corr, 3),
            "coint_pvalue": round(pvalue, 4),
            "hedge_ratio": round(beta, 4),
            "half_life_days": round(hl, 1),
        })

    df = pd.DataFrame(results)
    if len(df) == 0:
        print("No cointegrated pairs found.")
        return df

    df = df.sort_values("half_life_days").reset_index(drop=True)
    return df

# ============================================================
# PART 2: Signal Generation
# ============================================================

def generate_signals(price_a, price_b, beta, lookback=60,
                     entry_z=2.0, exit_z=0.5, stop_z=4.0):
    """
    Generate trading signals based on rolling z-score of the spread.

    Signal values:
         1 = long spread  (long A, short B) when z < -entry_z
        -1 = short spread (short A, long B) when z > +entry_z
         0 = no position / exit

    Exit when |z| < exit_z.
    Stop-loss when |z| > stop_z (spread may never revert).

    Parameters:
        price_a, price_b: Series of daily close prices
        beta: hedge ratio from formation period
        lookback: rolling window for z-score (days)
        entry_z: z-score threshold to open position
        exit_z: z-score threshold to close position
        stop_z: z-score threshold for stop-loss
    """
    spread = compute_spread(price_a, price_b, beta)
    mean = spread.rolling(lookback).mean()
    std = spread.rolling(lookback).std()
    zscore = (spread - mean) / std

    signals = pd.Series(0, index=zscore.index)
    position = 0

    for i in range(len(zscore)):
        z = zscore.iloc[i]

        if np.isnan(z):
            signals.iloc[i] = 0
            continue

        if position == 0:
            # No position: check for entry
            if z < -entry_z:
                position = 1   # spread is too low -> long A, short B
            elif z > entry_z:
                position = -1  # spread is too high -> short A, long B
        elif position == 1:
            # Long spread: exit or stop
            if z > -exit_z or z < -stop_z:
                position = 0
        elif position == -1:
            # Short spread: exit or stop
            if z < exit_z or z > stop_z:
                position = 0

        signals.iloc[i] = position

    return signals, zscore, spread


# ============================================================
# PART 3: Backtest
# ============================================================

def backtest_pair(price_a, price_b, beta, signals, cost_bps=10):
    """
    Backtest a single pair.

    When signal = 1:  long A, short B (weighted by beta)
    When signal = -1: short A, long B (weighted by beta)

    Returns daily portfolio returns (net of transaction costs).
    """
    ret_a = price_a.pct_change()
    ret_b = price_b.pct_change()

    # Normalize weights: $1 long A, $beta short B (or vice versa)
    total_exposure = 1 + abs(beta)
    w_a = 1 / total_exposure
    w_b = abs(beta) / total_exposure

    # Portfolio return based on signal direction
    prev_signal = signals.shift(1).fillna(0)
    port_return = prev_signal * (w_a * ret_a - w_b * ret_b)

    # Transaction costs on signal changes
    signal_changes = signals.diff().abs().fillna(0)
    costs = signal_changes * cost_bps / 10000
    net_return = port_return - costs

    return net_return.dropna()


def backtest_all_pairs(close, pairs_df, test_start=None, cost_bps=10):
    """
    Backtest all pairs on the out-of-sample period.

    Parameters:
        close: full price DataFrame
        pairs_df: output from screen_pairs()
        test_start: start of out-of-sample period
                    (default: last 30% of data)
        cost_bps: one-way transaction cost in basis points

    Returns:
        results: dict of {pair_name: {returns, signals, zscore, metrics}}
    """
    if test_start is None:
        n = len(close)
        split = int(n * 0.7)
        test_start = close.index[split]

    test_data = close.loc[test_start:]
    results = {}

    for _, row in pairs_df.iterrows():
        a, b = row["stock_a"], row["stock_b"]
        beta = row["hedge_ratio"]
        pair_name = f"{a}/{b}"

        pa = test_data[a]
        pb = test_data[b]

        signals, zscore, spread = generate_signals(pa, pb, beta)
        returns = backtest_pair(pa, pb, beta, signals, cost_bps)

        # Metrics
        n_trades = (signals.diff().abs() > 0).sum() // 2
        total_days = len(returns)
        days_in_market = (signals != 0).sum()

        cum = (1 + returns).cumprod()
        ann_ret = cum.iloc[-1] ** (252 / total_days) - 1
        ann_vol = returns.std() * np.sqrt(252)
        sharpe = ann_ret / ann_vol if ann_vol > 0 else 0

        peak = cum.cummax()
        max_dd = ((cum - peak) / peak).min()

        metrics = {
            "Ann. Return": ann_ret,
            "Ann. Vol": ann_vol,
            "Sharpe": sharpe,
            "Max DD": max_dd,
            "Trades": n_trades,
            "Days in Market": days_in_market,
            "Total Days": total_days,
            "Pct in Market": days_in_market / total_days,
        }

        results[pair_name] = {
            "returns": returns,
            "signals": signals,
            "zscore": zscore,
            "spread": spread,
            "metrics": metrics,
        }

        print(f"\n{'='*50}")
        print(f"  {pair_name}  (beta={beta:.4f})")
        print(f"{'='*50}")
        print(f"  Ann. Return:    {ann_ret:>8.2%}")
        print(f"  Ann. Vol:       {ann_vol:>8.2%}")
        print(f"  Sharpe:         {sharpe:>8.2f}")
        print(f"  Max Drawdown:   {max_dd:>8.2%}")
        print(f"  Trades:         {n_trades:>8d}")
        print(f"  Days in Market: {days_in_market:>8d} / {total_days} "
              f"({days_in_market/total_days:.0%})")
        print(f"{'='*50}")

    return results

if __name__ == "__main__":
    close = pd.read_csv("data/close_prices.csv", index_col=0, parse_dates=True)
    print(f"Screening pairs from {len(close.columns)} stocks...\n")

    # Find pairs using relaxed filter
    pairs = screen_pairs(close, corr_threshold=0.6, coint_pvalue=0.10)

    if len(pairs) == 0:
        print("No pairs found.")
    else:
        print(f"Found {len(pairs)} cointegrated pairs:\n")
        print(pairs.to_string(index=False))

        # Backtest on out-of-sample data
        print("\n\nBacktesting on out-of-sample period...")
        results = backtest_all_pairs(close, pairs)
