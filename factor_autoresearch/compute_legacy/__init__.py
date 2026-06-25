"""
Legacy 计算引擎包
集中保存最早的 pandas 单进程计算路径。
它负责保留正确性基准，不负责 v1 的矩阵化和并行优化。
"""

from factor_autoresearch.compute_legacy.calculator import FactorCalc
from factor_autoresearch.compute_legacy.metrics import MetricsResult, compute_candidate_metrics
from factor_autoresearch.compute_legacy.preprocess import preprocess_factor

__all__ = [
    "FactorCalc",
    "MetricsResult",
    "compute_candidate_metrics",
    "preprocess_factor",
]
