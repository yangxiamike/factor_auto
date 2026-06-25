"""PanelStore converts the long-format dataset into dense date x asset matrices."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from factor_autoresearch.data_loader import DatasetBundle


@dataclass(frozen=True)
class PanelStore:
    """Dense matrix view of a DatasetBundle panel."""

    date_index: pd.Index
    asset_index: pd.Index
    long_index: pd.MultiIndex
    field_map: dict[str, np.ndarray]
    universe_mask: np.ndarray

    @classmethod
    def from_dataset(cls, dataset: DatasetBundle) -> PanelStore:
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
        """Return a field matrix as float values."""
        if name not in self.field_map:
            raise KeyError(f"unknown panel field: {name}")
        return self.field_map[name].astype(float, copy=False)

    def to_series(self, name: str, values: np.ndarray) -> pd.Series:
        """Convert a matrix result back to legacy long-format Series."""
        return pd.Series(np.asarray(values, dtype=float).reshape(-1), index=self.long_index, name=name)
