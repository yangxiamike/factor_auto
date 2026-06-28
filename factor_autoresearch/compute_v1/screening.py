"""
Compute v1 Block3 筛选指标模块。
负责把候选因子转换成 Gate0-Gate3 需要的瘦身指标包。
不负责 Gate 判定、产物写入或 Block3 编排。
"""

from __future__ import annotations

import ast
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from factor_autoresearch.candidates import Candidate
from factor_autoresearch.compute_v1.calculator import V1FactorCalc
from factor_autoresearch.compute_v1.metrics_kernels import resolve_metrics_backend
from factor_autoresearch.compute_v1.panel import PanelStore
from factor_autoresearch.compute_v1.preprocess import preprocess_factor_matrix
from factor_autoresearch.config import ExperimentConfig
from factor_autoresearch.data_loader import DatasetBundle
from factor_autoresearch.expression import ExpressionValidationError


# ============== 输出对象 ==============
class MissingComputeV1MetricError(RuntimeError):
    """缺失指标异常: Gate 需要的底层输入或能力在 compute v1 内不可用。"""


@dataclass(frozen=True)
class Block3ScreeningMetricBundle:
    """Block3 指标包: 只包含 Gate 判定直接消费的字段。"""

    gate0_metrics: dict[str, object]
    gate1_metrics: dict[str, object]
    gate2_metrics: dict[str, object]
    gate3_metrics: dict[str, object]
    factor_exposure_ref: str | None
    engine_version: str


@dataclass(frozen=True)
class _ExpressionCheck:
    """表达式检查结果: 保存 Gate0 状态和可复用 AST。"""

    metrics: dict[str, object]
    tree: ast.Expression | None
    is_valid: bool


# ============== 配置与样本适配 ==============
def _resolve_experiment_config(config: Any, sample_view: Any) -> ExperimentConfig:
    """实验配置: 兼容直接传 ExperimentConfig 或由筛选配置包装的写法。"""

    required = ("allowed_fields", "allowed_functions", "allowed_windows", "gate", "preprocess")
    if all(hasattr(config, attr) for attr in required):
        return config
    for source in (config, sample_view):
        for attr in ("experiment_config", "compute_config", "base_config"):
            value = getattr(source, attr, None)
            if value is not None and all(hasattr(value, name) for name in required):
                return value
    raise MissingComputeV1MetricError(
        "compute v1 screening requires an ExperimentConfig via config or sample_view"
    )


def _resolve_admission_horizon(config: Any) -> str:
    """评价周期: Block3 v1 固定读取 admission_horizon，缺省为 5d。"""

    horizon = str(getattr(config, "admission_horizon", "5d"))
    if horizon != "5d":
        raise MissingComputeV1MetricError("Block3 admission_horizon must be fixed to 5d")
    return horizon


def _dataset_from_sample_view(sample_view: Any) -> DatasetBundle:
    """样本视图: 优先使用区块2暴露的筛选切片。"""

    dataset = getattr(sample_view, "dataset", None)
    if dataset is None:
        raise MissingComputeV1MetricError("sample_view must expose a DatasetBundle as dataset")

    panel_view = getattr(sample_view, "panel_view", None)
    forward_returns_view = getattr(sample_view, "forward_returns_view", None)
    if panel_view is None and forward_returns_view is None:
        return dataset
    if panel_view is None or forward_returns_view is None:
        raise MissingComputeV1MetricError(
            "sample_view must expose both panel_view and forward_returns_view for screening slices"
        )
    return DatasetBundle(
        panel=panel_view,
        forward_returns=forward_returns_view,
        manifest=dataset.manifest,
    )


def _requested_set(requested_gates: Sequence[str]) -> set[str]:
    """Gate 请求: 校验调用方只请求已支持的 Gate。"""

    requested = set(requested_gates)
    unknown = requested.difference({"gate0", "gate1", "gate2", "gate3"})
    if unknown:
        raise ValueError(f"unknown requested gates: {', '.join(sorted(unknown))}")
    return requested


# ============== 表达式检查 ==============
def _field_names(node: ast.AST) -> set[str]:
    """字段名提取: 只提取表达式输入字段，不把函数名当字段。"""

    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, ast.Call):
        names: set[str] = set()
        for arg in node.args:
            names.update(_field_names(arg))
        return names
    names = set()
    for child in ast.iter_child_nodes(node):
        names.update(_field_names(child))
    return names


def _has_leakage_field(tree: ast.Expression) -> bool:
    """泄漏检查: 拦截 forward return、label 和 future 类输入字段。"""

    leakage_names = set()
    for name in _field_names(tree.body):
        lowered = name.lower()
        if lowered.startswith("fwd_ret_") or lowered in {"label", "target", "future_return"}:
            leakage_names.add(name)
        if "forward_return" in lowered:
            leakage_names.add(name)
    return bool(leakage_names)


def _expression_depth(node: ast.AST) -> int:
    """表达式深度: 叶子为 1，函数或运算符嵌套逐层加 1。"""

    if isinstance(node, (ast.Name, ast.Constant)):
        return 1
    if isinstance(node, ast.UnaryOp):
        return _expression_depth(node.operand) + 1
    if isinstance(node, ast.BinOp):
        return max(_expression_depth(node.left), _expression_depth(node.right)) + 1
    if isinstance(node, ast.Call):
        if not node.args:
            return 1
        return _expression_depth(node.args[0]) + 1
    child_depths = [_expression_depth(child) for child in ast.iter_child_nodes(node)]
    return max(child_depths, default=0) + 1


def _check_expression(calc: V1FactorCalc, candidate: Candidate) -> _ExpressionCheck:
    """表达式检查: 产出 parse、allowlist、leakage 和深度四项 Gate0 字段。"""

    try:
        tree = calc.validator.parse(candidate.expression)
    except SyntaxError:
        return _ExpressionCheck(
            metrics={
                "expression_parse_status": "failed",
                "expression_allowlist_status": "not_checked",
                "leakage_check_status": "not_checked",
                "expression_depth": None,
            },
            tree=None,
            is_valid=False,
        )

    leakage_detected = _has_leakage_field(tree)
    depth = _expression_depth(tree.body)
    try:
        metadata = calc.validator.analyze(tree.body)
        if candidate.lookback_days < metadata.inferred_lookback:
            raise ExpressionValidationError(
                "declared lookback_days is smaller than inferred expression lookback"
            )
    except ExpressionValidationError:
        return _ExpressionCheck(
            metrics={
                "expression_parse_status": "ok",
                "expression_allowlist_status": "failed",
                "leakage_check_status": "failed" if leakage_detected else "ok",
                "expression_depth": depth,
            },
            tree=tree,
            is_valid=False,
        )

    if leakage_detected:
        return _ExpressionCheck(
            metrics={
                "expression_parse_status": "ok",
                "expression_allowlist_status": "ok",
                "leakage_check_status": "failed",
                "expression_depth": depth,
            },
            tree=tree,
            is_valid=False,
        )

    return _ExpressionCheck(
        metrics={
            "expression_parse_status": "ok",
            "expression_allowlist_status": "ok",
            "leakage_check_status": "ok",
            "expression_depth": depth,
        },
        tree=tree,
        is_valid=True,
    )


# ============== 基础矩阵指标 ==============
def _nanmean_or_nan(values: np.ndarray) -> float:
    """安全均值: 全空或全 NaN 时返回 NaN。"""

    array = np.asarray(values, dtype=float)
    if array.size == 0 or np.isnan(array).all():
        return math.nan
    return float(np.nanmean(array))


def _selected_return_matrix(dataset: DatasetBundle, panel: PanelStore, horizon: str) -> np.ndarray:
    """收益矩阵: 只读取 admission_horizon 对应的 forward return。"""

    column = f"fwd_ret_{horizon}"
    if column not in dataset.forward_returns.columns:
        raise MissingComputeV1MetricError(f"required compute v1 metric input is missing: {column}")
    aligned = dataset.forward_returns.reindex(panel.long_index)
    return aligned[column].to_numpy(dtype=float).reshape(panel.universe_mask.shape)


def _compute_factor_exposure(
    *,
    candidate: Candidate,
    dataset: DatasetBundle,
    experiment_config: ExperimentConfig,
) -> tuple[PanelStore, np.ndarray]:
    """因子暴露: 计算并预处理同一份矩阵，供各 Gate 共用。"""

    panel = PanelStore.from_dataset(dataset)
    calc = V1FactorCalc(experiment_config)
    raw_factor = calc.calculate_matrix(candidate, dataset, panel)
    factor_matrix = preprocess_factor_matrix(raw_factor, panel, experiment_config, dataset.panel["industry"])
    return panel, factor_matrix


def _gate0_health_metrics(
    *,
    factor_matrix: np.ndarray,
    panel: PanelStore,
    experiment_config: ExperimentConfig,
) -> dict[str, object]:
    """Gate0 健康度: 统计覆盖、有效天数、截面样本和分布质量。"""

    universe_mask = np.asarray(panel.universe_mask, dtype=bool)
    factor_valid = universe_mask & np.isfinite(factor_matrix)
    universe_count = universe_mask.sum(axis=1).astype(float)
    valid_count = factor_valid.sum(axis=1).astype(float)
    coverage = np.divide(
        valid_count,
        universe_count,
        out=np.full(valid_count.shape, np.nan, dtype=float),
        where=universe_count > 0,
    )
    finite_values = factor_matrix[factor_valid]
    finite_total = int(factor_valid.sum())
    universe_total = int(universe_mask.sum())
    finite_ratio = finite_total / universe_total if universe_total else math.nan
    unique_ratio = float(np.unique(finite_values).size / finite_total) if finite_total else math.nan
    min_cross_section_size = int(getattr(experiment_config.gate, "min_cross_section_size", 1))

    return {
        "coverage_mean": _nanmean_or_nan(coverage),
        "effective_trade_days": int(np.sum(valid_count >= min_cross_section_size)),
        "median_valid_stock_count": float(np.nanmedian(valid_count)) if valid_count.size else math.nan,
        "finite_ratio": float(finite_ratio),
        "std": float(np.nanstd(finite_values)) if finite_total else math.nan,
        "unique_ratio": unique_ratio,
    }


# ============== Gate1 和 Gate3 指标 ==============
def _direction_sign(expected_direction: str) -> float:
    """方向符号: 把 negative 因子方向统一成越大越好。"""

    if expected_direction == "positive":
        return 1.0
    if expected_direction == "negative":
        return -1.0
    raise MissingComputeV1MetricError("expected_direction must be 'positive' or 'negative'")


def _rankic_metrics(
    *,
    candidate: Candidate,
    factor_matrix: np.ndarray,
    return_matrix: np.ndarray,
    panel: PanelStore,
    experiment_config: ExperimentConfig,
    horizon: str,
) -> dict[str, object]:
    """Gate1 指标: 计算固定 horizon 的方向化 RankIC 均值和 IR。"""

    valid_mask = panel.universe_mask & np.isfinite(factor_matrix) & np.isfinite(return_matrix)
    valid_count = valid_mask.sum(axis=1).astype(int)
    backend = resolve_metrics_backend("auto")
    rankic = backend.rowwise_spearman(factor_matrix, return_matrix, valid_mask)
    rankic[valid_count < experiment_config.gate.min_cross_section_size] = np.nan

    rankic_mean = _nanmean_or_nan(rankic)
    rankic_std = float(np.nanstd(rankic)) if np.isfinite(rankic).any() else math.nan
    sign = _direction_sign(candidate.expected_direction)
    directional_mean = sign * rankic_mean if np.isfinite(rankic_mean) else math.nan
    directional_ir = (
        directional_mean / rankic_std
        if np.isfinite(directional_mean) and np.isfinite(rankic_std) and not np.isclose(rankic_std, 0.0, atol=1e-12)
        else math.nan
    )
    return {
        "admission_horizon": horizon,
        "expected_direction": candidate.expected_direction,
        "directional_rankic_mean": float(directional_mean),
        "directional_rankic_ir": float(directional_ir),
    }


def _horizon_days(horizon: str) -> int:
    """周期天数: 从 5d 这类 horizon 文本中提取交易日数。"""

    if not horizon.endswith("d"):
        raise MissingComputeV1MetricError(f"unsupported admission_horizon format: {horizon}")
    try:
        days = int(horizon[:-1])
    except ValueError as exc:
        raise MissingComputeV1MetricError(f"unsupported admission_horizon format: {horizon}") from exc
    if days <= 0:
        raise MissingComputeV1MetricError(f"unsupported admission_horizon format: {horizon}")
    return days


def _turnover_proxy(factor_matrix: np.ndarray, valid_mask: np.ndarray, quantiles: int) -> float:
    """换手代理: 用高分组集合相邻日期 Jaccard 距离均值近似。"""

    top_sets: list[set[int]] = []
    for day in range(factor_matrix.shape[0]):
        valid_indices = np.flatnonzero(valid_mask[day])
        if valid_indices.size < quantiles:
            top_sets.append(set())
            continue
        ordered = valid_indices[np.argsort(factor_matrix[day, valid_indices], kind="mergesort")]
        top_size = max(1, int(math.ceil(valid_indices.size / quantiles)))
        top_sets.append(set(int(value) for value in ordered[-top_size:]))

    distances: list[float] = []
    previous: set[int] | None = None
    for current in top_sets:
        if not current:
            continue
        if previous is not None:
            union_size = len(previous.union(current))
            if union_size:
                distances.append(1.0 - len(previous.intersection(current)) / union_size)
        previous = current
    return float(np.mean(distances)) if distances else math.nan


def _long_short_metrics(
    *,
    candidate: Candidate,
    factor_matrix: np.ndarray,
    return_matrix: np.ndarray,
    panel: PanelStore,
    experiment_config: ExperimentConfig,
    config: Any,
    horizon: str,
) -> dict[str, object]:
    """Gate3 指标: 计算方向化多空 Sharpe、有效天数、单调性和换手代理。"""

    valid_mask = panel.universe_mask & np.isfinite(factor_matrix) & np.isfinite(return_matrix)
    quantiles = int(getattr(config, "quantiles", experiment_config.gate.quantiles))
    backend = resolve_metrics_backend("auto")
    long_short, monotonicity, _, _ = backend.quantile_stats(
        factor_matrix,
        return_matrix,
        valid_mask,
        quantiles,
    )
    sign = _direction_sign(candidate.expected_direction)
    directional_long_short = sign * long_short
    valid_long_short = directional_long_short[np.isfinite(directional_long_short)]
    long_short_std = float(np.nanstd(valid_long_short)) if valid_long_short.size else math.nan
    annualization = math.sqrt(252.0 / _horizon_days(horizon))
    sharpe = (
        float(np.nanmean(valid_long_short) / long_short_std * annualization)
        if valid_long_short.size and np.isfinite(long_short_std) and not np.isclose(long_short_std, 0.0, atol=1e-12)
        else math.nan
    )
    monotonicity_mean = _nanmean_or_nan(monotonicity)
    monotonicity_score = sign * monotonicity_mean if np.isfinite(monotonicity_mean) else math.nan
    return {
        "directional_long_short_sharpe": sharpe,
        "long_short_effective_days": int(valid_long_short.size),
        "monotonicity_score": float(monotonicity_score),
        "turnover_proxy": _turnover_proxy(factor_matrix, valid_mask, quantiles),
    }


# ============== Gate2 相关性指标 ==============
def _factor_collection_items(factors: object, fallback_name: str) -> list[tuple[str, object]]:
    """因子集合: 兼容 dict、Series 和 DataFrame 三种输入。"""

    if factors is None:
        return []
    if isinstance(factors, Mapping):
        return [(str(name), value) for name, value in factors.items()]
    if isinstance(factors, pd.Series):
        return [(str(factors.name or fallback_name), factors)]
    if isinstance(factors, pd.DataFrame):
        return [(str(column), factors[column]) for column in factors.columns]
    raise MissingComputeV1MetricError(
        "correlation inputs must be a mapping, pandas Series, pandas DataFrame, or None"
    )


def _factor_to_series(value: object, panel: PanelStore, name: str) -> pd.Series:
    """因子序列: 把相关性输入对齐成 long-index Series。"""

    if isinstance(value, pd.Series):
        return value.reindex(panel.long_index).astype(float).rename(name)
    array = np.asarray(value, dtype=float)
    if array.shape == panel.universe_mask.shape:
        return panel.to_series(name, array)
    if array.ndim == 1 and array.size == len(panel.long_index):
        return pd.Series(array, index=panel.long_index, name=name)
    raise MissingComputeV1MetricError(f"correlation factor {name} shape does not match screening sample")


def _spearman_overlap(left: pd.Series, right: pd.Series) -> tuple[float, int]:
    """相关性: 返回双边有效样本上的 Spearman 相关和 overlap。"""

    frame = pd.concat([left, right], axis=1).dropna()
    overlap = int(len(frame))
    if overlap < 2:
        return math.nan, overlap
    corr = float(frame.iloc[:, 0].corr(frame.iloc[:, 1], method="spearman"))
    return (corr if np.isfinite(corr) else math.nan), overlap


def _correlation_summary(
    *,
    candidate: Candidate,
    factor_matrix: np.ndarray,
    panel: PanelStore,
    config: Any,
    library_factors: object,
    batch_factors: object,
) -> dict[str, object]:
    """Gate2 指标: 计算 batch 和 library 的最大绝对 Spearman 相关。"""

    candidate_series = panel.to_series(candidate.candidate_id, factor_matrix)
    batch_threshold = float(getattr(config, "batch_corr_threshold", 0.5))
    library_threshold = float(getattr(config, "library_corr_threshold", 0.5))
    max_batch = math.nan
    max_library = math.nan
    max_overlap = 0
    correlated_count = 0
    matched_factor_id: str | None = None

    for factor_id, value in _factor_collection_items(batch_factors, "batch_factor"):
        if factor_id == candidate.candidate_id:
            continue
        series = _factor_to_series(value, panel, factor_id)
        corr, overlap = _spearman_overlap(candidate_series, series)
        max_overlap = max(max_overlap, overlap)
        if not np.isfinite(corr):
            continue
        abs_corr = abs(corr)
        max_batch = max(abs_corr, max_batch) if np.isfinite(max_batch) else abs_corr
        if abs_corr >= batch_threshold:
            correlated_count += 1

    for factor_id, value in _factor_collection_items(library_factors, "library_factor"):
        series = _factor_to_series(value, panel, factor_id)
        corr, overlap = _spearman_overlap(candidate_series, series)
        max_overlap = max(max_overlap, overlap)
        if not np.isfinite(corr):
            continue
        abs_corr = abs(corr)
        if not np.isfinite(max_library) or abs_corr > max_library:
            max_library = abs_corr
            matched_factor_id = factor_id
        if abs_corr >= library_threshold:
            correlated_count += 1

    if not np.isfinite(max_library):
        matched_factor_id = None
    return {
        "max_abs_corr_to_batch": float(max_batch),
        "max_abs_corr_to_library": float(max_library),
        "correlation_overlap_count": int(max_overlap),
        "correlated_factor_count": int(correlated_count),
        "matched_factor_id": matched_factor_id,
    }


# ============== 主入口 ==============
def compute_block3_screening_metrics(
    *,
    candidate: Candidate,
    sample_view: object,
    config: object,
    library_factors: object = None,
    batch_factors: object = None,
    requested_gates: Sequence[str] = ("gate0", "gate1", "gate2", "gate3"),
) -> Block3ScreeningMetricBundle:
    """计算 Block3 Gate 指标: 输出瘦身指标包，不做 Gate 判定。"""

    requested = _requested_set(requested_gates)
    experiment_config = _resolve_experiment_config(config, sample_view)
    dataset = _dataset_from_sample_view(sample_view)
    calc = V1FactorCalc(experiment_config)
    expression_check = _check_expression(calc, candidate)
    gate0_metrics = dict(expression_check.metrics) if "gate0" in requested else {}

    if not expression_check.is_valid:
        return Block3ScreeningMetricBundle(
            gate0_metrics=gate0_metrics,
            gate1_metrics={},
            gate2_metrics={},
            gate3_metrics={},
            factor_exposure_ref=None,
            engine_version="compute_v1",
        )

    panel, factor_matrix = _compute_factor_exposure(
        candidate=candidate,
        dataset=dataset,
        experiment_config=experiment_config,
    )
    if "gate0" in requested:
        gate0_metrics.update(
            _gate0_health_metrics(
                factor_matrix=factor_matrix,
                panel=panel,
                experiment_config=experiment_config,
            )
        )

    horizon = _resolve_admission_horizon(config)
    return_matrix: np.ndarray | None = None
    if {"gate1", "gate3"}.intersection(requested):
        return_matrix = _selected_return_matrix(dataset, panel, horizon)

    gate1_metrics = (
        _rankic_metrics(
            candidate=candidate,
            factor_matrix=factor_matrix,
            return_matrix=return_matrix,
            panel=panel,
            experiment_config=experiment_config,
            horizon=horizon,
        )
        if "gate1" in requested and return_matrix is not None
        else {}
    )
    gate2_metrics = (
        _correlation_summary(
            candidate=candidate,
            factor_matrix=factor_matrix,
            panel=panel,
            config=config,
            library_factors=library_factors,
            batch_factors=batch_factors,
        )
        if "gate2" in requested
        else {}
    )
    gate3_metrics = (
        _long_short_metrics(
            candidate=candidate,
            factor_matrix=factor_matrix,
            return_matrix=return_matrix,
            panel=panel,
            experiment_config=experiment_config,
            config=config,
            horizon=horizon,
        )
        if "gate3" in requested and return_matrix is not None
        else {}
    )

    return Block3ScreeningMetricBundle(
        gate0_metrics=gate0_metrics,
        gate1_metrics=gate1_metrics,
        gate2_metrics=gate2_metrics,
        gate3_metrics=gate3_metrics,
        factor_exposure_ref=f"memory://compute_v1/screening/{candidate.candidate_id}/factor_exposure",
        engine_version="compute_v1",
    )
