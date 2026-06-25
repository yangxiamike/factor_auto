"""
Compute v1 诊断表模块
负责把 MetricsResult 展平为稳定的诊断表。
不重新计算指标，只做展示和落盘友好的投影。
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from factor_autoresearch.compute_legacy.metrics import MetricsResult

# ============== 字段合同 ==============
_HORIZON_COLUMNS = [
    "candidate_id",
    "horizon",
    "ic_mean",
    "rankic_mean",
    "icir",
    "coverage_mean",
    "long_short_return",
    "monotonicity",
    "effective_trade_days",
    "complexity_score",
]

_IC_SERIES_COLUMNS = [
    "candidate_id",
    "trade_date",
    "horizon",
    "coverage",
    "valid_count",
    "ic",
    "rankic",
    "long_short_return",
    "monotonicity",
    "bucket_count",
]


# ============== 诊断结果结构 ==============
@dataclass(frozen=True)
class MetricsDiagnostics:
    """诊断结果: 包含 horizon、日度、分组和聚合四张表。"""

    horizon_table: pd.DataFrame
    daily_summary_table: pd.DataFrame
    quantile_table: pd.DataFrame
    aggregate_table: pd.DataFrame


# ============== 基础辅助函数 ==============
def _empty_frame(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)




# ============== 诊断表构建 ==============
def build_metrics_diagnostics(metrics_result: MetricsResult) -> MetricsDiagnostics:
    """诊断表构建: 将指标结果投影为确定性表结构。"""

    horizon_rows = metrics_result.horizon_rows.copy()
    ic_series = metrics_result.ic_series.copy()

    quantile_columns = sorted(
        column for column in horizon_rows.columns if column.startswith("quantile_return_q")
    )
    horizon_columns = _HORIZON_COLUMNS + quantile_columns
    if horizon_rows.empty:
        horizon_table = _empty_frame(horizon_columns)
    else:
        horizon_table = horizon_rows.reindex(columns=horizon_columns)

    if ic_series.empty:
        daily_summary_table = _empty_frame(
            [
                "candidate_id",
                "horizon",
                "trade_days",
                "effective_trade_days",
                "coverage_mean",
                "ic_mean",
                "rankic_mean",
                "long_short_return",
                "monotonicity",
            ]
        )
    else:
        ic_table = ic_series.reindex(columns=_IC_SERIES_COLUMNS)
        daily_summary_table = (
            ic_table.groupby(["candidate_id", "horizon"], sort=False)
            .agg(
                trade_days=("trade_date", "size"),
                effective_trade_days=("ic", lambda values: int(values.notna().sum())),
                coverage_mean=("coverage", "mean"),
                ic_mean=("ic", "mean"),
                rankic_mean=("rankic", "mean"),
                long_short_return=("long_short_return", "mean"),
                monotonicity=("monotonicity", "mean"),
            )
            .reset_index()
        )

    if horizon_rows.empty or not quantile_columns:
        quantile_table = _empty_frame(["candidate_id", "horizon", "quantile", "mean_return"])
    else:
        quantile_table = (
            horizon_rows.melt(
                id_vars=["candidate_id", "horizon"],
                value_vars=quantile_columns,
                var_name="metric_name",
                value_name="mean_return",
            )
            .dropna(subset=["mean_return"])
            .assign(
                quantile=lambda frame: frame["metric_name"]
                .str.extract(r"quantile_return_q(\d+)_", expand=False)
                .astype(int)
            )
            .loc[:, ["candidate_id", "horizon", "quantile", "mean_return"]]
            .reset_index(drop=True)
        )

    aggregate_table = pd.DataFrame([metrics_result.aggregate]).sort_index(axis=1)

    return MetricsDiagnostics(
        horizon_table=horizon_table.reset_index(drop=True),
        daily_summary_table=daily_summary_table.reset_index(drop=True),
        quantile_table=quantile_table,
        aggregate_table=aggregate_table.reset_index(drop=True),
    )
