from pathlib import Path

from factor_autoresearch.config import load_block3_screening_config


def test_load_block3_screening_config_reads_all_thresholds() -> None:
    config = load_block3_screening_config(Path("configs/block3_screening_gate_v1.toml"))

    assert config.version == "block3_screening_gate_v1"
    assert config.screening_gate_profile == "block3_screening_gate"
    assert config.admission_horizon == "5d"
    assert config.metric_compute_policy == "staged"
    assert config.screening_sample_roles == ["research", "review"]

    assert config.expression_depth_max == 8
    assert config.coverage_mean_min == 0.65
    assert config.effective_trade_days_min == 20
    assert config.min_cross_section_size == 80
    assert config.finite_ratio_min == 0.95
    assert config.std_min == 0.01
    assert config.unique_ratio_min == 0.2
    assert config.quantiles == 5

    assert config.admission_quality_metric == "quality_score"
    assert config.admission_quality_min == 0.75
    assert config.admission_stability_metric == "stability_score"
    assert config.admission_stability_min == 0.6

    assert config.batch_corr_threshold == 0.85
    assert config.library_corr_threshold == 0.8
    assert config.correlation_min_overlap == 30
    assert config.tie_break_order == ["quality_score", "stability_score", "coverage_mean"]

    assert config.replacement_quality_metric == "quality_score"
    assert config.replacement_absolute_quality_min == 0.8
    assert config.replacement_improvement_ratio_min == 0.1
    assert config.correlated_factor_count_required == 2

    assert config.directional_long_short_sharpe_min == 0.3
    assert config.long_short_effective_days_min == 15
    assert config.monotonicity_score_min == 0.55
    assert config.turnover_proxy_max == 2.0
