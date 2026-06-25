# Run mainboard_pressure_v1_auto_benchmark_json Summary

## Dataset
dataset_id: mainboard_pressure_v1
experiment_id: mainboard_ohlcv_pressure_v1
universe: mainboard
date_range: 2024-01-01 to 2025-12-31
features: open_hfq, high_hfq, low_hfq, close_hfq, volume
adjustment: hfq
forward_return_definition: next_open_to_open_v1

## Batch Result
evaluated: 30
passed: 12
failed: 18
invalid: 0
errors: 0

## Candidate Results
| id | status | best_horizon | score | failure_bucket | details |
| --- | --- | --- | --- | --- | --- |
| fa_0001_range_position | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9776679803402978, "effective_trade_days": 464, "complexity_score": 8, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0002_intraday_return | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9776679803402978, "effective_trade_days": 464, "complexity_score": 6, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0003_upper_shadow_pressure | candidate_fail | 5d | 0.8 | gate_failed | {"coverage_mean": 0.9776679803402978, "effective_trade_days": 464, "complexity_score": 6, "best_horizon": "5d", "best_horizon_score": 0.8, "ic_component": 0.0, "rankic_component": 2.0, "monotonicity_component": 0.0} |
| fa_0004_lower_shadow_support | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9776679803402978, "effective_trade_days": 464, "complexity_score": 6, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0005_daily_range | candidate_pass | 20d | 1.4384269662921347 | - | {"coverage_mean": 0.9776679803402978, "effective_trade_days": 464, "complexity_score": 6, "best_horizon": "20d", "best_horizon_score": 1.4384269662921347, "ic_component": 2.0, "rankic_component": 2.0, "monotonicity_component": 0.12808988764044943} |
| fa_0006_open_gap_strength | candidate_pass | 20d | 1.0766864985854343 | - | {"coverage_mean": 0.9775423173390264, "effective_trade_days": 464, "complexity_score": 8, "best_horizon": "20d", "best_horizon_score": 1.0766864985854343, "ic_component": 0.9646128970562228, "rankic_component": 1.8843239894017556, "monotonicity_component": 0.11191011235955058} |
| fa_0007_open_gap_reversal | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9775423173390264, "effective_trade_days": 464, "complexity_score": 8, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0008_volume_change_3d | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9773324491939491, "effective_trade_days": 464, "complexity_score": 8, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0009_volume_change_5d | candidate_pass | 20d | 1.3644473097907222 | - | {"coverage_mean": 0.9771246782493669, "effective_trade_days": 464, "complexity_score": 8, "best_horizon": "20d", "best_horizon_score": 1.3644473097907222, "ic_component": 1.6889067629728196, "rankic_component": 2.0, "monotonicity_component": 0.19258426966292136} |
| fa_0010_volume_volatility | candidate_pass | 20d | 1.4794157303370785 | - | {"coverage_mean": 0.9768499528313054, "effective_trade_days": 464, "complexity_score": 9, "best_horizon": "20d", "best_horizon_score": 1.4794157303370785, "ic_component": 2.0, "rankic_component": 2.0, "monotonicity_component": 0.26471910112359553} |
| fa_0011_log_volume | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9776679803402978, "effective_trade_days": 464, "complexity_score": 3, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0012_short_vs_long_volume | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.974210673801135, "effective_trade_days": 464, "complexity_score": 9, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0013_close_mom_3d | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9773324491939491, "effective_trade_days": 464, "complexity_score": 3, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0014_close_mom_5d | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9771246782493669, "effective_trade_days": 464, "complexity_score": 3, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0015_cross_sectional_mom_5d | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9771246782493669, "effective_trade_days": 464, "complexity_score": 4, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0016_time_rank_mom | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9768499528313054, "effective_trade_days": 464, "complexity_score": 5, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0017_mean_daily_return_5d | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9768499528313054, "effective_trade_days": 464, "complexity_score": 5, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0018_mean_daily_return_10d | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9759104265551484, "effective_trade_days": 464, "complexity_score": 5, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0019_reversal_3d | candidate_pass | 20d | 1.438561797752809 | - | {"coverage_mean": 0.9773324491939491, "effective_trade_days": 464, "complexity_score": 3, "best_horizon": "20d", "best_horizon_score": 1.438561797752809, "ic_component": 2.0, "rankic_component": 2.0, "monotonicity_component": 0.12853932584269664} |
| fa_0020_reversal_5d | candidate_pass | 5d | 1.4369130434782609 | - | {"coverage_mean": 0.9771246782493669, "effective_trade_days": 464, "complexity_score": 3, "best_horizon": "5d", "best_horizon_score": 1.4369130434782609, "ic_component": 2.0, "rankic_component": 2.0, "monotonicity_component": 0.12304347826086957} |
| fa_0021_daily_vol_5d | candidate_pass | 5d | 1.440173913043478 | - | {"coverage_mean": 0.9768499528313054, "effective_trade_days": 464, "complexity_score": 5, "best_horizon": "5d", "best_horizon_score": 1.440173913043478, "ic_component": 2.0, "rankic_component": 2.0, "monotonicity_component": 0.13391304347826088} |
| fa_0022_daily_vol_10d | candidate_pass | 5d | 1.4452608695652174 | - | {"coverage_mean": 0.9759104265551484, "effective_trade_days": 464, "complexity_score": 5, "best_horizon": "5d", "best_horizon_score": 1.4452608695652174, "ic_component": 2.0, "rankic_component": 2.0, "monotonicity_component": 0.1508695652173913} |
| fa_0023_range_vol_5d | candidate_pass | 20d | 1.4698426966292133 | - | {"coverage_mean": 0.9770331837973404, "effective_trade_days": 464, "complexity_score": 7, "best_horizon": "20d", "best_horizon_score": 1.4698426966292133, "ic_component": 2.0, "rankic_component": 2.0, "monotonicity_component": 0.23280898876404493} |
| fa_0024_range_mean_5d | candidate_pass | 20d | 1.4346516853932583 | - | {"coverage_mean": 0.9770331837973404, "effective_trade_days": 464, "complexity_score": 7, "best_horizon": "20d", "best_horizon_score": 1.4346516853932583, "ic_component": 2.0, "rankic_component": 2.0, "monotonicity_component": 0.1155056179775281} |
| fa_0025_gap_mean_5d | candidate_pass | 20d | 1.1597231023282504 | - | {"coverage_mean": 0.9768499528313054, "effective_trade_days": 464, "complexity_score": 9, "best_horizon": "20d", "best_horizon_score": 1.1597231023282504, "ic_component": 1.044694985288925, "rankic_component": 2.0, "monotonicity_component": 0.15438202247191007} |
| fa_0026_gap_vol_5d | candidate_pass | 20d | 1.4623595505617977 | - | {"coverage_mean": 0.9768499528313054, "effective_trade_days": 464, "complexity_score": 9, "best_horizon": "20d", "best_horizon_score": 1.4623595505617977, "ic_component": 2.0, "rankic_component": 2.0, "monotonicity_component": 0.20786516853932585} |
| fa_0027_body_over_range | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9776679803402978, "effective_trade_days": 464, "complexity_score": 8, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0028_open_position_in_range | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9776679803402978, "effective_trade_days": 464, "complexity_score": 8, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0029_volume_vs_20d_mean | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.974210673801135, "effective_trade_days": 464, "complexity_score": 6, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0030_volume_rank_minus_price_rank | candidate_fail | 5d | 0.252479020107194 | gate_failed | {"coverage_mean": 0.9760998585998873, "effective_trade_days": 464, "complexity_score": 8, "best_horizon": "5d", "best_horizon_score": 0.252479020107194, "ic_component": 0.5684540315308338, "rankic_component": 0.20485702661985952, "monotonicity_component": 0.0} |

## Top Horizon Rows
| id | horizon | ic_mean | rankic_mean | monotonicity | coverage_mean | complexity |
| --- | --- | --- | --- | --- | --- | --- |
| fa_0025_gap_mean_5d | 20d | 0.010447 | 0.022420 | 0.154382 | 0.952045 | 9 |
| fa_0028_open_position_in_range | 1d | 0.007315 | 0.020190 | 0.037069 | 0.994662 | 8 |
| fa_0007_open_gap_reversal | 20d | 0.009646 | 0.018843 | 0.111910 | 0.952709 | 8 |
| fa_0006_open_gap_strength | 20d | 0.009646 | 0.018843 | 0.111910 | 0.952709 | 8 |
| fa_0028_open_position_in_range | 20d | 0.007592 | 0.017681 | 0.082022 | 0.952829 | 8 |
