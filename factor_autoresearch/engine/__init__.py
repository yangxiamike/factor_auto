"""
compute engine 包入口: 暴露引擎名称、路由和有序执行辅助。
这里仅维护公共导出，不直接参与因子计算。
"""

from factor_autoresearch.engine.legacy import ENGINE_NAME as LEGACY_ENGINE_NAME
from factor_autoresearch.engine.parallel import OrderedResult, parse_jobs, run_ordered
from factor_autoresearch.engine.routing import (
    DEFAULT_ENGINE_NAME,
    ENGINE_NAMES,
    get_engine_module,
    normalize_engine_name,
    validate_engine_name,
)
from factor_autoresearch.engine.v1 import ENGINE_NAME as V1_ENGINE_NAME

__all__ = [
    "DEFAULT_ENGINE_NAME",
    "ENGINE_NAMES",
    "LEGACY_ENGINE_NAME",
    "OrderedResult",
    "V1_ENGINE_NAME",
    "get_engine_module",
    "normalize_engine_name",
    "parse_jobs",
    "run_ordered",
    "validate_engine_name",
]
