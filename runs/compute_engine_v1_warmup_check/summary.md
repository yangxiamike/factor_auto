# Run compute_engine_v1_warmup_check Summary

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
| fa_0005_daily_range | candidate_pass | 20d | 1.1584377301575417 | - | {"coverage_mean": 0.978615082743369, "effective_trade_days": 462, "complexity_score": 6, "best_horizon": "20d", "best_horizon_score": 1.1584377301575417, "ic_component": 1.156869183294138, "rankic_component": 2.0, "monotonicity_component": 0.03792325056433409} |
| fa_0006_open_gap_strength | candidate_fail | 20d | 0.6596641038857867 | gate_failed | {"coverage_mean": 0.9785502804475964, "effective_trade_days": 462, "complexity_score": 8, "best_horizon": "20d", "best_horizon_score": 0.6596641038857867, "ic_component": 0.7368983880702981, "rankic_component": 1.0556851142599373, "monotonicity_component": 0.0544018058690745} |
| fa_0007_open_gap_reversal | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9785502804475964, "effective_trade_days": 462, "complexity_score": 8, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0008_volume_change_3d | candidate_fail | 1d | 0.10735117277730494 | gate_failed | {"coverage_mean": 0.9784063401300438, "effective_trade_days": 462, "complexity_score": 8, "best_horizon": "1d", "best_horizon_score": 0.10735117277730494, "ic_component": 0.346365381119155, "rankic_component": 0.0, "monotonicity_component": 0.011471861471861473} |
| fa_0009_volume_change_5d | candidate_fail | 5d | 0.9213616865105643 | gate_failed | {"coverage_mean": 0.9782853907785419, "effective_trade_days": 462, "complexity_score": 8, "best_horizon": "5d", "best_horizon_score": 0.9213616865105643, "ic_component": 0.7606071260042853, "rankic_component": 1.7077305311618427, "monotonicity_component": 0.03362445414847161} |
| fa_0010_volume_volatility | candidate_pass | 5d | 1.1020949220116627 | - | {"coverage_mean": 0.9782076054468304, "effective_trade_days": 462, "complexity_score": 9, "best_horizon": "5d", "best_horizon_score": 1.1020949220116627, "ic_component": 0.9447242364710285, "rankic_component": 1.9828294988549249, "monotonicity_component": 0.0851528384279476} |
| fa_0011_log_volume | candidate_fail | 20d | 0.24215646193382542 | gate_failed | {"coverage_mean": 0.978615082743369, "effective_trade_days": 462, "complexity_score": 3, "best_horizon": "20d", "best_horizon_score": 0.24215646193382542, "ic_component": 0.767233353172947, "rankic_component": 0.0, "monotonicity_component": 0.0399548532731377} |
| fa_0012_short_vs_long_volume | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9769204666299657, "effective_trade_days": 462, "complexity_score": 9, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0013_close_mom_3d | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9784063401300438, "effective_trade_days": 462, "complexity_score": 3, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0014_close_mom_5d | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9782853907785419, "effective_trade_days": 462, "complexity_score": 3, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0015_cross_sectional_mom_5d | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9782853907785419, "effective_trade_days": 462, "complexity_score": 4, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0016_time_rank_mom | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9782076054468304, "effective_trade_days": 462, "complexity_score": 5, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0017_mean_daily_return_5d | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9782076054468304, "effective_trade_days": 462, "complexity_score": 5, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0018_mean_daily_return_10d | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.9777671975894081, "effective_trade_days": 462, "complexity_score": 5, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0019_reversal_3d | candidate_pass | 5d | 1.1909572713805836 | - | {"coverage_mean": 0.9784063401300438, "effective_trade_days": 462, "complexity_score": 3, "best_horizon": "5d", "best_horizon_score": 1.1909572713805836, "ic_component": 1.252754223379238, "rankic_component": 2.0, "monotonicity_component": 0.050436681222707426} |
| fa_0020_reversal_5d | candidate_pass | 5d | 1.1893593248008343 | - | {"coverage_mean": 0.9782853907785419, "effective_trade_days": 462, "complexity_score": 3, "best_horizon": "5d", "best_horizon_score": 1.1893593248008343, "ic_component": 1.2598731496272353, "rankic_component": 2.0, "monotonicity_component": 0.03799126637554585} |
| fa_0021_daily_vol_5d | candidate_pass | 20d | 1.1915923665221964 | - | {"coverage_mean": 0.9782076054468304, "effective_trade_days": 462, "complexity_score": 5, "best_horizon": "20d", "best_horizon_score": 1.1915923665221964, "ic_component": 1.2366848635766214, "rankic_component": 2.0, "monotonicity_component": 0.06862302483069978} |
| fa_0022_daily_vol_10d | candidate_pass | 20d | 1.2561750301248458 | - | {"coverage_mean": 0.9777671975894081, "effective_trade_days": 462, "complexity_score": 5, "best_horizon": "20d", "best_horizon_score": 1.2561750301248458, "ic_component": 1.4269039755102084, "rankic_component": 2.0, "monotonicity_component": 0.09367945823927763} |
| fa_0023_range_vol_5d | candidate_pass | 20d | 1.42823927765237 | - | {"coverage_mean": 0.9782954598379492, "effective_trade_days": 462, "complexity_score": 7, "best_horizon": "20d", "best_horizon_score": 1.42823927765237, "ic_component": 2.0, "rankic_component": 2.0, "monotonicity_component": 0.0941309255079007} |
| fa_0024_range_mean_5d | candidate_pass | 20d | 1.4251918735891647 | - | {"coverage_mean": 0.9782954598379492, "effective_trade_days": 462, "complexity_score": 7, "best_horizon": "20d", "best_horizon_score": 1.4251918735891647, "ic_component": 2.0, "rankic_component": 2.0, "monotonicity_component": 0.08397291196388262} |
| fa_0025_gap_mean_5d | candidate_fail | 20d | 0.7725117524028339 | gate_failed | {"coverage_mean": 0.9782076054468304, "effective_trade_days": 462, "complexity_score": 9, "best_horizon": "20d", "best_horizon_score": 0.7725117524028339, "ic_component": 0.8816403561033792, "rankic_component": 1.2233222516270672, "monotonicity_component": 0.06230248306997743} |
| fa_0026_gap_vol_5d | candidate_fail | 20d | 0.8874421779558569 | gate_failed | {"coverage_mean": 0.9782076054468304, "effective_trade_days": 462, "complexity_score": 9, "best_horizon": "20d", "best_horizon_score": 0.8874421779558569, "ic_component": 0.2433926624111709, "rankic_component": 2.0, "monotonicity_component": 0.04808126410835214} |
| fa_0027_body_over_range | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.978615082743369, "effective_trade_days": 462, "complexity_score": 8, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0028_open_position_in_range | candidate_fail | 1d | 0.0 | gate_failed | {"coverage_mean": 0.978615082743369, "effective_trade_days": 462, "complexity_score": 8, "best_horizon": "1d", "best_horizon_score": 0.0, "ic_component": 0.0, "rankic_component": 0.0, "monotonicity_component": 0.0} |
| fa_0029_volume_vs_20d_mean | candidate_fail | 1d | 0.06558119411386835 | gate_failed | {"coverage_mean": 0.9769204666299657, "effective_trade_days": 462, "complexity_score": 6, "best_horizon": "1d", "best_horizon_score": 0.06558119411386835, "ic_component": 0.2129762747518556, "rankic_component": 0.0, "monotonicity_component": 0.005627705627705623} |
| fa_0030_volume_rank_minus_price_rank | candidate_fail | 1d | 0.456660948865202 | gate_failed | {"coverage_mean": 0.9778579051437647, "effective_trade_days": 462, "complexity_score": 8, "best_horizon": "1d", "best_horizon_score": 0.456660948865202, "ic_component": 0.4885226187939191, "rankic_component": 0.7684422262493837, "monotonicity_component": 0.009090909090909084} |

## Top Horizon Rows
| id | horizon | ic_mean | rankic_mean | monotonicity | coverage_mean | complexity |
| --- | --- | --- | --- | --- | --- | --- |
| fa_0028_open_position_in_range | 1d | 0.003934 | 0.016904 | 0.046970 | 0.995482 | 8 |
| fa_0025_gap_mean_5d | 20d | 0.008816 | 0.012233 | 0.062302 | 0.953406 | 9 |
| fa_0007_open_gap_reversal | 20d | 0.007369 | 0.010557 | 0.054402 | 0.953739 | 8 |
| fa_0006_open_gap_strength | 20d | 0.007369 | 0.010557 | 0.054402 | 0.953739 | 8 |
| fa_0028_open_position_in_range | 5d | 0.000836 | 0.008013 | 0.005022 | 0.986559 | 8 |
