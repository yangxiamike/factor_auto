"""
compute v1 内核测试: 对比矩阵化内核和 legacy operator 的结果。
重点验证时间序列、截面和并列排名口径，不做性能测试。
"""

import numpy as np
import pandas as pd

from factor_autoresearch.compute_v1 import kernels
from factor_autoresearch.compute_v1.panel import PanelStore
from factor_autoresearch.data_loader import DataLoader
from factor_autoresearch.operators import OPERATOR_REGISTRY


# ============== 测试辅助 ==============
def _series_from_matrix(store: PanelStore, values: np.ndarray, name: str = "x") -> pd.Series:
    """矩阵转序列: 按 PanelStore 的索引还原为 pandas Series。"""
    return store.to_series(name, values)


# ============== 内核等价性 ==============
def test_compute_v1_time_series_kernels_match_legacy(sample_dataset_dir, test_config) -> None:
    dataset = DataLoader(config=test_config, dataset_path=sample_dataset_dir).load()
    store = PanelStore.from_dataset(dataset)
    close = store.field("close_hfq")
    close_series = dataset.panel["close_hfq"]

    pd.testing.assert_series_equal(
        _series_from_matrix(store, kernels.ts_return(close, 3)).reindex(dataset.panel.index),
        OPERATOR_REGISTRY["ts_return"].func(close_series, 3).rename("x"),
    )
    pd.testing.assert_series_equal(
        _series_from_matrix(store, kernels.ts_mean(close, 3)).reindex(dataset.panel.index),
        OPERATOR_REGISTRY["ts_mean"].func(close_series, 3).rename("x"),
    )
    pd.testing.assert_series_equal(
        _series_from_matrix(store, kernels.ts_std(close, 3)).reindex(dataset.panel.index),
        OPERATOR_REGISTRY["ts_std"].func(close_series, 3).rename("x"),
    )
    pd.testing.assert_series_equal(
        _series_from_matrix(store, kernels.ts_rank(close, 3)).reindex(dataset.panel.index),
        OPERATOR_REGISTRY["ts_rank"].func(close_series, 3).rename("x"),
    )


def test_compute_v1_cross_sectional_kernels_match_legacy(sample_dataset_dir, test_config) -> None:
    dataset = DataLoader(config=test_config, dataset_path=sample_dataset_dir).load()
    store = PanelStore.from_dataset(dataset)
    close = store.field("close_hfq")
    close_series = dataset.panel["close_hfq"]

    pd.testing.assert_series_equal(
        _series_from_matrix(store, kernels.cs_rank(close, store.universe_mask)).reindex(dataset.panel.index),
        OPERATOR_REGISTRY["cs_rank"].func(close_series, dataset.panel).rename("x"),
    )
    pd.testing.assert_series_equal(
        _series_from_matrix(store, kernels.cs_zscore(close, store.universe_mask)).reindex(dataset.panel.index),
        OPERATOR_REGISTRY["cs_zscore"].func(close_series, dataset.panel).rename("x"),
    )


def test_compute_v1_ts_rank_uses_average_pct_ties() -> None:
    values = np.array([[1.0], [2.0], [2.0]])
    result = kernels.ts_rank(values, 3)
    assert result[-1, 0] == 2.5 / 3.0
