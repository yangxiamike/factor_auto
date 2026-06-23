from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np
import pandas as pd

OperatorKind = Literal["single_arg", "binary", "window"]


class OperatorFunc(Protocol):
    def __call__(
        self,
        series: pd.Series,
        other: pd.Series | float | None = None,
        *,
        panel: pd.DataFrame | None = None,
        window: int | None = None,
    ) -> pd.Series: ...


@dataclass(frozen=True)
class OperatorSpec:
    name: str
    kind: OperatorKind
    arg_count: int
    func: OperatorFunc


def _coerce_series(value: pd.Series | float, other: pd.Series | float) -> pd.Series:
    if isinstance(value, pd.Series):
        return value.astype(float)
    if isinstance(other, pd.Series):
        return pd.Series(float(value), index=other.index, dtype=float)
    return pd.Series(float(value), dtype=float)


def safe_divide(left: pd.Series | float, right: pd.Series | float) -> pd.Series:
    left_series = _coerce_series(left, right)
    right_series = _coerce_series(right, left)
    result = left_series / right_series.replace(0, np.nan)
    return result.replace([np.inf, -np.inf], np.nan)


def sanitize_series(series: pd.Series) -> pd.Series:
    return series.replace([np.inf, -np.inf], np.nan)


def _group_by_code(series: pd.Series) -> pd.core.groupby.generic.SeriesGroupBy:
    return series.groupby(level="ts_code", sort=False)


def _require_panel(panel: pd.DataFrame | None) -> pd.DataFrame:
    if panel is None:
        raise ValueError("panel is required for this operator")
    return panel


def _require_other(other: pd.Series | float | None, name: str) -> pd.Series | float:
    if other is None:
        raise ValueError(f"{name} requires a second operand")
    return other


# Basic arithmetic operators keep only the math definition and minimal protection.
def op_add(
    series: pd.Series,
    other: pd.Series | float | None = None,
    *,
    panel: pd.DataFrame | None = None,
    window: int | None = None,
) -> pd.Series:
    return sanitize_series(series + _require_other(other, "add"))


def op_sub(
    series: pd.Series,
    other: pd.Series | float | None = None,
    *,
    panel: pd.DataFrame | None = None,
    window: int | None = None,
) -> pd.Series:
    return sanitize_series(series - _require_other(other, "sub"))


def op_mul(
    series: pd.Series,
    other: pd.Series | float | None = None,
    *,
    panel: pd.DataFrame | None = None,
    window: int | None = None,
) -> pd.Series:
    return sanitize_series(series * _require_other(other, "mul"))


def op_div(
    series: pd.Series,
    other: pd.Series | float | None = None,
    *,
    panel: pd.DataFrame | None = None,
    window: int | None = None,
) -> pd.Series:
    return safe_divide(series, _require_other(other, "div"))


# Unary, time-series, and cross-sectional operators keep the panel semantics.
def op_abs(
    series: pd.Series,
    other: pd.Series | float | None = None,
    *,
    panel: pd.DataFrame | None = None,
    window: int | None = None,
) -> pd.Series:
    return series.abs()


def op_log(
    series: pd.Series,
    other: pd.Series | float | None = None,
    *,
    panel: pd.DataFrame | None = None,
    window: int | None = None,
) -> pd.Series:
    result = pd.Series(np.nan, index=series.index, dtype=float)
    positive = series > 0
    result.loc[positive] = np.log(series.loc[positive])
    return result


def op_delay(
    series: pd.Series,
    other: pd.Series | float | None = None,
    *,
    panel: pd.DataFrame | None = None,
    window: int | None = None,
) -> pd.Series:
    if window is None:
        raise ValueError("window is required for delay")
    return _group_by_code(series).shift(window)


def op_ts_mean(
    series: pd.Series,
    other: pd.Series | float | None = None,
    *,
    panel: pd.DataFrame | None = None,
    window: int | None = None,
) -> pd.Series:
    if window is None:
        raise ValueError("window is required for ts_mean")
    grouped = _group_by_code(series)
    return grouped.transform(lambda values: values.rolling(window, min_periods=window).mean())


def op_ts_std(
    series: pd.Series,
    other: pd.Series | float | None = None,
    *,
    panel: pd.DataFrame | None = None,
    window: int | None = None,
) -> pd.Series:
    if window is None:
        raise ValueError("window is required for ts_std")
    grouped = _group_by_code(series)
    return grouped.transform(lambda values: values.rolling(window, min_periods=window).std(ddof=0))


def op_ts_delta(
    series: pd.Series,
    other: pd.Series | float | None = None,
    *,
    panel: pd.DataFrame | None = None,
    window: int | None = None,
) -> pd.Series:
    if window is None:
        raise ValueError("window is required for ts_delta")
    grouped = _group_by_code(series)
    return series - grouped.shift(window)


def op_ts_return(
    series: pd.Series,
    other: pd.Series | float | None = None,
    *,
    panel: pd.DataFrame | None = None,
    window: int | None = None,
) -> pd.Series:
    if window is None:
        raise ValueError("window is required for ts_return")
    grouped = _group_by_code(series)
    return safe_divide(series, grouped.shift(window)) - 1.0


def op_ts_rank(
    series: pd.Series,
    other: pd.Series | float | None = None,
    *,
    panel: pd.DataFrame | None = None,
    window: int | None = None,
) -> pd.Series:
    if window is None:
        raise ValueError("window is required for ts_rank")
    grouped = _group_by_code(series)
    return grouped.transform(
        lambda values: values.rolling(window, min_periods=window).apply(
            lambda bucket: pd.Series(bucket).rank(pct=True).iloc[-1],
            raw=False,
        )
    )


def op_cs_rank(
    series: pd.Series,
    other: pd.Series | float | None = None,
    *,
    panel: pd.DataFrame | None = None,
    window: int | None = None,
) -> pd.Series:
    panel = _require_panel(panel)
    result = pd.Series(np.nan, index=series.index, dtype=float)
    mask = panel["in_universe"].fillna(False)
    result.loc[mask] = series.loc[mask].groupby(level="trade_date", sort=False).transform(
        lambda values: values.rank(method="average", pct=True)
    )
    return result


def op_cs_zscore(
    series: pd.Series,
    other: pd.Series | float | None = None,
    *,
    panel: pd.DataFrame | None = None,
    window: int | None = None,
) -> pd.Series:
    panel = _require_panel(panel)

    def _zscore(values: pd.Series) -> pd.Series:
        std = values.std(ddof=0)
        if pd.isna(std) or std == 0:
            return pd.Series(np.nan, index=values.index, dtype=float)
        return (values - values.mean()) / std

    result = pd.Series(np.nan, index=series.index, dtype=float)
    mask = panel["in_universe"].fillna(False)
    result.loc[mask] = series.loc[mask].groupby(level="trade_date", sort=False).transform(_zscore)
    return result


# The combined registry is the single place to inspect all supported operators.
INFIX_OPERATOR_REGISTRY: dict[str, OperatorSpec] = {
    "add": OperatorSpec(name="add", kind="binary", arg_count=2, func=op_add),
    "sub": OperatorSpec(name="sub", kind="binary", arg_count=2, func=op_sub),
    "mul": OperatorSpec(name="mul", kind="binary", arg_count=2, func=op_mul),
    "div": OperatorSpec(name="div", kind="binary", arg_count=2, func=op_div),
}


FUNCTION_OPERATOR_REGISTRY: dict[str, OperatorSpec] = {
    "abs": OperatorSpec(name="abs", kind="single_arg", arg_count=1, func=op_abs),
    "log": OperatorSpec(name="log", kind="single_arg", arg_count=1, func=op_log),
    "delay": OperatorSpec(name="delay", kind="window", arg_count=2, func=op_delay),
    "ts_mean": OperatorSpec(name="ts_mean", kind="window", arg_count=2, func=op_ts_mean),
    "ts_std": OperatorSpec(name="ts_std", kind="window", arg_count=2, func=op_ts_std),
    "ts_delta": OperatorSpec(name="ts_delta", kind="window", arg_count=2, func=op_ts_delta),
    "ts_return": OperatorSpec(name="ts_return", kind="window", arg_count=2, func=op_ts_return),
    "ts_rank": OperatorSpec(name="ts_rank", kind="window", arg_count=2, func=op_ts_rank),
    "cs_rank": OperatorSpec(name="cs_rank", kind="single_arg", arg_count=1, func=op_cs_rank),
    "cs_zscore": OperatorSpec(name="cs_zscore", kind="single_arg", arg_count=1, func=op_cs_zscore),
}


OPERATOR_REGISTRY: dict[str, OperatorSpec] = {
    **INFIX_OPERATOR_REGISTRY,
    **FUNCTION_OPERATOR_REGISTRY,
}
