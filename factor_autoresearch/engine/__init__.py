"""Compute engine routing and execution helpers."""

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
