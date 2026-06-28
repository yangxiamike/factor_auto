"""区块3 Gate 测试: 只验证决策分流，不承担指标计算。"""

from __future__ import annotations

import math

import pytest

from factor_autoresearch.block3_screening import (
    Block3GateInputs,
    Block3MetricContractError,
    apply_block3_screening_gate,
)
from factor_autoresearch.compute_v1.screening import Block3ScreeningMetricBundle


# ============== 测试辅助 ==============
def _build_config() -> dict[str, object]:
    return {
        "expression_depth_max": 8,
        "coverage_mean_min": 0.70,
        "effective_trade_days_min": 120,
        "min_cross_section_size": 100,
        "finite_ratio_min": 0.99,
        "std_min": 1e-12,
        "unique_ratio_min": 0.01,
        "admission_quality_metric": "directional_rankic_mean",
        "admission_quality_min": 0.04,
        "admission_stability_metric": "directional_rankic_ir",
        "admission_stability_min": 0.50,
        "library_corr_threshold": 0.50,
        "replacement_quality_metric": "directional_rankic_mean",
        "replacement_absolute_quality_min": 0.10,
        "replacement_improvement_ratio_min": 1.30,
        "directional_long_short_sharpe_min": 1.00,
        "long_short_effective_days_min": 50,
        "monotonicity_score_min": 0.30,
        "turnover_proxy_max": 0.70,
    }


def _build_metrics(**overrides: object) -> dict[str, object]:
    metrics = {
        "expression_parse_status": "ok",
        "expression_allowlist_status": "ok",
        "leakage_check_status": "ok",
        "expression_depth": 6,
        "coverage_mean": 0.92,
        "effective_trade_days": 160,
        "median_valid_stock_count": 260,
        "finite_ratio": 1.0,
        "std": 0.25,
        "unique_ratio": 0.30,
        "admission_horizon": "5d",
        "expected_direction": "positive",
        "directional_rankic_mean": 0.10,
        "directional_rankic_ir": 0.80,
        "max_abs_corr_to_batch": 0.10,
        "max_abs_corr_to_library": 0.20,
        "correlation_overlap_count": 12000,
        "correlated_factor_count": 0,
        "matched_factor_id": None,
        "directional_long_short_sharpe": 1.35,
        "long_short_effective_days": 88,
        "monotonicity_score": 0.44,
        "turnover_proxy": 0.25,
        "pearson_ic_mean": 0.99,
        "spread_return_mean": 9.99,
    }
    metrics.update(overrides)
    return metrics


def _bundle_from_flat_metrics(flat_metrics: dict[str, object]) -> Block3ScreeningMetricBundle:
    gate0_fields = (
        "expression_parse_status",
        "expression_allowlist_status",
        "leakage_check_status",
        "expression_depth",
        "coverage_mean",
        "effective_trade_days",
        "median_valid_stock_count",
        "finite_ratio",
        "std",
        "unique_ratio",
    )
    gate1_fields = (
        "admission_horizon",
        "expected_direction",
        "directional_rankic_mean",
        "directional_rankic_ir",
    )
    gate2_fields = (
        "max_abs_corr_to_batch",
        "max_abs_corr_to_library",
        "correlation_overlap_count",
        "correlated_factor_count",
        "matched_factor_id",
    )
    gate3_fields = (
        "directional_long_short_sharpe",
        "long_short_effective_days",
        "monotonicity_score",
        "turnover_proxy",
    )
    return Block3ScreeningMetricBundle(
        gate0_metrics={key: flat_metrics[key] for key in gate0_fields if key in flat_metrics},
        gate1_metrics={key: flat_metrics[key] for key in gate1_fields if key in flat_metrics},
        gate2_metrics={key: flat_metrics[key] for key in gate2_fields if key in flat_metrics},
        gate3_metrics={key: flat_metrics[key] for key in gate3_fields if key in flat_metrics},
        factor_exposure_ref="memory://factor",
        engine_version="compute_v1",
    )


def _build_inputs(
    *,
    metrics: dict[str, object] | None = None,
    existing_factor_metrics: dict[str, object] | None = None,
) -> Block3GateInputs:
    flat_metrics = _build_metrics() if metrics is None else metrics
    return Block3GateInputs(
        config=_build_config(),
        metrics=_bundle_from_flat_metrics(flat_metrics),
        existing_factor_metrics=existing_factor_metrics,
    )


# ============== Gate 决策 ==============
def test_apply_block3_screening_gate_returns_admitted_when_all_gates_pass() -> None:
    decision = apply_block3_screening_gate(_build_inputs())

    assert decision.decision == "admitted"
    assert decision.gate0_status == "pass"
    assert decision.gate1_status == "pass"
    assert decision.gate2_status == "pass"
    assert decision.gate3_status == "pass"
    assert decision.reject_reason is None
    assert decision.metrics["expression_depth"] == 6
    assert "pearson_ic_mean" not in decision.metrics


def test_apply_block3_screening_gate_rejects_when_expression_depth_too_high() -> None:
    decision = apply_block3_screening_gate(
        _build_inputs(metrics=_build_metrics(expression_depth=9))
    )

    assert decision.decision == "reject"
    assert decision.gate0_status == "fail"
    assert decision.reject_reason == "expression_too_deep"


@pytest.mark.parametrize(
    ("metric_name", "metric_value", "reject_reason"),
    [
        ("coverage_mean", 0.69, "low_coverage"),
        ("median_valid_stock_count", 99, "insufficient_cross_section"),
        ("effective_trade_days", 119, "insufficient_effective_trade_days"),
        ("finite_ratio", 0.98, "low_finite_ratio"),
        ("std", 0.0, "constant_factor"),
        ("unique_ratio", 0.001, "low_unique_ratio"),
    ],
)
def test_apply_block3_screening_gate_rejects_gate0_quality_failures(
    metric_name: str,
    metric_value: object,
    reject_reason: str,
) -> None:
    decision = apply_block3_screening_gate(
        _build_inputs(metrics=_build_metrics(**{metric_name: metric_value}))
    )

    assert decision.decision == "reject"
    assert decision.gate0_status == "fail"
    assert decision.reject_reason == reject_reason


def test_apply_block3_screening_gate_rejects_when_directional_rankic_mean_below_threshold() -> None:
    decision = apply_block3_screening_gate(
        _build_inputs(metrics=_build_metrics(directional_rankic_mean=0.03))
    )

    assert decision.decision == "reject"
    assert decision.gate0_status == "pass"
    assert decision.gate1_status == "fail"
    assert decision.reject_reason == "weak_rankic_mean"


def test_apply_block3_screening_gate_rejects_when_directional_rankic_ir_below_threshold() -> None:
    decision = apply_block3_screening_gate(
        _build_inputs(metrics=_build_metrics(directional_rankic_ir=0.49))
    )

    assert decision.decision == "reject"
    assert decision.gate1_status == "fail"
    assert decision.reject_reason == "weak_rankic_ir"


def test_apply_block3_screening_gate_marks_duplicate_when_highly_correlated_but_not_better() -> None:
    decision = apply_block3_screening_gate(
        _build_inputs(
            metrics=_build_metrics(
                max_abs_corr_to_library=0.72,
                correlated_factor_count=1,
                matched_factor_id="rf_001",
            ),
            existing_factor_metrics={"directional_rankic_mean": 0.08},
        )
    )

    assert decision.decision == "duplicate"
    assert decision.gate2_status == "duplicate"
    assert decision.matched_factor_id == "rf_001"
    assert decision.reject_reason == "library_duplicate_or_replace"


def test_apply_block3_screening_gate_marks_replace_candidate_for_unique_match_with_130x_improvement() -> None:
    decision = apply_block3_screening_gate(
        _build_inputs(
            metrics=_build_metrics(
                max_abs_corr_to_library=0.81,
                correlated_factor_count=1,
                matched_factor_id="rf_002",
            ),
            existing_factor_metrics={"directional_rankic_mean": 0.06},
        )
    )

    assert decision.decision == "replace_candidate"
    assert decision.gate2_status == "replace_candidate"
    assert decision.gate3_status == "pass"
    assert decision.matched_factor_id == "rf_002"
    assert decision.existing_metrics == {"directional_rankic_mean": 0.06}
    assert decision.metrics_delta["improvement_ratio"] == pytest.approx(1.6666666666666667)


@pytest.mark.parametrize("sharpe_value", [0.99, math.inf, math.nan])
def test_apply_block3_screening_gate_rejects_when_long_short_sharpe_is_invalid(
    sharpe_value: float,
) -> None:
    decision = apply_block3_screening_gate(
        _build_inputs(metrics=_build_metrics(directional_long_short_sharpe=sharpe_value))
    )

    assert decision.decision == "reject"
    assert decision.gate3_status == "fail"
    assert decision.reject_reason == "weak_long_short_sharpe"


def test_apply_block3_screening_gate_rejects_when_long_short_days_too_few() -> None:
    decision = apply_block3_screening_gate(
        _build_inputs(metrics=_build_metrics(long_short_effective_days=49))
    )

    assert decision.decision == "reject"
    assert decision.gate3_status == "fail"
    assert decision.reject_reason == "insufficient_long_short_days"


def test_apply_block3_screening_gate_rejects_when_monotonicity_too_low() -> None:
    decision = apply_block3_screening_gate(
        _build_inputs(metrics=_build_metrics(monotonicity_score=0.29))
    )

    assert decision.decision == "reject"
    assert decision.gate3_status == "fail"
    assert decision.reject_reason == "weak_monotonicity"


def test_apply_block3_screening_gate_rejects_when_turnover_too_high() -> None:
    decision = apply_block3_screening_gate(
        _build_inputs(metrics=_build_metrics(turnover_proxy=0.71))
    )

    assert decision.decision == "reject"
    assert decision.gate3_status == "fail"
    assert decision.reject_reason == "excessive_turnover"


def test_apply_block3_screening_gate_raises_clear_error_when_required_metric_missing() -> None:
    metrics = _build_metrics()
    metrics.pop("directional_long_short_sharpe")

    with pytest.raises(Block3MetricContractError) as exc_info:
        apply_block3_screening_gate(_build_inputs(metrics=metrics))

    message = str(exc_info.value)
    assert "directional_long_short_sharpe" in message
    assert "compute engine v1" in message
