"""
Compute v1 指标 kernel 模块
提供 NumPy 默认实现，并按需接入 Numba 加速后端。
不负责指标字段组装，只负责数组级核心计算。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

Array = np.ndarray


# ============== 后端合同 ==============
@dataclass(frozen=True)
class MetricsBackend:
    """后端合同: 封装一组可替换的指标 kernel。"""

    name: str
    rowwise_corr: Callable[[Array, Array, Array], Array]
    rowwise_spearman: Callable[[Array, Array, Array], Array]
    quantile_stats: Callable[[Array, Array, Array, int], tuple[Array, Array, Array, Array]]


# ============== NumPy 基础函数 ==============
def _pearson_corr_1d(x: Array, y: Array) -> float:
    if x.size < 2:
        return np.nan
    x_centered = x - float(np.mean(x))
    y_centered = y - float(np.mean(y))
    x_norm = float(np.dot(x_centered, x_centered))
    y_norm = float(np.dot(y_centered, y_centered))
    denom = x_norm * y_norm
    if not np.isfinite(denom) or denom <= 0.0:
        return np.nan
    corr = float(np.dot(x_centered, y_centered) / np.sqrt(denom))
    return corr if np.isfinite(corr) else np.nan


def _average_rank_1d(values: Array) -> Array:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(values.size, dtype=float)
    start = 0
    while start < values.size:
        stop = start + 1
        value = values[order[start]]
        while stop < values.size and values[order[stop]] == value:
            stop += 1
        average_rank = (start + 1 + stop) / 2.0
        ranks[order[start:stop]] = average_rank
        start = stop
    return ranks




# ============== NumPy 指标 kernel ==============
def rowwise_corr_numpy(x: Array, y: Array, valid_mask: Array) -> Array:
    out = np.full(x.shape[0], np.nan, dtype=float)
    for row in range(x.shape[0]):
        mask = valid_mask[row]
        if int(mask.sum()) < 2:
            continue
        out[row] = _pearson_corr_1d(x[row, mask], y[row, mask])
    return out


def rowwise_spearman_numpy(x: Array, y: Array, valid_mask: Array) -> Array:
    out = np.full(x.shape[0], np.nan, dtype=float)
    for row in range(x.shape[0]):
        mask = valid_mask[row]
        if int(mask.sum()) < 2:
            continue
        x_rank = _average_rank_1d(x[row, mask])
        y_rank = _average_rank_1d(y[row, mask])
        out[row] = _pearson_corr_1d(x_rank, y_rank)
    return out


def quantile_stats_numpy(
    factor_matrix: Array,
    return_matrix: Array,
    valid_mask: Array,
    quantiles: int,
) -> tuple[Array, Array, Array, Array]:
    day_count = factor_matrix.shape[0]
    long_short = np.full(day_count, np.nan, dtype=float)
    monotonicity = np.full(day_count, np.nan, dtype=float)
    bucket_count = np.zeros(day_count, dtype=int)
    quantile_returns = np.full((day_count, quantiles), np.nan, dtype=float)

    for day_index in range(day_count):
        valid_indices = np.flatnonzero(valid_mask[day_index])
        valid_count = valid_indices.size
        if valid_count < quantiles:
            continue

        ordered = valid_indices[np.argsort(factor_matrix[day_index, valid_indices], kind="mergesort")]
        ranks = np.arange(1, valid_count + 1, dtype=float)
        edges = 1.0 + (valid_count - 1.0) * np.arange(1, quantiles, dtype=float) / quantiles
        labels = np.searchsorted(edges, ranks, side="left")

        bucket_returns = np.full(quantiles, np.nan, dtype=float)
        for bucket in range(quantiles):
            bucket_assets = ordered[labels == bucket]
            if bucket_assets.size == 0:
                continue
            bucket_returns[bucket] = float(np.mean(return_matrix[day_index, bucket_assets]))

        non_empty = np.isfinite(bucket_returns)
        count = int(non_empty.sum())
        bucket_count[day_index] = count
        if count == 0:
            continue

        quantile_returns[day_index] = bucket_returns
        if count >= 2:
            ordered_returns = bucket_returns[non_empty]
            long_short[day_index] = float(ordered_returns[-1] - ordered_returns[0])
            bucket_index = np.arange(1, count + 1, dtype=float)
            monotonicity[day_index] = _pearson_corr_1d(bucket_index, _average_rank_1d(ordered_returns))

    return long_short, monotonicity, bucket_count, quantile_returns




# ============== 后端选择 ==============
def _numpy_backend() -> MetricsBackend:
    return MetricsBackend(
        name="numpy",
        rowwise_corr=rowwise_corr_numpy,
        rowwise_spearman=rowwise_spearman_numpy,
        quantile_stats=quantile_stats_numpy,
    )


@lru_cache(maxsize=1)
def _load_numba_backend() -> MetricsBackend:
    from factor_autoresearch.compute_v1.metrics_kernels_numba import build_numba_backend

    return build_numba_backend()


def resolve_metrics_backend(name: str = "auto") -> MetricsBackend:
    """后端选择: auto 优先 Numba，不可用时回退 NumPy。"""

    if name not in {"auto", "numpy", "numba"}:
        raise ValueError("metrics backend must be one of: auto, numpy, numba")
    if name == "numpy":
        return _numpy_backend()
    if name == "numba":
        try:
            return _load_numba_backend()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"numba metrics backend is not available: {exc}") from exc
    try:
        return _load_numba_backend()
    except Exception:
        return _numpy_backend()
