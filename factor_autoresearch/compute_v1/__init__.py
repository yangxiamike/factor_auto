"""
compute engine v1 包入口: 暴露矩阵化计算引擎的核心对象。
这里只做稳定导出，不承载具体计算逻辑。
"""

from factor_autoresearch.compute_v1.calculator import V1FactorCalc
from factor_autoresearch.compute_v1.panel import PanelStore

__all__ = ["PanelStore", "V1FactorCalc"]
