"""Matrix-backed factor calculator for compute engine v1."""

from __future__ import annotations

import ast

import numpy as np
import pandas as pd

from factor_autoresearch.candidates import Candidate
from factor_autoresearch.compute_v1 import kernels
from factor_autoresearch.compute_v1.cache import ExpressionCache
from factor_autoresearch.compute_v1.expression_dag import expression_key
from factor_autoresearch.compute_v1.panel import PanelStore
from factor_autoresearch.config import ExperimentConfig
from factor_autoresearch.data_loader import DatasetBundle
from factor_autoresearch.expression import ExpressionMetadata, ExpressionValidationError, ExpressionValidator
from factor_autoresearch.operators import OPERATOR_REGISTRY, OperatorSpec

_BINARY_OPERATOR_NAMES: dict[type[ast.operator], str] = {
    ast.Add: "add",
    ast.Sub: "sub",
    ast.Mult: "mul",
    ast.Div: "div",
}


class V1FactorCalc:
    """Evaluate the existing DSL through PanelStore matrices."""

    def __init__(
        self,
        config: ExperimentConfig,
        operators: dict[str, OperatorSpec] = OPERATOR_REGISTRY,
        cache: ExpressionCache | None = None,
    ) -> None:
        self.config = config
        self.operators = dict(operators)
        self.validator = ExpressionValidator(config, self.operators)
        self.cache = cache or ExpressionCache()

    def validate_candidate(self, candidate: Candidate) -> ExpressionMetadata:
        return self.validator.validate_candidate(candidate)

    def complexity_score(self, candidate: Candidate) -> int:
        return self.validate_candidate(candidate).complexity_score

    def calculate(self, candidate: Candidate, dataset: DatasetBundle) -> pd.Series:
        self.validator.validate_candidate(candidate)
        tree = self.validator.parse(candidate.expression)
        panel = PanelStore.from_dataset(dataset)
        values = self._evaluate(tree.body, panel)
        values = np.asarray(values, dtype=float)
        values[~np.isfinite(values)] = np.nan
        return panel.to_series(candidate.candidate_id, values).reindex(dataset.panel.index)

    def _evaluate(self, node: ast.AST, panel: PanelStore) -> np.ndarray:
        key = expression_key(node)
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        value = self._evaluate_uncached(node, panel)
        return self.cache.put(key, value)

    def _evaluate_uncached(self, node: ast.AST, panel: PanelStore) -> np.ndarray:
        if isinstance(node, ast.Name):
            return panel.field(node.id)
        if isinstance(node, ast.Constant):
            return np.full_like(panel.universe_mask, float(node.value), dtype=float)
        if isinstance(node, ast.UnaryOp):
            return -self._evaluate(node.operand, panel)
        if isinstance(node, ast.BinOp):
            operator_name = _BINARY_OPERATOR_NAMES.get(type(node.op))
            if operator_name is None:
                raise ExpressionValidationError("unsupported binary operator")
            left = self._evaluate(node.left, panel)
            right = self._evaluate(node.right, panel)
            if operator_name == "add":
                return left + right
            if operator_name == "sub":
                return left - right
            if operator_name == "mul":
                return left * right
            return kernels.div0(left, right)
        if isinstance(node, ast.Call):
            function_name = node.func.id
            x = self._evaluate(node.args[0], panel)
            if function_name == "abs":
                return np.abs(x)
            if function_name == "log":
                return np.log(np.where(x > 0, x, np.nan))
            if function_name == "delay":
                return kernels.delay(x, self.validator.extract_window(node.args[1]))
            if function_name == "ts_mean":
                return kernels.ts_mean(x, self.validator.extract_window(node.args[1]))
            if function_name == "ts_std":
                return kernels.ts_std(x, self.validator.extract_window(node.args[1]))
            if function_name == "ts_delta":
                return x - kernels.delay(x, self.validator.extract_window(node.args[1]))
            if function_name == "ts_return":
                return kernels.ts_return(x, self.validator.extract_window(node.args[1]))
            if function_name == "ts_rank":
                return kernels.ts_rank(x, self.validator.extract_window(node.args[1]))
            if function_name == "cs_rank":
                return kernels.cs_rank(x, panel.universe_mask)
            if function_name == "cs_zscore":
                return kernels.cs_zscore(x, panel.universe_mask)
        raise ExpressionValidationError(f"unsupported evaluation node: {type(node).__name__}")
