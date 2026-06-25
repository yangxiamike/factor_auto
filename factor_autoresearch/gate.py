"""
候选 gate 模块: 负责根据指标结果和 gate 配置做通过判定。
命名约定:
- 评分组件保持业务含义，不强行缩短
- 聚合判定沿用 best / failed 这类结果名
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from factor_autoresearch.candidates import Candidate
from factor_autoresearch.compute_legacy.metrics import MetricsResult
from factor_autoresearch.config import ExperimentConfig


# ============== 判定结果结构 ==============
@dataclass(frozen=True)
class GateDecision:
    """Gate 判定结果: 记录是否通过、失败原因和最佳 horizon。"""

    passed: bool
    status: str
    failure_bucket: str | None
    best_horizon: str | None
    best_horizon_score: float
    signal_direction: str | None
    failed_rules: list[str]
    details: dict[str, object]


# ============== 基础辅助函数 ==============
def _clamp(value: float, lower: float, upper: float) -> float:
    """截断数值: 把分数组件限制在指定区间内。"""

    return max(lower, min(upper, value))


# ============== Gate 主逻辑 ==============
def apply_candidate_gate(candidate: Candidate, metrics_result: MetricsResult, config: ExperimentConfig) -> GateDecision:
    """应用 gate: 计算 horizon 评分并给出候选通过结论。"""

    frame = metrics_result.horizon_rows.copy()
    if frame.empty:
        return GateDecision(
            passed=False,
            status="candidate_fail",
            failure_bucket="gate_failed",
            best_horizon=None,
            best_horizon_score=math.nan,
            signal_direction=None,
            failed_rules=["no_metrics"],
            details={"reason": "metrics frame is empty"},
        )

    scale_ic = config.gate.components["ic_scale"]
    scale_rankic = config.gate.components["rankic_scale"]
    component_max = config.gate.components["component_max"]
    mono_min = config.gate.components["monotonicity_min"]
    mono_max = config.gate.components["monotonicity_max"]

    scored_frame = frame
    scored_frame["ic_component"] = scored_frame["directional_ic_mean"].apply(
        lambda value: _clamp(value / scale_ic, 0.0, component_max) if pd.notna(value) else 0.0
    )
    scored_frame["rankic_component"] = scored_frame["directional_rankic_mean"].apply(
        lambda value: _clamp(value / scale_rankic, 0.0, component_max) if pd.notna(value) else 0.0
    )
    scored_frame["monotonicity_component"] = scored_frame["directional_monotonicity"].apply(
        lambda value: _clamp(value, mono_min, mono_max) if pd.notna(value) else 0.0
    )
    scored_frame["horizon_score"] = (
        config.gate.weights["ic"] * scored_frame["ic_component"]
        + config.gate.weights["rankic"] * scored_frame["rankic_component"]
        + config.gate.weights["monotonicity"] * scored_frame["monotonicity_component"]
    )

    best_row = scored_frame.sort_values("horizon_score", ascending=False).iloc[0]
    coverage_mean = float(metrics_result.aggregate["coverage_mean"])
    effective_trade_days = int(metrics_result.aggregate["effective_trade_days"])
    complexity_score = int(metrics_result.aggregate["complexity_score"])
    best_horizon_score = float(best_row["horizon_score"])

    hard_failed_rules: list[str] = []
    if not pd.notna(coverage_mean) or coverage_mean < config.gate.coverage_mean_min:
        hard_failed_rules.append("coverage_mean")
    if effective_trade_days < config.gate.effective_trade_days_min:
        hard_failed_rules.append("effective_trade_days")
    if complexity_score > config.gate.complexity_score_max:
        hard_failed_rules.append("complexity_score")
    if (
        not pd.notna(best_row["directional_ic_mean"])
        or float(best_row["directional_ic_mean"])
        < config.gate.best_horizon_directional_ic_mean_min
    ):
        hard_failed_rules.append("best_horizon_directional_ic_mean")
    if (
        not pd.notna(best_row["directional_rankic_mean"])
        or float(best_row["directional_rankic_mean"])
        < config.gate.best_horizon_directional_rankic_mean_min
    ):
        hard_failed_rules.append("best_horizon_directional_rankic_mean")
    if (
        not pd.notna(best_row["directional_ic_positive_ratio"])
        or float(best_row["directional_ic_positive_ratio"])
        < config.gate.best_horizon_directional_ic_positive_ratio_min
    ):
        hard_failed_rules.append("best_horizon_directional_ic_positive_ratio")
    if (
        not pd.notna(best_row["directional_rankic_positive_ratio"])
        or float(best_row["directional_rankic_positive_ratio"])
        < config.gate.best_horizon_directional_rankic_positive_ratio_min
    ):
        hard_failed_rules.append("best_horizon_directional_rankic_positive_ratio")
    if (
        not pd.notna(best_row["directional_monotonicity"])
        or float(best_row["directional_monotonicity"])
        <= config.gate.best_horizon_directional_monotonicity_min
    ):
        hard_failed_rules.append("best_horizon_directional_monotonicity")

    failed_rules = list(hard_failed_rules)
    if not hard_failed_rules and (
        not pd.notna(best_horizon_score) or best_horizon_score < config.gate.best_horizon_score_min
    ):
        failed_rules.append("best_horizon_score")

    signal_direction = None
    if pd.notna(best_row["rankic_mean"]):
        signal_direction = "positive" if float(best_row["rankic_mean"]) >= 0 else "negative"

    details = {
        "coverage_mean": coverage_mean,
        "effective_trade_days": effective_trade_days,
        "complexity_score": complexity_score,
        "best_horizon": best_row["horizon"],
        "best_horizon_score": best_horizon_score,
        "best_horizon_directional_ic_mean": float(best_row["directional_ic_mean"]),
        "best_horizon_directional_rankic_mean": float(best_row["directional_rankic_mean"]),
        "best_horizon_ic_positive_ratio": float(best_row["ic_positive_ratio"]),
        "best_horizon_rankic_positive_ratio": float(best_row["rankic_positive_ratio"]),
        "best_horizon_directional_ic_positive_ratio": float(
            best_row["directional_ic_positive_ratio"]
        ),
        "best_horizon_directional_rankic_positive_ratio": float(
            best_row["directional_rankic_positive_ratio"]
        ),
        "best_horizon_directional_monotonicity": float(best_row["directional_monotonicity"]),
        "ic_component": float(best_row["ic_component"]),
        "rankic_component": float(best_row["rankic_component"]),
        "monotonicity_component": float(best_row["monotonicity_component"]),
    }
    return GateDecision(
        passed=not failed_rules,
        status="candidate_pass" if not failed_rules else "candidate_fail",
        failure_bucket=None if not failed_rules else "gate_failed",
        best_horizon=str(best_row["horizon"]),
        best_horizon_score=best_horizon_score,
        signal_direction=signal_direction,
        failed_rules=failed_rules,
        details=details,
    )
