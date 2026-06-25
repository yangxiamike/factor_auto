"""Small in-memory expression cache for compute engine v1."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class ExpressionCache:
    """Cache expression matrices across candidates."""

    values: dict[tuple, np.ndarray] = field(default_factory=dict)
    hits: int = 0
    misses: int = 0

    def get(self, key: tuple) -> np.ndarray | None:
        if key in self.values:
            self.hits += 1
            return self.values[key]
        self.misses += 1
        return None

    def put(self, key: tuple, value: np.ndarray) -> np.ndarray:
        self.values[key] = value
        return value

    def stats(self) -> dict[str, Any]:
        return {"entries": len(self.values), "hits": self.hits, "misses": self.misses}
