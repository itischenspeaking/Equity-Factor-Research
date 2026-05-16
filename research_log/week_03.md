# Week 3: Residual Momentum — Diagnostics, Universe Expansion, and Research Write-Up

**2026-05-11 — 2026-05-17**

This week focused on turning the residual momentum replication from a working script into a cleaner research project. The main goals were to diagnose why the first version behaved poorly, expand the universe, add paper-inspired diagnostics, and start restructuring the GitHub documentation around the residual momentum case study.

The week also clarified the main interpretation of the project: in this sample, residual momentum is more convincing as a risk and factor-exposure reduction technique than as a strong standalone alpha signal.

---

## Day 1 (Mon): Stock Forensics and Universe Diagnosis

Reviewed the residual momentum implementation for timing correctness. The main signal construction appears to avoid look-ahead bias: each signal is formed using information available before the holding-period return.

I then built diagnostic tools to inspect which stocks repeatedly enter the extreme deciles and to trace individual stocks through signal formation, decile assignment, and subsequent holding-period returns.

Added diagnostic functions including:

- `print_d1_d10_composition`
- `print_stock_forensics`
- `print_worst_months`

These functions are useful for debugging and interpretation, but they are kept optional rather than part of the default research pipeline.

### D1/D10 Composition Diagnostics

The S&P 500 version showed that total-return momentum was highly concentrated in a small number of extreme stocks.

Total-return momentum D10 was often dominated by mega-growth and high-beta names such as ENPH, NVDA, and AMD. Total-return momentum D1 contained more distressed or temporarily impaired stocks. Residual momentum was more dispersed and less concentrated in the same high-profile momentum names.

This suggested that residual momentum was doing something economically different from total-return momentum, even when headline performance was not strong.

### Stock-Level Case Studies

A few stock traces were useful for understanding the short-leg problem.

- **NVDA** spent a long period in residual D1 while remaining strong on total-return momentum. Residual momentum appeared to classify some of its returns as factor-driven rather than stock-specific momentum. Shorting it was not profitable in this period.
- **ENPH** was another example where total-return and residual momentum gave very different classifications. It appeared in total D10 and residual D1 at the same time, and the residual short leg performed poorly.
- **CCL** was a clearer example of a distressed loser where shorting from D1 worked better.
- **PCAR** looked closer to an ideal residual momentum winner, with repeated D10 assignments and positive subsequent returns.

Main takeaway:

> The first version had a meaningful short-leg problem. In a large-cap universe, some loser stocks behave more like temporarily distressed rebound candidates than persistent underperformers. This motivated expanding the universe beyond the S&P 500.

---

## Day 2 (Tue): Universe Expansion to S&P 1500 and Data Quality Fixes

Expanded the universe from the S&P 500 to the S&P 1500, combining approximate current constituents from:

- S&P 500
- S&P MidCap 400
- S&P SmallCap 600

The expanded universe contains 1,469 stocks after ticker collection.

Updated `download_data.py` to support broader universe downloads, batching, and membership tagging.

### Data Quality Issue

The first S&P 1500 run produced unrealistic results. The worst-month diagnostic traced the issue to a corporate-action data error in Yahoo Finance data. One stock-month showed an extreme return above 30,000%, which contaminated the portfolio returns.

This reinforced an important data lesson: with cross-sectional strategies, a single bad stock-month can dominate a decile portfolio and distort the whole backtest.

### Filters Added

Added two simple filters:

- Exclude stock-months with price below $5
- Exclude stock-months with absolute monthly return above 300%

The paper uses CRSP and a lower price filter. Since this project uses Yahoo Finance data, the extreme-return filter is a practical data-cleaning step rather than a direct paper replication choice.

### S&P 1500 Results After Filtering

| Metric | K=1 Total | K=1 Residual | K=3 Total | K=3 Residual |
|---|---:|---:|---:|---:|
| Annualized Return | -2.25% | 2.14% | 0.08% | 3.37% |
| Annualized Volatility | 19.94% | 10.44% | 19.23% | 9.72% |
| Sharpe | -0.11 | 0.21 | 0.00 | 0.35 |
| Max Drawdown | -52.29% | -20.09% | -42.34% | -18.48% |

The expanded universe did not produce strong alpha, but residual momentum looked more stable than total-return momentum. Volatility was roughly cut in half, and drawdowns improved materially.

Main takeaway:

> Universe expansion helped stabilize the research setup, but the stronger and more consistent result is risk reduction rather than high standalone returns.

---

## Day 3 (Wed): Main Pipeline Results and Conditional Factor Attribution

Ran the cleaned residual momentum pipeline on the S&P 1500 universe for multiple holding periods.

The main portfolio-level result was consistent across K=1, K=3, and K=6: residual momentum had much lower volatility than total-return momentum.

| Holding Period | Total Ann. Return | Residual Ann. Return | Total Volatility | Residual Volatility | Total Max DD | Residual Max DD |
|---:|---:|---:|---:|---:|---:|---:|
| K=1 | -2.25% | 2.14% | 19.94% | 10.44% | -52.29% | -20.09% |
| K=3 | 0.08% | 3.37% | 19.23% | 9.72% | -42.34% | -18.48% |
| K=6 | 0.41% | 2.17% | 18.86% | 9.01% | -43.25% | -21.67% |

This is not a strong return result, but it is a consistent risk result.

### Conditional Fama-French Attribution

The conditional Fama-French regression produced one of the clearest diagnostics of the project.

| Strategy | R² | Adjusted R² |
|---|---:|---:|
| Total-return momentum | 0.388 | 0.340 |
| Residual momentum | 0.077 | 0.004 |

Total-return momentum showed meaningful dynamic exposure to Fama-French factors. Residual momentum substantially reduced that exposure.

Main takeaway:

> The conditional attribution supports the paper’s core mechanism in this sample: residualization reduces the common-factor component embedded in conventional momentum.

This result helped shape the main interpretation of the project. I should not present residual momentum as a strong standalone return predictor in this sample. The more defensible conclusion is that residualization improves the risk and factor-exposure profile of momentum portfolios.

---

## Day 4 (Thu): Crisis Study, Calendar Effects, Decile Characteristics, and IC Diagnostics

Today I added several paper-inspired diagnostics and moved the script closer to a clean research pipeline. The goal was not only to compare total-return momentum and residual momentum at the portfolio level, but also to understand why their behaviour differs.

### Code Refactor

Refactored `residual_momentum.py` so that most diagnostic code is now separated into helper functions rather than sitting directly in the main block.

Diagnostic functions now include:

- `print_d1_d10_composition`
- `print_stock_forensics`
- `print_worst_months`

These functions are currently kept optional/commented out in the main execution flow. The main script now follows a cleaner multi-phase structure, with the core pipeline focused on data preparation, signal construction, portfolio formation, attribution, and diagnostics.

This makes the file easier to run end-to-end while still preserving deeper forensic tools for debugging and interpretation.

### Figure 3-Style Crisis Case Study

Added a crisis-month case study inspired by Figure 3 of Blitz, Huij, and Martens. The purpose is to check whether total-return momentum suffers more during sharp market reversals, while residual momentum is less exposed.

The clearest episode in my sample is 2020.

In April 2020:

| Series | Return |
|---|---:|
| RMRF | +13.6% |
| Total Momentum | -8.9% |
| Residual Momentum | -1.0% |

In November 2020:

| Series | Return |
|---|---:|
| RMRF | +12.4% |
| Total Momentum | -23.6% |
| Residual Momentum | -2.5% |

These months are directionally consistent with the mechanism discussed in the paper. During sharp market rebounds, total-return momentum can be exposed to factor reversals and experience large losses. Residual momentum also lost money in these episodes, but the losses were much smaller.

I would not describe this as a full replication of the paper’s 2009 case, because the sample, universe, and crisis dynamics are different. However, it is a useful case study showing that the same type of market-reversal vulnerability appears in the modern sample.

The 2022 results were less clean. Some months showed the expected pattern, but the year was also affected by the rate-hike/value regime. This makes 2022 more of a supplementary diagnostic than a central example.

### Table 6-Style Calendar Month Effects

Added a calendar-month analysis inspired by Table 6 of the paper.

The paper predicts that total-return momentum should perform poorly in January due to tax-loss selling and the rebound of loser stocks, while residual momentum should be less affected.

In my sample:

| Month | Total Momentum | Residual Momentum |
|---|---:|---:|
| January | -2.52% | -1.40% |
| December | -2.68% | -0.58% |

The January result is directionally consistent with the paper: total-return momentum loses more than residual momentum. The magnitude for total momentum is also close to the paper’s reported January return.

However, the December pattern does not match the paper. In the original paper, December is positive for total-return momentum, which supports the tax-loss selling story. In my sample, December is negative for both strategies, although residual momentum again loses less.

Given that the backtest has only around seven observations per calendar month, I treat this as a diagnostic rather than a strong seasonal result.

Main takeaway:

> The January effect appears directionally consistent with the paper, but the short sample and the reversed December pattern prevent a strong replication claim.

### Table 5-Style Decile Characteristics

Added decile-level factor exposure diagnostics to understand whether residual momentum produces cleaner portfolios than total-return momentum.

This produced one of the strongest pieces of evidence for the residualization mechanism.

For the total-return momentum D10-D1 hedge portfolio:

| Exposure | Estimate |
|---|---:|
| Market beta | -0.26 |
| SMB | -0.45 |
| HML | -0.42 |
| R² | 0.28 |

For the residual momentum D10-D1 hedge portfolio:

| Exposure | Estimate |
|---|---:|
| Market beta | -0.06 |
| SMB | -0.08 |
| HML | 0.01 |
| R² | 0.03 |

This suggests that total-return momentum still carries meaningful market, size, and value exposure, while residual momentum is much closer to factor-neutral.

The per-decile results also help explain the shape of the decile returns. Total-return momentum shows a stronger beta pattern across deciles, while residual momentum has much more uniform beta exposure across the decile portfolios.

Main takeaway:

> Residual momentum does not just reduce portfolio volatility; it also produces a cleaner cross-section with substantially lower factor exposure.

### Cross-Sectional IC Analysis

Added a stock-level IC diagnostic to measure whether the signals have one-month-ahead cross-sectional predictive power.

| Signal | IC Mean | IC Std | IC IR | Hit Rate | t-stat |
|---|---:|---:|---:|---:|---:|
| Total Momentum | -0.0042 | 0.1750 | -0.0239 | 54.9% | -0.22 |
| Residual Momentum | 0.0067 | 0.1056 | 0.0633 | 56.1% | 0.57 |

The IC results are weak and statistically insignificant for both signals.

Residual momentum has the right sign and a slightly higher hit rate, but the evidence is not strong enough to claim meaningful stock-level predictability. The main value of residual momentum in this sample appears to come from lower volatility, lower drawdowns, and reduced factor exposure rather than strong one-month cross-sectional prediction.

One useful observation is that the residual momentum IC is less volatile than the total momentum IC. The IC volatility ratio is approximately:

```text
0.1056 / 0.1750 ≈ 0.60
```

This is directionally consistent with the portfolio-level result that residual momentum has much lower volatility.

Main takeaway:

> The IC analysis does not show strong alpha, but it supports the broader interpretation that residual momentum produces a more stable and less factor-driven signal.

### README and Research Log Cleanup

Started restructuring the GitHub-facing documentation.

The README is now closer to a landing page rather than a full research report. It highlights the main residual momentum case study, gives a concise overview of the workflow, summarizes key findings, and links to the code, research logs, and future report.

The research logs are being repositioned as chronological development notes rather than polished strategy claims. This is important because the early parts of the project were exploratory and should not be presented as final research conclusions.

Main takeaway:

> The repository should present residual momentum as the main reviewed case study, while earlier experiments remain documented as exploratory research logs.

---

## Days 5–7 (Fri–Sun): Report Planning and Wrap-Up

The next step is to turn the residual momentum work into a structured research report rather than continuing to add diagnostics indefinitely.

The report should be framed around three themes:

1. **Risk reduction** — strongly supported in this sample.
2. **Alpha generation** — weak and period-dependent.
3. **Universe and data sensitivity** — clearly demonstrated through the S&P 500 to S&P 1500 expansion and the Yahoo Finance data-quality issue.

Planned report sections:

- Paper motivation
- Data and universe construction
- Signal methodology
- Portfolio construction
- Main holding-period results
- Conditional Fama-French attribution
- Crisis-month case study
- Calendar-month effects
- Decile characteristics
- Cross-sectional IC analysis
- Limitations
- Final interpretation

---

## Replication Summary

| Paper mechanism | Status in this sample | Evidence |
|---|---|---|
| Residual momentum lowers volatility | Strong support | Residual volatility is 0.48–0.52x total momentum across K=1, K=3, and K=6 |
| Residual momentum reduces dynamic factor exposure | Strong support | Conditional FF R² falls from 0.388 to 0.077 |
| Residual momentum reduces drawdown | Strong support | K=1 max drawdown improves from -52.29% to -20.09% |
| D10-D1 factor exposure is reduced | Strong support | D10-D1 R² falls from 0.28 to 0.03 in decile-level diagnostics |
| Crisis-month resilience | Directional support | 2020 rebound months show much smaller losses for residual momentum |
| January effect is reduced | Partial support | January loss is smaller for residual momentum, but the sample is short and December pattern differs from the paper |
| Residual momentum improves Sharpe | Partial support | Residual Sharpe is higher, but absolute Sharpe remains modest |
| Strong standalone alpha | Not supported | Alpha and IC are weak and statistically insignificant |

---

## Current Interpretation

The strongest conclusion is not that residual momentum is a high-alpha strategy in this sample. It is that residualization changes the risk profile of momentum in a meaningful way.

Across multiple diagnostics, residual momentum appears less exposed to common Fama-French factors, less volatile, and less vulnerable to sharp market-reversal months than total-return momentum. However, the evidence for strong one-month-ahead stock-level prediction is weak.

The project should therefore be presented as a replication and stress test of the residual momentum mechanism, with the main finding that residualization is useful for factor-exposure control and portfolio stabilization in this sample.

---

## Reading List

- [x] Avellaneda & Lee (2010) — skimmed
- [x] Frazzini, Kabiller & Pedersen (2018), "Buffett's Alpha"
- [x] Blitz, Huij & Martens (2011), "Residual Momentum"
- [ ] Huij & Lansdorp (2017), "Residual Momentum Revisited"
- [ ] Grundy & Martin (2001), "Understanding the Nature of the Risks and the Source of the Rewards to Momentum Investing"
