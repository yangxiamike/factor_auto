"""
表达式校验模块
负责 DSL 的静态校验、复杂度计算和 lookback 推断。
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

from factor_autoresearch.candidates import Candidate
from factor_autoresearch.config import ExperimentConfig
from factor_autoresearch.operators import OperatorSpec


class ExpressionValidationError(ValueError):
    """表达式异常: 表示 DSL 违反了语法或配置约束。"""


@dataclass(frozen=True)
class ExpressionMetadata:
    """表达式元信息: 保存复杂度和推断出的真实回看窗口。"""

    complexity_score: int
    inferred_lookback: int


class ExpressionValidator:
    """表达式校验器: 负责 DSL 的静态校验和元信息分析。"""

    def __init__(self, config: ExperimentConfig, operators: dict[str, OperatorSpec]):
        """初始化: 绑定实验配置和当前可用算子集合。"""

        self.config = config
        self.operators = operators

    def parse(self, expression: str) -> ast.Expression:
        """解析表达式: 把字符串形式的 DSL 解析成 AST。"""

        return ast.parse(expression, mode="eval")

    def validate_candidate(self, candidate: Candidate) -> ExpressionMetadata:
        """校验候选因子: 返回表达式是否合法及其元信息。"""

        tree = self.parse(candidate.expression)
        metadata = self.analyze(tree.body)
        if candidate.lookback_days < metadata.inferred_lookback:
            raise ExpressionValidationError(
                "declared lookback_days is smaller than inferred expression lookback"
            )
        return metadata

    def complexity_score(self, candidate: Candidate) -> int:
        """复杂度评分: 返回候选因子的表达式复杂度。"""

        return self.validate_candidate(candidate).complexity_score

    def analyze(self, node: ast.AST) -> ExpressionMetadata:
        """递归分析: 推断表达式复杂度和真实 lookback。"""

        if isinstance(node, ast.Name):
            if node.id not in self.config.allowed_fields:
                raise ExpressionValidationError(f"unknown field: {node.id}")
            return ExpressionMetadata(complexity_score=1, inferred_lookback=0)

        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise ExpressionValidationError("only numeric constants are allowed")
            return ExpressionMetadata(complexity_score=1, inferred_lookback=0)

        if isinstance(node, ast.UnaryOp):
            if not isinstance(node.op, ast.USub):
                raise ExpressionValidationError("only unary '-' is allowed")
            child = self.analyze(node.operand)
            return ExpressionMetadata(
                complexity_score=child.complexity_score + 1,
                inferred_lookback=child.inferred_lookback,
            )

        if isinstance(node, ast.BinOp):
            if not isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
                raise ExpressionValidationError("unsupported binary operator")
            left = self.analyze(node.left)
            right = self.analyze(node.right)
            return ExpressionMetadata(
                complexity_score=left.complexity_score + right.complexity_score + 1,
                inferred_lookback=max(left.inferred_lookback, right.inferred_lookback),
            )

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ExpressionValidationError("function calls must use plain names")
            func_name = node.func.id
            if func_name not in self.config.allowed_functions:
                raise ExpressionValidationError(f"unknown function: {func_name}")
            spec = self.operators.get(func_name)
            if spec is None:
                raise ExpressionValidationError(f"unsupported function: {func_name}")
            if node.keywords:
                raise ExpressionValidationError("keyword arguments are not allowed")
            if len(node.args) != spec.arg_count:
                if spec.arg_count == 1:
                    raise ExpressionValidationError(f"{func_name} expects exactly one argument")
                raise ExpressionValidationError(f"{func_name} expects two arguments")

            child = self.analyze(node.args[0])
            if spec.kind in {"unary", "panel"}:
                return ExpressionMetadata(
                    complexity_score=child.complexity_score + 1,
                    inferred_lookback=child.inferred_lookback,
                )

            window = self.extract_window(node.args[1])
            return ExpressionMetadata(
                complexity_score=child.complexity_score + 2,
                inferred_lookback=child.inferred_lookback + window,
            )

        raise ExpressionValidationError(f"unsupported expression node: {type(node).__name__}")

    def extract_window(self, node: ast.AST) -> int:
        """提取窗口: 读取并校验 window 参数是否合法。"""

        if not isinstance(node, ast.Constant) or isinstance(node.value, bool) or not isinstance(
            node.value, int
        ):
            raise ExpressionValidationError("window arguments must be integer constants")
        window = int(node.value)
        if window not in self.config.allowed_windows:
            raise ExpressionValidationError(f"invalid window: {window}")
        return window
