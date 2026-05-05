"""
export_all_results.py - Export all analysis results to CSV files

Generates a complete data dump of every quantitative result produced
by this project, organised into separate CSV files with a manifest
describing each one.
"""
import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, ".")

OUTPUT_DIR = "results/data_export"


def export_csv(df, filename, description):
    """Save DataFrame to CSV and print confirmation."""
    path = os.path.join(OUTPUT_DIR, filename)
    df.to_csv(path)
    print(f"  [{filename}] {description}")
    return filename, description


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    manifest = []

    close = pd.read_csv("data/close_prices.csv", index_col=0,
                        parse_dates=True)

    # ==================================================================
    # 1. Cross-sectional factor backtest results
    #    Source: python3 -m backtest.engine
    # ==================================================================
    print("\n1. Cross-sectional factor backtests (backtest/engine.py)")

    from factors.momentum import compute_momentum
    from factors.mean_reversion import compute_mean_reversion
    from factors.volatility import compute_volatility_factor
    from backtest.engine import run_backtest
    from backtest.metrics import annualised_return, annualised_vol, \
        sharpe_ratio, max_drawdown, turnover

    factor_results = []
    factor_returns = {}

    for func, name in [
        (compute_momentum, "Momentum (12-1)"),
        (compute_mean_reversion, "Mean Reversion (5d)"),
        (compute_volatility_factor, "Low Volatility (63d)"),
    ]:
        scores = func(close)
        ret, wts, _ = run_backtest(scores, close, name=name)
        factor_returns[name] = ret
        factor_results.append({
            "Strategy": name,
            "Ann_Return": annualised_return(ret),
            "Ann_Volatility": annualised_vol(ret),
            "Sharpe_Ratio": sharpe_ratio(ret),
            "Max_Drawdown": max_drawdown(ret),
            "Avg_Turnover": turnover(wts),
        })

    df = pd.DataFrame(factor_results)
    manifest.append(export_csv(
        df, "01_cross_sectional_factor_performance.csv",
        "Backtest results for 3 cross-sectional factors. "
        "Source: backtest/engine.py. Decile long-short, monthly "
        "rebalance, 10bps cost, 462 S&P 500 stocks, 2015-2024."
    ))

    # ==================================================================
    # 2. Pairs trading: cointegration screening
    #    Source: python3 factors/pairs_trading.py
    # ==================================================================
    print("\n2. Pairs trading screening (factors/pairs_trading.py)")

    from factors.pairs_trading import screen_pairs

    pairs = screen_pairs(close, corr_threshold=0.6, coint_pvalue=0.10)
    manifest.append(export_csv(
        pairs, "02_pairs_screening_results.csv",
        "Cointegrated pairs found by Engle-Granger test. "
        "Source: factors/pairs_trading.py. Filters: corr > 0.6, "
        "coint p < 0.10, half-life 2-120 days. Formation period: "
        "first 70% of data."
    ))

    # ==================================================================
    # 3. Pairs trading: out-of-sample backtest
    #    Source: python3 factors/pairs_trading.py
    # ==================================================================
    print("\n3. Pairs trading backtest (factors/pairs_trading.py)")

    from factors.pairs_trading import backtest_all_pairs

    if len(pairs) > 0:
        pt_results = backtest_all_pairs(close, pairs)
        pt_rows = []
        for pair_name, pr in pt_results.items():
            m = pr["metrics"]
            pt_rows.append({
                "Pair": pair_name,
                "Ann_Return": m["Ann. Return"],
                "Ann_Volatility": m["Ann. Vol"],
                "Sharpe": m["Sharpe"],
                "Max_Drawdown": m["Max DD"],
                "Trades": m["Trades"],
                "Days_in_Market": m["Days in Market"],
                "Total_Days": m["Total Days"],
            })
        df = pd.DataFrame(pt_rows)
        manifest.append(export_csv(
            df, "03_pairs_trading_backtest.csv",
            "Out-of-sample backtest of 4 cointegrated pairs. "
            "Source: factors/pairs_trading.py. Test period: last "
            "30% of data (~2022-2024). Z-score entry ±2, exit ±0.5."
        ))

    # ==================================================================
    # 4. Post-pairs v1: all 6 baskets
    #    Source: python3 factors/post_pairs_v1.py
    # ==================================================================
    print("\n4. Post-pairs v1 results (factors/post_pairs_v1.py)")

    from factors.post_pairs_v1 import run_post_pairs

    pp1 = run_post_pairs(close)
    pp1_rows = []
    for name, res in pp1.items():
        m = res["metrics"]
        pp1_rows.append({
            "Basket": name,
            "Stocks": ", ".join(res["basket"]),
            "Ann_Return": m["Ann. Return"],
            "Ann_Volatility": m["Ann. Vol"],
            "Sharpe": m["Sharpe"],
            "Max_Drawdown": m["Max DD"],
            "Trades": m["Trades"],
            "Days_Active": m["Days Active"],
            "Total_Days": m["Total Days"],
            "Pct_in_Market": m["Days Active"] / m["Total Days"],
        })
    df = pd.DataFrame(pp1_rows)
    manifest.append(export_csv(
        df, "04_post_pairs_v1_performance.csv",
        "Basket stat arb v1 (no filtering) results for 6 sector "
        "baskets. Source: factors/post_pairs_v1.py. Equal-weight, "
        "z-score entry ±2, exit ±0.5, 10bps cost."
    ))

    # ==================================================================
    # 5. Post-pairs v2: all 6 baskets
    #    Source: python3 factors/post_pairs_v2.py
    # ==================================================================
    print("\n5. Post-pairs v2 results (factors/post_pairs_v2.py)")

    from factors.post_pairs_v2 import run_all_baskets_v2

    pp2 = run_all_baskets_v2(close)
    pp2_rows = []
    for name, res in pp2.items():
        m = res["metrics"]
        diag = res["diagnostics"]
        avg_pass = np.mean([d["pass_rate"] for d in diag.values()])
        pp2_rows.append({
            "Basket": name,
            "Ann_Return": m["Ann. Return"],
            "Ann_Volatility": m["Ann. Vol"],
            "Sharpe": m["Sharpe"],
            "Max_Drawdown": m["Max DD"],
            "Trades": m["Trades"],
            "Days_Active": m["Days Active"],
            "Total_Days": m["Total Days"],
            "Avg_Filter_Pass_Rate": avg_pass,
        })
    df = pd.DataFrame(pp2_rows)
    manifest.append(export_csv(
        df, "05_post_pairs_v2_performance.csv",
        "Basket stat arb v2 (OU + ADF filtering) results for 6 "
        "sector baskets. Source: factors/post_pairs_v2.py. "
        "60-day rolling OU estimation, kappa > 252/30, ADF p < 0.10, "
        "s-score entry ±1.25, exit ±0.5."
    ))

    # ==================================================================
    # 6. Post-pairs v2: per-stock filter pass rates
    #    Source: python3 factors/post_pairs_v2.py
    # ==================================================================
    print("\n6. Post-pairs v2 filter diagnostics (factors/post_pairs_v2.py)")

    filter_rows = []
    for basket_name, res in pp2.items():
        for stock, diag in res["diagnostics"].items():
            filter_rows.append({
                "Basket": basket_name,
                "Stock": stock,
                "Pass_Rate": diag["pass_rate"],
                "Passed_Days": diag["passed_days"],
                "Total_Days": diag["total_days"],
            })
    df = pd.DataFrame(filter_rows)
    manifest.append(export_csv(
        df, "06_post_pairs_v2_filter_diagnostics.csv",
        "Per-stock filter pass rates for v2. Shows how often each "
        "stock's residual passed the OU kappa and ADF stationarity "
        "filters. Source: factors/post_pairs_v2.py."
    ))

    # ==================================================================
    # 7. v1 vs v2 comparison (Consumer Staples)
    # ==================================================================
    print("\n7. v1 vs v2 comparison")

    if "Consumer_Staples" in pp1 and "Consumer_Staples" in pp2:
        m1 = pp1["Consumer_Staples"]["metrics"]
        m2 = pp2["Consumer_Staples"]["metrics"]
        comp = pd.DataFrame([
            {"Version": "v1 (no filter)", "Ann_Return": m1["Ann. Return"],
             "Ann_Vol": m1["Ann. Vol"], "Sharpe": m1["Sharpe"],
             "Max_DD": m1["Max DD"], "Days_Active": m1["Days Active"],
             "Total_Days": m1["Total Days"]},
            {"Version": "v2 (OU filter)", "Ann_Return": m2["Ann. Return"],
             "Ann_Vol": m2["Ann. Vol"], "Sharpe": m2["Sharpe"],
             "Max_DD": m2["Max DD"], "Days_Active": m2["Days Active"],
             "Total_Days": m2["Total Days"]},
        ])
        manifest.append(export_csv(
            comp, "07_v1_vs_v2_consumer_staples.csv",
            "Side-by-side performance comparison of Consumer Staples "
            "basket strategy with and without OU filtering."
        ))

    # ==================================================================
    # 8. FF6 factor attribution: all strategies
    #    Source: python3 -m analysis.ff_attribution
    # ==================================================================
    print("\n8. FF6 factor attribution (analysis/ff_attribution.py)")

    from analysis.ff_attribution import download_ff_factors, \
        compute_monthly_returns, run_ff_regression

    ff = download_ff_factors()

    ff_rows = []
    strategies = {}

    # Cross-sectional factors
    for name, ret in factor_returns.items():
        monthly = compute_monthly_returns(ret)
        _, summary = run_ff_regression(monthly, ff)
        summary["Strategy"] = name
        ff_rows.append(summary)

    # Post-pairs v1 Consumer Staples
    if "Consumer_Staples" in pp1:
        ret = pp1["Consumer_Staples"]["returns"]
        monthly = compute_monthly_returns(ret)
        _, summary = run_ff_regression(monthly, ff)
        summary["Strategy"] = "Post-Pairs v1: Staples"
        ff_rows.append(summary)

    # Post-pairs v2 Consumer Staples
    if "Consumer_Staples" in pp2:
        ret = pp2["Consumer_Staples"]["returns"]
        monthly = compute_monthly_returns(ret)
        _, summary = run_ff_regression(monthly, ff)
        summary["Strategy"] = "Post-Pairs v2: Staples"
        ff_rows.append(summary)

    df = pd.DataFrame(ff_rows)
    cols = ["Strategy", "alpha_monthly", "alpha_annualised", "alpha_pvalue",
            "beta_mkt_rf", "pvalue_mkt_rf", "beta_smb", "pvalue_smb",
            "beta_hml", "pvalue_hml", "beta_rmw", "pvalue_rmw",
            "beta_cma", "pvalue_cma", "beta_mom", "pvalue_mom",
            "r_squared", "adj_r_squared"]
    df = df[[c for c in cols if c in df.columns]]
    manifest.append(export_csv(
        df, "08_ff6_factor_attribution.csv",
        "Fama-French 5-factor + Momentum (6-factor) regression "
        "results for all strategies. Source: analysis/ff_attribution.py. "
        "Monthly returns regressed on Mkt-RF, SMB, HML, RMW, CMA, Mom. "
        "Alpha in percentage points."
    ))

    # ==================================================================
    # 9. Manifest
    # ==================================================================
    print("\n9. Writing manifest")

    manifest_df = pd.DataFrame(manifest, columns=["Filename", "Description"])
    manifest_path = os.path.join(OUTPUT_DIR, "00_MANIFEST.csv")
    manifest_df.to_csv(manifest_path, index=False)
    print(f"  [00_MANIFEST.csv] Index of all exported files\n")

    print(f"All files saved to {OUTPUT_DIR}/")
    print(f"Total: {len(manifest) + 1} CSV files")


if __name__ == "__main__":
    main()
