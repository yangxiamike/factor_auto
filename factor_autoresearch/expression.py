from __future__ import annotations

import ast
from dataclasses import dataclass

from factor_autoresearch.candidates import Candidate
from factor_autoresearch.config import ExperimentConfig
from factor_autoresearch.operators import OperatorSpec


class ExpressionValidationError(ValueError):
    """Raised when a DSL expression violates syntax or config rules."""


@dataclass(frozen=True)
class ExpressionMetadata:
    complexity_score: int
    inferred_lookback: int


class ExpressionValidator:
    def __init__(self, config: ExperimentConfig, operators: dict[str, OperatorSpec]):
        self.config = config
        self.operators = operators

    def parse(self, expression: str) -> ast.Expression:
        return ast.parse(expression, mode="eval")

    def validate_candidate(self, candidate: Candidate) -> ExpressionMetadata:
        tree = self.parse(candidate.expression)
        metadata = self.analyze(tree.body)
        if candidate.lookback_days < metadata.inferred_lookback:
            raise ExpressionValidationError(
                "declared lookback_days is smaller than inferred expression lookback"
            )
        return metadata

    def complexity_score(self, candidate: Candidate) -> int:
        return self.validate_candidate(candidate).complexity_score

    def analyze(self, node: ast.AST) -> ExpressionMetadata:
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
            if spec.kind == "single_arg":
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
        if not isinstance(node, ast.Constant) or isinstance(node.value, bool) or not isinstance(
            node.value, int
        ):
            raise ExpressionValidationError("window arguments must be integer constants")
        window = int(node.value)
        if window not in self.config.allowed_windows:
            raise ExpressionValidationError(f"invalid window: {window}")
        return window
