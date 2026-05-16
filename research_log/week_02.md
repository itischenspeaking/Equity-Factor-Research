# Week 2: Factor Attribution, Rolling Validation, IC Analysis, and Residual Momentum

**2026-05-04 ---- 2026-05-11**

Week 2 started with attribution and validation work on the earlier exploratory strategies. In the second half of the week, the project shifted toward a more serious replication of residual momentum.

The main transition this week was from "try a strategy and check Sharpe" to a more structured research workflow:

- factor attribution;
- rolling validation;
- IC analysis;
- debugging signal timing and date alignment;
- paper-based strategy replication;
- diagnosing why a strategy works or fails.

---

## Day 1: Fama-French 3-Factor Attribution

Implemented Fama-French 3-factor attribution using:

- Mkt-RF;
- SMB;
- HML.

The goal was to understand whether the earlier strategies were actually producing independent returns, or just loading on known common factors.

### Momentum strategy

The momentum strategy had a significant negative HML loading:

```text
HML loading = -0.45
R² = 0.33
```

This means the strategy was unintentionally long growth and short value.

This was an important early result because it showed that even a simple "momentum" strategy is not necessarily a clean standalone signal. It may carry meaningful style exposure.

### Consumer Staples basket v1

Consumer Staples v1 had insignificant factor loadings and low explanatory power:

```text
R² = 0.07
```

This suggested that the basket result was not obviously explained by the basic FF3 factors. I would not call this conclusive, but it was a useful first attribution check.

---

## Day 2: Upgrade to FF5 + Momentum

Expanded the regression to include:

- RMW;
- CMA;
- UMD.

This created a useful example of omitted-variable bias. After adding the momentum factor, the momentum strategy's explanatory power increased substantially:

```text
R²: 0.33 → 0.72
UMD loading: 0.94
```

The strategy was largely capturing the standard momentum factor, but with negative implementation drag from universe choice, weighting, rebalancing, and transaction costs.

### Consumer Staples v1

Consumer Staples v1 remained mostly orthogonal to the six-factor model:

```text
R² = 0.07
Adjusted R² = -0.12
```

This does not prove the strategy has alpha, but it means the standard factor model did not explain much of its variation.

### Consumer Staples v2

The OU-filtered version behaved worse under attribution:

```text
Mkt-RF loading = -0.079
p = 0.026
Alpha = -4.16%
p = 0.041
```

The filter design appeared to introduce unwanted market exposure and did not improve returns.

I also built `export_all_results.py` to export quantitative results to CSV with a manifest. This made it easier to keep outputs reproducible and inspectable.

---

## Day 3: Rolling Forward Validation

Replaced the fixed 70/30 train/test split with rolling 60-day forward windows, stepped daily.

Evaluated 2,203 windows for both v1 and v2.

### v1 results

```text
Mean Sharpe: -0.20
Positive windows: 44%
```

The rolling results showed strong regime dependence.

The fixed 70/30 split had produced a Sharpe of 0.56, but that appears to have depended heavily on the 2022-2024 test period. Rolling validation gave a less flattering and more realistic view.

The compounded rolling-window returns were strong during 2016-2017, when mean-reversion signals were more favourable, but decayed afterwards.

### v2 results

```text
Mean Sharpe: -1.26
Positive windows: 23%
```

The OU-filtered version did not improve under rolling validation. It reduced some drawdown risks in the earlier backtest, but in rolling validation it was mostly unproductive.

### Paper trading period: 2025-01 to 2026-05

Tested v1 trained on 2015-2024 data.

```text
Total return: -17.3%
Sharpe: -0.84
Max drawdown: -25.5%
```

FF6 attribution during this period showed insignificant loadings and negative adjusted R². The strategy remained broadly factor-neutral, but factor neutrality did not prevent losses.

This was a useful lesson: being factor-neutral is not the same thing as having a reliable positive expected return.

---

## Day 4: IC Analysis

Computed rolling Information Coefficient using Spearman rank correlation between the z-score signal and 21-day forward return.

### Full sample

```text
IC mean = 0.034
IC_IR = 0.069
Hit rate = 51%
t-stat = 3.61
```

### Training period: 2015-2024

```text
IC mean = 0.025
Hit rate = 50.2%
```

### Forward period: 2025-2026

```text
IC mean = 0.105
Hit rate = 57.0%
t-stat = 3.76
```

The surprising result was that IC was stronger in the forward period, even though the trading strategy lost money.

### IC-to-PnL gap

This was one of the more useful findings from the week.

The signal had positive rank IC, but the strategy still lost money. This suggests that the signal may contain some directional information, but the trading rule failed to convert that information into PnL.

Possible reasons:

- entry threshold too strict or poorly calibrated;
- holding period mismatch;
- transaction costs;
- poor position sizing;
- losses concentrated in a small number of high-impact trades;
- signal works in rank space but not under the current long/short construction.

The important lesson is that positive IC is not the same as a profitable trading strategy.

---

## Day 5: Residual Momentum Replication on S&P 500

Started replicating the core methodology of Blitz, Huij, and Martens (2011), *Residual Momentum*, on the S&P 500 universe.

This became the most serious part of the project.

### Implementation

For each stock and each month:

1. Run a rolling 36-month FF3 regression.
2. Extract residual returns.
3. Build a standardized 12-1M residual momentum signal:
   - sum of residuals from t-12 to t-2;
   - divided by residual standard deviation over the same period.
4. Compare residual momentum with total-return momentum.
5. Build D10-D1 hedge portfolios.
6. Test K=1, K=3, and K=6 overlapping holding periods.

The stock pools and time periods were matched so that the comparison between total and residual momentum was fair.

### Debugging and controlled comparison

Several issues had to be fixed:

- date alignment between FF factor data and monthly returns;
- timestamp precision mismatch;
- total-return momentum signal construction;
- matched stock pools;
- aligned backtest periods.

Changing total-return momentum from a simple sum to a compounded return had a material impact and helped make the implementation more consistent with the intended signal definition.

### S&P 500 results, K=1

| Metric | Total Return | Residual |
|---|---:|---:|
| Ann. Return | -1.37% | 2.25% |
| Ann. Volatility | 21.16% | 11.02% |
| Sharpe Ratio | -0.06 | 0.20 |
| Max Drawdown | -47.07% | -16.04% |
| Conditional FF R² | 0.457 | 0.082 |

The main result was not strong alpha. Instead, the important result was risk reduction.

Residual momentum roughly halved volatility and substantially reduced conditional factor exposure. This was directionally consistent with the paper's central mechanism.

---

## Day 6: Stock Forensics and Universe Expansion

### Code review

Reviewed the month-end timing logic.

The intended timing is:

- signal uses information through t-2;
- t-1 is skipped;
- the signal is known by the end of t-1;
- the strategy earns month t return.

I did not find an obvious look-ahead bias in this structure.

### Stock forensics on S&P 500

Printed D1/D10 composition and per-stock holding-period returns to understand why the strategy did not work better on S&P 500.

#### Case studies

**NVDA**

NVDA appeared in residual D1 for 17 consecutive months from 2018-06 to 2019-11 while also appearing in total-return D10.

The residual signal treated much of NVDA's performance as factor-driven rather than firm-specific momentum. That interpretation may be reasonable, but shorting it still lost money:

```text
Average D1 hold return: +0.32%
```

**ENPH**

ENPH appeared in total D10 with a very high total-return score while also appearing in residual D1 in mid-2021.

Its D1 months averaged:

```text
+4.03%
```

This was damaging for the short leg.

**CCL**

CCL was one of the few cases where shorting D1 was profitable:

```text
Average hold return: -3.59%
```

This looked more like genuine structural decline.

**PCAR**

PCAR was one of the better residual D10 examples:

```text
23 months in D10
Average hold return: +3.40%
Cumulative contribution: +78%
```

### Interpretation

The S&P 500 short leg often contained temporarily distressed large caps that later recovered. This made the D1 leg costly to short.

This suggested a hypothesis: residual momentum may need a broader universe, including smaller-cap names, to work better on the short side.

I would treat this as a hypothesis rather than a conclusion, but it motivated the next experiment.

---

## Universe Expansion to S&P 1500

Expanded from S&P 500 to S&P 1500:

```text
497 S&P 500 stocks
390 S&P 400 stocks
582 S&P 600 stocks
1,469 total stocks
```

Updated `download_data.py` to support:

- Wikipedia scraping for index constituents;
- batched `yfinance` downloads;
- index membership tagging.

### Data quality issue

The first run produced extreme and clearly unrealistic results.

The main issue was CHRD, where `yfinance` showed a +30,991% monthly return in November 2020 due to a corporate-action/ticker-history problem related to Chord Energy and Oasis Petroleum.

This single stock-month contaminated the hedge portfolio and created nonsensical volatility and drawdown numbers.

### Filters applied

To make the dataset more usable:

- excluded stock-months with price below $5;
- excluded stock-months with absolute monthly return above 300%.

The price filter is inspired by the paper's exclusion of very low-priced stocks, though the threshold is not identical. The extreme-return filter is mainly a practical fix for `yfinance` corporate-action errors.

### S&P 1500 results after filtering

| Metric | K=1 Total | K=1 Resid | K=3 Total | K=3 Resid |
|---|---:|---:|---:|---:|
| Ann. Return | -2.25% | 2.14% | 0.08% | 3.37% |
| Ann. Volatility | 19.94% | 10.44% | 19.23% | 9.72% |
| Sharpe Ratio | -0.11 | 0.21 | 0.00 | 0.35 |
| Max Drawdown | -52.29% | -20.09% | -42.34% | -18.48% |

The S&P 1500 results continued to support the risk-reduction mechanism:

```text
Volatility ratio: about 0.50x
Conditional FF R²: 0.388 → 0.077
```

Residual momentum improved from the S&P 500 test, especially at K=3, but the alpha remained modest.

### Decile pattern

Total-return momentum still had a U-shaped decile pattern, likely driven by loser rebounds and high-beta exposure at the extremes.

Residual momentum K=3 showed a more useful upward slope, especially from the middle deciles onward. It was not perfectly monotonic, but it was cleaner than the S&P 500 version.

### Cumulative returns

The cumulative return charts showed a clear divergence after 2020.

Total-return momentum struggled to recover from the COVID reversal, while residual momentum recovered more quickly and had a smaller drawdown.

This pattern appeared across K=1, K=3, and K=6, which made it worth exploring further in Week 3.

### Code

Main code touched this week:

- `factors/residual_momentum.py`
- `data/download_data.py`

Outputs saved under:

```text
results/residual_momentum/K{1,3,6}/
```

---

## Structural Decisions

### Deleted the original factor attribution report

The original report was written before rolling validation and IC analysis. Its framing was too optimistic relative to the later evidence.

I decided to delete it and rewrite a new report after the residual momentum work is more complete.

### Chose residual momentum as the main project direction

The residual momentum project directly builds on the Week 2 attribution result: traditional momentum can be contaminated by time-varying factor exposures.

This made it a good candidate for a more serious paper replication and stress test.

---

## Summary of What Replicated

| Paper claim / mechanism | Status in this sample | Evidence |
|---|---|---|
| Residual momentum reduces volatility | Strong support | 0.48-0.52x vol ratio across K and universes |
| Residual momentum reduces dynamic factor exposure | Strong support | Conditional FF R² falls from about 0.39-0.46 to about 0.08 |
| Conditional beta structure improves | Strong support | Significant SMB/HML exposure becomes much smaller |
| Max drawdown improves | Strong support | S&P 1500 K=1 max DD improves from -52% to -20% |
| Sharpe improves | Partial support | Direction is right, but alpha is weak in this period |
| Decile monotonicity improves | Partial support | Residual K=3 is cleaner, but not perfectly monotonic |
| Business-cycle or crisis resilience | Not yet tested | Planned for Week 3 |

---

## TODO for Next Week

- [ ] COVID crash/reversal case study: monthly returns of RMRF vs total momentum vs residual momentum in 2020.
- [ ] Per-decile beta and size characteristics inspired by the paper's Table 5.
- [ ] Revisit mean reversion factor. The D1 loser-bounce finding suggests large-cap losers may be worth studying separately.
- [ ] Write a comprehensive residual momentum report.
- [ ] Add rolling validation on residual momentum.
- [ ] Think carefully about survivorship bias from using current index constituents.

---

## Reading List

- [x] Avellaneda & Lee (2010) — skimmed
- [x] Frazzini, Kabiller & Pedersen (2018), "Buffett's Alpha"
- [x] Blitz, Huij & Martens (2011), *Residual Momentum*
- [ ] Huij & Lansdorp (2017), "Residual Momentum and Reversal Strategies Revisited"
- [ ] Grundy & Martin (2001), "Understanding the Nature of the Risks and the Source of the Rewards to Momentum Investing"
