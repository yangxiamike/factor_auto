"""Canonical expression keys for compute engine v1 cache reuse."""

from __future__ import annotations

import ast


def expression_key(node: ast.AST) -> tuple:
    """Build a stable cache key from an AST node without candidate identity."""
    if isinstance(node, ast.Name):
        return ("field", node.id)
    if isinstance(node, ast.Constant):
        return ("const", float(node.value))
    if isinstance(node, ast.UnaryOp):
        return ("unary", type(node.op).__name__, expression_key(node.operand))
    if isinstance(node, ast.BinOp):
        return ("binop", type(node.op).__name__, expression_key(node.left), expression_key(node.right))
    if isinstance(node, ast.Call):
        return ("call", node.func.id, tuple(expression_key(arg) for arg in node.args))
    return (type(node).__name__, ast.dump(node))
