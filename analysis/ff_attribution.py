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


def download_ff3_monthly(start="2015-01-01", end="2024-12-31"):
    """
    Download Fama-French 3 factors (monthly) from Kenneth French's
    data library via pandas_datareader.

    Returns DataFrame with columns: [Mkt-RF, SMB, HML, RF]
    Values are in percentage points (e.g. 1.5 means 1.5%).
    """
    ff = web.DataReader("F-F_Research_Data_Factors", "famafrench",
                        start, end)
    df = ff[0]  # monthly data
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


def run_ff3_regression(monthly_returns_pct, ff_factors):
    """
    Run Fama-French 3-factor regression.

    Parameters:
        monthly_returns_pct: Series of monthly returns in pct points
        ff_factors: DataFrame with [Mkt-RF, SMB, HML, RF] in pct points

    Returns:
        model: fitted OLS model
        summary_dict: dict with key metrics
    """
    # Align dates
    common = monthly_returns_pct.index.intersection(ff_factors.index)
    ret = monthly_returns_pct.loc[common]
    ff = ff_factors.loc[common]

    # Excess return = strategy return - risk-free rate
    excess_return = ret - ff["RF"]

    # Independent variables
    X = sm.add_constant(ff[["Mkt-RF", "SMB", "HML"]])
    y = excess_return

    model = sm.OLS(y, X).fit()

    summary_dict = {
        "alpha_monthly": model.params["const"],
        "alpha_annualised": model.params["const"] * 12,
        "alpha_pvalue": model.pvalues["const"],
        "beta_mkt": model.params["Mkt-RF"],
        "beta_smb": model.params["SMB"],
        "beta_hml": model.params["HML"],
        "pvalue_mkt": model.pvalues["Mkt-RF"],
        "pvalue_smb": model.pvalues["SMB"],
        "pvalue_hml": model.pvalues["HML"],
        "r_squared": model.rsquared,
        "adj_r_squared": model.rsquared_adj,
    }

    return model, summary_dict


def print_attribution(name, summary):
    """Pretty-print factor attribution results."""
    print(f"\n{'='*60}")
    print(f"  Fama-French 3-Factor Attribution: {name}")
    print(f"{'='*60}")
    print(f"  Alpha (monthly):     {summary['alpha_monthly']:>8.3f}%"
          f"   (p={summary['alpha_pvalue']:.3f})")
    print(f"  Alpha (annualised):  {summary['alpha_annualised']:>8.2f}%")
    print(f"  ---")
    print(f"  Mkt-RF loading:      {summary['beta_mkt']:>8.3f}"
          f"   (p={summary['pvalue_mkt']:.3f})")
    print(f"  SMB loading:         {summary['beta_smb']:>8.3f}"
          f"   (p={summary['pvalue_smb']:.3f})")
    print(f"  HML loading:         {summary['beta_hml']:>8.3f}"
          f"   (p={summary['pvalue_hml']:.3f})")
    print(f"  ---")
    print(f"  R-squared:           {summary['r_squared']:>8.3f}")
    print(f"  Adj R-squared:       {summary['adj_r_squared']:>8.3f}")
    print(f"{'='*60}")

    # Interpretation
    sig = lambda p: "significant" if p < 0.05 else "not significant"
    print(f"\n  Interpretation:")
    print(f"  - Market beta {summary['beta_mkt']:.2f}: "
          f"{'more' if summary['beta_mkt'] > 1 else 'less'} volatile "
          f"than the market ({sig(summary['pvalue_mkt'])})")

    smb_dir = "small-cap" if summary['beta_smb'] > 0 else "large-cap"
    print(f"  - SMB {summary['beta_smb']:.2f}: tilts toward "
          f"{smb_dir} ({sig(summary['pvalue_smb'])})")

    hml_dir = "value" if summary['beta_hml'] > 0 else "growth"
    print(f"  - HML {summary['beta_hml']:.2f}: tilts toward "
          f"{hml_dir} ({sig(summary['pvalue_hml'])})")

    if summary['alpha_pvalue'] < 0.05:
        print(f"  - Alpha is statistically significant: "
              f"{summary['alpha_annualised']:.1f}% annualised "
              f"return not explained by FF3 factors")
    else:
        print(f"  - Alpha is NOT significant: returns are fully "
              f"explained by factor exposures")


def plot_factor_loadings(results_dict, save_path=None):
    """
    Bar chart comparing factor loadings across multiple strategies.
    """
    names = list(results_dict.keys())
    factors = ["beta_mkt", "beta_smb", "beta_hml"]
    labels = ["Mkt-RF", "SMB", "HML"]

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    fig.suptitle("Fama-French 3-Factor Loadings", fontsize=14,
                 fontweight="bold")

    for i, (factor, label) in enumerate(zip(factors, labels)):
        ax = axes[i]
        values = [results_dict[n][factor] for n in names]
        pvalues = [results_dict[n][f"pvalue_{label.lower().replace('-', '_')}"]
                   if f"pvalue_{label.lower().replace('-', '_')}" in results_dict[n]
                   else results_dict[n].get(f"pvalue_{'mkt' if 'Mkt' in label else label.lower()}", 1)
                   for n in names]

        colors = ["steelblue" if p < 0.05 else "lightgray" for p in pvalues]
        ax.bar(names, values, color=colors)
        ax.axhline(0, color="black", linewidth=0.5)
        ax.set_title(label)
        ax.set_ylabel("Loading" if i == 0 else "")
        ax.tick_params(axis="x", rotation=45)

    plt.tight_layout()
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  Saved: {save_path}")
    plt.close()


if __name__ == "__main__":
    print("Downloading FF3 factors...")
    ff = download_ff3_monthly()
    print(f"FF3 data: {ff.index[0]} to {ff.index[-1]}\n")

    # Load price data
    close = pd.read_csv("data/close_prices.csv", index_col=0,
                        parse_dates=True)

    # --- Analyse cross-sectional factor strategies ---
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
        model, summary = run_ff3_regression(monthly_ret, ff)
        print_attribution(name, summary)
        all_results[name] = summary

    # --- Analyse post-pairs v1 (Consumer Staples only) ---
    from factors.post_pairs_v1 import run_post_pairs
    pp_results = run_post_pairs(close)

    if "Consumer_Staples" in pp_results:
        daily_ret = pp_results["Consumer_Staples"]["returns"]
        monthly_ret = compute_monthly_returns(daily_ret)
        model, summary = run_ff3_regression(monthly_ret, ff)
        print_attribution("Post-Pairs v1: Staples", summary)
        all_results["Post-Pairs v1: Staples"] = summary

    # Plot comparison
    plot_factor_loadings(
        all_results,
        save_path="results/cross_sectional_factors/plots/ff3_loadings.png"
    )
    print("\nDone.")
