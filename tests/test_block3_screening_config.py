from pathlib import Path

from factor_autoresearch.config import load_block3_screening_config


def test_load_block3_screening_config_reads_all_gate_thresholds() -> None:
    config = load_block3_screening_config(Path("configs/block3_screening_gate_v1.toml"))

    assert config.version == "block3_screening_gate_v1"
    assert config.screening_gate_profile == "initial_research_factorminer_like_v1"
    assert config.admission_horizon == "5d"
    assert config.metric_compute_policy == "staged"
    assert config.screening_sample_roles == ["validation"]
    assert config.expression_depth_max == 8
    assert config.coverage_mean_min == 0.70
    assert config.effective_trade_days_min == 120
    assert config.min_cross_section_size == 100
    assert config.finite_ratio_min == 0.99
    assert config.std_min == 1e-12
    assert config.unique_ratio_min == 0.01
    assert config.quantiles == 5
    assert config.admission_quality_metric == "directional_rankic_mean"
    assert config.admission_quality_min == 0.04
    assert config.admission_stability_metric == "directional_rankic_ir"
    assert config.admission_stability_min == 0.50
    assert config.batch_corr_threshold == 0.50
    assert config.library_corr_threshold == 0.50
    assert config.correlation_min_overlap == 10000
    assert config.tie_break_order == [
        "directional_rankic_mean",
        "directional_rankic_ir",
        "coverage_mean",
    ]
    assert config.replacement_quality_metric == "directional_rankic_mean"
    assert config.replacement_absolute_quality_min == 0.10
    assert config.replacement_improvement_ratio_min == 1.30
    assert config.correlated_factor_count_required == 1
    assert config.directional_long_short_sharpe_min == 1.00
    assert config.long_short_effective_days_min == 50
    assert config.monotonicity_score_min == 0.30
    assert config.turnover_proxy_max == 0.70
