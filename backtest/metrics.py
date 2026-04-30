"""
metrics.py - Performance metrics for backtesting

Includes annualised return, Sharpe ratio, max drawdown, and turnover.
"""
import numpy as np
import pandas as pd


def annualised_return(returns, trading_days=252):
    """Annualised return from a series of daily returns."""
    total = (1 + returns).prod()
    n_years = len(returns) / trading_days
    if n_years <= 0:
        return 0.0
    return total ** (1 / n_years) - 1


def annualised_vol(returns, trading_days=252):
    """Annualised volatility."""
    return returns.std() * np.sqrt(trading_days)


def sharpe_ratio(returns, trading_days=252):
    """Annualised Sharpe ratio (assuming zero risk-free rate)."""
    vol = annualised_vol(returns, trading_days)
    if vol == 0:
        return 0.0
    return annualised_return(returns, trading_days) / vol


def max_drawdown(returns):
    """Maximum drawdown from peak to trough."""
    cum = (1 + returns).cumprod()
    peak = cum.cummax()
    drawdown = (cum - peak) / peak
    return drawdown.min()


def turnover(weights):
    """Average daily turnover: mean of absolute weight changes."""
    return weights.diff().abs().sum(axis=1).mean()


def performance_summary(returns, weights, name="Strategy"):
    """Print a one-line performance summary. Returns dict of metrics."""
    metrics = {
        "Ann. Return": annualised_return(returns),
        "Ann. Vol": annualised_vol(returns),
        "Sharpe": sharpe_ratio(returns),
        "Max DD": max_drawdown(returns),
        "Turnover": turnover(weights),
    }

    print(f"\n{'='*55}")
    print(f"  {name}")
    print(f"{'='*55}")
    print(f"  Ann. Return:   {metrics['Ann. Return']:>8.2%}")
    print(f"  Ann. Vol:      {metrics['Ann. Vol']:>8.2%}")
    print(f"  Sharpe Ratio:  {metrics['Sharpe']:>8.2f}")
    print(f"  Max Drawdown:  {metrics['Max DD']:>8.2%}")
    print(f"  Avg Turnover:  {metrics['Turnover']:>8.4f}")
    print(f"{'='*55}")

    return metrics
