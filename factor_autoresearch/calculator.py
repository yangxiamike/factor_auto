from __future__ import annotations

import ast
from dataclasses import dataclass

import numpy as np
import pandas as pd

from factor_autoresearch.candidates import Candidate
from factor_autoresearch.config import ExperimentConfig
from factor_autoresearch.data_loader import DatasetBundle


class ExpressionValidationError(ValueError):
    """Raised when a DSL expression is invalid."""


@dataclass(frozen=True)
class ExpressionMetadata:
    complexity_score: int
    inferred_lookback: int


def _safe_divide(left: pd.Series | float, right: pd.Series | float) -> pd.Series:
    left_series = left if isinstance(left, pd.Series) else pd.Series(left)
    right_series = right if isinstance(right, pd.Series) else pd.Series(right)
    result = left_series / right_series.replace(0, np.nan)
    return result.replace([np.inf, -np.inf], np.nan)


class FactorCalc:
    _WINDOW_FUNCTIONS = {"delay", "ts_mean", "ts_std", "ts_delta", "ts_return", "ts_rank"}
    _SINGLE_ARG_FUNCTIONS = {"abs", "log", "cs_rank", "cs_zscore"}

    def validate_candidate(
        self, candidate: Candidate, config: ExperimentConfig
    ) -> ExpressionMetadata:
        tree = ast.parse(candidate.expression, mode="eval")
        metadata = self._analyze(tree.body, config)
        if candidate.lookback_days < metadata.inferred_lookback:
            raise ExpressionValidationError(
                "declared lookback_days is smaller than inferred expression lookback"
            )
        return metadata

    def complexity_score(self, candidate: Candidate, config: ExperimentConfig) -> int:
        return self.validate_candidate(candidate, config).complexity_score

    def calculate(
        self, candidate: Candidate, dataset: DatasetBundle, config: ExperimentConfig
    ) -> pd.Series:
        self.validate_candidate(candidate, config)
        tree = ast.parse(candidate.expression, mode="eval")
        series = self._evaluate(tree.body, dataset.panel, config)
        series = series.replace([np.inf, -np.inf], np.nan)
        series.name = candidate.candidate_id
        return series

    def _analyze(self, node: ast.AST, config: ExperimentConfig) -> ExpressionMetadata:
        if isinstance(node, ast.Name):
            if node.id not in config.allowed_fields:
                raise ExpressionValidationError(f"unknown field: {node.id}")
            return ExpressionMetadata(complexity_score=1, inferred_lookback=0)

        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)):
                raise ExpressionValidationError("only numeric constants are allowed")
            return ExpressionMetadata(complexity_score=1, inferred_lookback=0)

        if isinstance(node, ast.UnaryOp):
            if not isinstance(node.op, ast.USub):
                raise ExpressionValidationError("only unary '-' is allowed")
            child = self._analyze(node.operand, config)
            return ExpressionMetadata(
                complexity_score=child.complexity_score + 1,
                inferred_lookback=child.inferred_lookback,
            )

        if isinstance(node, ast.BinOp):
            if not isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
                raise ExpressionValidationError("unsupported binary operator")
            left = self._analyze(node.left, config)
            right = self._analyze(node.right, config)
            return ExpressionMetadata(
                complexity_score=left.complexity_score + right.complexity_score + 1,
                inferred_lookback=max(left.inferred_lookback, right.inferred_lookback),
            )

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ExpressionValidationError("function calls must use plain names")
            func_name = node.func.id
            if func_name not in config.allowed_functions:
                raise ExpressionValidationError(f"unknown function: {func_name}")
            if node.keywords:
                raise ExpressionValidationError("keyword arguments are not allowed")
            if func_name in self._SINGLE_ARG_FUNCTIONS:
                if len(node.args) != 1:
                    raise ExpressionValidationError(f"{func_name} expects exactly one argument")
                child = self._analyze(node.args[0], config)
                return ExpressionMetadata(
                    complexity_score=child.complexity_score + 1,
                    inferred_lookback=child.inferred_lookback,
                )
            if func_name in self._WINDOW_FUNCTIONS:
                if len(node.args) != 2:
                    raise ExpressionValidationError(f"{func_name} expects two arguments")
                child = self._analyze(node.args[0], config)
                window = self._extract_window(node.args[1], config)
                return ExpressionMetadata(
                    complexity_score=child.complexity_score + 2,
                    inferred_lookback=child.inferred_lookback + window,
                )
            raise ExpressionValidationError(f"unsupported function: {func_name}")

        raise ExpressionValidationError(f"unsupported expression node: {type(node).__name__}")

    def _extract_window(self, node: ast.AST, config: ExperimentConfig) -> int:
        if not isinstance(node, ast.Constant) or not isinstance(node.value, int):
            raise ExpressionValidationError("window arguments must be integer constants")
        window = int(node.value)
        if window not in config.allowed_windows:
            raise ExpressionValidationError(f"invalid window: {window}")
        return window

    def _evaluate(
        self, node: ast.AST, panel: pd.DataFrame, config: ExperimentConfig
    ) -> pd.Series:
        if isinstance(node, ast.Name):
            return panel[node.id].astype(float)

        if isinstance(node, ast.Constant):
            return pd.Series(float(node.value), index=panel.index, dtype=float)

        if isinstance(node, ast.UnaryOp):
            operand = self._evaluate(node.operand, panel, config)
            return -operand

        if isinstance(node, ast.BinOp):
            left = self._evaluate(node.left, panel, config)
            right = self._evaluate(node.right, panel, config)
            if isinstance(node.op, ast.Add):
                return (left + right).replace([np.inf, -np.inf], np.nan)
            if isinstance(node.op, ast.Sub):
                return (left - right).replace([np.inf, -np.inf], np.nan)
            if isinstance(node.op, ast.Mult):
                return (left * right).replace([np.inf, -np.inf], np.nan)
            return _safe_divide(left, right)

        if isinstance(node, ast.Call):
            func_name = node.func.id
            if func_name in self._SINGLE_ARG_FUNCTIONS:
                series = self._evaluate(node.args[0], panel, config)
                return self._call_single_arg(func_name, series, panel)
            series = self._evaluate(node.args[0], panel, config)
            window = self._extract_window(node.args[1], config)
            return self._call_window_function(func_name, series, window)

        raise ExpressionValidationError(f"unsupported evaluation node: {type(node).__name__}")

    def _call_single_arg(self, func_name: str, series: pd.Series, panel: pd.DataFrame) -> pd.Series:
        if func_name == "abs":
            return series.abs()
        if func_name == "log":
            result = pd.Series(np.nan, index=series.index, dtype=float)
            positive = series > 0
            result.loc[positive] = np.log(series.loc[positive])
            return result
        if func_name == "cs_rank":
            return self._cross_section_rank(series, panel["in_universe"])
        if func_name == "cs_zscore":
            return self._cross_section_zscore(series, panel["in_universe"])
        raise ExpressionValidationError(f"unsupported function: {func_name}")

    def _call_window_function(self, func_name: str, series: pd.Series, window: int) -> pd.Series:
        grouped = series.groupby(level="ts_code", sort=False)
        if func_name == "delay":
            return grouped.shift(window)
        if func_name == "ts_mean":
            return grouped.transform(lambda values: values.rolling(window, min_periods=window).mean())
        if func_name == "ts_std":
            return grouped.transform(
                lambda values: values.rolling(window, min_periods=window).std(ddof=0)
            )
        if func_name == "ts_delta":
            return series - grouped.shift(window)
        if func_name == "ts_return":
            return _safe_divide(series, grouped.shift(window)) - 1.0
        if func_name == "ts_rank":
            return grouped.transform(
                lambda values: values.rolling(window, min_periods=window).apply(
                    lambda bucket: pd.Series(bucket).rank(pct=True).iloc[-1],
                    raw=False,
                )
            )
        raise ExpressionValidationError(f"unsupported function: {func_name}")

    def _cross_section_rank(self, series: pd.Series, in_universe: pd.Series) -> pd.Series:
        result = pd.Series(np.nan, index=series.index, dtype=float)
        mask = in_universe.fillna(False)
        result.loc[mask] = series.loc[mask].groupby(level="trade_date", sort=False).transform(
            lambda values: values.rank(method="average", pct=True)
        )
        return result

    def _cross_section_zscore(self, series: pd.Series, in_universe: pd.Series) -> pd.Series:
        def _zscore(values: pd.Series) -> pd.Series:
            std = values.std(ddof=0)
            if pd.isna(std) or std == 0:
                return pd.Series(np.nan, index=values.index, dtype=float)
            return (values - values.mean()) / std

        result = pd.Series(np.nan, index=series.index, dtype=float)
        mask = in_universe.fillna(False)
        result.loc[mask] = series.loc[mask].groupby(level="trade_date", sort=False).transform(_zscore)
        return result
