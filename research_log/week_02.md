# Week 2: Factor Attribution, Rolling Validation, IC Analysis

**2026-05-04 ---- 2026-05-11**

---

## Day 1: Fama-French 3-Factor Attribution

Implemented FF3 factor attribution (Mkt-RF, SMB, HML) on all
strategies. Key finding: Momentum strategy's HML loading was
-0.45 (significant) under FF3, meaning the strategy was
unintentionally shorting value and going long growth. R² = 0.33.

Consumer Staples v1: all loadings insignificant, R² = 0.07.
Confirmed market neutrality.

## Day 2: Upgrade to FF5 + Momentum (6-Factor)

Added RMW, CMA, and UMD to the regression. This revealed a
textbook case of omitted variable bias: Momentum strategy's
R² jumped from 0.33 to 0.72 after adding the Mom factor
(loading = 0.94, p = 0.000). The strategy is almost a pure
replication of the Fama-French momentum factor, with -6.5%
annualised negative alpha — implementation drag from universe
composition and rebalancing mechanics.

Consumer Staples v1 remained orthogonal under FF6: all 6
loadings insignificant, R² = 0.07, Adj R² = -0.12. Returns
come from a source outside the standard factor zoo.

Consumer Staples v2 (OU filter): Mkt-RF loading became
significant (-0.079, p = 0.026), and alpha turned significantly
negative (-4.16%, p = 0.041). The filter introduces market
exposure that did not exist in v1, confirming that the current
filter design is harmful.

Also built `export_all_results.py` to dump all quantitative
results to CSV with a manifest. This makes data access and
reproducibility easier going forward.

## Day 3: Rolling Forward Validation

Replaced the fixed 70/30 train/test split with rolling 60-day
forward windows, stepped daily. 2203 windows evaluated for both
v1 and v2.

**v1 results:** Mean Sharpe -0.20, 44% positive windows. Clear
regime structure — compounded window returns spiked to 14x
during 2016-2017 when mean reversion signals were strong, then
decayed steadily. The fixed 70/30 split Sharpe of 0.56 was an
artefact of the test period (2022-2024) being a favourable
regime.

**v2 results:** Mean Sharpe -1.26, 23% positive windows.
Compounded returns flatlined from the start, never showing
any meaningful positive accumulation. OU filter is conclusively
harmful under rolling validation as well.

**Paper trading (2025-01 to 2026-05):** Deployed v1 trained on
full 2015-2024 data. Total return -17.3%, Sharpe -0.84, max
drawdown -25.5%. FF6 attribution on this period: all loadings
insignificant (Adj R² = -0.254), consistent with the strategy
remaining factor-neutral. The loss falls well within the
distribution predicted by rolling validation (mean Sharpe -0.20,
std 1.71).

## Day 4: IC Analysis

Computed rolling Information Coefficient (Spearman rank
correlation between z-score and 21-day forward return) across
the full sample including 2025-2026.

**Full sample:** IC mean = 0.034, IC_IR = 0.069, hit rate = 51%,
t-stat = 3.61 (statistically significant). The factor has weak
but real predictive power.

**Training (2015-2024):** IC mean = 0.025, hit rate = 50.2%.

**Forward (2025-2026):** IC mean = 0.105, hit rate = 57.0%,
t-stat = 3.76. Surprisingly, IC is BETTER in the forward period
than in training.

**IC-to-PnL gap:** The strategy lost 17% during a period when IC
was persistently positive. This reveals that the signal predicts
the right direction (IC > 0) but the execution layer (z-score
threshold entry at ±2, holding period, transaction costs) fails
to convert predictive power into profit. The problem is not the
factor but the trading rule.

## Day 5: Residual Momentum Replication (S&P 500)

Replicated the core methodology of Blitz, Huij & Martens (2011)
"Residual Momentum" on the S&P 500 universe (462 stocks).

**Implementation:** For each stock each month, run a rolling
36-month FF3 regression to extract residuals. Rank stocks on
standardised 12-1M residual returns (sum / std of formation-
period residuals). Compare D10-D1 hedge portfolios for residual
momentum vs total return momentum, with matched stock pools and
identical time periods. Tested K=1, 3, 6 month overlapping
holding periods following Jegadeesh & Titman (1993).

**Debugging and controlled comparison:** Several iterations were
needed to get the comparison right. Fixed date alignment between
FF factor data and monthly returns (timestamp precision mismatch).
Changed total return momentum signal from simple sum to compounded
return — this had a material impact, flipping total return
momentum from slightly positive to negative. Matched stock pools
and aligned time periods for fair comparison.

**S&P 500 results (K=1):**

| Metric              | Total Return | Residual |
|----------------------|-------------|----------|
| Ann. Return          | -1.37%      | 2.25%    |
| Ann. Volatility      | 21.16%      | 11.02%   |
| Sharpe Ratio         | -0.06       | 0.20     |
| Max Drawdown         | -47.07%     | -16.04%  |
| Cond. FF R²          | 0.457       | 0.082    |

Vol halved and dynamic factor exposure eliminated, but Sharpe
only marginally better because momentum alpha ≈ 0 on S&P 500.

## Day 6: Stock Forensics and Universe Expansion

### Code review

Verified month-end trading timing: signal[t] uses data through
t-2 (skipping t-1), is known at t-1 month-end, and earns t's
return. No look-ahead bias. Confirmed independently.

### Stock forensics (S&P 500)

Printed D1/D10 composition and per-stock holding-period returns
to diagnose why momentum doesn't work on S&P 500.

**Key case studies:**

- NVDA: in residual D1 for 17 consecutive months (2018-06 to
  2019-11) while simultaneously in total return D10. Residual
  signal correctly identified that NVDA's returns were factor
  exposure, not firm-specific momentum. But avg hold return in
  D1 months was +0.32% — shorting it lost money.
- ENPH: in total D10 (score +246%) while residual D1 (score
  -3.42) in mid-2021. ENPH's D1 months averaged +4.03% hold
  return — disastrous for the short leg.
- CCL: the only stock where D1 shorting was profitable (avg
  hold return -3.59%). Genuine structural decline.
- PCAR: model residual D10 stock. 23 months in D10, avg hold
  return +3.40%, cumulative contribution +78%.

**Root cause:** S&P 500 D1 is populated by temporarily distressed
large-caps that almost always recover. The short leg earns
positive returns, killing the hedge. Hypothesis: a broader
universe with small caps (where losers actually fail) would fix
this.

### Universe expansion to S&P 1500

Expanded from S&P 500 (462 stocks) to S&P 1500 (1469 stocks:
497 SP500 + 390 SP400 + 582 SP600). Updated `download_data.py`
with batched downloads and index membership tags.

**Data quality issue discovered:** CHRD (Chord Energy, post-
bankruptcy ticker change from Oasis Petroleum) showed +30,991%
monthly return in Nov 2020 due to yfinance not handling the
corporate action correctly. This single stock in one month
caused -260% hedge return and 100% annualised volatility.
Diagnosed by printing worst months and identifying D1 top
gainers.

**Data quality filter:** Following the paper's approach of
excluding stocks with price < $1 to reduce microstructure
concerns, applied two filters: (1) exclude stock-months with
price < $5 (adjusted for post-2015 price levels and inflation);
(2) exclude stock-months with |return| > 300% (yfinance
corporate action errors not present in CRSP).

**S&P 1500 results after filtering:**

| Metric              | K=1 Total | K=1 Resid | K=3 Total | K=3 Resid |
|----------------------|-----------|-----------|-----------|-----------|
| Ann. Return          | -2.25%    | 2.14%     | 0.08%     | 3.37%     |
| Ann. Volatility      | 19.94%    | 10.44%    | 19.23%    | 9.72%     |
| Sharpe Ratio         | -0.11     | 0.21      | 0.00      | 0.35      |
| Max Drawdown         | -52.29%   | -20.09%   | -42.34%   | -18.48%   |

Vol ratio ~0.50x across all K. Conditional FF R²: 0.388
(total) → 0.077 (residual). K=3 is the sweet spot for
residual momentum (Sharpe 0.35).

**Improvement from universe expansion:** Residual momentum
Sharpe went from 0.20 (S&P 500) to 0.35 (S&P 1500, K=3).
The hypothesis that the short leg needs small caps to work
is partially confirmed — vol ratio and factor exposure
removal are identical, but absolute returns improved.

**Decile pattern:** Total return momentum still U-shaped (even
worse with small caps added — D1 at 20%+ from loser bounces).
Residual momentum K=3 shows the best monotonicity: D1 ≈ 13%
increasing to D10 ≈ 18%, with a clear upward slope from D6
onward. Not perfect, but a meaningful improvement over the
flat S&P 500 decile pattern.

**Cumulative return charts:** Total return momentum and residual
momentum permanently diverge from mid-2020 onward across all
holding periods. Total return momentum never recovers from
the 2020 COVID reversal (drawdown stays at -30% to -50%);
residual momentum recovers and makes new highs. This pattern
is consistent across K=1, K=3, and K=6 — structural, not
coincidental.

**Code:** `factors/residual_momentum.py` — self-contained script
with all phases. `data/download_data.py` — updated with S&P
1500 support, batched downloads, and index membership tags.
Results in `results/residual_momentum/K{1,3,6}/`.

---

## Structural Decisions

**Deleted the original factor attribution report.** The report was
written before rolling validation and IC analysis, and its
conclusions (particularly the optimistic framing of v1 Consumer
Staples) are now superseded. A new report will be written once
the full analysis is complete.

**Decided on next project direction.** Replicate an established
academic factor with a clean research framework. The factor
chosen is **Residual Momentum** (Blitz, Huij & Martens, 2011).
This directly addresses the finding from Day 2 that traditional
momentum is contaminated by time-varying factor exposures.

---

## Summary of what replicated

| Paper claim | Status | Evidence |
|-------------|--------|----------|
| Vol reduced to ~55% | ✓ Confirmed | 0.48-0.52x across all K and both universes |
| Dynamic factor R² eliminated | ✓ Confirmed | 0.39-0.46 → 0.08 |
| Conditional beta structure | ✓ Confirmed | Significant SMB/HML loadings disappear |
| Max drawdown reduced | ✓ Confirmed | -52% → -20% (S&P 1500 K=1) |
| Sharpe ratio doubled | ✗ Partial | Direction right, but alpha ≈ 0 in this period |
| Monotonic decile returns | ✗ Partial | Weak upward slope in residual K=3, U-shape in total |
| Consistent across business cycles | Untested | Need COVID case study |

---

## TODO for next week

- [ ] COVID crash case study: monthly returns of RMRF vs total
      vs residual momentum in 2020, replicating paper Figure 3
- [ ] Per-decile beta and size characteristics (paper Table 5)
- [ ] Revisit mean reversion factor — the D1 loser bounce
      finding suggests large-cap losers may be a profitable
      long-only signal
- [ ] Write comprehensive report covering Weeks 1-2 findings
- [ ] Rolling validation on residual momentum
- [ ] Consider whether survivorship bias in the ticker list
      (using current constituents for historical data) is
      materially affecting results

## Reading list

- [x] Avellaneda & Lee (2010) — skimmed
- [x] Frazzini, Kabiller & Pedersen (2018) "Buffett's Alpha"
- [x] **Blitz, Huij & Martens (2011) "Residual Momentum"**
- [ ] Huij & Lansdorp (2017) "Residual Momentum and Reversal
      Strategies Revisited" — replication/robustness check
- [ ] Grundy & Martin (2001) "Understanding the Nature of the
      Risks and the Source of the Rewards to Momentum Investing"
