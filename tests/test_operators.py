import numpy as np
import pandas as pd

from factor_autoresearch.data_loader import DataLoader
from factor_autoresearch.operators import OPERATOR_REGISTRY, div0


def _load_panel(sample_dataset_dir, test_config) -> pd.DataFrame:
    return DataLoader(config=test_config, dataset_path=sample_dataset_dir).load().panel


def test_operator_registry_contains_expected_names() -> None:
    assert set(OPERATOR_REGISTRY) == {
        "add",
        "sub",
        "mul",
        "div",
        "abs",
        "log",
        "delay",
        "ts_mean",
        "ts_std",
        "ts_delta",
        "ts_return",
        "ts_rank",
        "cs_rank",
        "cs_zscore",
    }


def test_add_operator(sample_dataset_dir, test_config) -> None:
    panel = _load_panel(sample_dataset_dir, test_config)
    left = panel["close_hfq"]
    right = panel["open_hfq"]
    result = OPERATOR_REGISTRY["add"].func(left, right)
    expected = left + right
    pd.testing.assert_series_equal(result, expected)


def test_sub_operator(sample_dataset_dir, test_config) -> None:
    panel = _load_panel(sample_dataset_dir, test_config)
    left = panel["close_hfq"]
    right = panel["open_hfq"]
    result = OPERATOR_REGISTRY["sub"].func(left, right)
    expected = left - right
    pd.testing.assert_series_equal(result, expected)


def test_mul_operator(sample_dataset_dir, test_config) -> None:
    panel = _load_panel(sample_dataset_dir, test_config)
    left = panel["close_hfq"]
    result = OPERATOR_REGISTRY["mul"].func(left, 2.0)
    expected = left * 2.0
    pd.testing.assert_series_equal(result, expected)


def test_div_operator_uses_div0(sample_dataset_dir, test_config) -> None:
    panel = _load_panel(sample_dataset_dir, test_config)
    left = panel["close_hfq"]
    right = panel["open_hfq"].copy()
    right.iloc[0] = 0.0
    result = OPERATOR_REGISTRY["div"].func(left, right)
    expected = div0(left, right)
    pd.testing.assert_series_equal(result, expected)


def test_abs_operator(sample_dataset_dir, test_config) -> None:
    panel = _load_panel(sample_dataset_dir, test_config)
    series = panel["close_hfq"] - panel["open_hfq"]
    result = OPERATOR_REGISTRY["abs"].func(series)
    expected = series.abs()
    pd.testing.assert_series_equal(result, expected)


def test_log_operator_masks_non_positive_values() -> None:
    index = pd.MultiIndex.from_tuples(
        [
            (pd.Timestamp("2024-01-02"), "000001.SZ"),
            (pd.Timestamp("2024-01-02"), "000002.SZ"),
            (pd.Timestamp("2024-01-02"), "000003.SZ"),
            (pd.Timestamp("2024-01-02"), "000004.SZ"),
        ],
        names=["trade_date", "ts_code"],
    )
    series = pd.Series([1.0, np.e, 0.0, -1.0], index=index, dtype=float)
    result = OPERATOR_REGISTRY["log"].func(series)
    expected = pd.Series([0.0, 1.0, np.nan, np.nan], index=index, dtype=float)
    pd.testing.assert_series_equal(result, expected)


def test_delay_operator(sample_dataset_dir, test_config) -> None:
    panel = _load_panel(sample_dataset_dir, test_config)
    series = panel["close_hfq"]
    result = OPERATOR_REGISTRY["delay"].func(series, 1)
    expected = series.groupby(level="ts_code", sort=False).shift(1)
    pd.testing.assert_series_equal(result, expected)


def test_ts_mean_operator(sample_dataset_dir, test_config) -> None:
    panel = _load_panel(sample_dataset_dir, test_config)
    series = panel["close_hfq"]
    result = OPERATOR_REGISTRY["ts_mean"].func(series, 3)
    expected = series.groupby(level="ts_code", sort=False).transform(
        lambda values: values.rolling(3, min_periods=3).mean()
    )
    pd.testing.assert_series_equal(result, expected)


def test_ts_std_operator(sample_dataset_dir, test_config) -> None:
    panel = _load_panel(sample_dataset_dir, test_config)
    series = panel["close_hfq"]
    result = OPERATOR_REGISTRY["ts_std"].func(series, 3)
    expected = series.groupby(level="ts_code", sort=False).transform(
        lambda values: values.rolling(3, min_periods=3).std(ddof=0)
    )
    pd.testing.assert_series_equal(result, expected)


def test_ts_delta_operator(sample_dataset_dir, test_config) -> None:
    panel = _load_panel(sample_dataset_dir, test_config)
    series = panel["close_hfq"]
    result = OPERATOR_REGISTRY["ts_delta"].func(series, 1)
    expected = series - series.groupby(level="ts_code", sort=False).shift(1)
    pd.testing.assert_series_equal(result, expected)


def test_ts_return_operator_uses_div0(sample_dataset_dir, test_config) -> None:
    panel = _load_panel(sample_dataset_dir, test_config)
    series = panel["close_hfq"].copy()
    first_code = series.index.get_level_values("ts_code")[0]
    stock_slice = series.loc[(slice(None), first_code)].copy()
    stock_slice.iloc[0] = 0.0
    series.loc[(slice(None), first_code)] = stock_slice.to_numpy()
    result = OPERATOR_REGISTRY["ts_return"].func(series, 1)
    expected = div0(series, series.groupby(level="ts_code", sort=False).shift(1)) - 1.0
    pd.testing.assert_series_equal(result, expected)


def test_ts_rank_operator(sample_dataset_dir, test_config) -> None:
    panel = _load_panel(sample_dataset_dir, test_config)
    series = panel["close_hfq"]
    result = OPERATOR_REGISTRY["ts_rank"].func(series, 3)
    expected = series.groupby(level="ts_code", sort=False).transform(
        lambda values: values.rolling(3, min_periods=3).apply(
            lambda bucket: pd.Series(bucket).rank(pct=True).iloc[-1],
            raw=False,
        )
    )
    pd.testing.assert_series_equal(result, expected)


def test_cs_rank_operator_respects_universe_mask(sample_dataset_dir, test_config) -> None:
    panel = _load_panel(sample_dataset_dir, test_config).copy()
    first_date = panel.index.get_level_values("trade_date")[0]
    first_row = panel.index[0]
    panel.loc[first_row, "in_universe"] = False
    series = panel["close_hfq"] - panel["open_hfq"]
    result = OPERATOR_REGISTRY["cs_rank"].func(series, panel)

    expected = pd.Series(np.nan, index=series.index, dtype=float)
    mask = panel["in_universe"].fillna(False)
    expected.loc[mask] = series.loc[mask].groupby(level="trade_date", sort=False).transform(
        lambda values: values.rank(method="average", pct=True)
    )
    assert pd.isna(result.loc[first_row])
    pd.testing.assert_series_equal(result.loc[(first_date, slice(None))], expected.loc[(first_date, slice(None))])


def test_cs_zscore_operator_respects_universe_mask(sample_dataset_dir, test_config) -> None:
    panel = _load_panel(sample_dataset_dir, test_config).copy()
    first_row = panel.index[0]
    panel.loc[first_row, "in_universe"] = False
    series = panel["close_hfq"]
    result = OPERATOR_REGISTRY["cs_zscore"].func(series, panel)

    def _zscore(values: pd.Series) -> pd.Series:
        std = values.std(ddof=0)
        if pd.isna(std) or std == 0:
            return pd.Series(np.nan, index=values.index, dtype=float)
        return (values - values.mean()) / std

    expected = pd.Series(np.nan, index=series.index, dtype=float)
    mask = panel["in_universe"].fillna(False)
    expected.loc[mask] = series.loc[mask].groupby(level="trade_date", sort=False).transform(_zscore)
    assert pd.isna(result.loc[first_row])
    pd.testing.assert_series_equal(result, expected)
