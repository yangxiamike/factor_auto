"""
Compute v1 表达式 key 模块
负责把 AST 子树转成稳定缓存 key。
key 不包含候选 id，因此相同子表达式可跨候选复用。
"""

from __future__ import annotations

import ast


# ============== 表达式缓存 key ==============
def expression_key(node: ast.AST) -> tuple:
    """表达式 key: 从 AST 节点生成稳定缓存键。"""
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
