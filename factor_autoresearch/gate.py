from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from factor_autoresearch.candidates import Candidate
from factor_autoresearch.config import ExperimentConfig
from factor_autoresearch.metrics import MetricsResult


@dataclass(frozen=True)
class GateDecision:
    passed: bool
    status: str
    failure_bucket: str | None
    best_horizon: str | None
    best_horizon_score: float
    signal_direction: str | None
    failed_rules: list[str]
    details: dict[str, object]


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def apply_candidate_gate(candidate: Candidate, metrics_result: MetricsResult, config: ExperimentConfig) -> GateDecision:
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

    sign = 1.0 if candidate.expected_direction == "positive" else -1.0
    scale_ic = config.gate.components["ic_scale"]
    scale_rankic = config.gate.components["rankic_scale"]
    component_max = config.gate.components["component_max"]
    mono_min = config.gate.components["monotonicity_min"]
    mono_max = config.gate.components["monotonicity_max"]

    frame["directional_ic_mean"] = sign * frame["ic_mean"]
    frame["directional_rankic_mean"] = sign * frame["rankic_mean"]
    frame["directional_monotonicity"] = sign * frame["monotonicity"]
    frame["ic_component"] = frame["directional_ic_mean"].apply(
        lambda value: _clamp(value / scale_ic, 0.0, component_max) if pd.notna(value) else 0.0
    )
    frame["rankic_component"] = frame["directional_rankic_mean"].apply(
        lambda value: _clamp(value / scale_rankic, 0.0, component_max) if pd.notna(value) else 0.0
    )
    frame["monotonicity_component"] = frame["directional_monotonicity"].apply(
        lambda value: _clamp(value, mono_min, mono_max) if pd.notna(value) else 0.0
    )
    frame["horizon_score"] = (
        config.gate.weights["ic"] * frame["ic_component"]
        + config.gate.weights["rankic"] * frame["rankic_component"]
        + config.gate.weights["monotonicity"] * frame["monotonicity_component"]
    )

    best_row = frame.sort_values("horizon_score", ascending=False).iloc[0]
    coverage_mean = float(metrics_result.aggregate["coverage_mean"])
    effective_trade_days = int(metrics_result.aggregate["effective_trade_days"])
    complexity_score = int(metrics_result.aggregate["complexity_score"])
    best_horizon_score = float(best_row["horizon_score"])

    failed_rules: list[str] = []
    if not pd.notna(coverage_mean) or coverage_mean < config.gate.coverage_mean_min:
        failed_rules.append("coverage_mean")
    if effective_trade_days < config.gate.effective_trade_days_min:
        failed_rules.append("effective_trade_days")
    if complexity_score > config.gate.complexity_score_max:
        failed_rules.append("complexity_score")
    if not pd.notna(best_horizon_score) or best_horizon_score < config.gate.best_horizon_score_min:
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
