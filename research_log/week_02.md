# Week 2: Fama-French Factor Attribution

**2026-05-04 ---- 2026-05-10**

---

Ran Fama-French factor attribution on all strategies. Started with
FF3 (Mkt-RF, SMB, HML), then upgraded to FF5 + Momentum (6 factors)
after discovering omitted variable bias in the Momentum strategy's
HML loading. Also compared Post-Pairs v1 vs v2 under the 6-factor
model — the OU filter introduces unintended market exposure and
significant negative alpha. Full analysis in the standalone report.

See: [Factor Attribution Report](../results/reports/factor_attribution_report.md)
