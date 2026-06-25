# Run toolchain_v0_smoke Summary

## Dataset
- dataset_id: sandbox_v1
- experiment_id: csi500_ohlcv_sandbox_v1
- universe: csi500
- date_range: 2024-01-01 to 2025-12-31

## Batch Result
- evaluated: 30
- passed: 0
- failed: 30
- invalid: 0
- errors: 0

## Candidate Results
| id | status | best_horizon | score | failed_rules | failure_bucket |
| --- | --- | --- | --- | --- | --- |
| fa_0001_range_position | candidate_fail | 1d | 0.0 | best_horizon_directional_ic_mean,best_horizon_directional_rankic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio,best_horizon_directional_monotonicity | gate_failed |
| fa_0002_intraday_return | candidate_fail | 1d | 0.0 | best_horizon_directional_ic_mean,best_horizon_directional_rankic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio,best_horizon_directional_monotonicity | gate_failed |
| fa_0003_upper_shadow_pressure | candidate_fail | 20d | 0.9 | best_horizon_directional_ic_mean,best_horizon_directional_rankic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio,best_horizon_directional_monotonicity | gate_failed |
| fa_0004_lower_shadow_support | candidate_fail | 1d | 0.0 | best_horizon_directional_ic_mean,best_horizon_directional_rankic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio,best_horizon_directional_monotonicity | gate_failed |
| fa_0005_daily_range | candidate_fail | 20d | 1.2570494683065285 | best_horizon_directional_ic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio | gate_failed |
| fa_0006_open_gap_strength | candidate_fail | 20d | 0.7096154024881761 | best_horizon_directional_ic_mean,best_horizon_directional_rankic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio | gate_failed |
| fa_0007_open_gap_reversal | candidate_fail | 1d | 0.0 | best_horizon_directional_ic_mean,best_horizon_directional_rankic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio,best_horizon_directional_monotonicity | gate_failed |
| fa_0008_volume_change_3d | candidate_fail | 1d | 0.10661524204137313 | best_horizon_directional_ic_mean,best_horizon_directional_rankic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio | gate_failed |
| fa_0009_volume_change_5d | candidate_fail | 5d | 1.005066990361229 | best_horizon_directional_ic_mean,best_horizon_directional_rankic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio | gate_failed |
| fa_0010_volume_volatility | candidate_fail | 5d | 1.196924169880176 | best_horizon_directional_ic_mean,best_horizon_directional_rankic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio | gate_failed |
| fa_0011_log_volume | candidate_fail | 20d | 0.23998941904443322 | best_horizon_directional_ic_mean,best_horizon_directional_rankic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio | gate_failed |
| fa_0012_short_vs_long_volume | candidate_fail | 1d | 0.0 | best_horizon_directional_ic_mean,best_horizon_directional_rankic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio,best_horizon_directional_monotonicity | gate_failed |
| fa_0013_close_mom_3d | candidate_fail | 1d | 0.0 | best_horizon_directional_ic_mean,best_horizon_directional_rankic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio,best_horizon_directional_monotonicity | gate_failed |
| fa_0014_close_mom_5d | candidate_fail | 1d | 0.0 | best_horizon_directional_ic_mean,best_horizon_directional_rankic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio,best_horizon_directional_monotonicity | gate_failed |
| fa_0015_cross_sectional_mom_5d | candidate_fail | 1d | 0.0 | best_horizon_directional_ic_mean,best_horizon_directional_rankic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio,best_horizon_directional_monotonicity | gate_failed |
| fa_0016_time_rank_mom | candidate_fail | 1d | 0.0 | best_horizon_directional_ic_mean,best_horizon_directional_rankic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio,best_horizon_directional_monotonicity | gate_failed |
| fa_0017_mean_daily_return_5d | candidate_fail | 1d | 0.0 | best_horizon_directional_ic_mean,best_horizon_directional_rankic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio,best_horizon_directional_monotonicity | gate_failed |
| fa_0018_mean_daily_return_10d | candidate_fail | 1d | 0.0 | best_horizon_directional_ic_mean,best_horizon_directional_rankic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio,best_horizon_directional_monotonicity | gate_failed |
| fa_0019_reversal_3d | candidate_fail | 5d | 1.288599192777962 | best_horizon_directional_ic_mean,best_horizon_directional_rankic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio | gate_failed |
| fa_0020_reversal_5d | candidate_fail | 5d | 1.287514346634892 | best_horizon_directional_ic_mean,best_horizon_directional_rankic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio | gate_failed |
| fa_0021_daily_vol_5d | candidate_fail | 20d | 1.2883305155063938 | best_horizon_directional_ic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio | gate_failed |
| fa_0022_daily_vol_10d | candidate_fail | 20d | 1.3514910572128844 | best_horizon_directional_ic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio | gate_failed |
| fa_0023_range_vol_5d | candidate_fail | 20d | 1.523589164785553 | best_horizon_directional_ic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio | gate_failed |
| fa_0024_range_mean_5d | candidate_fail | 20d | 1.5211625282167043 | best_horizon_directional_ic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio | gate_failed |
| fa_0025_gap_mean_5d | candidate_fail | 20d | 0.8303934406049569 | best_horizon_directional_ic_mean,best_horizon_directional_rankic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio | gate_failed |
| fa_0026_gap_vol_5d | candidate_fail | 20d | 0.9851509814123193 | best_horizon_directional_ic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio | gate_failed |
| fa_0027_body_over_range | candidate_fail | 1d | 0.0 | best_horizon_directional_ic_mean,best_horizon_directional_rankic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio,best_horizon_directional_monotonicity | gate_failed |
| fa_0028_open_position_in_range | candidate_fail | 1d | 0.0 | best_horizon_directional_ic_mean,best_horizon_directional_rankic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio,best_horizon_directional_monotonicity | gate_failed |
| fa_0029_volume_vs_20d_mean | candidate_fail | 1d | 0.06578682181949744 | best_horizon_directional_ic_mean,best_horizon_directional_rankic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio | gate_failed |
| fa_0030_volume_rank_minus_price_rank | candidate_fail | 1d | 0.4943038393984521 | best_horizon_directional_ic_mean,best_horizon_directional_rankic_mean,best_horizon_ic_positive_ratio,best_horizon_rankic_positive_ratio | gate_failed |

## Failed Rules Summary
| rule | count |
| --- | --- |
| best_horizon_directional_ic_mean | 30 |
| best_horizon_ic_positive_ratio | 30 |
| best_horizon_rankic_positive_ratio | 30 |
| best_horizon_directional_rankic_mean | 24 |
| best_horizon_directional_monotonicity | 14 |

## Passed Candidates
- none

## Diagnostics
- runs\toolchain_v0_smoke\results\diagnostics.parquet
