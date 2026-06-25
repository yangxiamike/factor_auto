"""NumPy kernels used by compute engine v1."""

from __future__ import annotations

import numpy as np
import pandas as pd


def div0(x: np.ndarray, y: np.ndarray | float) -> np.ndarray:
    """Safe division that maps zero denominators and infinities to NaN."""
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.asarray(x, dtype=float) / np.asarray(y, dtype=float)
    result = np.asarray(result, dtype=float)
    result[~np.isfinite(result)] = np.nan
    return result


def delay(x: np.ndarray, d: int) -> np.ndarray:
    out = np.full_like(np.asarray(x, dtype=float), np.nan, dtype=float)
    if d == 0:
        return np.asarray(x, dtype=float).copy()
    out[d:, :] = np.asarray(x, dtype=float)[:-d, :]
    return out


def ts_return(x: np.ndarray, d: int) -> np.ndarray:
    return div0(x, delay(x, d)) - 1.0


def ts_mean(x: np.ndarray, d: int) -> np.ndarray:
    values = np.asarray(x, dtype=float)
    out = np.full_like(values, np.nan, dtype=float)
    for row in range(d - 1, values.shape[0]):
        window = values[row - d + 1 : row + 1, :]
        valid = np.isfinite(window).sum(axis=0) == d
        out[row, valid] = np.nanmean(window[:, valid], axis=0)
    return out


def ts_std(x: np.ndarray, d: int) -> np.ndarray:
    values = np.asarray(x, dtype=float)
    out = np.full_like(values, np.nan, dtype=float)
    for row in range(d - 1, values.shape[0]):
        window = values[row - d + 1 : row + 1, :]
        valid = np.isfinite(window).sum(axis=0) == d
        out[row, valid] = np.nanstd(window[:, valid], axis=0, ddof=0)
    return out


def ts_rank(x: np.ndarray, d: int) -> np.ndarray:
    values = np.asarray(x, dtype=float)
    out = np.full_like(values, np.nan, dtype=float)
    for row in range(d - 1, values.shape[0]):
        window = values[row - d + 1 : row + 1, :]
        valid = np.isfinite(window).all(axis=0)
        if not np.any(valid):
            continue
        last = window[-1, valid]
        valid_window = window[:, valid]
        count_less = np.sum(valid_window < last, axis=0)
        count_equal = np.sum(valid_window == last, axis=0)
        out[row, valid] = (count_less + (count_equal + 1.0) / 2.0) / d
    return out


def cs_rank(x: np.ndarray, universe_mask: np.ndarray) -> np.ndarray:
    values = np.asarray(x, dtype=float)
    out = np.full_like(values, np.nan, dtype=float)
    for row in range(values.shape[0]):
        mask = universe_mask[row] & np.isfinite(values[row])
        if mask.any():
            out[row, mask] = pd.Series(values[row, mask]).rank(method="average", pct=True).to_numpy()
    return out


def cs_zscore(x: np.ndarray, universe_mask: np.ndarray) -> np.ndarray:
    values = np.asarray(x, dtype=float)
    out = np.full_like(values, np.nan, dtype=float)
    for row in range(values.shape[0]):
        mask = universe_mask[row] & np.isfinite(values[row])
        if not mask.any():
            continue
        std = float(np.nanstd(values[row, mask], ddof=0))
        if not np.isfinite(std) or std == 0:
            continue
        out[row, mask] = (values[row, mask] - float(np.nanmean(values[row, mask]))) / std
    return out


def daily_ic(factor: np.ndarray, returns: np.ndarray, universe_mask: np.ndarray, min_count: int) -> np.ndarray:
    return _daily_corr(factor, returns, universe_mask, min_count, rank=False)


def daily_rankic(factor: np.ndarray, returns: np.ndarray, universe_mask: np.ndarray, min_count: int) -> np.ndarray:
    return _daily_corr(factor, returns, universe_mask, min_count, rank=True)


def _daily_corr(
    factor: np.ndarray,
    returns: np.ndarray,
    universe_mask: np.ndarray,
    min_count: int,
    *,
    rank: bool,
) -> np.ndarray:
    out = np.full(factor.shape[0], np.nan, dtype=float)
    for row in range(factor.shape[0]):
        mask = universe_mask[row] & np.isfinite(factor[row]) & np.isfinite(returns[row])
        if int(mask.sum()) < min_count:
            continue
        x = pd.Series(factor[row, mask])
        y = pd.Series(returns[row, mask])
        out[row] = float(x.corr(y, method="spearman" if rank else "pearson"))
    return out
