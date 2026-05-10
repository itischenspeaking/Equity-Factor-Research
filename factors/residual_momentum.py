"""
residual_momentum.py — Residual Momentum factor

Replicates core methodology from Blitz, Huij & Martens (2011):
  1. Aggregate daily prices to monthly returns
  2. Run rolling 36-month FF3 regressions per stock
  3. Compute 12-1M residual momentum signal (standardized)
  4. Compare to 12-1M total return momentum

Usage:
    python3 -m factors.residual_momentum
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from pathlib import Path


# ── 1. DATA PREPARATION ─────────────────────────────────────────────

def load_monthly_returns(csv_path="data/close_prices.csv"):
    """Load daily close prices → monthly returns."""
    daily = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    monthly_price = daily.resample("ME").last()
    monthly_ret = monthly_price.pct_change().dropna(how="all")
    monthly_ret.index = monthly_ret.index + pd.offsets.MonthEnd(0)
    return monthly_ret


def load_ff3_monthly():
    """
    Load Fama-French 3-factor monthly data from French's data library.
    Returns DataFrame with columns: Mkt-RF, SMB, HML, RF
    Values are in decimal (not percentage).
    """
    try:
        import pandas_datareader.data as web
        ff = web.DataReader(
            "F-F_Research_Data_Factors", "famafrench", start="2010-01-01"
        )[0]
    except Exception as e:
        print(f"pandas_datareader failed: {e}")
        print("Falling back to direct CSV download...")
        ff = _download_ff3_csv()

    ff = ff / 100.0

    if isinstance(ff.index, pd.PeriodIndex):
        ff.index = ff.index.to_timestamp(how="end")

    ff.index = ff.index.normalize()
    ff.index = ff.index + pd.offsets.MonthEnd(0)
    ff.index.name = "date"

    return ff


def _download_ff3_csv():
    """Fallback: download FF3 CSV directly from French's website."""
    import io, zipfile, urllib.request

    url = ("https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/"
           "ftp/F-F_Research_Data_Factors_CSV.zip")
    response = urllib.request.urlopen(url)
    z = zipfile.ZipFile(io.BytesIO(response.read()))
    csv_name = [n for n in z.namelist() if n.endswith(".CSV")][0]
    raw = z.read(csv_name).decode("utf-8")

    df = pd.read_csv(
        io.StringIO(raw), skiprows=3, nrows=2000,
        header=0, index_col=0,
    )
    df.index.name = "date"
    df = df[df.index.notna()]
    df = df[df.index.astype(str).str.match(r"^\d{6}$")]
    df.index = pd.to_datetime(df.index.astype(str), format="%Y%m")
    df.index = df.index + pd.offsets.MonthEnd(0)
    df.columns = [c.strip() for c in df.columns]
    return df


def prepare_data(csv_path="data/close_prices.csv"):
    """Master data preparation function."""
    monthly_ret = load_monthly_returns(csv_path)
    ff3 = load_ff3_monthly()

    common_dates = monthly_ret.index.intersection(ff3.index)
    monthly_ret = monthly_ret.loc[common_dates]
    ff3 = ff3.loc[common_dates]

    excess_ret = monthly_ret.sub(ff3["RF"], axis=0)

    print(f"Monthly returns: {monthly_ret.shape[0]} months, "
          f"{monthly_ret.shape[1]} stocks")
    if len(common_dates) > 0:
        print(f"Date range: {common_dates[0].strftime('%Y-%m')} to "
              f"{common_dates[-1].strftime('%Y-%m')}")
    print(f"FF3 factors loaded: {ff3.columns.tolist()}")

    # Exclude stock-months with returns beyond ±300%.
    # CRSP handles corporate actions (ticker changes, bankruptcy
    # re-emergences, reverse splits) correctly; yfinance does not.
    # This filter removes data errors, not genuine returns.
    n_before = monthly_ret.notna().sum().sum()
    monthly_ret = monthly_ret.where(monthly_ret.abs() <= 3.0)
    excess_ret = excess_ret.where(monthly_ret.notna())
    n_after = monthly_ret.notna().sum().sum()
    print(f"Data quality filter (|ret| > 300%): "
          f"removed {n_before - n_after} stock-months")

    return excess_ret, ff3, monthly_ret


# ── 2. ROLLING REGRESSION & SIGNAL CONSTRUCTION ─────────────────────

def compute_residual_momentum_signals(excess_ret, ff3, window=36,
                                      lookback=12, skip=1):
    """
    Combined rolling regression + signal construction (vectorized).

    Each signal month t uses residuals from its OWN regression window
    [t-36, t-1]. Signal = sum(formation residuals) / std(formation
    residuals), where formation = [t-12, t-2].
    """
    factors = ff3[["Mkt-RF", "SMB", "HML"]].values
    n_months, n_stocks = excess_ret.shape
    dates = excess_ret.index
    tickers = excess_ret.columns

    ones = np.ones((n_months, 1))
    X_full = np.hstack([ones, factors])
    Y = excess_ret.values

    signal = np.full((n_months, n_stocks), np.nan)

    form_start = window - lookback   # 24
    form_end = window - skip         # 35 (exclusive -> indices 24..34)

    print(f"\nComputing residual momentum signals (vectorized)...")
    print(f"  Regression window: {window} months")
    print(f"  Formation period: months t-{lookback} to t-{skip+1} "
          f"({lookback - skip} months)")

    for t in range(window, n_months):
        X_w = X_full[t - window:t]
        Y_w = Y[t - window:t]

        valid = ~np.isnan(Y_w).any(axis=0)
        if valid.sum() == 0:
            continue

        try:
            beta, _, _, _ = np.linalg.lstsq(X_w, Y_w[:, valid], rcond=None)
            eps_all = Y_w[:, valid] - X_w @ beta
        except np.linalg.LinAlgError:
            continue

        eps_form = eps_all[form_start:form_end]
        eps_sum = eps_form.sum(axis=0)
        eps_std = eps_form.std(axis=0, ddof=1)
        eps_std[eps_std == 0] = np.nan

        signal[t, valid] = eps_sum / eps_std

        if (t - window) % 12 == 0:
            pct = (t - window) / (n_months - window) * 100
            print(f"  Progress: {pct:.0f}% "
                  f"({dates[t].strftime('%Y-%m')})")

    signal_df = pd.DataFrame(signal, index=dates, columns=tickers)
    n_valid = np.isfinite(signal).sum()
    print(f"  Done. {n_valid} valid signal-month observations")
    return signal_df


def compute_total_return_momentum(monthly_ret, skip=1, lookback=12):
    """
    12-1M Total Return Momentum signal (monthly frequency).
    Uses COMPOUNDED cumulative return over formation period.
    """
    signal = pd.DataFrame(
        np.nan, index=monthly_ret.index, columns=monthly_ret.columns
    )

    for t in range(lookback, len(monthly_ret)):
        ret_window = monthly_ret.iloc[t - lookback:t - skip]
        valid = ret_window.notna().sum() >= 8

        # Compounded cumulative return (not simple sum)
        cumulative = (1 + ret_window).prod() - 1
        signal.iloc[t] = cumulative.where(valid)

    n_valid = signal.notna().sum().sum()
    print(f"Total return momentum signals: {n_valid} stock-months")
    return signal


# ── 3. DECILE PORTFOLIO CONSTRUCTION ────────────────────────────────

def form_decile_assignments(signal, n_quantiles=10):
    """
    For each month, assign stocks to deciles based on signal.
    Returns dict: {month_index: pd.Series of decile labels 1..10}
    """
    assignments = {}

    for i in range(len(signal)):
        sig = signal.iloc[i].dropna()
        if len(sig) < n_quantiles * 5:
            continue
        try:
            ranks = pd.qcut(sig, n_quantiles, labels=False,
                            duplicates="drop") + 1
        except ValueError:
            continue
        if ranks.nunique() < n_quantiles:
            continue
        assignments[i] = ranks

    return assignments


def build_decile_portfolios(signal, monthly_ret, n_quantiles=10, K=1):
    """
    Overlapping portfolio approach (Jegadeesh & Titman 1993).

    For K=1: standard monthly rebalancing.
    For K>1: at each month t, hold K sub-portfolios formed at
    t, t-1, ..., t-K+1. Strategy return = equal-weighted average
    across all K sub-portfolios.
    """
    dates = signal.index
    assignments = form_decile_assignments(signal, n_quantiles)

    decile_returns = pd.DataFrame(
        np.nan, index=dates, columns=range(1, n_quantiles + 1))

    for t in range(len(dates)):
        fwd = monthly_ret.iloc[t]
        if fwd.isna().all():
            continue

        sub_returns = {q: [] for q in range(1, n_quantiles + 1)}

        for k in range(K):
            form_idx = t - k
            if form_idx not in assignments:
                continue

            for q in range(1, n_quantiles + 1):
                stocks_in_q = assignments[form_idx][
                    assignments[form_idx] == q].index
                valid = stocks_in_q.intersection(fwd.dropna().index)
                if len(valid) > 0:
                    sub_returns[q].append(fwd[valid].mean())

        for q in range(1, n_quantiles + 1):
            if sub_returns[q]:
                decile_returns.loc[dates[t], q] = np.mean(sub_returns[q])

    decile_returns = decile_returns.dropna(how="all")
    hedge_returns = decile_returns[n_quantiles] - decile_returns[1]
    hedge_returns.name = "D10-D1"

    return decile_returns, hedge_returns


# ── 4. PERFORMANCE METRICS ──────────────────────────────────────────

def compute_strategy_stats(returns, name="Strategy", annualize=12):
    """Compute standard performance statistics for a return series."""
    r = returns.dropna()
    n = len(r)
    if n < 12:
        print(f"  {name}: insufficient data ({n} months)")
        return {}

    ann_ret = r.mean() * annualize
    ann_vol = r.std() * np.sqrt(annualize)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0

    cumulative = (1 + r).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    max_dd = drawdown.min()

    pct_pos = (r > 0).mean()

    return {
        "Ann. Return": ann_ret,
        "Ann. Volatility": ann_vol,
        "Sharpe Ratio": sharpe,
        "Max Drawdown": max_dd,
        "% Months > 0": pct_pos,
        "N months": n,
    }


def print_comparison(stats_total, stats_resid, label=""):
    """Print side-by-side comparison table."""
    header = f"  TOTAL RETURN vs RESIDUAL MOMENTUM{label}"
    print("\n" + "=" * 65)
    print(header)
    print("=" * 65)
    print(f"  {'Metric':<22s} {'Total Return':>18s} {'Residual':>18s}")
    print("-" * 65)

    for key in stats_total:
        v1 = stats_total[key]
        v2 = stats_resid[key]
        if key == "N months":
            print(f"  {key:<22s} {v1:>18.0f} {v2:>18.0f}")
        elif key == "% Months > 0":
            print(f"  {key:<22s} {v1:>17.1%} {v2:>17.1%}")
        elif key == "Sharpe Ratio":
            print(f"  {key:<22s} {v1:>18.2f} {v2:>18.2f}")
        else:
            print(f"  {key:<22s} {v1:>17.2%} {v2:>17.2%}")

    print("=" * 65)

    if (stats_total.get("Sharpe Ratio", 0) != 0 and
            stats_resid.get("Sharpe Ratio", 0) != 0):
        ratio = stats_resid["Sharpe Ratio"] / stats_total["Sharpe Ratio"]
        print(f"\n  Sharpe ratio (residual / total): {ratio:.2f}x")
        print(f"  Vol ratio (residual / total):    "
              f"{stats_resid['Ann. Volatility'] / stats_total['Ann. Volatility']:.2f}x")


# ── 5. CONDITIONAL FF REGRESSION (Paper Equation 2) ─────────────────

def conditional_ff_regression(hedge_returns, ff3, monthly_ret,
                              lookback=12, skip=1):
    """Conditional Fama-French regression from Grundy & Martin (2001)."""
    ff_aligned = ff3.loc[hedge_returns.index]
    factors = ff_aligned[["Mkt-RF", "SMB", "HML"]].copy()

    for col in ["Mkt-RF", "SMB", "HML"]:
        rolling_sum = ff3[col].rolling(lookback - skip).sum()
        trend = (rolling_sum.shift(skip + 1) > 0).astype(float)
        trend = trend.loc[hedge_returns.index]
        up_col = col.replace("-", "") + "_UP"
        factors[up_col] = factors[col] * trend

    y = hedge_returns.dropna()
    X = factors.loc[y.index]
    X = sm.add_constant(X)

    valid = y.notna() & X.notna().all(axis=1)
    y = y[valid]
    X = X[valid]

    if len(y) < 20:
        print("  Insufficient data for conditional regression")
        return None

    return sm.OLS(y, X).fit()


def print_regression_results(model, name="Strategy"):
    """Print formatted regression results."""
    if model is None:
        return

    print(f"\n{'─' * 55}")
    print(f"  Conditional FF Regression: {name}")
    print(f"{'─' * 55}")
    print(f"  {'Variable':<14s} {'Coeff':>10s} {'t-stat':>10s} {'p':>8s}")
    print(f"  {'─' * 44}")

    for var in model.params.index:
        coef = model.params[var]
        t = model.tvalues[var]
        p = model.pvalues[var]
        label = var if var != "const" else "Alpha"
        if var == "const":
            coef_display = coef * 12
            print(f"  {label:<14s} {coef_display:>9.2%} {t:>10.2f} {p:>8.3f}")
        else:
            print(f"  {label:<14s} {coef:>10.4f} {t:>10.2f} {p:>8.3f}")

    print(f"  {'─' * 44}")
    print(f"  R-squared:     {model.rsquared:.3f}")
    print(f"  Adj R-squared: {model.rsquared_adj:.3f}")
    print(f"  N obs:         {int(model.nobs)}")


# ── 6. VISUALIZATION ────────────────────────────────────────────────

def plot_comparison(hedge_total, hedge_resid,
                    save_dir="results/residual_momentum"):
    """Cumulative returns and drawdowns (Figures 1 and 2)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    Path(save_dir).mkdir(parents=True, exist_ok=True)

    common = hedge_total.dropna().index.intersection(
        hedge_resid.dropna().index)
    ht = hedge_total.loc[common]
    hr = hedge_resid.loc[common]

    fig, ax = plt.subplots(figsize=(12, 6))
    cum_total = (1 + ht).cumprod()
    cum_resid = (1 + hr).cumprod()

    ax.plot(cum_total.index, cum_total.values,
            label="Total Return Momentum", linewidth=1.5, color="#d62728")
    ax.plot(cum_resid.index, cum_resid.values,
            label="Residual Momentum", linewidth=1.5, color="#1f77b4")
    ax.axhline(1.0, color="grey", linestyle="--", linewidth=0.8)

    ax.set_ylabel("Cumulative Return ($1 invested)")
    ax.set_title("Total Return Momentum vs Residual Momentum")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(f"{save_dir}/cumulative_returns.png", dpi=150)
    plt.close(fig)
    print(f"  Saved: {save_dir}/cumulative_returns.png")

    fig, ax = plt.subplots(figsize=(12, 5))
    dd_total = (cum_total / cum_total.cummax()) - 1
    dd_resid = (cum_resid / cum_resid.cummax()) - 1

    ax.fill_between(dd_total.index, dd_total.values, 0,
                    alpha=0.3, color="#d62728", label="Total Return Mom")
    ax.fill_between(dd_resid.index, dd_resid.values, 0,
                    alpha=0.3, color="#1f77b4", label="Residual Mom")

    ax.set_ylabel("Drawdown")
    ax.set_title("Drawdown Comparison")
    ax.legend(loc="lower left")
    ax.grid(True, alpha=0.3)
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    fig.tight_layout()
    fig.savefig(f"{save_dir}/drawdowns.png", dpi=150)
    plt.close(fig)
    print(f"  Saved: {save_dir}/drawdowns.png")


def plot_decile_returns(decile_total, decile_resid,
                        save_dir="results/residual_momentum"):
    """Bar chart of average annualized returns per decile."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    Path(save_dir).mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)

    for ax, dec, title in [
        (axes[0], decile_total, "Total Return Momentum"),
        (axes[1], decile_resid, "Residual Momentum"),
    ]:
        avg = dec.mean() * 12
        colors = ["#d62728" if v < 0 else "#1f77b4" for v in avg]
        ax.bar(avg.index, avg.values, color=colors, alpha=0.8)
        ax.set_xlabel("Decile (1=Losers, 10=Winners)")
        ax.set_ylabel("Annualized Return")
        ax.set_title(title)
        ax.axhline(0, color="black", linewidth=0.8)
        ax.grid(True, alpha=0.3, axis="y")
        ax.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda x, _: f"{x:.0%}"))

    fig.suptitle("Decile Portfolio Returns", fontsize=14, y=1.02)
    fig.tight_layout()
    fig.savefig(f"{save_dir}/decile_returns.png", dpi=150,
                bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {save_dir}/decile_returns.png")


# ── MAIN ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  RESIDUAL MOMENTUM — Blitz, Huij & Martens (2011)")
    print("=" * 60)

    # ── Phase 1: Data preparation ──
    print("\n── Phase 1: Data Preparation ──")
    excess_ret, ff3, monthly_ret = prepare_data()

    # ── Phase 2+3: Signals ──
    print("\n── Phase 2+3: Rolling FF3 Regressions + Signal Construction ──")
    sig_resid = compute_residual_momentum_signals(
        excess_ret, ff3, window=36)
    sig_total_raw = compute_total_return_momentum(monthly_ret)

    # Price filter: exclude stocks below $5 in any given month.
    # Paper excludes <$1; we use $5 given shorter sample and
    # post-2015 price levels.
    monthly_price = pd.read_csv(
        "data/close_prices.csv", index_col=0, parse_dates=True
    ).resample("ME").last()
    monthly_price.index = monthly_price.index + pd.offsets.MonthEnd(0)
    price_ok = monthly_price.reindex(
        index=sig_resid.index, columns=sig_resid.columns) >= 5.0
    sig_resid = sig_resid.where(price_ok)
    sig_total_raw = sig_total_raw.where(price_ok)
    n_excluded = (~price_ok).sum().sum()
    print(f"\n  Price filter (<$5): excluded {n_excluded} stock-months")

    # Match stock pool: only use stocks where BOTH signals exist
    sig_total = sig_total_raw.where(sig_resid.notna())
    print(f"\n  Stock-month alignment:")
    print(f"    Total (raw):     {sig_total_raw.notna().sum().sum()}")
    print(f"    Total (matched): {sig_total.notna().sum().sum()}")
    print(f"    Residual:        {sig_resid.notna().sum().sum()}")

    # ── Phase 4: Holding period comparison (K=1, 3, 6) ──
    print("\n── Phase 4: Holding Period Comparison ──")

    for K in [1, 3, 6]:
        print(f"\n{'━' * 65}")
        print(f"  K = {K} month holding period")
        print(f"{'━' * 65}")

        dec_total, hedge_total = build_decile_portfolios(
            sig_total, monthly_ret, K=K)
        dec_resid, hedge_resid = build_decile_portfolios(
            sig_resid, monthly_ret, K=K)

        # Align to same time period
        common_dates = hedge_total.dropna().index.intersection(
            hedge_resid.dropna().index)
        hedge_total_a = hedge_total.loc[common_dates]
        hedge_resid_a = hedge_resid.loc[common_dates]

        stats_t = compute_strategy_stats(hedge_total_a)
        stats_r = compute_strategy_stats(hedge_resid_a)
        print_comparison(stats_t, stats_r, label=f"  (K={K})")

        # Save plots for each K
        save_dir = f"results/residual_momentum/K{K}"
        plot_comparison(hedge_total_a, hedge_resid_a, save_dir=save_dir)
        plot_decile_returns(
            dec_total.loc[common_dates],
            dec_resid.loc[common_dates],
            save_dir=save_dir)

        if K == 1:
            hedge_total_k1 = hedge_total_a
            hedge_resid_k1 = hedge_resid_a

    # ── Phase 5: Conditional FF regressions (K=1) ──
    print("\n── Phase 5: Conditional FF Attribution (K=1) ──")

    model_total = conditional_ff_regression(
        hedge_total_k1, ff3, monthly_ret)
    print_regression_results(model_total, "Total Return Momentum")

    model_resid = conditional_ff_regression(
        hedge_resid_k1, ff3, monthly_ret)
    print_regression_results(model_resid, "Residual Momentum")

    print("\n✓ Done. Check results/residual_momentum/K{1,3,6}/ for plots.")


    print("\n✓ Done. Check results/residual_momentum/ for plots.")

# ── Diagnostic: who's in D1 and D10? ──
    print("\n── Diagnostic: D1/D10 Composition ──")

    for name, sig in [("Total Return Mom", sig_total),
                      ("Residual Mom", sig_resid)]:
        assignments = form_decile_assignments(sig, n_quantiles=10)

        d1_counts = pd.Series(dtype=int)
        d10_counts = pd.Series(dtype=int)

        for idx, ranks in assignments.items():
            d1_stocks = ranks[ranks == 1].index
            d10_stocks = ranks[ranks == 10].index
            d1_counts = d1_counts.add(
                pd.Series(1, index=d1_stocks), fill_value=0)
            d10_counts = d10_counts.add(
                pd.Series(1, index=d10_stocks), fill_value=0)

        n_months = len(assignments)
        print(f"\n  {name} ({n_months} formation months)")
        print(f"  D1 (LOSERS) — top 15 most frequent:")
        for tk, cnt in d1_counts.sort_values(ascending=False).head(15).items():
            print(f"    {tk:<6s}  {int(cnt):>3d}/{n_months} months "
                  f"({cnt/n_months:.0%})")
        print(f"  D10 (WINNERS) — top 15 most frequent:")
        for tk, cnt in d10_counts.sort_values(ascending=False).head(15).items():
            print(f"    {tk:<6s}  {int(cnt):>3d}/{n_months} months "
                  f"({cnt/n_months:.0%})")

# ── Deep dive: single stock forensics ──
    print("\n── Stock Forensics ──")

    for ticker in ["NVDA", "ENPH", "CCL", "PCAR"]:
        if ticker not in sig_resid.columns:
            continue

        assignments_resid = form_decile_assignments(sig_resid, 10)
        assignments_total = form_decile_assignments(sig_total, 10)

        print(f"\n  {'─' * 60}")
        print(f"  {ticker}")
        print(f"  {'─' * 60}")
        print(f"  {'Date':<10s} {'Decile':>8s} {'Decile':>8s} "
              f"{'Resid':>8s} {'Total':>8s} {'Next Mo':>8s}")
        print(f"  {'':10s} {'(resid)':>8s} {'(total)':>8s} "
              f"{'Score':>8s} {'Score':>8s} {'Return':>8s}")
        print(f"  {'─' * 60}")

        d1_returns = []
        d10_returns = []

        for idx in sorted(assignments_resid.keys()):
            ranks_r = assignments_resid[idx]
            if ticker not in ranks_r.index:
                continue

            decile_r = int(ranks_r[ticker])
            if decile_r not in [1, 10]:
                continue

            date = sig_resid.index[idx]
            score_r = sig_resid.iloc[idx].get(ticker, np.nan)
            score_t = sig_total.iloc[idx].get(ticker, np.nan)

            # Next month return
            if idx < len(monthly_ret) - 1:
                next_ret = monthly_ret.iloc[idx].get(ticker, np.nan)
            else:
                next_ret = np.nan

            # What decile in total return?
            decile_t = "—"
            if idx in assignments_total and ticker in assignments_total[idx].index:
                decile_t = str(int(assignments_total[idx][ticker]))

            flag = "◀" if decile_r == 1 else "▶"
            print(f"  {date.strftime('%Y-%m'):<10s} "
                  f"{'D'+str(decile_r):>8s} "
                  f"{'D'+decile_t:>8s} "
                  f"{score_r:>8.2f} "
                  f"{score_t:>7.1%} "
                  f"{next_ret:>7.1%}  {flag}")

            if decile_r == 1:
                d1_returns.append(next_ret)
            else:
                d10_returns.append(next_ret)

        if d1_returns:
            d1_arr = [r for r in d1_returns if not np.isnan(r)]
            print(f"\n  D1 months: {len(d1_arr)}, "
                  f"avg next-mo return: {np.mean(d1_arr):.2%}, "
                  f"total contrib: {np.sum(d1_arr):.2%}")
        if d10_returns:
            d10_arr = [r for r in d10_returns if not np.isnan(r)]
            print(f"  D10 months: {len(d10_arr)}, "
                  f"avg next-mo return: {np.mean(d10_arr):.2%}, "
                  f"total contrib: {np.sum(d10_arr):.2%}")

# ── Diagnostic: worst months for total return momentum ──
    print("\n── Total Return Momentum: Worst 10 Months ──")
    assignments_t = form_decile_assignments(sig_total, n_quantiles=10)

    month_details = []
    for t in range(len(monthly_ret)):
        if t not in assignments_t:
            continue
        date = monthly_ret.index[t]
        fwd = monthly_ret.iloc[t]
        ranks = assignments_t[t]

        d1_stocks = ranks[ranks == 1].index
        d10_stocks = ranks[ranks == 10].index

        d1_ret = fwd[d1_stocks.intersection(fwd.dropna().index)]
        d10_ret = fwd[d10_stocks.intersection(fwd.dropna().index)]

        hedge = d10_ret.mean() - d1_ret.mean()
        month_details.append({
            "date": date, "hedge": hedge,
            "d1_mean": d1_ret.mean(), "d10_mean": d10_ret.mean(),
            "d1_max": d1_ret.max(), "d1_max_tk": d1_ret.idxmax() if len(d1_ret) > 0 else "",
            "d1_top3": d1_ret.nlargest(3),
            "d1_count": len(d1_ret),
        })

    md = sorted(month_details, key=lambda x: x["hedge"])

    for m in md[:10]:
        print(f"\n  {m['date'].strftime('%Y-%m')}  "
              f"Hedge: {m['hedge']:+.1%}  "
              f"D10 avg: {m['d10_mean']:+.1%}  "
              f"D1 avg: {m['d1_mean']:+.1%}  "
              f"D1 stocks: {m['d1_count']}")
        print(f"    D1 top 3 gainers (short leg killers):")
        for tk, ret in m["d1_top3"].items():
            print(f"      {tk:<8s} {ret:+.1%}")
