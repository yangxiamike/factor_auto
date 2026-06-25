"""
Compute v1 面板存储模块
负责把 long-format dataset 转为 date x asset 稠密矩阵。
它是 v1 计算、预处理和指标模块共享的数据视图。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from factor_autoresearch.data_loader import DatasetBundle


# ============== 面板矩阵结构 ==============
@dataclass(frozen=True)
class PanelStore:
    """面板存储: 持有字段矩阵、股票池 mask 和长表索引。"""

    date_index: pd.Index
    asset_index: pd.Index
    long_index: pd.MultiIndex
    field_map: dict[str, np.ndarray]
    universe_mask: np.ndarray

    @classmethod
    def from_dataset(cls, dataset: DatasetBundle) -> PanelStore:
        """构建面板: 从 DatasetBundle 生成稠密矩阵视图。"""

        panel = dataset.panel.sort_index()
        date_index = pd.Index(panel.index.get_level_values("trade_date").unique(), name="trade_date")
        asset_index = pd.Index(panel.index.get_level_values("ts_code").unique(), name="ts_code")
        long_index = pd.MultiIndex.from_product([date_index, asset_index], names=["trade_date", "ts_code"])
        aligned = panel.reindex(long_index)

        field_map: dict[str, np.ndarray] = {}
        for column in aligned.columns:
            if column == "industry":
                continue
            field_map[column] = aligned[column].to_numpy().reshape(len(date_index), len(asset_index))

        universe = aligned["in_universe"].fillna(False).to_numpy(dtype=bool).reshape(len(date_index), len(asset_index))
        return cls(
            date_index=date_index,
            asset_index=asset_index,
            long_index=long_index,
            field_map=field_map,
            universe_mask=universe,
        )

    def field(self, name: str) -> np.ndarray:
        """字段读取: 返回指定字段的 float 矩阵。"""
        if name not in self.field_map:
            raise KeyError(f"unknown panel field: {name}")
        return self.field_map[name].astype(float, copy=False)

    def to_series(self, name: str, values: np.ndarray) -> pd.Series:
        """转回长表: 将矩阵结果恢复为 legacy Series。"""
        return pd.Series(np.asarray(values, dtype=float).reshape(-1), index=self.long_index, name=name)
