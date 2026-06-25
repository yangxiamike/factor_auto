"""
Compute v1 表达式缓存模块
负责在单批候选内复用相同表达式子树的矩阵结果。
不跨运行持久化缓存。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


# ============== 表达式缓存 ==============
@dataclass
class ExpressionCache:
    """表达式缓存: 记录矩阵结果和命中统计。"""

    values: dict[tuple, np.ndarray] = field(default_factory=dict)
    hits: int = 0
    misses: int = 0

    def get(self, key: tuple) -> np.ndarray | None:
        """读取缓存: 命中时返回矩阵并累计 hits。"""

        if key in self.values:
            self.hits += 1
            return self.values[key]
        self.misses += 1
        return None

    def put(self, key: tuple, value: np.ndarray) -> np.ndarray:
        """写入缓存: 保存矩阵并原样返回。"""

        self.values[key] = value
        return value

    def stats(self) -> dict[str, Any]:
        """缓存统计: 返回条目数和命中/未命中次数。"""

        return {"entries": len(self.values), "hits": self.hits, "misses": self.misses}
