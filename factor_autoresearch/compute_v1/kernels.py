"""
compute engine v1 NumPy 内核: 提供矩阵化时间序列、截面和 IC 计算。
本模块只处理二维数组计算，不负责表达式解析、数据装载或指标汇总。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ============== 基础数值内核 ==============
def div0(x: np.ndarray, y: np.ndarray | float) -> np.ndarray:
    """安全除法: 把零分母、无穷值和非法结果统一转成 NaN。"""
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.asarray(x, dtype=float) / np.asarray(y, dtype=float)
    result = np.asarray(result, dtype=float)
    result[~np.isfinite(result)] = np.nan
    return result


def delay(x: np.ndarray, d: int) -> np.ndarray:
    """滞后矩阵: 按日期轴向后平移 d 期，前段补 NaN。"""
    out = np.full_like(np.asarray(x, dtype=float), np.nan, dtype=float)
    if d == 0:
        return np.asarray(x, dtype=float).copy()
    out[d:, :] = np.asarray(x, dtype=float)[:-d, :]
    return out


# ============== 时间序列内核 ==============
def ts_return(x: np.ndarray, d: int) -> np.ndarray:
    """时间序列收益: 计算当前值相对 d 期前的变化率。"""
    return div0(x, delay(x, d)) - 1.0


def ts_mean(x: np.ndarray, d: int) -> np.ndarray:
    """时间序列均值: 仅在完整 d 期窗口有效时输出均值。"""
    values = np.asarray(x, dtype=float)
    out = np.full_like(values, np.nan, dtype=float)
    for row in range(d - 1, values.shape[0]):
        window = values[row - d + 1 : row + 1, :]
        valid = np.isfinite(window).sum(axis=0) == d
        out[row, valid] = np.nanmean(window[:, valid], axis=0)
    return out


def ts_std(x: np.ndarray, d: int) -> np.ndarray:
    """时间序列标准差: 仅在完整 d 期窗口有效时输出总体标准差。"""
    values = np.asarray(x, dtype=float)
    out = np.full_like(values, np.nan, dtype=float)
    for row in range(d - 1, values.shape[0]):
        window = values[row - d + 1 : row + 1, :]
        valid = np.isfinite(window).sum(axis=0) == d
        out[row, valid] = np.nanstd(window[:, valid], axis=0, ddof=0)
    return out


def ts_rank(x: np.ndarray, d: int) -> np.ndarray:
    """时间序列排名: 返回窗口末值在完整 d 期窗口中的百分位排名。"""
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


# ============== 截面内核 ==============
def cs_rank(x: np.ndarray, universe_mask: np.ndarray) -> np.ndarray:
    """截面排名: 在每日有效股票池内输出百分位排名。"""
    values = np.asarray(x, dtype=float)
    out = np.full_like(values, np.nan, dtype=float)
    for row in range(values.shape[0]):
        mask = universe_mask[row] & np.isfinite(values[row])
        if mask.any():
            out[row, mask] = pd.Series(values[row, mask]).rank(method="average", pct=True).to_numpy()
    return out


def cs_zscore(x: np.ndarray, universe_mask: np.ndarray) -> np.ndarray:
    """截面标准化: 在每日有效股票池内做均值方差标准化。"""
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


# ============== IC 内核 ==============
def daily_ic(factor: np.ndarray, returns: np.ndarray, universe_mask: np.ndarray, min_count: int) -> np.ndarray:
    """每日 IC: 按日期计算因子值和未来收益的 Pearson 相关。"""
    return _daily_corr(factor, returns, universe_mask, min_count, rank=False)


def daily_rankic(factor: np.ndarray, returns: np.ndarray, universe_mask: np.ndarray, min_count: int) -> np.ndarray:
    """每日 RankIC: 按日期计算因子值和未来收益排名的 Spearman 相关。"""
    return _daily_corr(factor, returns, universe_mask, min_count, rank=True)


def _daily_corr(
    factor: np.ndarray,
    returns: np.ndarray,
    universe_mask: np.ndarray,
    min_count: int,
    *,
    rank: bool,
) -> np.ndarray:
    """每日相关: 根据 rank 参数复用 Pearson / Spearman 的共同流程。"""
    out = np.full(factor.shape[0], np.nan, dtype=float)
    for row in range(factor.shape[0]):
        mask = universe_mask[row] & np.isfinite(factor[row]) & np.isfinite(returns[row])
        if int(mask.sum()) < min_count:
            continue
        x = pd.Series(factor[row, mask])
        y = pd.Series(returns[row, mask])
        out[row] = float(x.corr(y, method="spearman" if rank else "pearson"))
    return out
