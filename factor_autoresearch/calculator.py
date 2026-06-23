"""DSL validation and raw factor calculation."""

from __future__ import annotations

import ast

import pandas as pd

from factor_autoresearch.candidates import Candidate
from factor_autoresearch.config import ExperimentConfig
from factor_autoresearch.data_loader import DatasetBundle
from factor_autoresearch.expression import (
    ExpressionMetadata,
    ExpressionValidationError,
    ExpressionValidator,
)
from factor_autoresearch.operators import OPERATOR_REGISTRY, OperatorSpec, sanitize_series


_BINARY_OPERATOR_NAMES: dict[type[ast.operator], str] = {
    ast.Add: "add",
    ast.Sub: "sub",
    ast.Mult: "mul",
    ast.Div: "div",
}


class FactorCalc:
    def __init__(
        self,
        config: ExperimentConfig,
        operators: dict[str, OperatorSpec] = OPERATOR_REGISTRY,
    ) -> None:
        self.config = config
        self.operators = dict(operators)
        self.validator = ExpressionValidator(config, self.operators)

    def validate_candidate(self, candidate: Candidate) -> ExpressionMetadata:
        return self.validator.validate_candidate(candidate)

    def complexity_score(self, candidate: Candidate) -> int:
        return self.validate_candidate(candidate).complexity_score

    def calculate(self, candidate: Candidate, dataset: DatasetBundle) -> pd.Series:
        self.validator.validate_candidate(candidate)
        tree = self.validator.parse(candidate.expression)
        series = self._evaluate(tree.body, dataset.panel)
        series = sanitize_series(series)
        series.name = candidate.candidate_id
        return series

    def _evaluate(
        self,
        node: ast.AST,
        panel: pd.DataFrame,
    ) -> pd.Series:
        if isinstance(node, ast.Name):
            return panel[node.id].astype(float)

        if isinstance(node, ast.Constant):
            return pd.Series(float(node.value), index=panel.index, dtype=float)

        if isinstance(node, ast.UnaryOp):
            operand = self._evaluate(node.operand, panel)
            return -operand

        if isinstance(node, ast.BinOp):
            operator_name = _BINARY_OPERATOR_NAMES.get(type(node.op))
            if operator_name is None:
                raise ExpressionValidationError("unsupported binary operator")
            left = self._evaluate(node.left, panel)
            right = self._evaluate(node.right, panel)
            spec = self.operators[operator_name]
            return spec.func(left, right, panel=panel)

        if isinstance(node, ast.Call):
            spec = self.operators[node.func.id]
            series = self._evaluate(node.args[0], panel)
            window = None
            if spec.kind == "window":
                window = self.validator.extract_window(node.args[1])
            return spec.func(series, panel=panel, window=window)

        raise ExpressionValidationError(f"unsupported evaluation node: {type(node).__name__}")
