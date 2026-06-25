# Factor Autoresearch Calculation Profiling Initial Diagnosis

Date: 2026-06-24

## 1. Purpose

This note is the first profiling pass after toolchain v0 hardening.

Goal:

- Measure where `fm factor evaluate` spends time.
- Separate true calculation bottlenecks from gate / artifact overhead.
- Decide the first safe optimization target without changing evaluation semantics.

This is a diagnosis note, not an optimization patch.

## 2. Profiling Scope

Dataset:

```text
datasets/sandbox_v1
```

Candidates:

```text
candidate_factors/candidates.jsonl
30 candidates
```

Measured stages:

```text
validate
calculate
preprocess
metrics
diagnostics
gate
```

The main timing run executed all 30 candidates in memory and did not write run artifacts.
This keeps the measurement focused on calculation cost.

## 3. Stage Timing Summary

Wall time:

```text
332.167s
```

Stage summary:

| stage | total_s | mean_s_per_candidate | median_s | max_s | pct_total |
| --- | ---: | ---: | ---: | ---: | ---: |
| metrics | 148.503 | 4.950 | 4.825 | 5.872 | 44.7% |
| calculate | 91.720 | 3.057 | 0.106 | 58.893 | 27.6% |
| preprocess | 56.066 | 1.869 | 1.832 | 2.728 | 16.9% |
| diagnostics | 35.807 | 1.194 | 1.143 | 1.883 | 10.8% |
| gate | 0.045 | 0.002 | 0.001 | 0.002 | 0.0% |
| validate | 0.001 | 0.000 | 0.000 | 0.000 | 0.0% |

High-level read:

- `metrics` is the largest steady bottleneck.
- `calculate` has two extreme outliers caused by `ts_rank`.
- `preprocess` is consistently second-tier cost.
- `diagnostics` is now acceptable after the previous vectorization fix.
- `gate` and `validate` are negligible.

## 4. Calculate Outliers

Most candidates calculate quickly:

```text
median calculate ~= 0.106s
```

Two candidates dominate calculate time:

| candidate_id | actual_calculate_s | expression |
| --- | ---: | --- |
| `fa_0030_volume_rank_minus_price_rank` | 58.893 | `cs_zscore(ts_rank(volume,10)-ts_rank(close_hfq,10))` |
| `fa_0016_time_rank_mom` | about 29.7 | `ts_rank(ts_return(close_hfq,1),5)` |

Profile finding:

`ts_rank` currently uses:

```python
v.rolling(d, min_periods=d).apply(
    lambda b: pd.Series(b).rank(pct=True).iloc[-1],
    raw=False,
)
```

This creates a new `Series` and calls `rank` for every rolling window.
For `fa_0030`, it happens twice, so the cost doubles.

This is a clear optimization target, but it touches operator semantics and should be guarded by exact result comparison tests.

## 5. Metrics Hotspots

Representative profiled candidate:

```text
fa_0024_range_mean_5d
```

Non-profiled mean metrics cost:

```text
about 4.95s per candidate
```

Profile hotspots:

- Daily Pearson correlation via `Series.corr`.
- Daily RankIC via Spearman correlation.
- Daily quantile assignment via `qcut`.
- Repeated `groupby(level="trade_date")` across each horizon.

Current metrics shape:

```text
for each horizon:
  for each trade_date:
    filter universe
    drop NaN
    compute IC
    compute RankIC
    compute quantile buckets
    compute monotonicity
```

Interpretation:

- The algorithm repeats similar per-day work for every horizon.
- RankIC and quantile work are pandas-heavy and allocate many temporary objects.
- This is the best first optimization area because it is both large and steady across candidates.

## 6. Preprocess Hotspots

Representative profiled candidate:

```text
fa_0024_range_mean_5d
```

Non-profiled mean preprocess cost:

```text
about 1.87s per candidate
```

Profile hotspots:

- `neutralize_by_date`
- `winsorize_by_date`
- `zscore_by_date`

Key detail:

`neutralize_by_date` builds industry dummy matrices and runs `np.linalg.lstsq` once per trade date.

This is meaningful cost, but it is also more semantically sensitive than metrics.
Changing it can affect every downstream result.

Preprocess should be optimized after metrics and `ts_rank`, unless a purely cached design-matrix approach is implemented with strong equivalence tests.

## 7. Diagnostics Status

Current diagnostics cost:

```text
about 1.19s per candidate
35.807s total
10.8% of measured wall time
```

This is acceptable for v0 profiling.

The previous diagnostics bottleneck has already been reduced by replacing slice/day Python loops with grouped vectorized correlation calculations.

Do not optimize diagnostics first.

## 8. Initial Optimization Priority

### Priority 1: Metrics vectorization

Target:

- Reduce daily IC / RankIC computation overhead.
- Avoid repeated pandas object allocation.
- Keep `metrics.parquet`, `ic_series.parquet`, `candidate_results.jsonl`, and summary semantics identical within tolerance.

Suggested approach:

- Build a single aligned frame per candidate.
- Compute daily Pearson correlations with grouped sums rather than per-day `Series.corr`.
- Compute RankIC from grouped ranks and grouped Pearson on ranks.
- Keep quantile / monotonicity behavior unchanged at first, or isolate it behind equivalence tests.

Acceptance:

```text
same candidate_results statuses
same failed_rules
same best_horizon
same score within tight tolerance
same metrics columns
```

### Priority 2: `ts_rank` operator

Target:

- Replace rolling `Series.rank()` per window with a cheaper rolling percentile-rank implementation.

Risk:

- Tie handling and NaN behavior must match the current implementation.

Acceptance:

```text
operator-level tests for ties, NaN, min_periods, multi-stock grouping
candidate-level equality for fa_0016 and fa_0030
```

### Priority 3: Preprocess caching / vectorization

Target:

- Reuse per-date industry dummy structure where possible.
- Reduce repeated MultiIndex copying and DataFrame allocation.

Risk:

- Neutralization changes can alter all factor values.

Acceptance:

```text
processed factor equality or tight numerical tolerance
full evaluate equivalence on sandbox_v1
```

## 9. What Not To Do Yet

Do not start with:

- Parallel execution.
- Gate threshold changes.
- Dataset or forward-return changes.
- Preprocess rewrite without equivalence tests.
- Dropping quantile / monotonicity calculations.

Parallel execution may still be useful later, but it should not hide known algorithmic bottlenecks.

## 10. Recommended Next Step

Create a metrics optimization branch or patch with an explicit equivalence harness:

```text
old metrics implementation
new metrics implementation
same candidate + same dataset
compare horizon rows, ic series, gate decisions
```

Then optimize only `factor_autoresearch/metrics.py` first.

Expected upside:

- If metrics is reduced by 50%, full 30-candidate evaluate should drop by roughly 70-75 seconds.
- If `ts_rank` is optimized too, runs containing time-rank candidates should drop by another 80-90 seconds.

Combined realistic target for the current 30-candidate sandbox:

```text
current: about 5.5-6.0 minutes
near-term target: about 3.0-4.0 minutes
```

