"""
ff_attribution.py - Fama-French Factor Attribution

Run FF3 regression on any return series to decompose performance
into market, size, and value exposures.

Conceptual summary:
    R(t) - Rf(t) = alpha + b1*(Mkt-Rf) + b2*SMB + b3*HML + epsilon

    - alpha: return not explained by the three factors (skill or luck)
    - b1 (Mkt-RF loading): sensitivity to overall market
    - b2 (SMB loading): tilt toward small-cap (+) or large-cap (-)
    - b3 (HML loading): tilt toward value (+) or growth (-)

    High R-squared means the factors explain most of the return.
    Significant alpha means there is return beyond factor exposures.

Reference:
    Fama & French (1993) "Common Risk Factors in the Returns on
    Stocks and Bonds" — Journal of Financial Economics
"""
import pandas as pd
import numpy as np
import statsmodels.api as sm
import pandas_datareader.data as web
import matplotlib.pyplot as plt
import os

def download_ff_factors(start="2015-01-01", end="2024-12-31"):
    """
    Download Fama-French 5 factors + Momentum (UMD) monthly data.

    FF5 factors: Mkt-RF, SMB, HML, RMW (profitability), CMA (investment), RF
    Momentum: Mom (UMD = Up Minus Down)

    Returns DataFrame with columns:
        [Mkt-RF, SMB, HML, RMW, CMA, RF, Mom]
    Values in percentage points.
    """
    ff5 = web.DataReader("F-F_Research_Data_5_Factors_2x3",
                         "famafrench", start, end)
    mom = web.DataReader("F-F_Momentum_Factor", "famafrench",
                         start, end)

    df = ff5[0].join(mom[0], how="inner")
    return df


def compute_monthly_returns(daily_returns):
    """
    Convert a daily return series to monthly returns.
    Input: Series of daily returns (decimal, e.g. 0.01 = 1%)
    Output: Series of monthly returns in percentage points
    """
    monthly = (1 + daily_returns).resample("ME").prod() - 1
    monthly = monthly * 100  # convert to percentage points to match FF data
    monthly.index = monthly.index.to_period("M")
    return monthly


def run_ff_regression(monthly_returns_pct, ff_factors):
    """
    Run Fama-French 5-factor + Momentum (6-factor) regression.

    R(t) - Rf = alpha + b1*MktRF + b2*SMB + b3*HML
                      + b4*RMW  + b5*CMA + b6*Mom + eps

    New factors vs FF3:
        RMW (Robust Minus Weak): profitable firms outperform weak ones
        CMA (Conservative Minus Aggressive): conservative investors
             outperform aggressive ones
        Mom (Momentum / UMD): past winners outperform past losers
    """
    common = monthly_returns_pct.index.intersection(ff_factors.index)
    ret = monthly_returns_pct.loc[common]
    ff = ff_factors.loc[common]

    excess_return = ret - ff["RF"]

    factor_cols = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"]
    X = sm.add_constant(ff[factor_cols])
    y = excess_return

    model = sm.OLS(y, X).fit()

    summary_dict = {
        "alpha_monthly": model.params["const"],
        "alpha_annualised": model.params["const"] * 12,
        "alpha_pvalue": model.pvalues["const"],
        "r_squared": model.rsquared,
        "adj_r_squared": model.rsquared_adj,
    }
    for col in factor_cols:
        key = col.lower().replace("-", "_")
        summary_dict[f"beta_{key}"] = model.params[col]
        summary_dict[f"pvalue_{key}"] = model.pvalues[col]

    return model, summary_dict

def print_attribution(name, summary):
    """Pretty-print 6-factor attribution results."""
    print(f"\n{'='*60}")
    print(f"  FF5 + Momentum Attribution: {name}")
    print(f"{'='*60}")
    print(f"  Alpha (monthly):     {summary['alpha_monthly']:>8.3f}%"
          f"   (p={summary['alpha_pvalue']:.3f})")
    print(f"  Alpha (annualised):  {summary['alpha_annualised']:>8.2f}%")
    print(f"  ---")

    factors = [
        ("mkt_rf",  "Mkt-RF",  "market"),
        ("smb",     "SMB",     "small-cap (+) / large-cap (-)"),
        ("hml",     "HML",     "value (+) / growth (-)"),
        ("rmw",     "RMW",     "profitable (+) / weak (-)"),
        ("cma",     "CMA",     "conservative (+) / aggressive (-)"),
        ("mom",     "Mom",     "winners (+) / losers (-)"),
    ]

    for key, label, desc in factors:
        beta = summary[f"beta_{key}"]
        pval = summary[f"pvalue_{key}"]
        sig = "*" if pval < 0.05 else " "
        print(f"  {label:6s} loading:      {beta:>8.3f}"
              f"   (p={pval:.3f}) {sig}")

    print(f"  ---")
    print(f"  R-squared:           {summary['r_squared']:>8.3f}")
    print(f"  Adj R-squared:       {summary['adj_r_squared']:>8.3f}")
    print(f"{'='*60}")

def plot_factor_loadings(results_dict, save_path=None):
    """Bar chart comparing 6-factor loadings across strategies."""
    names = list(results_dict.keys())
    factors = [
        ("beta_mkt_rf", "pvalue_mkt_rf", "Mkt-RF"),
        ("beta_smb", "pvalue_smb", "SMB"),
        ("beta_hml", "pvalue_hml", "HML"),
        ("beta_rmw", "pvalue_rmw", "RMW"),
        ("beta_cma", "pvalue_cma", "CMA"),
        ("beta_mom", "pvalue_mom", "Mom"),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(16, 8))
    fig.suptitle("FF5 + Momentum Factor Loadings",
                 fontsize=14, fontweight="bold")

    for i, (beta_key, pval_key, label) in enumerate(factors):
        ax = axes[i // 3][i % 3]
        values = [results_dict[n].get(beta_key, 0) for n in names]
        pvalues = [results_dict[n].get(pval_key, 1) for n in names]
        colors = ["steelblue" if p < 0.05 else "lightgray"
                  for p in pvalues]
        ax.bar(names, values, color=colors)
        ax.axhline(0, color="black", linewidth=0.5)
        ax.set_title(label)
        ax.tick_params(axis="x", rotation=45, labelsize=7)

    plt.tight_layout()
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  Saved: {save_path}")
    plt.close()

if __name__ == "__main__":
    print("Downloading FF5 + Momentum factors...")
    ff = download_ff_factors()
    print(f"Factor data: {ff.index[0]} to {ff.index[-1]}")
    print(f"Columns: {list(ff.columns)}\n")

    close = pd.read_csv("data/close_prices.csv", index_col=0,
                        parse_dates=True)

    import sys
    sys.path.insert(0, ".")
    from factors.momentum import compute_momentum
    from factors.mean_reversion import compute_mean_reversion
    from factors.volatility import compute_volatility_factor
    from backtest.engine import run_backtest

    all_results = {}

    for factor_func, name in [
        (compute_momentum, "Momentum (12-1)"),
        (compute_mean_reversion, "Mean Reversion (5d)"),
        (compute_volatility_factor, "Low Volatility (63d)"),
    ]:
        scores = factor_func(close)
        daily_ret, _, _ = run_backtest(scores, close, name=name)
        monthly_ret = compute_monthly_returns(daily_ret)
        model, summary = run_ff_regression(monthly_ret, ff)
        print_attribution(name, summary)
        all_results[name] = summary

    from factors.post_pairs_v1 import run_post_pairs
    pp_results = run_post_pairs(close)

    if "Consumer_Staples" in pp_results:
        daily_ret = pp_results["Consumer_Staples"]["returns"]
        monthly_ret = compute_monthly_returns(daily_ret)
        model, summary = run_ff_regression(monthly_ret, ff)
        print_attribution("Post-Pairs v1: Staples", summary)
        all_results["Post-Pairs v1: Staples"] = summary

    # --- Post-Pairs v2 ---
    from factors.post_pairs_v2 import run_all_baskets_v2
    pp2_results = run_all_baskets_v2(close)

    if "Consumer_Staples" in pp2_results:
        daily_ret = pp2_results["Consumer_Staples"]["returns"]
        monthly_ret = compute_monthly_returns(daily_ret)
        model, summary = run_ff_regression(monthly_ret, ff)
        print_attribution("Post-Pairs v2: Staples", summary)
        all_results["Post-Pairs v2: Staples"] = summary


    # Chart 1: Cross-sectional factors + Post-Pairs v1
    chart1 = {k: v for k, v in all_results.items()
              if "v2" not in k}
    plot_factor_loadings(
        chart1,
        save_path="results/cross_sectional_factors/plots/ff6_factors_and_v1.png"
    )

    # Chart 2: Post-Pairs v1 vs v2 comparison
    chart2 = {k: v for k, v in all_results.items()
              if "Post-Pairs" in k}
    if len(chart2) > 1:
        plot_factor_loadings(
            chart2,
            save_path="results/post_pairs/plots/ff6_v1_vs_v2.png"
        )

    print("\nDone.")
