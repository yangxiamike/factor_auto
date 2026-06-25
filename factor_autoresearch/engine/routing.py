"""Routing helpers for supported compute engine names."""

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


def validate_engine_name(engine: str) -> EngineName:
    """Validate and normalize a configured engine name."""
    normalized = engine.strip().lower()
    if normalized not in ENGINE_NAMES:
        supported = ", ".join(ENGINE_NAMES)
        raise ValueError(f"Unsupported engine '{engine}'. Expected one of: {supported}.")
    return normalized  # type: ignore[return-value]


def normalize_engine_name(engine: str | None, *, default: EngineName = DEFAULT_ENGINE_NAME) -> EngineName:
    """Resolve an optional engine name to a supported value."""
    if engine is None:
        return default
    return validate_engine_name(engine)


def get_engine_module(engine: str | None = None) -> ModuleType:
    """Import and return the module for a supported engine name."""
    engine_name = normalize_engine_name(engine)
    return import_module(_ENGINE_MODULES[engine_name])
