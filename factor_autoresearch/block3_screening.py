"""
区块3筛选模块
只负责读取 compute v1 输出的 metric bundle 做 Gate 决策。
不负责指标计算、数据读取或样本协议解析。
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

# ============== 指标字段约定 ==============
GATE0_METRIC_FIELDS = (
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
GATE1_METRIC_FIELDS = (
    "admission_horizon",
    "expected_direction",
    "directional_rankic_mean",
    "directional_rankic_ir",
)
GATE2_METRIC_FIELDS = (
    "max_abs_corr_to_batch",
    "max_abs_corr_to_library",
    "correlation_overlap_count",
    "correlated_factor_count",
    "matched_factor_id",
)
GATE3_METRIC_FIELDS = (
    "directional_long_short_sharpe",
    "long_short_effective_days",
    "monotonicity_score",
    "turnover_proxy",
)
BLOCK3_GATE_METRIC_FIELDS = (
    *GATE0_METRIC_FIELDS,
    *GATE1_METRIC_FIELDS,
    *GATE2_METRIC_FIELDS,
    *GATE3_METRIC_FIELDS,
)
PREDICTION_METRIC_FIELDS = ("directional_rankic_mean", "directional_rankic_ir")
CORRELATION_PROFILE_FIELDS = (
    "max_abs_corr_to_batch",
    "max_abs_corr_to_library",
    "correlation_overlap_count",
    "correlated_factor_count",
    "matched_factor_id",
)
LIGHT_TRADING_PROFILE_FIELDS = (
    "directional_long_short_sharpe",
    "long_short_effective_days",
    "monotonicity_score",
    "turnover_proxy",
)


# ============== 数据结构 ==============
class Block3MetricContractError(ValueError):
    """指标合同异常: Block3 缺少 compute engine v1 应输出的字段时抛出。"""


@dataclass(frozen=True)
class Block3GateInputs:
    """区块3 Gate 输入: 配置、指标 bundle 和旧因子比较指标。"""

    config: object
    metrics: object
    existing_factor_metrics: Mapping[str, object] | None = None


@dataclass(frozen=True)
class Block3GateDecision:
    """区块3 Gate 决策: 记录各 Gate 状态、最终去向和精简指标。"""

    decision: str
    gate0_status: str
    gate1_status: str
    gate2_status: str
    gate3_status: str
    reject_reason: str | None
    matched_factor_id: str | None
    metrics: dict[str, object]
    existing_metrics: dict[str, object] | None = None
    metrics_delta: dict[str, object] | None = None


# ============== 基础辅助函数 ==============
def _get_value(container: object, field_name: str, default: object = None) -> object:
    """读取字段: 同时兼容 Mapping 和普通对象。"""

    if isinstance(container, Mapping):
        return container.get(field_name, default)
    return getattr(container, field_name, default)


def _flatten_metrics(metrics: object) -> dict[str, object]:
    """拉平指标: 同时兼容 flat mapping 和 compute v1 metric bundle。"""

    if isinstance(metrics, Mapping):
        return dict(metrics)

    flattened: dict[str, object] = {}
    for field_name in ("gate0_metrics", "gate1_metrics", "gate2_metrics", "gate3_metrics"):
        bucket = getattr(metrics, field_name, None)
        if bucket is None:
            continue
        if not isinstance(bucket, Mapping):
            raise Block3MetricContractError(
                f"Block3 screening expects '{field_name}' to be a mapping"
            )
        flattened.update(bucket)
    if flattened:
        return flattened
    raise Block3MetricContractError(
        "Block3 screening requires a metric mapping or Block3ScreeningMetricBundle"
    )


def _require_metric(metrics: Mapping[str, object], field_name: str) -> object:
    """读取必需指标: 缺失时提示应由 compute engine v1 补输出。"""

    if field_name not in metrics:
        raise Block3MetricContractError(
            f"Block3 screening requires metric '{field_name}'; "
            "it should be output by compute engine v1."
        )
    return metrics[field_name]


def _require_float(metrics: Mapping[str, object], field_name: str) -> float:
    """读取浮点指标: 用统一错误出口保证提示可读。"""

    return float(_require_metric(metrics, field_name))


def _require_int(metrics: Mapping[str, object], field_name: str) -> int:
    """读取整型指标: 用统一错误出口保证提示可读。"""

    return int(_require_metric(metrics, field_name))


def _get_threshold(config: object, field_name: str, default: object) -> object:
    """读取阈值: 优先用输入配置，缺失时退回区块3默认值。"""

    return _get_value(config, field_name, default)


def _select_gate_metrics(metrics: Mapping[str, object]) -> dict[str, object]:
    """提取 Gate 指标: 只保留区块3直接用到的字段。"""

    return {field_name: metrics.get(field_name) for field_name in BLOCK3_GATE_METRIC_FIELDS}


def _build_decision(
    *,
    decision: str,
    gate0_status: str,
    gate1_status: str,
    gate2_status: str,
    gate3_status: str,
    reject_reason: str | None,
    matched_factor_id: str | None,
    metrics: Mapping[str, object],
    existing_metrics: dict[str, object] | None = None,
    metrics_delta: dict[str, object] | None = None,
) -> Block3GateDecision:
    """构造决策对象: 统一收敛状态和精简指标。"""

    return Block3GateDecision(
        decision=decision,
        gate0_status=gate0_status,
        gate1_status=gate1_status,
        gate2_status=gate2_status,
        gate3_status=gate3_status,
        reject_reason=reject_reason,
        matched_factor_id=matched_factor_id,
        metrics=_select_gate_metrics(metrics),
        existing_metrics=existing_metrics,
        metrics_delta=metrics_delta,
    )


def _evaluate_replacement(
    *,
    config: object,
    metrics: Mapping[str, object],
    existing_factor_metrics: Mapping[str, object] | None,
) -> tuple[str, str | None, dict[str, object] | None, dict[str, object] | None]:
    """判断 replacement: 高相关时只区分 duplicate 和 replace_candidate。"""

    corr_threshold = float(_get_threshold(config, "library_corr_threshold", 0.50))
    max_abs_corr = _require_float(metrics, "max_abs_corr_to_library")
    if max_abs_corr < corr_threshold:
        return "pass", None, None, None

    matched_factor_id = _get_value(metrics, "matched_factor_id")
    correlated_factor_count = _require_int(metrics, "correlated_factor_count")
    if correlated_factor_count != 1 or not matched_factor_id or not existing_factor_metrics:
        return "duplicate", str(matched_factor_id) if matched_factor_id else None, None, None

    quality_metric = str(
        _get_threshold(config, "replacement_quality_metric", "directional_rankic_mean")
    )
    absolute_quality_min = float(
        _get_threshold(config, "replacement_absolute_quality_min", 0.10)
    )
    improvement_min = float(
        _get_threshold(config, "replacement_improvement_ratio_min", 1.30)
    )
    candidate_quality = float(_require_metric(metrics, quality_metric))
    existing_quality_raw = existing_factor_metrics.get(quality_metric)
    if existing_quality_raw is None:
        return "duplicate", str(matched_factor_id), None, None

    existing_quality = float(existing_quality_raw)
    if existing_quality == 0.0:
        improvement_ratio = math.inf if candidate_quality > 0.0 else 1.0
    else:
        improvement_ratio = candidate_quality / existing_quality

    existing_metrics = {quality_metric: existing_quality}
    metrics_delta = {
        "quality_metric": quality_metric,
        "candidate_value": candidate_quality,
        "existing_value": existing_quality,
        "improvement_ratio": improvement_ratio,
    }
    if (
        candidate_quality >= absolute_quality_min
        and candidate_quality > existing_quality
        and improvement_ratio >= improvement_min
    ):
        return "replace_candidate", str(matched_factor_id), existing_metrics, metrics_delta
    return "duplicate", str(matched_factor_id), existing_metrics, metrics_delta


# ============== Gate 主入口 ==============
def apply_block3_screening_gate(inputs: Block3GateInputs) -> Block3GateDecision:
    """应用区块3 Gate: 只基于 metric bundle 给出 admitted / reject / duplicate / replacement。"""

    metrics = _flatten_metrics(inputs.metrics)
    config = inputs.config

    expression_depth_max = int(_get_threshold(config, "expression_depth_max", 8))
    coverage_mean_min = float(_get_threshold(config, "coverage_mean_min", 0.70))
    effective_trade_days_min = int(_get_threshold(config, "effective_trade_days_min", 120))
    min_cross_section_size = int(_get_threshold(config, "min_cross_section_size", 100))
    finite_ratio_min = float(_get_threshold(config, "finite_ratio_min", 0.99))
    std_min = float(_get_threshold(config, "std_min", 1e-12))
    unique_ratio_min = float(_get_threshold(config, "unique_ratio_min", 0.01))
    admission_quality_metric = str(
        _get_threshold(config, "admission_quality_metric", "directional_rankic_mean")
    )
    admission_quality_min = float(_get_threshold(config, "admission_quality_min", 0.04))
    admission_stability_metric = str(
        _get_threshold(config, "admission_stability_metric", "directional_rankic_ir")
    )
    admission_stability_min = float(_get_threshold(config, "admission_stability_min", 0.50))
    directional_long_short_sharpe_min = float(
        _get_threshold(config, "directional_long_short_sharpe_min", 1.00)
    )
    long_short_effective_days_min = int(
        _get_threshold(config, "long_short_effective_days_min", 50)
    )
    monotonicity_score_min = float(_get_threshold(config, "monotonicity_score_min", 0.30))
    turnover_proxy_max = float(_get_threshold(config, "turnover_proxy_max", 0.70))

    if _require_metric(metrics, "expression_parse_status") != "ok":
        return _build_decision(
            decision="reject",
            gate0_status="fail",
            gate1_status="skip",
            gate2_status="skip",
            gate3_status="skip",
            reject_reason="expression_parse_failed",
            matched_factor_id=None,
            metrics=metrics,
        )
    if _require_metric(metrics, "expression_allowlist_status") != "ok":
        return _build_decision(
            decision="reject",
            gate0_status="fail",
            gate1_status="skip",
            gate2_status="skip",
            gate3_status="skip",
            reject_reason="expression_not_allowlisted",
            matched_factor_id=None,
            metrics=metrics,
        )
    if _require_metric(metrics, "leakage_check_status") != "ok":
        return _build_decision(
            decision="reject",
            gate0_status="fail",
            gate1_status="skip",
            gate2_status="skip",
            gate3_status="skip",
            reject_reason="leakage_detected",
            matched_factor_id=None,
            metrics=metrics,
        )

    expression_depth = _require_int(metrics, "expression_depth")
    if expression_depth > expression_depth_max:
        return _build_decision(
            decision="reject",
            gate0_status="fail",
            gate1_status="skip",
            gate2_status="skip",
            gate3_status="skip",
            reject_reason="expression_too_deep",
            matched_factor_id=None,
            metrics=metrics,
        )

    coverage_mean = _require_float(metrics, "coverage_mean")
    if coverage_mean < coverage_mean_min:
        return _build_decision(
            decision="reject",
            gate0_status="fail",
            gate1_status="skip",
            gate2_status="skip",
            gate3_status="skip",
            reject_reason="low_coverage",
            matched_factor_id=None,
            metrics=metrics,
        )

    effective_trade_days = _require_int(metrics, "effective_trade_days")
    if effective_trade_days < effective_trade_days_min:
        return _build_decision(
            decision="reject",
            gate0_status="fail",
            gate1_status="skip",
            gate2_status="skip",
            gate3_status="skip",
            reject_reason="insufficient_effective_trade_days",
            matched_factor_id=None,
            metrics=metrics,
        )

    median_valid_stock_count = int(round(_require_float(metrics, "median_valid_stock_count")))
    if median_valid_stock_count < min_cross_section_size:
        return _build_decision(
            decision="reject",
            gate0_status="fail",
            gate1_status="skip",
            gate2_status="skip",
            gate3_status="skip",
            reject_reason="insufficient_cross_section",
            matched_factor_id=None,
            metrics=metrics,
        )

    finite_ratio = _require_float(metrics, "finite_ratio")
    if finite_ratio < finite_ratio_min:
        return _build_decision(
            decision="reject",
            gate0_status="fail",
            gate1_status="skip",
            gate2_status="skip",
            gate3_status="skip",
            reject_reason="low_finite_ratio",
            matched_factor_id=None,
            metrics=metrics,
        )

    std_value = _require_float(metrics, "std")
    if not math.isfinite(std_value) or std_value <= std_min:
        return _build_decision(
            decision="reject",
            gate0_status="fail",
            gate1_status="skip",
            gate2_status="skip",
            gate3_status="skip",
            reject_reason="constant_factor",
            matched_factor_id=None,
            metrics=metrics,
        )

    unique_ratio = _require_float(metrics, "unique_ratio")
    if unique_ratio < unique_ratio_min:
        return _build_decision(
            decision="reject",
            gate0_status="fail",
            gate1_status="skip",
            gate2_status="skip",
            gate3_status="skip",
            reject_reason="low_unique_ratio",
            matched_factor_id=None,
            metrics=metrics,
        )

    directional_rankic_mean = float(_require_metric(metrics, admission_quality_metric))
    if directional_rankic_mean < admission_quality_min:
        return _build_decision(
            decision="reject",
            gate0_status="pass",
            gate1_status="fail",
            gate2_status="skip",
            gate3_status="skip",
            reject_reason="weak_rankic_mean",
            matched_factor_id=None,
            metrics=metrics,
        )

    directional_rankic_ir = float(_require_metric(metrics, admission_stability_metric))
    if directional_rankic_ir < admission_stability_min:
        return _build_decision(
            decision="reject",
            gate0_status="pass",
            gate1_status="fail",
            gate2_status="skip",
            gate3_status="skip",
            reject_reason="weak_rankic_ir",
            matched_factor_id=None,
            metrics=metrics,
        )

    gate2_status, matched_factor_id, existing_metrics, metrics_delta = _evaluate_replacement(
        config=config,
        metrics=metrics,
        existing_factor_metrics=inputs.existing_factor_metrics,
    )
    if gate2_status == "duplicate":
        return _build_decision(
            decision="duplicate",
            gate0_status="pass",
            gate1_status="pass",
            gate2_status="duplicate",
            gate3_status="skip",
            reject_reason="library_duplicate_or_replace",
            matched_factor_id=matched_factor_id,
            metrics=metrics,
            existing_metrics=existing_metrics,
            metrics_delta=metrics_delta,
        )

    directional_long_short_sharpe = _require_float(metrics, "directional_long_short_sharpe")
    if (
        not math.isfinite(directional_long_short_sharpe)
        or directional_long_short_sharpe < directional_long_short_sharpe_min
    ):
        return _build_decision(
            decision="reject",
            gate0_status="pass",
            gate1_status="pass",
            gate2_status=gate2_status,
            gate3_status="fail",
            reject_reason="weak_long_short_sharpe",
            matched_factor_id=matched_factor_id,
            metrics=metrics,
            existing_metrics=existing_metrics,
            metrics_delta=metrics_delta,
        )

    long_short_effective_days = _require_int(metrics, "long_short_effective_days")
    if long_short_effective_days < long_short_effective_days_min:
        return _build_decision(
            decision="reject",
            gate0_status="pass",
            gate1_status="pass",
            gate2_status=gate2_status,
            gate3_status="fail",
            reject_reason="insufficient_long_short_days",
            matched_factor_id=matched_factor_id,
            metrics=metrics,
            existing_metrics=existing_metrics,
            metrics_delta=metrics_delta,
        )

    monotonicity_score = _require_float(metrics, "monotonicity_score")
    if monotonicity_score < monotonicity_score_min:
        return _build_decision(
            decision="reject",
            gate0_status="pass",
            gate1_status="pass",
            gate2_status=gate2_status,
            gate3_status="fail",
            reject_reason="weak_monotonicity",
            matched_factor_id=matched_factor_id,
            metrics=metrics,
            existing_metrics=existing_metrics,
            metrics_delta=metrics_delta,
        )

    turnover_proxy = _require_float(metrics, "turnover_proxy")
    if turnover_proxy > turnover_proxy_max:
        return _build_decision(
            decision="reject",
            gate0_status="pass",
            gate1_status="pass",
            gate2_status=gate2_status,
            gate3_status="fail",
            reject_reason="excessive_turnover",
            matched_factor_id=matched_factor_id,
            metrics=metrics,
            existing_metrics=existing_metrics,
            metrics_delta=metrics_delta,
        )

    final_decision = "replace_candidate" if gate2_status == "replace_candidate" else "admitted"
    return _build_decision(
        decision=final_decision,
        gate0_status="pass",
        gate1_status="pass",
        gate2_status=gate2_status,
        gate3_status="pass",
        reject_reason=None,
        matched_factor_id=matched_factor_id,
        metrics=metrics,
        existing_metrics=existing_metrics,
        metrics_delta=metrics_delta,
    )
