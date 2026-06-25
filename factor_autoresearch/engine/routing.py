"""
compute engine 路由: 统一解析 legacy 和 v1 的引擎名称。
本模块只负责名称校验和模块导入，不执行具体计算。
"""

from __future__ import annotations

from collections.abc import Mapping
from importlib import import_module
from types import ModuleType
from typing import Literal

EngineName = Literal["legacy", "v1"]

DEFAULT_ENGINE_NAME: EngineName = "legacy"
ENGINE_NAMES: tuple[EngineName, ...] = ("legacy", "v1")
_ENGINE_MODULES: Mapping[EngineName, str] = {
    "legacy": "factor_autoresearch.engine.legacy",
    "v1": "factor_autoresearch.engine.v1",
}


# ============== 引擎名称解析 ==============
def validate_engine_name(engine: str) -> EngineName:
    """校验引擎名: 接受 legacy / v1，并统一大小写和空白。"""
    normalized = engine.strip().lower()
    if normalized not in ENGINE_NAMES:
        supported = ", ".join(ENGINE_NAMES)
        raise ValueError(f"Unsupported engine '{engine}'. Expected one of: {supported}.")
    return normalized  # type: ignore[return-value]


def normalize_engine_name(engine: str | None, *, default: EngineName = DEFAULT_ENGINE_NAME) -> EngineName:
    """归一化引擎名: 空值使用默认引擎。"""
    if engine is None:
        return default
    return validate_engine_name(engine)


# ============== 模块加载 ==============
def get_engine_module(engine: str | None = None) -> ModuleType:
    """加载引擎模块: 返回已支持引擎对应的 Python 模块。"""
    engine_name = normalize_engine_name(engine)
    return import_module(_ENGINE_MODULES[engine_name])
