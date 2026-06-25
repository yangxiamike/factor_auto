"""
兼容入口: 重新导出 legacy 因子计算器。
真实实现位于 factor_autoresearch.compute_legacy.calculator。
"""

from factor_autoresearch.compute_legacy.calculator import FactorCalc
from factor_autoresearch.expression import ExpressionValidationError

__all__ = ["ExpressionValidationError", "FactorCalc"]
