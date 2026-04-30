"""
engine.py - Backtest engine

Takes factor scores and price data, constructs monthly-rebalanced
long-short portfolios, and computes net-of-cost returns.
"""
import pandas as pd
from backtest.portfolio import construct_long_short_portfolio
from backtest.metrics import performance_summary


def run_backtest(factor_scores, close, rebalance_freq="ME",
                 n_quantiles=10, cost_bps=10, name="Strategy"):
    """
    Run a full backtest for a single factor.

    Parameters:
        factor_scores: DataFrame (dates x tickers), the raw factor values
        close: DataFrame (dates x tickers), daily close prices
        rebalance_freq: how often to rebalance ("ME" = month-end)
        n_quantiles: number of groups for long-short split
        cost_bps: one-way transaction cost in basis points
        name: label for printing results

    Returns:
        net_returns: Series of daily portfolio returns (after costs)
        weights: DataFrame of daily portfolio weights
        metrics: dict of performance metrics
    """
    daily_returns = close.pct_change()

    common_dates = factor_scores.index.intersection(daily_returns.index)
    common_tickers = factor_scores.columns.intersection(daily_returns.columns)
    factor_scores = factor_scores.loc[common_dates, common_tickers]
    daily_returns = daily_returns.loc[common_dates, common_tickers]

    rebalance_dates = factor_scores.resample(rebalance_freq).last().index
    rebalance_scores = factor_scores.loc[
        factor_scores.index.isin(rebalance_dates)
    ]
    target_weights = construct_long_short_portfolio(
        rebalance_scores, n_quantiles
    )

    weights = target_weights.reindex(factor_scores.index).ffill().fillna(0)

    gross_returns = (weights.shift(1) * daily_returns).sum(axis=1)

    weight_changes = weights.diff().abs().sum(axis=1)
    costs = weight_changes * cost_bps / 10000
    net_returns = gross_returns - costs

    net_returns = net_returns.dropna()

    metrics = performance_summary(net_returns, weights, name=name)
    return net_returns, weights, metrics


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")

    close = pd.read_csv("data/close_prices.csv", index_col=0, parse_dates=True)

    from factors.momentum import compute_momentum
    from factors.mean_reversion import compute_mean_reversion
    from factors.volatility import compute_volatility_factor

    mom = compute_momentum(close)
    run_backtest(mom, close, name="Momentum (12-1)")

    mr = compute_mean_reversion(close)
    run_backtest(mr, close, name="Mean Reversion (5d)")

    vol = compute_volatility_factor(close)
    run_backtest(vol, close, name="Low Volatility (63d)")
