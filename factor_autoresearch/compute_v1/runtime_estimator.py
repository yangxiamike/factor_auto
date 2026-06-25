"""
Compute v1 运行时间估算模块
负责把实测 benchmark 外推到目标挖掘规模。
不参与实际评估流程，只提供优化决策参考。
"""

from __future__ import annotations

from dataclasses import dataclass


# ============== 估算结果结构 ==============
@dataclass(frozen=True)
class RuntimeEstimate:
    """运行时间估算: 保存目标规模下的耗时和分级。"""

    projected_seconds: float
    projected_minutes: float
    classification: str
    should_trigger_optimization_loop: bool




# ============== 估算主入口 ==============
def estimate_mining_runtime(
    *,
    baseline_seconds: float,
    baseline_trade_days: int,
    baseline_candidates: int,
    target_years: int,
    target_candidates: int,
    trading_days_per_year: int = 252,
    oos_multiplier: float = 1.0,
    walk_forward_windows: int = 1,
) -> RuntimeEstimate:
    """运行时间估算: 基于一次实测 benchmark 外推目标规模。"""

    numeric_inputs = {
        "baseline_seconds": baseline_seconds,
        "baseline_trade_days": baseline_trade_days,
        "baseline_candidates": baseline_candidates,
        "target_years": target_years,
        "target_candidates": target_candidates,
        "trading_days_per_year": trading_days_per_year,
        "oos_multiplier": oos_multiplier,
        "walk_forward_windows": walk_forward_windows,
    }
    for name, value in numeric_inputs.items():
        if value <= 0:
            raise ValueError(f"{name} must be positive")

    seconds_per_candidate_day = baseline_seconds / (baseline_trade_days * baseline_candidates)
    projected_seconds = (
        seconds_per_candidate_day
        * trading_days_per_year
        * target_years
        * target_candidates
        * oos_multiplier
        * walk_forward_windows
    )
    rounded_seconds = round(projected_seconds, 6)
    classification = _classify_runtime(rounded_seconds)
    return RuntimeEstimate(
        projected_seconds=rounded_seconds,
        projected_minutes=round(rounded_seconds / 60.0, 3),
        classification=classification,
        should_trigger_optimization_loop=classification not in {"strong_green", "green"},
    )




# ============== 分级规则 ==============
def _classify_runtime(projected_seconds: float) -> str:
    if projected_seconds <= 300.0:
        return "strong_green"
    if projected_seconds <= 600.0:
        return "green"
    if projected_seconds <= 1200.0:
        return "yellow"
    return "red"
