"""
算子库模块
定义因子 DSL 使用的基础算子与注册表。
命名约定：
- 二元基础算子使用 add/sub/mul/div
- 时间序列算子使用 ts_ 前缀
- 截面算子使用 cs_ 前缀
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

OperatorKind = Literal["unary", "binary", "window", "panel"]


@dataclass(frozen=True)
class OperatorSpec:
    """算子描述: 记录调用类型、参数个数和实现函数。"""

    name: str
    kind: OperatorKind
    arg_count: int
    func: Callable[..., pd.Series]


# ============== 基础辅助函数 ==============
def div0(x: pd.Series, y: pd.Series | float) -> pd.Series:
    """安全除法: 执行 x / y，并把除零结果处理为 NaN。"""
    if isinstance(y, pd.Series):
        z = x / y.replace(0, np.nan)
    else:
        z = x / (np.nan if y == 0 else y)
    return z.replace([np.inf, -np.inf], np.nan)


def _by(x: pd.Series) -> pd.core.groupby.generic.SeriesGroupBy:
    """按股票分组: 供时间序列算子复用。"""
    return x.groupby(level="ts_code", sort=False)


# ============== 基础算术算子 ==============
def add(x: pd.Series, y: pd.Series | float) -> pd.Series:
    """加法: x + y"""
    return x + y


def sub(x: pd.Series, y: pd.Series | float) -> pd.Series:
    """减法: x - y"""
    return x - y


def mul(x: pd.Series, y: pd.Series | float) -> pd.Series:
    """乘法: x * y"""
    return x * y


def div(x: pd.Series, y: pd.Series | float) -> pd.Series:
    """除法: x / y，并处理除零。"""
    return div0(x, y)


# ============== 单参数算子 ==============
def abs_(x: pd.Series) -> pd.Series:
    """绝对值: |x|"""
    return x.abs()


def log(x: pd.Series) -> pd.Series:
    """自然对数: log(x)，非正数位置保留为 NaN。"""
    return np.log(x.where(x > 0))


# ============== 时间序列算子 ==============
def delay(x: pd.Series, d: int) -> pd.Series:
    """延迟算子: 返回 d 天前的取值。"""
    return _by(x).shift(d)


def ts_mean(x: pd.Series, d: int) -> pd.Series:
    """滚动均值: 返回过去 d 天的平均值。"""
    g = _by(x)
    return g.transform(lambda v: v.rolling(d, min_periods=d).mean())


def ts_std(x: pd.Series, d: int) -> pd.Series:
    """滚动标准差: 返回过去 d 天的标准差。"""
    g = _by(x)
    return g.transform(lambda v: v.rolling(d, min_periods=d).std(ddof=0))


def ts_delta(x: pd.Series, d: int) -> pd.Series:
    """差分算子: x - delay(x, d)"""
    g = _by(x)
    return x - g.shift(d)


def ts_return(x: pd.Series, d: int) -> pd.Series:
    """收益率: x 相对 d 天前取值的变化比例。"""
    g = _by(x)
    return div0(x, g.shift(d)) - 1.0


def ts_rank(x: pd.Series, d: int) -> pd.Series:
    """时序分位: 当前值在过去 d 天窗口内的分位排名。"""
    g = _by(x)
    return g.transform(
        lambda v: v.rolling(d, min_periods=d).apply(
            lambda b: pd.Series(b).rank(pct=True).iloc[-1],
            raw=False,
        )
    )


# ============== 截面算子 ==============
def cs_rank(x: pd.Series, p: pd.DataFrame) -> pd.Series:
    """截面分位: 返回当日股票池内的分位排名。"""
    out = pd.Series(np.nan, index=x.index, dtype=float)
    m = p["in_universe"].fillna(False)
    out.loc[m] = x.loc[m].groupby(level="trade_date", sort=False).transform(
        lambda v: v.rank(method="average", pct=True)
    )
    return out


def cs_zscore(x: pd.Series, p: pd.DataFrame) -> pd.Series:
    """截面标准化: 返回当日股票池内的 z-score。"""

    def z(v: pd.Series) -> pd.Series:
        """单日标准化: 对单个交易日截面做 z-score。"""
        s = v.std(ddof=0)
        if pd.isna(s) or s == 0:
            return pd.Series(np.nan, index=v.index, dtype=float)
        return (v - v.mean()) / s

    out = pd.Series(np.nan, index=x.index, dtype=float)
    m = p["in_universe"].fillna(False)
    out.loc[m] = x.loc[m].groupby(level="trade_date", sort=False).transform(z)
    return out


# ============== 算子注册表 ==============
INFIX_OPERATOR_REGISTRY: dict[str, OperatorSpec] = {
    "add": OperatorSpec(name="add", kind="binary", arg_count=2, func=add),
    "sub": OperatorSpec(name="sub", kind="binary", arg_count=2, func=sub),
    "mul": OperatorSpec(name="mul", kind="binary", arg_count=2, func=mul),
    "div": OperatorSpec(name="div", kind="binary", arg_count=2, func=div),
}


FUNCTION_OPERATOR_REGISTRY: dict[str, OperatorSpec] = {
    "abs": OperatorSpec(name="abs", kind="unary", arg_count=1, func=abs_),
    "log": OperatorSpec(name="log", kind="unary", arg_count=1, func=log),
    "delay": OperatorSpec(name="delay", kind="window", arg_count=2, func=delay),
    "ts_mean": OperatorSpec(name="ts_mean", kind="window", arg_count=2, func=ts_mean),
    "ts_std": OperatorSpec(name="ts_std", kind="window", arg_count=2, func=ts_std),
    "ts_delta": OperatorSpec(name="ts_delta", kind="window", arg_count=2, func=ts_delta),
    "ts_return": OperatorSpec(name="ts_return", kind="window", arg_count=2, func=ts_return),
    "ts_rank": OperatorSpec(name="ts_rank", kind="window", arg_count=2, func=ts_rank),
    "cs_rank": OperatorSpec(name="cs_rank", kind="panel", arg_count=1, func=cs_rank),
    "cs_zscore": OperatorSpec(name="cs_zscore", kind="panel", arg_count=1, func=cs_zscore),
}


OPERATOR_REGISTRY: dict[str, OperatorSpec] = {
    # 统一从这里查看当前 DSL 支持的全部算子。
    **INFIX_OPERATOR_REGISTRY,
    **FUNCTION_OPERATOR_REGISTRY,
}
