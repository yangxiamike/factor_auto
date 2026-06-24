from __future__ import annotations

import numpy as np
import pandas as pd

from factor_autoresearch.compute_v1.panel import PanelStore
from factor_autoresearch.compute_v1.preprocess import (
    build_neutralization_design,
    neutralize_by_date,
    preprocess_factor_matrix,
    winsorize_by_date,
    zscore_by_date,
)
from factor_autoresearch.data_loader import DataLoader, DatasetBundle
from factor_autoresearch.preprocess import neutralize_by_date as legacy_neutralize_by_date
from factor_autoresearch.preprocess import preprocess_factor


def _dataset_from_panel(panel: pd.DataFrame) -> DatasetBundle:
    empty_forward = pd.DataFrame(index=panel.index)
    return DatasetBundle(panel=panel, forward_returns=empty_forward, manifest={})


def test_winsorize_by_date_respects_universe_mask() -> None:
    values = np.array([[1.0, 2.0, 100.0, 50.0]])
    universe_mask = np.array([[True, True, True, False]])

    result = winsorize_by_date(values, universe_mask, mad_scale=1.0)

    expected = np.array([[1.0, 2.0, 3.0, np.nan]])
    np.testing.assert_allclose(result[:, :3], expected[:, :3])
    assert np.isnan(result[0, 3])


def test_zscore_by_date_uses_ddof_zero() -> None:
    values = np.array([[1.0, 2.0, 3.0, 999.0]])
    universe_mask = np.array([[True, True, True, False]])

    result = zscore_by_date(values, universe_mask)

    expected = np.array([[-1.22474487, 0.0, 1.22474487, np.nan]])
    np.testing.assert_allclose(result[:, :3], expected[:, :3], atol=1e-8)
    assert np.isnan(result[0, 3])


def test_neutralize_by_date_matches_legacy() -> None:
    dates = pd.DatetimeIndex(["2024-01-02", "2024-01-03"], name="trade_date")
    assets = pd.Index(["A", "B", "C", "D"], name="ts_code")
    index = pd.MultiIndex.from_product([dates, assets], names=["trade_date", "ts_code"])
    panel = pd.DataFrame(
        {
            "in_universe": [True] * 8,
            "industry": ["I1", "I1", "I2", "I2"] * 2,
            "market_cap": [100.0, 150.0, 200.0, 260.0, 110.0, 140.0, 230.0, 300.0],
            "open_hfq": [1.0] * 8,
            "high_hfq": [1.0] * 8,
            "low_hfq": [1.0] * 8,
            "close_hfq": [1.0] * 8,
            "volume": [1.0] * 8,
        },
        index=index,
    )
    factor_z = pd.Series([0.6, 1.2, -0.4, -1.1, 0.9, 1.1, -0.2, -1.4], index=index)
    dataset = _dataset_from_panel(panel)
    store = PanelStore.from_dataset(dataset)
    matrix_result = neutralize_by_date(
        factor_z.to_numpy(dtype=float).reshape(len(dates), len(assets)),
        store,
        panel["industry"],
    )
    expected = legacy_neutralize_by_date(factor_z, panel)
    actual = store.to_series("factor", matrix_result).reindex(index)
    pd.testing.assert_series_equal(actual, expected.rename("factor"), atol=1e-10, rtol=1e-10)


def test_neutralize_by_date_uses_cached_design_without_changing_results() -> None:
    dates = pd.DatetimeIndex(["2024-01-02", "2024-01-03"], name="trade_date")
    assets = pd.Index(["A", "B", "C", "D"], name="ts_code")
    index = pd.MultiIndex.from_product([dates, assets], names=["trade_date", "ts_code"])
    panel = pd.DataFrame(
        {
            "in_universe": [True] * 8,
            "industry": ["I1", "I1", "I2", "I2"] * 2,
            "market_cap": [100.0, 150.0, 200.0, 260.0, 110.0, 140.0, 230.0, 300.0],
            "open_hfq": [1.0] * 8,
            "high_hfq": [1.0] * 8,
            "low_hfq": [1.0] * 8,
            "close_hfq": [1.0] * 8,
            "volume": [1.0] * 8,
        },
        index=index,
    )
    factor_matrix = np.array([[0.6, 1.2, -0.4, -1.1], [0.9, 1.1, -0.2, -1.4]])
    dataset = _dataset_from_panel(panel)
    store = PanelStore.from_dataset(dataset)
    design = build_neutralization_design(store, panel["industry"])

    uncached = neutralize_by_date(factor_matrix, store, panel["industry"])
    cached = neutralize_by_date(factor_matrix, store, panel["industry"], design)

    np.testing.assert_allclose(cached, uncached, atol=1e-10, rtol=1e-10, equal_nan=True)


def test_preprocess_factor_matrix_matches_legacy_fixture(sample_dataset_dir, test_config) -> None:
    dataset = DataLoader(config=test_config, dataset_path=sample_dataset_dir).load()
    store = PanelStore.from_dataset(dataset)
    raw_series = ((dataset.panel["close_hfq"] - dataset.panel["open_hfq"]) / dataset.panel["open_hfq"]).rename("raw")
    raw_matrix = raw_series.to_numpy(dtype=float).reshape(store.universe_mask.shape)

    expected = preprocess_factor(raw_series, dataset, test_config).rename("raw")
    actual_matrix = preprocess_factor_matrix(raw_matrix, store, test_config, dataset.panel["industry"])
    actual = store.to_series("raw", actual_matrix).reindex(dataset.panel.index)

    pd.testing.assert_series_equal(actual, expected, atol=1e-10, rtol=1e-10)
