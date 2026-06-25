"""
兼容入口: 重新导出 legacy 因子预处理函数。
真实实现位于 factor_autoresearch.compute_legacy.preprocess。
"""

from factor_autoresearch.compute_legacy.preprocess import (
    neutralize_by_date,
    preprocess_factor,
    winsorize_by_date,
    zscore_by_date,
)

__all__ = [
    "neutralize_by_date",
    "preprocess_factor",
    "winsorize_by_date",
    "zscore_by_date",
]
