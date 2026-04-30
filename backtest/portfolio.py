"""
portfolio.py - Construct long-short portfolios from factor scores

At each rebalance date, rank all stocks by factor score, go long the
top decile and short the bottom decile, equal-weighted within each leg.
"""
import pandas as pd
import numpy as np


def construct_long_short_portfolio(factor_scores, n_quantiles=10):
    """
    Build long-short portfolio weights from cross-sectional factor scores.

    At each date, split stocks into n_quantiles groups by factor score.
    Long the top group, short the bottom group, equal-weighted.

    Parameters:
        factor_scores: DataFrame (dates x tickers)
        n_quantiles: number of groups (default 10 = deciles)

    Returns:
        weights: DataFrame (dates x tickers), values are portfolio weights
                 (+1/n_long for top group, -1/n_short for bottom group, 0 otherwise)
    """
    weights = pd.DataFrame(0.0, index=factor_scores.index,
                           columns=factor_scores.columns)

    for date in factor_scores.index:
        scores = factor_scores.loc[date].dropna()
        if len(scores) < n_quantiles:
            continue

        quantile_labels = pd.qcut(scores.rank(method="first"), n_quantiles,
                                  labels=False, duplicates="drop")

        top = quantile_labels[quantile_labels == quantile_labels.max()].index
        bottom = quantile_labels[quantile_labels == 0].index

        weights.loc[date, top] = 1.0 / len(top)
        weights.loc[date, bottom] = -1.0 / len(bottom)

    return weights
