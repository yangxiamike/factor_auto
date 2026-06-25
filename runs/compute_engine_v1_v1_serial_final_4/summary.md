# Run compute_engine_v1_v1_serial_final_4 Summary

## Dataset
dataset_id: sandbox_v1
experiment_id: csi500_ohlcv_sandbox_v1
universe: csi500
date_range: 2024-01-01 to 2025-12-31
features: open_hfq, high_hfq, low_hfq, close_hfq, volume
adjustment: hfq
forward_return_definition: next_open_to_open_v1

## Batch Result
evaluated: 30
passed: 8
failed: 22
invalid: 0
errors: 0

## Candidate Results
| id | status | best_horizon | score | failure_bucket | details |
| --- | --- | --- | --- | --- | --- |
| fa_0001_range_position | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.978615082743369, "effective_trade_days": 462, "complexity_score": 8, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0002_intraday_return | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.978615082743369, "effective_trade_days": 462, "complexity_score": 6, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0003_upper_shadow_pressure | candidate_fail | 20d | 0.8 | gate_failed | {"coverage_mean": 0.978615082743369, "effective_trade_days": 462, "complexity_score": 6, "best_horizon": "20d", "best_horizon_score": 0.8, "ic_component": 0.0, "rankic_component": 2.0, "monotonicity_component": 0.0} |
| fa_0004_lower_shadow_support | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.978615082743369, "effective_trade_days": 462, "complexity_score": 6, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0005_daily_range | candidate_pass | 20d | 1.1590472109701826 | - | {"coverage_mean": 0.978615082743369, "effective_trade_days": 462, "complexity_score": 6, "best_horizon": "20d", "best_horizon_score": 1.1590472109701826, "ic_component": 1.1568691832941371, "rankic_component": 2.0, "monotonicity_component": 0.039954853273137685} |
| fa_0006_open_gap_strength | candidate_fail | 20d | 0.6595286637051999 | gate_failed | {"coverage_mean": 0.9785502804475964, "effective_trade_days": 462, "complexity_score": 8, "best_horizon": "20d", "best_horizon_score": 0.6595286637051999, "ic_component": 0.7368983880702984, "rankic_component": 1.0556851142599373, "monotonicity_component": 0.05395033860045145} |
| fa_0007_open_gap_reversal | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9785502804475964, "effective_trade_days": 462, "complexity_score": 8, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0008_volume_change_3d | candidate_fail | 1d | 0.10715636758249986 | gate_failed | {"coverage_mean": 0.9784063401300438, "effective_trade_days": 462, "complexity_score": 8, "best_horizon": "1d", "best_horizon_score": 0.10715636758249986, "ic_component": 0.3463653811191554, "rankic_component": 0.0, "monotonicity_component": 0.010822510822510815} |
| fa_0009_volume_change_5d | candidate_fail | 5d | 0.921361686510564 | gate_failed | {"coverage_mean": 0.9782853907785419, "effective_trade_days": 462, "complexity_score": 8, "best_horizon": "5d", "best_horizon_score": 0.921361686510564, "ic_component": 0.7606071260042853, "rankic_component": 1.7077305311618423, "monotonicity_component": 0.033624454148471594} |
| fa_0010_volume_volatility | candidate_pass | 5d | 1.102029419828257 | - | {"coverage_mean": 0.9782076054468304, "effective_trade_days": 462, "complexity_score": 9, "best_horizon": "5d", "best_horizon_score": 1.102029419828257, "ic_component": 0.9447242364710288, "rankic_component": 1.9828294988549249, "monotonicity_component": 0.08493449781659387} |
| fa_0011_log_volume | candidate_fail | 20d | 0.24195330166294493 | gate_failed | {"coverage_mean": 0.978615082743369, "effective_trade_days": 462, "complexity_score": 3, "best_horizon": "20d", "best_horizon_score": 0.24195330166294493, "ic_component": 0.7672333531729467, "rankic_component": 0.0, "monotonicity_component": 0.03927765237020315} |
| fa_0012_short_vs_long_volume | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9769204666299657, "effective_trade_days": 462, "complexity_score": 9, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0013_close_mom_3d | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9784063401300438, "effective_trade_days": 462, "complexity_score": 3, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0014_close_mom_5d | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9782853907785419, "effective_trade_days": 462, "complexity_score": 3, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0015_cross_sectional_mom_5d | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9782853907785419, "effective_trade_days": 462, "complexity_score": 4, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0016_time_rank_mom | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9782076054468304, "effective_trade_days": 462, "complexity_score": 5, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0017_mean_daily_return_5d | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9782076054468304, "effective_trade_days": 462, "complexity_score": 5, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0018_mean_daily_return_10d | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9777671975894081, "effective_trade_days": 462, "complexity_score": 5, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0019_reversal_3d | candidate_pass | 5d | 1.191153777930802 | - | {"coverage_mean": 0.9784063401300438, "effective_trade_days": 462, "complexity_score": 3, "best_horizon": "5d", "best_horizon_score": 1.191153777930802, "ic_component": 1.2527542233792375, "rankic_component": 2.0, "monotonicity_component": 0.05109170305676856} |
| fa_0020_reversal_5d | candidate_pass | 5d | 1.1894248269842402 | - | {"coverage_mean": 0.9782853907785419, "effective_trade_days": 462, "complexity_score": 3, "best_horizon": "5d", "best_horizon_score": 1.1894248269842402, "ic_component": 1.2598731496272344, "rankic_component": 2.0, "monotonicity_component": 0.03820960698689956} |
| fa_0021_daily_vol_5d | candidate_pass | 20d | 1.1917955267930767 | - | {"coverage_mean": 0.9782076054468304, "effective_trade_days": 462, "complexity_score": 5, "best_horizon": "20d", "best_horizon_score": 1.1917955267930767, "ic_component": 1.2366848635766208, "rankic_component": 2.0, "monotonicity_component": 0.0693002257336343} |
| fa_0022_daily_vol_10d | candidate_pass | 20d | 1.256175030124846 | - | {"coverage_mean": 0.9777671975894081, "effective_trade_days": 462, "complexity_score": 5, "best_horizon": "20d", "best_horizon_score": 1.256175030124846, "ic_component": 1.4269039755102086, "rankic_component": 2.0, "monotonicity_component": 0.09367945823927762} |
| fa_0023_range_vol_5d | candidate_pass | 20d | 1.4283069977426635 | - | {"coverage_mean": 0.9782954598379492, "effective_trade_days": 462, "complexity_score": 7, "best_horizon": "20d", "best_horizon_score": 1.4283069977426635, "ic_component": 2.0, "rankic_component": 2.0, "monotonicity_component": 0.09435665914221217} |
| fa_0024_range_mean_5d | candidate_pass | 20d | 1.425395033860045 | - | {"coverage_mean": 0.9782954598379492, "effective_trade_days": 462, "complexity_score": 7, "best_horizon": "20d", "best_horizon_score": 1.425395033860045, "ic_component": 2.0, "rankic_component": 2.0, "monotonicity_component": 0.08465011286681715} |
| fa_0025_gap_mean_5d | candidate_fail | 20d | 0.7723085921319538 | gate_failed | {"coverage_mean": 0.9782076054468304, "effective_trade_days": 462, "complexity_score": 9, "best_horizon": "20d", "best_horizon_score": 0.7723085921319538, "ic_component": 0.88164035610338, "rankic_component": 1.2233222516270672, "monotonicity_component": 0.06162528216704288} |
| fa_0026_gap_vol_5d | candidate_fail | 20d | 0.8875776181364438 | gate_failed | {"coverage_mean": 0.9782076054468304, "effective_trade_days": 462, "complexity_score": 9, "best_horizon": "20d", "best_horizon_score": 0.8875776181364438, "ic_component": 0.24339266241117052, "rankic_component": 2.0, "monotonicity_component": 0.048532731376975155} |
| fa_0027_body_over_range | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.978615082743369, "effective_trade_days": 462, "complexity_score": 8, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0028_open_position_in_range | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.978615082743369, "effective_trade_days": 462, "complexity_score": 8, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0029_volume_vs_20d_mean | candidate_fail | 1d | 0.06616560969828403 | gate_failed | {"coverage_mean": 0.9769204666299657, "effective_trade_days": 462, "complexity_score": 6, "best_horizon": "1d", "best_horizon_score": 0.06616560969828403, "ic_component": 0.21297627475185585, "rankic_component": 0.0, "monotonicity_component": 0.007575757575757567} |
| fa_0030_volume_rank_minus_price_rank | candidate_fail | 1d | 0.4562713384755916 | gate_failed | {"coverage_mean": 0.9778579051437647, "effective_trade_days": 462, "complexity_score": 8, "best_horizon": "1d", "best_horizon_score": 0.4562713384755916, "ic_component": 0.4885226187939191, "rankic_component": 0.7684422262493837, "monotonicity_component": 0.007792207792207791} |

## Top Horizon Rows
| id | horizon | ic_mean | rankic_mean | monotonicity | coverage_mean | complexity |
| --- | --- | --- | --- | --- | --- | --- |
| fa_0028_open_position_in_range | 1d | 0.003934 | 0.016904 | 0.046753 | 0.995482 | 8 |
| fa_0025_gap_mean_5d | 20d | 0.008816 | 0.012233 | 0.061625 | 0.953406 | 9 |
| fa_0007_open_gap_reversal | 20d | 0.007369 | 0.010557 | 0.053950 | 0.953739 | 8 |
| fa_0006_open_gap_strength | 20d | 0.007369 | 0.010557 | 0.053950 | 0.953739 | 8 |
| fa_0028_open_position_in_range | 5d | 0.000836 | 0.008013 | 0.005240 | 0.986559 | 8 |
