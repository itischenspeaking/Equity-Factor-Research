# Week 2: Factor Attribution, Rolling Validation, IC Analysis

**2026-05-04 ---- 2026-05-10**

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

IC_IR remained above -0.5 throughout 2025, indicating the factor
has not "reversed" (which would mean trading the opposite
direction), it has merely "weakened" as a standalone trading
signal.

Dispersion remained normal (~1.2%) in 2025, confirming that
trading opportunities existed — the strategy just couldn't
capitalise on them.

## Day 5: Residual Momentum Replication

Replicated the core methodology of Blitz, Huij & Martens (2011)
"Residual Momentum" on the S&P 500 universe.

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
(`sig_total.where(sig_resid.notna())`) and aligned time periods
so both strategies are evaluated on identical stock-months.

**What replicated successfully:**

- Volatility reduction: residual momentum vol is 46-52% of
  total return momentum across all holding periods. Paper
  reports ~55%. Core mechanism confirmed.
- Dynamic factor exposure removal: conditional FF3 R² drops
  from 0.457 (total) to 0.082 (residual). Paper reports
  0.34-0.48 vs 0.13-0.17. The pattern is even stronger in
  our sample.
- Conditional beta structure: total return momentum loads
  significantly on SMB (-0.75, SMB_UP +0.93) and HML (-0.93,
  HML_UP +0.94). Residual momentum: all loadings insignificant
  except marginal Mkt-RF. Exactly matches paper Table 2.
- Max drawdown reduction: -47% (total) vs -16% (residual) at
  K=1. Total return momentum never recovered from the 2020-2021
  drawdown; residual momentum did.

**What did not replicate:**

- Sharpe ratio doubling. Paper reports residual Sharpe ~ 2x
  total. Our data shows residual Sharpe = 0.20 vs total = -0.06
  (K=1). Residual is better but the absolute level is low.
- Monotonic decile returns. Both strategies show noisy, non-
  monotonic decile patterns. D1 (losers) earns ~19% annualised
  — higher than most other deciles.

**Code:** `factors/residual_momentum.py` — self-contained script
with data prep, rolling regression, signal construction, decile
portfolio builder (with overlapping holding periods), conditional
FF regression, and visualisation. Results in
`results/residual_momentum/K{1,3,6}/`.

## Day 6: Code Review, Diagnostics, and Universe Analysis

Reviewed the residual momentum code for correctness. Verified
the month-end trading timing: signal[t] uses data through t-2
(skipping t-1), is known at t-1 month-end, and earns t's return.
No look-ahead bias. Confirmed independently.

**D1/D10 composition analysis:** Printed the 15 most frequent
stocks in each extreme decile to understand the persistent
U-shaped decile pattern.

Total return momentum D10 is dominated by mega-growth: ENPH
(64% of months), NVDA (59%), AMD (51%), LLY, NFLX, the
semiconductor equipment cluster. D1 is structurally distressed
large-caps: CCL (47%), NWL (47%), LUMN (46%), WBD, PCG. Both
extremes are high-beta, high-vol — explaining the U-shape in
absolute returns (both outperform low-beta mid-deciles in a
bull market).

Residual momentum composition is strikingly different. D10:
PCAR (28%), ITW, PSX, COP, XOM, JPM, COST — industrials,
energy, financials with genuine firm-specific outperformance.
D1: VRSN (33%), MAA, CNP, DXC — and notably NVDA at 23%.
Much more dispersed (max frequency 33% vs 64%), indicating
higher turnover and less concentration.

**Stock forensics — four case studies:**

- NVDA: in residual D1 for 17 consecutive months (2018-06 to
  2019-11) while simultaneously in total return D10. Residual
  signal correctly identified that NVDA's returns were factor
  exposure, not firm-specific momentum. But avg hold return in
  D1 months was +0.32% — shorting it lost money.
- ENPH: in total D10 (score +246%) and residual D1 (score
  -3.42) simultaneously in mid-2021. The signals directly
  contradicted. ENPH's D1 months averaged +4.03% hold return
  — disastrous for the short leg.
- CCL: the only stock where D1 shorting was profitable (avg
  hold return -3.59%). Genuine structural decline.
- PCAR: model residual D10 stock. 23 months in D10, avg hold
  return +3.40%, cumulative contribution +78%. Steady firm-
  specific outperformance invisible to total return momentum
  (ranked only D7-D9 in total).

**Root cause — universe composition:**

The paper uses CRSP (all NYSE/AMEX/Nasdaq, thousands of names
including micro-caps). D1 in that universe contains genuine
penny stocks and failing companies that continue to decline —
the short leg generates alpha. In S&P 500, D1 is populated by
temporarily distressed large-caps (CCL, LUMN, WBD) that almost
always recover because they have the balance sheets and index
inclusion to survive. The short leg of momentum earns POSITIVE
returns on average, which kills the D10-D1 hedge regardless of
how well the long leg performs.

**This is the single most important finding from the replication:
the same factor can work or fail depending entirely on the
universe it operates in.** The paper's methodology is correct,
the signal construction is correct, the risk reduction is real
— but the alpha comes from the short leg, and the short leg
requires a universe where losers actually keep losing.

---

## Structural Decisions

**Deleted the original factor attribution report.** The report was
written before rolling validation and IC analysis, and its
conclusions (particularly the optimistic framing of v1 Consumer
Staples) are now superseded. A new report will be written once
the full analysis is complete, incorporating rolling validation,
IC analysis, and the IC-to-PnL gap finding.

**Decided on next project direction.** Two options were considered:

1. Continue refining the basket strategy — redesign filters,
   optimise basket composition, build a regime-conditional
   deployment system. Rejected because: the basket selection
   was ad hoc (no principled reason for these 5 stocks), the
   strategy is already too complex for my current skill level,
   and further tuning without theoretical grounding risks
   overfitting.

2. Replicate an established academic factor with a clean
   research framework. **Selected this option.** The factor
   chosen is **Residual Momentum** (Blitz, Huij & Martens, 2011),
   which ranks stocks by momentum of their FF-residual returns
   rather than total returns. This directly addresses the
   finding from Day 2 that traditional momentum is contaminated
   by time-varying factor exposures (Mom loading = 0.94). The
   existing FF regression infrastructure can be reused. A 2017
   replication (Huij & Lansdorp) confirms out-of-sample
   robustness.

---

## TODO for next week

- [ ] COVID crash case study: monthly returns of RMRF vs total
      vs residual momentum in 2020, replicating paper Figure 3
- [ ] Per-decile beta and size characteristics (paper Table 5)
      to explain the U-shaped decile pattern quantitatively
- [ ] Consider expanding universe beyond S&P 500 — the forensics
      show the short leg problem is a universe issue, not a
      methodology issue. Russell 2000 or CRSP-equivalent data
      would be the proper test.
- [ ] Revisit mean reversion factor — the D1 loser bounce
      finding suggests large-cap losers may be a profitable
      long-only signal
- [ ] Write comprehensive report covering Weeks 1-2 findings
- [ ] Rolling validation on residual momentum

## Reading list

- [x] Avellaneda & Lee (2010) — skimmed
- [x] Frazzini, Kabiller & Pedersen (2018) "Buffett's Alpha"
- [x] **Blitz, Huij & Martens (2011) "Residual Momentum"**
- [ ] Huij & Lansdorp (2017) "Residual Momentum and Reversal
      Strategies Revisited" — replication/robustness check
- [ ] Grundy & Martin (2001) "Understanding the Nature of the
      Risks and the Source of the Rewards to Momentum Investing"
      — cited by Blitz et al. as key predecessor
