"""
因子计算模块
负责执行 DSL 表达式，并产出原始因子序列。
"""

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
from factor_autoresearch.operators import OPERATOR_REGISTRY, OperatorSpec


_BINARY_OPERATOR_NAMES: dict[type[ast.operator], str] = {
    ast.Add: "add",
    ast.Sub: "sub",
    ast.Mult: "mul",
    ast.Div: "div",
}


class FactorCalc:
    """因子计算器: 串起表达式校验、AST 解析和算子执行。"""

    def __init__(
        self,
        config: ExperimentConfig,
        operators: dict[str, OperatorSpec] = OPERATOR_REGISTRY,
    ) -> None:
        """初始化: 绑定实验配置，并准备可用算子表。"""

        self.config = config
        self.operators = dict(operators)
        self.validator = ExpressionValidator(config, self.operators)

    def validate_candidate(self, candidate: Candidate) -> ExpressionMetadata:
        """表达式校验: 检查候选因子的 DSL 是否合法。"""

        return self.validator.validate_candidate(candidate)

    def complexity_score(self, candidate: Candidate) -> int:
        """复杂度评分: 返回候选因子的表达式复杂度。"""

        return self.validate_candidate(candidate).complexity_score

    def calculate(self, candidate: Candidate, dataset: DatasetBundle) -> pd.Series:
        """执行表达式: 计算候选因子的原始因子序列。"""

        self.validator.validate_candidate(candidate)
        tree = self.validator.parse(candidate.expression)
        x = self._evaluate(tree.body, dataset.panel)
        x = x.replace([float("inf"), float("-inf")], float("nan"))
        x.name = candidate.candidate_id
        return x

    def _evaluate(
        self,
        node: ast.AST,
        panel: pd.DataFrame,
    ) -> pd.Series:
        """递归执行: 按 AST 节点类型逐层计算表达式结果。"""

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
            return spec.func(left, right)

        if isinstance(node, ast.Call):
            spec = self.operators[node.func.id]
            x = self._evaluate(node.args[0], panel)
            if spec.kind == "window":
                d = self.validator.extract_window(node.args[1])
                return spec.func(x, d)
            if spec.kind == "panel":
                return spec.func(x, panel)
            return spec.func(x)

        raise ExpressionValidationError(f"unsupported evaluation node: {type(node).__name__}")
