"""
兼容入口: 重新导出 legacy 指标计算函数。
真实实现位于 factor_autoresearch.compute_legacy.metrics。
"""

from factor_autoresearch.compute_legacy.metrics import MetricsResult, compute_candidate_metrics

__all__ = ["MetricsResult", "compute_candidate_metrics"]
