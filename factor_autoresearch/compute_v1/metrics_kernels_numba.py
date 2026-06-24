"""Optional Numba metrics kernels for compute engine v1."""

from __future__ import annotations

import numpy as np
from numba import njit

from factor_autoresearch.compute_v1.metrics_kernels import MetricsBackend


@njit(cache=True)
def _pearson_corr_1d_numba(x: np.ndarray, y: np.ndarray) -> float:
    size = x.size
    if size < 2:
        return np.nan

    x_mean = 0.0
    y_mean = 0.0
    for idx in range(size):
        x_mean += x[idx]
        y_mean += y[idx]
    x_mean /= size
    y_mean /= size

    dot = 0.0
    x_norm = 0.0
    y_norm = 0.0
    for idx in range(size):
        x_diff = x[idx] - x_mean
        y_diff = y[idx] - y_mean
        dot += x_diff * y_diff
        x_norm += x_diff * x_diff
        y_norm += y_diff * y_diff

    denom = x_norm * y_norm
    if not np.isfinite(denom) or denom <= 0.0:
        return np.nan
    corr = dot / np.sqrt(denom)
    if not np.isfinite(corr):
        return np.nan
    return corr


@njit(cache=True)
def _average_rank_numba(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values)
    ranks = np.empty(values.size, dtype=np.float64)
    start = 0
    while start < values.size:
        stop = start + 1
        value = values[order[start]]
        while stop < values.size and values[order[stop]] == value:
            stop += 1
        average_rank = (start + 1 + stop) / 2.0
        for idx in range(start, stop):
            ranks[order[idx]] = average_rank
        start = stop
    return ranks


@njit(cache=True)
def _stable_sort_indices_by_values(values: np.ndarray, indices: np.ndarray) -> np.ndarray:
    order = indices.copy()
    temp = np.empty(indices.size, dtype=np.int64)
    width = 1
    size = indices.size

    while width < size:
        left = 0
        while left < size:
            mid = min(left + width, size)
            right = min(left + 2 * width, size)
            i = left
            j = mid
            k = left

            while i < mid and j < right:
                left_index = order[i]
                right_index = order[j]
                left_value = values[left_index]
                right_value = values[right_index]
                if left_value < right_value or (left_value == right_value and left_index <= right_index):
                    temp[k] = left_index
                    i += 1
                else:
                    temp[k] = right_index
                    j += 1
                k += 1

            while i < mid:
                temp[k] = order[i]
                i += 1
                k += 1
            while j < right:
                temp[k] = order[j]
                j += 1
                k += 1

            left += 2 * width

        for idx in range(size):
            order[idx] = temp[idx]
        width *= 2

    return order


@njit(cache=True)
def _rowwise_corr_numba(x: np.ndarray, y: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    out = np.empty(x.shape[0], dtype=np.float64)
    out[:] = np.nan
    scratch_x = np.empty(x.shape[1], dtype=np.float64)
    scratch_y = np.empty(y.shape[1], dtype=np.float64)

    for row in range(x.shape[0]):
        count = 0
        for col in range(x.shape[1]):
            if valid_mask[row, col]:
                scratch_x[count] = x[row, col]
                scratch_y[count] = y[row, col]
                count += 1
        if count < 2:
            continue
        out[row] = _pearson_corr_1d_numba(scratch_x[:count], scratch_y[:count])

    return out


@njit(cache=True)
def _rowwise_spearman_numba(x: np.ndarray, y: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    out = np.empty(x.shape[0], dtype=np.float64)
    out[:] = np.nan
    scratch_x = np.empty(x.shape[1], dtype=np.float64)
    scratch_y = np.empty(y.shape[1], dtype=np.float64)

    for row in range(x.shape[0]):
        count = 0
        for col in range(x.shape[1]):
            if valid_mask[row, col]:
                scratch_x[count] = x[row, col]
                scratch_y[count] = y[row, col]
                count += 1
        if count < 2:
            continue
        x_rank = _average_rank_numba(scratch_x[:count])
        y_rank = _average_rank_numba(scratch_y[:count])
        out[row] = _pearson_corr_1d_numba(x_rank, y_rank)

    return out


@njit(cache=True)
def _quantile_stats_numba(
    factor_matrix: np.ndarray,
    return_matrix: np.ndarray,
    valid_mask: np.ndarray,
    quantiles: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    day_count = factor_matrix.shape[0]
    asset_count = factor_matrix.shape[1]
    long_short = np.empty(day_count, dtype=np.float64)
    monotonicity = np.empty(day_count, dtype=np.float64)
    long_short[:] = np.nan
    monotonicity[:] = np.nan
    bucket_count = np.zeros(day_count, dtype=np.int64)
    quantile_returns = np.empty((day_count, quantiles), dtype=np.float64)
    quantile_returns[:] = np.nan

    valid_indices = np.empty(asset_count, dtype=np.int64)
    edges = np.empty(max(quantiles - 1, 1), dtype=np.float64)
    bucket_sums = np.empty(quantiles, dtype=np.float64)
    bucket_sizes = np.empty(quantiles, dtype=np.int64)
    bucket_means = np.empty(quantiles, dtype=np.float64)
    bucket_x = np.empty(quantiles, dtype=np.float64)

    for day_index in range(day_count):
        valid_count = 0
        for col in range(asset_count):
            if valid_mask[day_index, col]:
                valid_indices[valid_count] = col
                valid_count += 1
        if valid_count < quantiles:
            continue

        ordered = _stable_sort_indices_by_values(factor_matrix[day_index], valid_indices[:valid_count])
        for edge_index in range(quantiles - 1):
            edges[edge_index] = 1.0 + (valid_count - 1.0) * (edge_index + 1.0) / quantiles

        for bucket in range(quantiles):
            bucket_sums[bucket] = 0.0
            bucket_sizes[bucket] = 0
            bucket_means[bucket] = np.nan
            bucket_x[bucket] = bucket + 1.0

        for order_index in range(valid_count):
            rank_value = order_index + 1.0
            bucket = 0
            while bucket < quantiles - 1 and rank_value >= edges[bucket]:
                bucket += 1
            asset_index = ordered[order_index]
            bucket_sums[bucket] += return_matrix[day_index, asset_index]
            bucket_sizes[bucket] += 1

        count = 0
        for bucket in range(quantiles):
            if bucket_sizes[bucket] > 0:
                bucket_means[bucket] = bucket_sums[bucket] / bucket_sizes[bucket]
                quantile_returns[day_index, bucket] = bucket_means[bucket]
                count += 1
        bucket_count[day_index] = count

        if count >= 2:
            long_short[day_index] = bucket_means[count - 1] - bucket_means[0]
            monotonicity[day_index] = _pearson_corr_1d_numba(
                bucket_x[:count],
                _average_rank_numba(bucket_means[:count]),
            )

    return long_short, monotonicity, bucket_count, quantile_returns


def build_numba_backend() -> MetricsBackend:
    """Build the optional Numba backend."""

    return MetricsBackend(
        name="numba",
        rowwise_corr=_rowwise_corr_numba,
        rowwise_spearman=_rowwise_spearman_numba,
        quantile_stats=_quantile_stats_numba,
    )
